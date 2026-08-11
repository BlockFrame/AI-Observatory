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
        """Attach evidence links deterministically, once per visible bullet.

        The previous LLM-based rewrite was expensive and frequently exhausted
        its output budget before emitting the required XML wrapper. Evidence
        links are a coverage requirement, not a creative-writing task, so this
        path is deterministic and preserves the generated prose verbatim.
        """
        return self._inject_per_block_links(
            text, items, context_name, links_per_block, evidence_by_bullet
        )

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
        """Ensure each substantive bullet/paragraph carries source evidence."""
        if not text or not items:
            return text

        # Retain any high-confidence inline anchor, then fill remaining
        # coverage gaps with compact source links at the end of each block.
        enriched = self._inject_deterministic_links(
            text, items, context_name, append_read_more=False
        )
        enriched = self._inject_explicit_item_links(enriched, items)
        used_ids = set(re.findall(r"#item-([\w-]+)", enriched))
        lines = enriched.splitlines()
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
            existing_ids = set(re.findall(r"#item-([\w-]+)", line))
            existing = len(existing_ids)

            if structured_ids:
                selected = [
                    item_by_id[item_id]
                    for item_id in structured_ids
                    if item_id in item_by_id and item_id not in existing_ids
                ]
                needed = 0
            else:
                selected = []
                needed = max(0, links_per_block - existing)
            if needed:
                selected = self._select_evidence_items(
                    stripped, items, existing_ids | used_ids, needed
                )
            if not selected:
                continue
            links = []
            for item in selected:
                item_id = item["id"]
                category = item["category"]
                used_ids.add(item_id)
                label = self._evidence_link_label(item)
                links.append(
                    f"[{label}](/?date={self.date}&category={category}#item-{item_id})"
                )
            lines[index] = line.rstrip() + " (" + "; ".join(links) + ")"

        result = self._sanitize_internal_link_labels("\n".join(lines))
        logger.info("  %s: ensured evidence links on visible content blocks", context_name)
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

        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+._'’-]*", title)
        # Longest fragments first: a two-or-more word phrase provides enough
        # identity to map an editorial reference to one collected item.
        for size in range(min(6, len(words)), 1, -1):
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
            if (
                len(words) < 2
                or len(words) > 7
                or normalized[0] in edge_stopwords
                or normalized[-1] in edge_stopwords
                or len(meaningful) < 2
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
