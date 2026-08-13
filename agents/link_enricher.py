"""
Link Enricher

Enriches summary text with internal links to collected items.
This module adds a post-processing step that uses LLM to identify
references in summary text and inject markdown links pointing to
the corresponding items on the site.
"""

import asyncio
import json
import logging
import re
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass

from .llm_client import AsyncAnthropicClient, ThinkingLevel
from .prompt_security import (
    build_fenced_user_message,
    build_hardened_system,
    new_fence_nonce,
    normalize_untrusted_text,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config.prompts import PromptAccessor

logger = logging.getLogger(__name__)


@dataclass
class LinkResult:
    """Result of link enrichment for a single text."""
    enriched_text: str
    links_added: List[Dict[str, str]]  # [{phrase, item_id, category}]
    original_text: str


class LinkEnricher:
    """
    Enriches summary text with internal links to items.

    Uses LLM to identify phrases in summary text that reference
    specific collected items, and injects markdown links to those items.
    """

    def __init__(
        self,
        async_client: AsyncAnthropicClient,
        date: str,
        prompt_accessor: Optional['PromptAccessor'] = None
    ):
        """
        Initialize link enricher.

        Args:
            async_client: Async Anthropic client for LLM calls.
            date: Target date (YYYY-MM-DD) for link URLs.
            prompt_accessor: Optional PromptAccessor for config-based prompts.
        """
        self.async_client = async_client
        self.date = date
        self.prompt_accessor = prompt_accessor

    async def enrich_all(
        self,
        executive_summary: str,
        category_reports: Dict[str, Any],
        top_topics: List[Any],
        executive_summary_evidence: Optional[List[List[str]]] = None,
    ) -> Tuple[str, Dict[str, str], List[Any]]:
        """
        Enrich all summary text with internal links.

        Runs all enrichment tasks in parallel for efficiency.
        - Executive summary: can link to items from ANY category
        - Category summaries: can ONLY link to items from that category
        - Topic descriptions: can link to items from ANY category

        Args:
            executive_summary: The executive summary text.
            category_reports: Dict of category -> CategoryReport.
            top_topics: List of TopTopic objects.

        Returns:
            Tuple of (enriched_exec_summary, enriched_category_summaries, enriched_topics)
        """
        # Build complete item list from all categories
        all_items = self._build_item_list(category_reports)

        if not all_items:
            logger.warning("No items available for link enrichment")
            return executive_summary, {}, top_topics

        logger.info(f"Link enrichment: {len(all_items)} items available for linking")

        # Build category-specific item lists for category summaries
        items_by_category: Dict[str, List[Dict[str, Any]]] = {}
        for item in all_items:
            cat = item['category']
            if cat not in items_by_category:
                items_by_category[cat] = []
            items_by_category[cat].append(item)

        # Prepare all enrichment tasks for parallel execution
        tasks = []
        task_keys: List[Tuple[str, Any]] = []

        # Executive summary task (all items available)
        tasks.append(self._enrich_text(
            executive_summary, all_items, "executive summary",
            evidence_by_bullet=executive_summary_evidence,
        ))
        task_keys.append(('exec', None))

        # Category summary tasks (ONLY items from that category)
        for category, report in category_reports.items():
            summary = report.category_summary if hasattr(report, 'category_summary') else report.get('category_summary', '')
            if summary:
                category_items = items_by_category.get(category, [])
                if category_items:
                    evidence = (
                        report.category_summary_evidence
                        if hasattr(report, 'category_summary_evidence')
                        else report.get('category_summary_evidence', [])
                    )
                    tasks.append(self._enrich_text(
                        summary, category_items, f"{category} summary",
                        evidence_by_bullet=evidence,
                    ))
                    task_keys.append(('category', category))
                else:
                    # No items for this category, skip enrichment
                    logger.debug(f"  {category} summary: no items available, skipping")

        # Topic description tasks (all items available)
        for i, topic in enumerate(top_topics):
            description = topic.description if hasattr(topic, 'description') else topic.get('description', '')
            if description:
                topic_name = topic.name if hasattr(topic, 'name') else topic.get('name', 'unknown')
                representative_ids = (
                    topic.representative_items if hasattr(topic, 'representative_items')
                    else topic.get('representative_items', [])
                )
                topic_items = [
                    item for item in all_items if item.get('id') in set(representative_ids)
                ]
                tasks.append(self._enrich_text(
                    description,
                    topic_items or all_items,
                    f"topic: {topic_name}",
                    links_per_block=2,
                ))
                task_keys.append(('topic', i))

        logger.info(f"  Running {len(tasks)} enrichment tasks in parallel...")

        # Run all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        enriched_exec = executive_summary
        enriched_categories: Dict[str, str] = {}
        enriched_topics = list(top_topics)  # Make a copy to modify

        for (key_type, key_value), result in zip(task_keys, results):
            if isinstance(result, Exception):
                logger.error(f"Link enrichment failed for {key_type}/{key_value}: {result}")
                continue

            if key_type == 'exec':
                enriched_exec = result
            elif key_type == 'category':
                enriched_categories[key_value] = result
            elif key_type == 'topic':
                topic = enriched_topics[key_value]
                if hasattr(topic, 'description'):
                    topic.description = result
                    topic.description_html = self._markdown_links_to_html(result)
                else:
                    topic['description'] = result
                    topic['description_html'] = self._markdown_links_to_html(result)

        return enriched_exec, enriched_categories, enriched_topics

    # How many items per category to expose to the link-enrichment LLM.
    # The executive summary is generated with visibility into category summaries
    # and cross-category topics, so it often mentions stories beyond each
    # category's top 10. Passing a wider slice (ranked by importance_score)
    # gives the enricher a realistic chance of finding matches.
    ITEMS_PER_CATEGORY = 30

    def _exclude_from_summaries(self, analyzed_item: Any) -> bool:
        """Return True if freshness metadata says the item must not shape summaries."""
        metadata = {}
        if hasattr(analyzed_item, 'item'):
            item = analyzed_item.item
            metadata = item.metadata if hasattr(item, 'metadata') else {}
        elif isinstance(analyzed_item, dict):
            item = analyzed_item.get('item', analyzed_item)
            metadata = item.get('metadata', {}) if isinstance(item, dict) else {}
            if not metadata and isinstance(analyzed_item.get('freshness'), dict):
                metadata = {'freshness': analyzed_item.get('freshness')}

        freshness = metadata.get('freshness') if isinstance(metadata, dict) else {}
        return bool(isinstance(freshness, dict) and freshness.get('exclude_from_summaries'))

    def _build_item_list(self, category_reports: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build a simplified list of items for LLM context.

        Prefer ``all_items`` (sorted by importance_score descending) so the
        pool isn't capped at the per-category top-10 ranked list. This lets
        the enricher match stories the executive summary pulled in from
        cross-category context. Fall back to ``top_items`` if ``all_items``
        isn't populated on the report.
        """
        items = []

        for category, report in category_reports.items():
            # Prefer all_items (already sorted by importance_score desc in the
            # reduce phase) so we can take a wider slice. Fall back to
            # top_items for backward compatibility with older checkpoints.
            source_items = None
            if hasattr(report, 'all_items'):
                source_items = report.all_items or report.top_items
            elif isinstance(report, dict):
                source_items = report.get('all_items') or report.get('top_items', [])
            source_items = source_items or []

            added_for_category = 0
            for analyzed_item in source_items:
                if self._exclude_from_summaries(analyzed_item):
                    continue
                if added_for_category >= self.ITEMS_PER_CATEGORY:
                    break
                # Handle both object and dict formats
                if hasattr(analyzed_item, 'item'):
                    item = analyzed_item.item
                    item_id = item.id if hasattr(item, 'id') else item.get('id', '')
                    title = item.title if hasattr(item, 'title') else item.get('title', '')
                    summary = analyzed_item.summary if hasattr(analyzed_item, 'summary') else ''
                elif isinstance(analyzed_item, dict):
                    item = analyzed_item.get('item', analyzed_item)
                    item_id = item.get('id', analyzed_item.get('id', ''))
                    title = item.get('title', analyzed_item.get('title', ''))
                    summary = analyzed_item.get('summary', '')
                else:
                    continue

                if item_id and title:
                    items.append({
                        'id': item_id,
                        'title': normalize_untrusted_text(title)[:300],
                        'category': category,
                        'summary': summary[:200] if summary else ''
                    })
                    added_for_category += 1

        return items

    async def _enrich_text(
        self,
        text: str,
        items: List[Dict[str, Any]],
        context_name: str,
        links_per_block: int = 1,
        evidence_by_bullet: Optional[List[List[str]]] = None,
    ) -> str:
        """Apply the upstream AATF full-text enrichment contract safely.

        Gemini returns the complete original text with contextual Markdown
        links. We accept it only when removing those links reproduces the
        original prose exactly and every target belongs to the supplied item
        catalog. Empty or invalid output falls back locally and never blocks
        publication.
        """
        if not text or not items:
            return text
        items_json = json.dumps(items[:140], ensure_ascii=False)
        system = f"""You are a link enrichment agent. Add contextual internal links to the supplied text.

Rules:
1. Preserve every original character, word, heading, bullet, emphasis marker and newline. Only wrap existing text spans in Markdown links.
2. Add one link for every distinct named story, research result, social post, product or repository that has a clear matching AVAILABLE ITEM.
3. A bullet may contain multiple links when it references multiple supported items.
4. Prefer short action/event phrases. Exact product, model and repository names may be one or two words.
5. Never add source lists, parentheses, ellipses, labels such as 'read more', or text that was not already present.
6. Never link generic glue, broad concepts or section headings. If uncertain, leave that reference unlinked.
7. Use only supplied item IDs and categories. URL format: /?date={self.date}&category=CATEGORY#item-ITEMID
8. Return JSON only, with exactly: {{"enriched_text":"complete text","links":[{{"phrase":"exact visible phrase","item_id":"id","category":"category"}}]}}
9. Return the unchanged text and an empty links array when no reliable match exists.
"""
        nonce = new_fence_nonce()
        payload = build_fenced_user_message(
            f"AVAILABLE ITEMS:\n{items_json}\n\nTEXT TO ENRICH:\n{text}",
            nonce,
            task_line="Add only validated internal links to the fenced source data.",
        )
        try:
            response = await self.async_client.call_with_thinking(
                messages=[{"role": "user", "content": payload}],
                system=build_hardened_system(system, nonce),
                profile=ThinkingLevel.QUICK,
                max_tokens=8192,
                temperature=0.0,
                caller=f"link_enricher.{context_name}",
            )
            parsed = self._parse_aatf_enrichment_response(response.content)
            enriched = parsed.get("enriched_text")
            if not isinstance(enriched, str):
                raise ValueError("enriched_text is missing")
            validated = self._validate_aatf_enriched_text(text, enriched, items)
            if validated and self._has_internal_links(validated):
                logger.info("  %s: accepted %s validated AATF-style link(s)", context_name, validated.count("](/?date="))
                return validated
            logger.info("  %s: model returned no usable links; applying exact-match fallback", context_name)
        except Exception as exc:
            logger.warning("  %s: AATF-style enrichment unavailable; applying exact-match fallback: %s", context_name, exc)
        return self._inject_per_block_links(
            text, items, context_name, links_per_block, evidence_by_bullet
        )

    @staticmethod
    def _parse_aatf_enrichment_response(content: str) -> Dict[str, Any]:
        """Parse the JSON envelope used by upstream AATF."""
        value = (content or "").strip()
        if value.startswith("```json"):
            value = value[7:]
        elif value.startswith("```"):
            value = value[3:]
        if value.endswith("```"):
            value = value[:-3]
        value = value.strip()
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end < start:
            raise ValueError("enrichment response has no JSON object")
        parsed = json.loads(value[start:end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("enrichment response is not a JSON object")
        return parsed

    def _validate_aatf_enriched_text(
        self, original: str, enriched: str, items: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Accept only link-only transformations targeting eligible items."""
        pattern = re.compile(r"\[([^\]]+)\]\((/\?date=([0-9-]+)&category=([\w-]+)#item-([\w-]+))\)")
        links = list(pattern.finditer(enriched))
        if not links:
            return None
        # Removing internal Markdown wrappers must restore the input byte for byte.
        plain = pattern.sub(lambda match: match.group(1), enriched)
        if plain != original:
            logger.warning("Rejected enrichment because Gemini changed the original prose")
            return None
        eligible = {
            (str(item.get("id")), str(item.get("category"))): item
            for item in items
        }
        seen = set()
        rejected = 0

        def keep_or_unwrap(match: re.Match) -> str:
            nonlocal rejected
            label, _, date, category, item_id = match.groups()
            item = eligible.get((item_id, category))
            line_start = enriched.rfind("\n", 0, match.start()) + 1
            is_heading = enriched[line_start:match.start()].lstrip().startswith("#")
            key = (item_id, label.casefold())
            if (
                date != self.date
                or item is None
                or is_heading
                or key in seen
                or not self._label_identifies_item(label, item)
            ):
                rejected += 1
                return label
            seen.add(key)
            return match.group(0)

        sanitized = pattern.sub(keep_or_unwrap, enriched)
        if rejected:
            logger.warning("Removed %s invalid link(s) while preserving valid enrichment", rejected)
        return sanitized if self._has_internal_links(sanitized) else None

    @staticmethod
    def _label_identifies_item(label: str, item: Dict[str, Any]) -> bool:
        """Allow concise technical names while rejecting generic overlap."""
        normalized = label.strip().casefold()
        title = str(item.get("title") or "").casefold()
        if re.fullmatch(r"[\w.-]+/[\w.-]+", normalized):
            return normalized in title
        words = re.findall(r"[a-z0-9][a-z0-9+._'-]*", normalized)
        if len(words) == 1:
            generic = {
                "agent", "agents", "framework", "model", "models", "news",
                "platform", "research", "system", "systems", "update",
            }
            return (
                len(words[0]) >= 4
                and words[0] not in generic
                and words[0] in set(re.findall(r"[a-z0-9][a-z0-9+._'-]*", title))
            )
        meaningful = {word for word in words if len(word) >= 3 and word not in {"and", "for", "the", "with", "from"}}
        title_words = set(re.findall(r"[a-z0-9][a-z0-9+._'-]*", title))
        return len(meaningful & title_words) >= 2

    async def _select_semantic_link_spans(
        self, text: str, items: List[Dict[str, Any]], context_name: str,
        evidence_by_bullet: Optional[List[List[str]]],
    ) -> Optional[str]:
        """Select verbatim source spans with Gemini and validate every result."""
        if not self.async_client or not text or not items:
            return None
        item_by_id = {str(item.get("id")): item for item in items if item.get("id")}
        lines = text.splitlines()
        bullet_lines = [i for i, line in enumerate(lines) if line.strip().startswith(("- ", "* "))]
        payload = {
            "bullets": [
                {"line": line_no, "text": lines[line_no], "allowed_item_ids": (
                    [item_id for item_id in evidence_by_bullet[pos] if item_id in item_by_id]
                    if evidence_by_bullet and pos < len(evidence_by_bullet) else []
                )}
                for pos, line_no in enumerate(bullet_lines)
            ],
            "items": [{key: item.get(key, "") for key in ("id", "category", "title", "summary")} for item in items],
        }
        system = (
            "Return one JSON object only, with exactly this schema: "
            "{\"selections\":[{\"line\":0,\"item_id\":\"id\",\"exact_span\":\"verbatim\"}]}. "
            "Do not use Markdown, code fences, prose, explanations, URLs, or additional keys. "
            "A selection is optional: return {\"selections\":[]} when no exact, grounded anchor exists. "
            "For every selection: line must be a supplied bullet line; item_id must be a supplied item and, "
            "when allowed_item_ids is non-empty, it must be in that list. exact_span must be copied character-for-character "
            "from that bullet, be 3-12 meaningful words, name a concrete event/product/repository/result, and overlap the "
            "selected item's title with at least two meaningful words. Never select generic terms, connective text, headings, "
            "claims, implications, dates, quantities, or source labels. Select at most two non-overlapping spans per bullet, "
            "and never repeat an item_id or exact_span. Do not rewrite text or emit Markdown."
        )
        try:
            response = await self.async_client.call_with_thinking(
                messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                system=system, profile=ThinkingLevel.STANDARD, max_tokens=4096,
                temperature=0.0, caller=f"link_enricher.{context_name}",
            )
            content = response.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(content)
            if not isinstance(parsed, dict) or set(parsed) != {"selections"}:
                raise ValueError("Gemini link output does not match the required JSON envelope")
            selections = parsed["selections"]
            if not isinstance(selections, list):
                raise ValueError("Gemini link selections must be a JSON array")
        except Exception as exc:
            logger.warning("  %s: Gemini unavailable; using exact-match fallback: %s", context_name, exc)
            return None

        allowed_by_line = {entry["line"]: set(entry["allowed_item_ids"]) for entry in payload["bullets"]}
        seen_item_ids, seen_spans = set(), set()
        links_by_line: Dict[int, int] = {}
        accepted = 0
        for selection in selections:
            if not isinstance(selection, dict) or set(selection) != {"line", "item_id", "exact_span"}:
                continue
            line_no, item_id, span = selection.get("line"), str(selection.get("item_id") or ""), selection.get("exact_span")
            item = item_by_id.get(item_id)
            if not isinstance(line_no, int) or line_no not in allowed_by_line or not item or not isinstance(span, str):
                continue
            if allowed_by_line[line_no] and item_id not in allowed_by_line[line_no]:
                continue
            span = span.strip()
            words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+._'’-]*", span)
            if not (3 <= len(words) <= 12) or span.lower() not in lines[line_no].lower():
                continue
            normalized_span = " ".join(word.lower() for word in words)
            if (
                item_id in seen_item_ids
                or normalized_span in seen_spans
                or links_by_line.get(line_no, 0) >= 2
                or f"#item-{item_id}" in lines[line_no]
                or not self._span_is_grounded_in_item(span, item)
            ):
                continue
            url = f"/?date={self.date}&category={item['category']}#item-{item_id}"
            lines[line_no], count = re.subn(re.escape(span), lambda m: f"[{m.group(0)}]({url})", lines[line_no], count=1, flags=re.I)
            if count:
                accepted += 1
                seen_item_ids.add(item_id)
                seen_spans.add(normalized_span)
                links_by_line[line_no] = links_by_line.get(line_no, 0) + 1
        logger.info("  %s: Gemini selected %s validated inline link span(s)", context_name, accepted)
        return self._sanitize_internal_link_labels("\n".join(lines))

    @staticmethod
    def _span_is_grounded_in_item(span: str, item: Dict[str, Any]) -> bool:
        """Require two distinctive words shared with the selected item's title.

        This local check prevents a model from attaching an allowed-but-
        irrelevant source to a plausible phrase in the bullet.
        """
        stopwords = {
            "about", "agent", "agents", "and", "are", "for", "from", "into", "its",
            "model", "models", "new", "of", "on", "or", "the", "this", "to", "with",
        }
        def distinctive(value: str) -> set:
            return {
                token.lower() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9+._'’-]*", value)
                if len(token) >= 4 and token.lower() not in stopwords
            }
        overlap = distinctive(span) & distinctive(str(item.get("title") or ""))
        return len(overlap) >= 2

    async def _enrich_text_with_llm(
        self,
        text: str,
        items: List[Dict[str, Any]],
        context_name: str
    ) -> str:
        """
        Enrich a single text with internal links.

        Args:
            text: The text to enrich.
            items: List of items available for linking.
            context_name: Name for logging purposes.

        Returns:
            Enriched text with markdown links.
        """
        if not text or not items:
            return text

        # Link labels are editorial content. A lexical matcher cannot reliably
        # distinguish a meaningful action phrase from incidental title overlap
        # (for example "and the" or "research and"). Let the routed MiniMax
        # model perform that semantic choice; deterministic matching remains an
        # availability fallback if the model call fails or is unusable.

        # Build items context. Cap is 4 categories * ITEMS_PER_CATEGORY plus
        # headroom; kept generous so the LLM sees enough candidates to link
        # every story mentioned by the executive summary.
        items_json = json.dumps(items[:140], indent=2, ensure_ascii=False)

        # CWE-1427: enrichment instructions travel in the system prompt; the
        # item list and text to enrich travel in the user message inside a
        # nonce fence, as labeled sections the instruction pointers name.
        nonce = new_fence_nonce()
        items_pointer = "[Provided in the user message inside the <source_data> fence, under AVAILABLE ITEMS.]"
        text_pointer = "[Provided in the user message inside the <source_data> fence, under TEXT TO ENRICH.]"
        if self.prompt_accessor:
            instructions = self.prompt_accessor.get_post_processing_prompt(
                'link_enrichment',
                {'date': self.date, 'items_json': items_pointer, 'text': text_pointer}
            )
        else:
            # Fallback to inline prompt for backwards compatibility
            instructions = f"""You are a link enrichment agent. Add contextual "read more" links to summary text so readers can dive deeper into stories.

LINKING STRATEGY (CRITICAL):
1. Keep links SHORT (3-7 words max) - just the key action phrase
   - BAD (too long): "Google [published verification that GPT-5.2 solved an unsolved problem](/...)"
   - BAD (too long): "[announced Vera Rubin chips are in full production](/...)"
   - GOOD: "Google [published verification](/...) that GPT-5.2 solved a problem"
   - GOOD: "Nvidia [announced Vera Rubin chips](/...) are in full production"
2. Link the ACTION/EVENT phrase, NOT the leading company/entity name
   - BAD: "[Google DeepMind](/...) announced robots"
   - GOOD: "Google DeepMind [announced Atlas robots](/...)"
3. ONE link per distinct story/development in the text
4. Link to the HIGHEST-RANKED item that covers that story (items are ordered by importance)
5. Do NOT add new **bold** markers inside link labels. Preserve existing bold markers outside links.
6. Preserve ALL original formatting exactly unless a link would require moving existing bold markers outside the link.
7. For bullet points, link the key action/event after the entity prefix
8. NEVER link generic glue text or section labels such as "and the", "the most", "the best", "research and", or "Source"
9. Every link label must contain at least two meaningful content words and must not begin or end with an article, conjunction, or preposition

LINK FORMAT (exact format required):
[descriptive phrase](/?date={self.date}&category=CATEGORY#item-ITEMID)

CRITICAL: The hash MUST start with "item-" followed by the item's id. Example:
  - Item with id "abc123def456" and category "news" becomes: /?date={self.date}&category=news#item-abc123def456

DATE: {self.date}

AVAILABLE ITEMS (ordered by importance - use id and category exactly as shown):
{items_pointer}

TEXT TO ENRICH:
{text_pointer}

OUTPUT (Use XML tags):
<enriched_text>
Full text with links using format /?date={self.date}&category=CATEGORY#item-actualItemId
</enriched_text>

<links>
  <link phrase="the linked phrase" item_id="actualItemId" category="news" />
</links>

Remember: The anchor MUST be #item-ID (with item- prefix). Link specific actions, not entities or generic connective words. Avoid bold markers inside links."""

        system_prompt = build_hardened_system(instructions, nonce)
        fenced_payload = (
            f"AVAILABLE ITEMS (ordered by importance):\n{items_json}\n\n"
            f"TEXT TO ENRICH:\n{text}"
        )
        user_message = build_fenced_user_message(
            fenced_payload, nonce,
            task_line="Enrich the fenced text below according to your system instructions.",
        )

        try:
            response = await self.async_client.call_with_thinking(
                messages=[{"role": "user", "content": user_message}],
                system=system_prompt,
                profile=ThinkingLevel.STANDARD,
                caller=f"link_enricher.{context_name}"
            )

            content = response.content.strip()

            # Parse XML response
            enriched_match = re.search(r'<enriched_text>(.*?)</enriched_text>', content, re.DOTALL)
            if not enriched_match:
                # If LLM returned enriched text with internal links without XML wrapper, preserve LLM links
                if self._has_internal_links(content):
                    logger.info(f"  {context_name}: no <enriched_text> tag, but found internal links in response")
                    sanitized = self._sanitize_internal_link_labels(content)
                    if self._has_internal_links(sanitized):
                        return sanitized
                logger.warning(f"  {context_name}: no <enriched_text> tag found, applying deterministic fallback")
                return self._inject_deterministic_links(text, items, context_name)
            
            enriched = enriched_match.group(1).strip()
            
            # Parse links
            links = []
            link_matches = re.finditer(r'<link\s+phrase="([^"]*)"\s+item_id="([^"]*)"\s+category="([^"]*)"\s*/>', content)
            for m in link_matches:
                links.append({
                    "phrase": m.group(1),
                    "item_id": m.group(2),
                    "category": m.group(3)
                })

            if links and self._has_internal_links(enriched):
                enriched = self._sanitize_internal_link_labels(enriched)
                if not self._has_internal_links(enriched):
                    logger.warning(
                        f"  {context_name}: model links had no meaningful labels; "
                        "applying deterministic fallback"
                    )
                    return self._inject_deterministic_links(text, items, context_name)
                logger.info(f"  {context_name}: added {len(links)} links")
                for link in links:
                    logger.debug(f"    Linked '{link.get('phrase', '')}' -> {link.get('category', '')}/{link.get('item_id', '')[:8]}...")
                return enriched

            logger.warning(f"  {context_name}: model returned no usable links, applying deterministic fallback")
            fallback = self._inject_deterministic_links(enriched or text, items, context_name)
            return fallback

        except Exception as e:
            logger.error(f"Link enrichment failed for {context_name}: {e}")
            return self._inject_deterministic_links(text, items, context_name)

    def _has_internal_links(self, text: str) -> bool:
        return bool(text) and "](/?date=" in text

    def _inject_per_block_links(
        self,
        text: str,
        items: List[Dict[str, Any]],
        context_name: str,
        links_per_block: int = 1,
        evidence_by_bullet: Optional[List[List[str]]] = None,
    ) -> str:
        """Add only verifiable, inline source links to visible content blocks.

        Evidence IDs prove which records informed a bullet, but they do not
        license a synthetic source list at the end of the sentence.  A reader
        should see a link only where the prose actually names that story.
        """
        if not text or not items:
            return text

        lines = text.splitlines()
        item_by_id = {item.get("id"): item for item in items}
        bullet_index = 0

        for index, line in enumerate(lines):
            stripped = line.strip()
            is_bullet = stripped.startswith(("- ", "* "))
            structured_ids = []
            if is_bullet and evidence_by_bullet and bullet_index < len(evidence_by_bullet):
                structured_ids = evidence_by_bullet[bullet_index]
            if is_bullet:
                bullet_index += 1
            if (
                not stripped
                or stripped.startswith("#")
                or len(re.sub(r"^[*\-]\s+", "", stripped)) < 35
            ):
                continue

            # Structured evidence is the authoritative candidate set. Where a
            # bullet has no structured mapping (e.g. legacy checkpoints), use
            # the category pool but still require a literal, specific mention.
            candidates = (
                [item_by_id[item_id] for item_id in structured_ids if item_id in item_by_id]
                if structured_ids else items
            )
            lines[index] = self._inject_explicit_item_links(line, candidates)

        result = self._sanitize_internal_link_labels("\n".join(lines))
        logger.info("  %s: added only inline, explicitly grounded evidence links", context_name)
        return result

    @staticmethod
    def _evidence_link_label(item: Dict[str, Any]) -> str:
        """Build a compact, identifiable source label."""
        title = normalize_untrusted_text(item.get("title") or "").strip()
        words = title.split()
        if len(words) > 6:
            title = " ".join(words[:6]).rstrip(" ,;:") + "…"
        if len(re.findall(r"[A-Za-z0-9]+", title)) < 2:
            category = str(item.get("category") or "source").replace("_", " ").title()
            title = f"{category}: {title}"
        return title or "View source"

    def _inject_explicit_item_links(
        self,
        block: str,
        items: List[Dict[str, Any]],
    ) -> str:
        """Link collected items named verbatim in a visible block.

        Exact matching avoids guessing semantic equivalence while ensuring a
        reader can open every named news story, research result, social post,
        or repository the editorial text explicitly cites.
        """
        enriched = block
        for item in items:
            item_id = (item.get("id") or "").strip()
            category = (item.get("category") or "").strip()
            title = normalize_untrusted_text(item.get("title") or "").strip()
            if not item_id or not category or f"#item-{item_id}" in enriched or not title:
                continue

            phrase = self._find_explicit_item_phrase(title, enriched)
            if not phrase:
                continue
            url = f"/?date={self.date}&category={category}#item-{item_id}"
            pattern = re.compile(
                r"(?<![\w.\-\[])" + re.escape(phrase) + r"(?![\w.\-])",
                re.I,
            )
            enriched, _ = pattern.subn(
                lambda match: f"[{match.group(0)}]({url})", enriched, count=1
            )
        return enriched

    @staticmethod
    def _find_explicit_item_phrase(title: str, text: str) -> Optional[str]:
        """Find the most specific literal title fragment present in ``text``."""
        repository = re.search(r"(?<![\w.-])([\w.-]+/[\w.-]+)(?![\w.-])", title)
        candidates = [repository.group(1)] if repository else []
        if repository:
            repository_name = repository.group(1).split("/", 1)[1]
            if len(repository_name) >= 4:
                candidates.append(repository_name)

        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+._'’-]*", title)
        # Longest fragments first. Two-word lexical overlap ("LLM APIs",
        # "real-time clinical") is too ambiguous across a news corpus and was
        # the source of contextually wrong links; require three words unless a
        # repository identifier supplies an unambiguous canonical name.
        for size in range(min(6, len(words)), 2, -1):
            for start in range(len(words) - size + 1):
                phrase_words = words[start:start + size]
                if not any(len(word) >= 5 or word[:1].isupper() for word in phrase_words):
                    continue
                candidates.append(" ".join(phrase_words))

        for candidate in candidates:
            if re.search(
                r"(?<![\w.\-])" + re.escape(candidate) + r"(?![\w.\-])",
                text,
                re.I,
            ):
                return candidate
        return None

    @staticmethod
    def _select_evidence_items(
        block: str,
        items: List[Dict[str, Any]],
        used_ids: set,
        count: int,
    ) -> List[Dict[str, Any]]:
        """Pick evidence with the strongest lexical overlap, then rank order."""
        tokens = set(re.findall(r"[a-z0-9]{4,}", block.lower()))
        ranked = []
        for position, item in enumerate(items):
            item_id = (item.get("id") or "").strip()
            if not item_id:
                continue
            evidence = f"{item.get('title', '')} {item.get('summary', '')}".lower()
            score = len(tokens & set(re.findall(r"[a-z0-9]{4,}", evidence)))
            # Prefer unused, high-overlap evidence but always return a link.
            ranked.append((item_id in used_ids, -score, position, item))
        ranked.sort(key=lambda value: value[:3])
        return [value[3] for value in ranked[:count]]

    def _sanitize_internal_link_labels(self, text: str) -> str:
        """Remove links whose labels are generic connective text.

        The visible wording is preserved; only the unusable hyperlink is
        removed. This guards the UI even if an enrichment model ignores the
        editorial constraints in its prompt.
        """
        edge_stopwords = {
            "a", "an", "and", "as", "at", "but", "by", "for", "from",
            "in", "into", "of", "on", "or", "the", "to", "with",
        }
        generic_words = edge_stopwords | {
            "best", "important", "most", "news", "research", "source",
        }
        pattern = re.compile(r"\[([^\]]+)\]\((/\?date=[^)]+#item-[^)]+)\)")

        def sanitize(match: re.Match) -> str:
            label = match.group(1)
            words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+.'’-]*", label)
            normalized = [word.lower().strip(".'’") for word in words]
            meaningful = [word for word in normalized if word not in generic_words]
            technical_single = len(words) == 1 and bool(
                re.search(r"[./_-]|\d|[a-z][A-Z]", label)
            )
            if (
                (len(words) < 2 and not technical_single)
                or len(words) > 7
                or normalized[0] in edge_stopwords
                or normalized[-1] in edge_stopwords
                or (len(meaningful) < 2 and not technical_single)
            ):
                logger.warning("Removed generic internal-link label %r", label)
                return label
            return match.group(0)

        sanitized = pattern.sub(sanitize, text)

        # Section headings are navigation structure, never link targets. Strip
        # any Markdown link a model may have inserted while preserving the
        # visible heading text.
        def sanitize_heading(match: re.Match) -> str:
            prefix, heading = match.groups()
            plain_heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
            return prefix + plain_heading

        return re.sub(
            r"(?m)^(#{1,6}\s+)(.+)$",
            sanitize_heading,
            sanitized,
        )

    def _inject_deterministic_links(
        self,
        text: str,
        items: List[Dict[str, Any]],
        context_name: str,
        append_read_more: bool = True,
    ) -> str:
        """Best-effort inline contextual links when LLM enrichment fails or returns no links."""
        if not text or not items:
            return text

        stopwords = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'been', 'but', 'by',
            'for', 'from', 'have', 'in', 'into', 'is', 'it', 'its', 'more',
            'of', 'on', 'or', 'our', 'research', 'source', 'than', 'that',
            'the', 'their', 'these', 'this', 'to', 'using', 'was', 'were',
            'which', 'will', 'with', 'model', 'models', 'paper', 'report',
            'news', 'today', 'released', 'release', 'deep', 'learning',
            'single', 'world', 'open', 'first', 'also', 'over', 'some',
            'most', 'best', 'important', 'development', 'developments',
        }
        
        enriched_text = text
        used_item_ids = set()

        for item in items:
            item_id = (item.get("id") or "").strip()
            category = (item.get("category") or "").strip()
            title = normalize_untrusted_text(item.get("title") or "").strip()
            if not item_id or not category or not title or item_id in used_item_ids:
                continue

            url = f"/?date={self.date}&category={category}#item-{item_id}"
            
            raw_words = [w.strip(".,()[]:\"'") for w in title.split()]
            title_words = [w for w in raw_words if len(w) >= 3 and w.lower() not in stopwords]
            
            matched_phrase = None
            
            # 1. Try 2-word combinations of proper/technical terms
            for j in range(len(title_words) - 1):
                w1, w2 = title_words[j], title_words[j+1]
                phrase_cand = f"{w1} {w2}"
                if len(phrase_cand) >= 7 and re.search(r'\b' + re.escape(phrase_cand) + r'\b', enriched_text):
                    matched_phrase = phrase_cand
                    break
                    
            # 2. Try single capitalized proper noun (e.g. Qwen, Anthropic, OpenAI, AISI, LongCat, Cloudflare)
            if not matched_phrase:
                for w in title_words:
                    if w[0].isupper() and len(w) >= 4 and w.lower() not in stopwords:
                        if re.search(r'\b' + re.escape(w) + r'\b', enriched_text):
                            matched_phrase = w
                            break

            if matched_phrase:
                pattern = re.compile(r'(?<!\[)\b(' + re.escape(matched_phrase) + r')\b(?![^\[]*\])', re.IGNORECASE)
                
                def replace_match(m):
                    matched_str = m.group(1)
                    return f"[{matched_str}]({url})"

                new_text, count = pattern.subn(replace_match, enriched_text, count=1)
                if count > 0 and '](/' in new_text:
                    enriched_text = new_text
                    used_item_ids.add(item_id)

        if used_item_ids:
            logger.info(f"  {context_name}: deterministic fallback added {len(used_item_ids)} inline links")
            return self._sanitize_internal_link_labels(enriched_text)

        if not append_read_more:
            return enriched_text

        # Fallback to appending read more if no inline phrases matched
        max_links = 8 if "executive" in context_name else 6
        lines = text.splitlines()
        link_count = 0
        item_index = 0
        for i, line in enumerate(lines):
            if link_count >= max_links or item_index >= len(items):
                break
            stripped = line.strip()
            if not stripped or stripped.startswith("####") or "](/?date=" in line:
                continue
            if stripped.startswith("- ") or len(stripped) >= 40:
                item = items[item_index]
                item_index += 1
                item_id = (item.get("id") or "").strip()
                category = (item.get("category") or "").strip()
                if not item_id or not category:
                    continue
                url = f"/?date={self.date}&category={category}#item-{item_id}"
                lines[i] = line.rstrip() + f" ([read more]({url}))"
                link_count += 1

        return "\n".join(lines)

    def _markdown_links_to_html(self, text: str) -> str:
        """Convert markdown links to HTML, differentiating internal vs external."""
        def link_replacer(match):
            link_text, url = match.groups()
            if url.startswith('/') or url.startswith('#'):
                # Internal link
                return f'<a href="{url}" class="internal-link">{link_text}</a>'
            else:
                # External link
                return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{link_text}</a>'

        return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link_replacer, text)
