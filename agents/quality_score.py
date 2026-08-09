"""Deterministic editorial quality scoring for generated reports."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable


_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BROKEN_MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\([^)]*$|\[[^\]]*$")
_FAILURE_MARKERS = ("analysis failed", "analysis complete", "generation failed", "connection error")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _link_integrity(text: str) -> float:
    """Return 0..1 for syntactic and internal-link integrity."""
    if not text:
        return 0.0
    if _BROKEN_MARKDOWN_LINK.search(text):
        return 0.0
    links = _MARKDOWN_LINK.findall(text)
    if not links:
        return 0.75
    valid = sum(
        1
        for label, url in links
        if label.strip()
        and (
            url.startswith(("https://", "http://"))
            or re.match(r"^/\?date=\d{4}-\d{2}-\d{2}&category=[\w-]+#item-[\w-]+$", url)
        )
    )
    return valid / len(links)


def _category_score(category: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    count = max(0, int(payload.get("count") or 0))
    summary = str(payload.get("category_summary") or "").strip()
    top_items = payload.get("top_items") or []
    quality = payload.get("analysis_quality") or {}
    fallback_rate = _clamp(float(quality.get("fallback_rate") or 0.0))

    sources = {
        str(item.get("source") or item.get("source_type") or "").strip().lower()
        for item in top_items
        if isinstance(item, dict) and (item.get("source") or item.get("source_type"))
    }
    safe_urls = sum(
        1 for item in top_items
        if isinstance(item, dict) and str(item.get("url") or "").startswith(("https://", "http://"))
    )
    expected_top = min(count, 5)
    components = {
        "summary_substance": _clamp(len(summary) / 300),
        "analysis_coverage": 1.0 - fallback_rate,
        "top_item_coverage": 1.0 if expected_top == 0 else _clamp(len(top_items) / expected_top),
        "source_quality": 1.0 if expected_top == 0 else (
            0.6 * _clamp(len(sources) / min(expected_top, 3))
            + 0.4 * _clamp(safe_urls / max(1, min(len(top_items), expected_top)))
        ),
        "markdown_link_integrity": _link_integrity(summary),
    }
    weights = {
        "summary_substance": 25,
        "analysis_coverage": 30,
        "top_item_coverage": 20,
        "source_quality": 15,
        "markdown_link_integrity": 10,
    }
    score = sum(components[name] * weight for name, weight in weights.items())
    if any(marker in summary.lower() for marker in _FAILURE_MARKERS):
        score = min(score, 20.0)
    return {
        "category": category,
        "score": round(score, 1),
        "components": {name: round(value * 100, 1) for name, value in components.items()},
        "items": count,
    }


def _active_category_scores(categories: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for category, payload in categories.items():
        if isinstance(payload, dict) and int(payload.get("count") or 0) > 0:
            yield _category_score(category, payload)


def calculate_quality_score(
    summary: Dict[str, Any],
    report_threshold: float = 70.0,
    category_threshold: float = 55.0,
) -> Dict[str, Any]:
    """Calculate a stable 0..100 score without invoking an LLM."""
    categories = summary.get("categories") or {}
    category_results = list(_active_category_scores(categories))
    analysis_funnel = summary.get("analysis_funnel") or {}
    wiped_out_categories = [
        category
        for category, funnel in analysis_funnel.items()
        if isinstance(funnel, dict)
        and int(funnel.get("collected") or 0) > 0
        and int(funnel.get("analyzed") or 0) == 0
    ]
    scored_categories = {result["category"] for result in category_results}
    for category in wiped_out_categories:
        if category not in scored_categories:
            category_results.append({
                "category": category,
                "score": 0.0,
                "components": {"analysis_retention": 0.0},
                "items": 0,
            })
    category_average = (
        sum(result["score"] for result in category_results) / len(category_results)
        if category_results else 0.0
    )
    executive = str(summary.get("executive_summary") or "").strip()
    topics = summary.get("top_topics") or []
    generation_quality = summary.get("generation_quality") or {}
    collection = summary.get("collection_status") or {}

    components = {
        "executive_summary": _clamp(len(executive) / 400),
        "topic_coverage": _clamp(len(topics) / 3),
        "category_quality": category_average / 100.0,
        "synthesis_reliability": 0.0 if generation_quality.get("fallback_used") is True else 1.0,
        "collection_health": {
            "success": 1.0,
            "partial": 0.6,
            "failed": 0.0,
        }.get(collection.get("overall"), 0.6),
    }
    weights = {
        "executive_summary": 25,
        "topic_coverage": 15,
        "category_quality": 40,
        "synthesis_reliability": 15,
        "collection_health": 5,
    }
    score = sum(components[name] * weight for name, weight in weights.items())
    if any(marker in executive.lower() for marker in _FAILURE_MARKERS):
        score = min(score, 20.0)
    if wiped_out_categories:
        score = min(score, 20.0)

    failed_categories = [
        result["category"] for result in category_results
        if result["score"] < category_threshold
    ]
    passed = score >= report_threshold and not failed_categories and not wiped_out_categories
    return {
        "score": round(score, 1),
        "threshold": report_threshold,
        "category_threshold": category_threshold,
        "passed": passed,
        "components": {name: round(value * 100, 1) for name, value in components.items()},
        "categories": {result["category"]: result for result in category_results},
        "failed_categories": failed_categories,
        "wiped_out_categories": wiped_out_categories,
        "version": 2,
    }
