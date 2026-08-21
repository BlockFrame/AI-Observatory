#!/usr/bin/env python3
"""
Validate a generated/published daily report's summary.json.

Purpose
-------
The daily pipeline can exit 0 ("PIPELINE COMPLETED SUCCESSFULLY") even when the
Executive Summary and Topic Detection phases failed, because those failures are
caught internally and written into summary.json as sentinel strings rather than
raised. On 2026-06-02 a ~90 min triple-provider outage produced a published
report whose executive_summary literally read "Executive summary generation
failed: Connection error." while CI stayed green.

This script inspects the actual user-facing artifact (summary.json) and exits
non-zero when the report is not publishable, so callers can gate a commit
(publish gate) or trigger a re-run (watchdog).

Usage
-----
  # Validate a freshly generated local report (publish gate, in CI):
  python3 scripts/validate_report.py --web-dir ./web --date 2026-06-02

  # Validate the live published report (watchdog):
  python3 scripts/validate_report.py --url https://radar.wiredframe.xyz --date 2026-06-02

Exit codes
----------
  0  report is valid / publishable
  1  report is INVALID (failed checks) -> caller should block or re-run
  2  could not load the report at all (missing file / fetch error / bad JSON)

When --date is omitted it defaults to "today" in America/New_York.
Add --json to emit a machine-readable result object on stdout.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Executing ``python scripts/validate_report.py`` makes ``scripts/`` the first
# import root, not the repository root. Add the project root before importing
# pipeline modules so the documented CLI and GitHub Actions publish gate work
# without relying on an ambient PYTHONPATH.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.quality_score import calculate_quality_score
from agents.editorial_guard import (
    find_forbidden_editorial_fields,
    find_leaked_evidence_fields,
)
from report_schema import REPORT_SCHEMA_REQUIRED_FROM, REPORT_SCHEMA_VERSION

# Substrings that indicate a phase wrote a failure sentinel instead of real content.
# Matched case-insensitively against the executive summary text.
FAILURE_SENTINELS = (
    "executive summary generation failed",
    "generation failed:",
    "connection error",
    "apiconnectionerror",
    "apitimeouterror",
    "error:",
)

# Minimum acceptable executive summary length (chars). The failure sentinel is
# ~54 chars; a real summary on this platform runs 1.5k-5k chars. 400 is a
# conservative floor that flags truncated/empty output without false-flagging a
# genuinely short day.
MIN_EXEC_SUMMARY_CHARS = 400
MIN_CATEGORY_SUMMARY_CHARS = 300
MAX_ANALYSIS_FALLBACK_RATE = float(os.getenv("MAX_ANALYSIS_FALLBACK_RATE", "0.20"))
MIN_REPORT_QUALITY_SCORE = float(os.getenv("MIN_REPORT_QUALITY_SCORE", "70"))
MIN_CATEGORY_QUALITY_SCORE = float(os.getenv("MIN_CATEGORY_QUALITY_SCORE", "55"))
CRITICAL_PHASES = (
    "Phase 3: Topic Detection",
    "Phase 4: Executive Summary",
)


def _load_local(web_dir: str, date_str: str) -> dict:
    import os
    path = os.path.join(web_dir, "data", date_str, "summary.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"summary.json not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_url(base_url: str, date_str: str) -> dict:
    url = base_url.rstrip("/") + f"/data/{date_str}/summary.json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ai-news-report-validator/1.0", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise IOError(f"HTTP {resp.status} fetching {url}")
        return json.loads(resp.read().decode("utf-8"))


def validate(summary: dict, date_str: str) -> dict:
    """Return a result dict: {valid: bool, failures: [str], warnings: [str], stats: {}}."""
    failures = []
    warnings = []

    exec_summary = (summary.get("executive_summary") or "").strip()
    exec_lower = exec_summary.lower()
    top_topics = summary.get("top_topics") or []
    analyzed = summary.get("total_items_analyzed") or 0
    collected = summary.get("total_items_collected") or 0
    report_date = summary.get("date") or summary.get("coverage_date") or ""
    phase_status = summary.get("phase_status") or []
    generation_quality = summary.get("generation_quality") or {}
    published_quality_score = summary.get("quality_score")
    schema_version = summary.get("schema_version")

    # The public artifact contract is explicit from the v1.0 cutover onward.
    # Historical reports remain readable, but an unknown declared version is
    # always unsafe because this validator cannot prove compatibility.
    if schema_version is None:
        if date_str >= REPORT_SCHEMA_REQUIRED_FROM:
            failures.append(
                f"schema_version missing for report on/after {REPORT_SCHEMA_REQUIRED_FROM}"
            )
        else:
            warnings.append("schema_version missing on legacy report")
    elif schema_version != REPORT_SCHEMA_VERSION:
        failures.append(
            f"unsupported schema_version {schema_version!r}; expected {REPORT_SCHEMA_VERSION!r}"
        )

    # 1) Executive summary must be non-empty and substantive.
    if not exec_summary:
        failures.append("executive_summary is empty")
    elif len(exec_summary) < MIN_EXEC_SUMMARY_CHARS:
        failures.append(
            f"executive_summary too short ({len(exec_summary)} < {MIN_EXEC_SUMMARY_CHARS} chars)"
        )

    # 2) Executive summary must not be a failure sentinel.
    for sentinel in FAILURE_SENTINELS:
        if sentinel in exec_lower:
            failures.append(f"executive_summary contains failure sentinel: {sentinel!r}")
            break

    # 3) Topic detection must have produced topics.
    if not isinstance(top_topics, list) or len(top_topics) == 0:
        failures.append("top_topics is empty (topic detection failed)")

    # 4) Analysis must have produced items (catches a gather/analysis wipeout).
    if analyzed <= 0:
        failures.append(f"total_items_analyzed is {analyzed} (no analyzed items)")

    # 5) Critical synthesis phases must be real LLM output, not deterministic
    # fallbacks. New reports carry phase_status; older reports remain readable
    # but surface a warning because their quality cannot be proven.
    phases_by_name = {
        phase.get("name"): phase
        for phase in phase_status
        if isinstance(phase, dict) and phase.get("name")
    }
    if phases_by_name:
        for phase_name in CRITICAL_PHASES:
            phase = phases_by_name.get(phase_name)
            if not phase:
                failures.append(f"missing critical phase status: {phase_name}")
                continue
            status = phase.get("status")
            details = phase.get("details") or phase.get("error") or ""
            loaded_checkpoint = status == "skipped" and "loaded from checkpoint" in details
            if status != "success" and not loaded_checkpoint:
                failures.append(
                    f"{phase_name} status is {status!r}: {details or 'no details'}"
                )
    else:
        warnings.append("phase_status missing; synthesis quality cannot be verified")

    if generation_quality.get("fallback_used") is True:
        failures.append("generation_quality reports deterministic synthesis fallback")

    # 6) Every non-empty category needs a substantive briefing. This catches
    # both the hardcoded "Analysis complete" fallback and token-starved output.
    categories = summary.get("categories") or {}
    for category, payload in categories.items():
        if not isinstance(payload, dict):
            continue
        category_summary = (payload.get("category_summary") or "").strip()
        if category_summary.lower().startswith(("analysis complete", "analysis failed")):
            failures.append(f"{category} category_summary is a generic fallback")
        elif (payload.get("count") or 0) > 0 and len(category_summary) < MIN_CATEGORY_SUMMARY_CHARS:
            failures.append(
                f"{category} category_summary too short "
                f"({len(category_summary)} < {MIN_CATEGORY_SUMMARY_CHARS} chars)"
            )

        analysis_quality = payload.get("analysis_quality")
        if isinstance(analysis_quality, dict):
            total_items = int(analysis_quality.get("total_items") or 0)
            fallback_items = int(analysis_quality.get("fallback_items") or 0)
            fallback_rate = float(analysis_quality.get("fallback_rate") or 0.0)
            if total_items >= 5 and fallback_rate > MAX_ANALYSIS_FALLBACK_RATE:
                failures.append(
                    f"{category} analysis fallback rate is {fallback_rate:.1%} "
                    f"({fallback_items}/{total_items}, max {MAX_ANALYSIS_FALLBACK_RATE:.0%})"
                )
        elif (payload.get("count") or 0) > 0:
            warnings.append(f"{category} analysis_quality missing; map coverage cannot be verified")

    # 6b) A category that had items entering analysis may not silently collapse
    # to zero. This is the exact failure mode that emptied News on 2026-08-09.
    analysis_funnel = summary.get("analysis_funnel") or {}
    if analysis_funnel:
        editorial_categories = {"news", "research", "social", "github_trending"}
        for category, funnel in analysis_funnel.items():
            if category not in editorial_categories:
                continue
            if not isinstance(funnel, dict):
                continue
            gathered_count = int(funnel.get("collected") or 0)
            analyzed_count = int(funnel.get("analyzed") or 0)
            if gathered_count > 0 and analyzed_count == 0:
                failures.append(
                    f"{category} category wipeout: {gathered_count} items entered analysis, 0 survived"
                )
    else:
        warnings.append("analysis_funnel missing; category wipeouts cannot be verified")

    # 6c) Generated editorial copy must not leak internal style references.
    editorial_fields = [("executive_summary", exec_summary)]
    for category, payload in categories.items():
        if isinstance(payload, dict):
            editorial_fields.append(
                (f"categories.{category}.category_summary", payload.get("category_summary"))
            )
    for index, topic in enumerate(top_topics if isinstance(top_topics, list) else []):
        if not isinstance(topic, dict):
            continue
        for field in ("name", "description", "business_implication"):
            editorial_fields.append((f"top_topics[{index}].{field}", topic.get(field)))
    for field_name in find_forbidden_editorial_fields(editorial_fields):
        failures.append(f"{field_name} contains a forbidden internal style reference")
    for field_name in find_leaked_evidence_fields(editorial_fields):
        failures.append(f"{field_name} contains visible machine evidence IDs")

    # 6d) Evidence IDs must resolve to current items. Topics advertised as
    # cross-category must be backed by at least two real, non-empty categories.
    current_item_categories = {}
    has_evidence_catalog = False
    for category, payload in categories.items():
        if not isinstance(payload, dict):
            continue
        if "current_item_ids" in payload:
            has_evidence_catalog = True
        for item_id in payload.get("current_item_ids") or []:
            if isinstance(item_id, str) and item_id:
                current_item_categories[item_id] = category

    if has_evidence_catalog:
        executive_evidence = summary.get("executive_evidence_items") or []
        invalid_exec_evidence = [
            item_id for item_id in executive_evidence
            if item_id not in current_item_categories
        ]
        executive_categories = {
            current_item_categories[item_id]
            for item_id in executive_evidence
            if item_id in current_item_categories
        }
        active_categories = {
            category for category, payload in categories.items()
            if isinstance(payload, dict) and int(payload.get("count") or 0) > 0
        }
        required_exec_categories = min(2, len(active_categories))
        if invalid_exec_evidence:
            failures.append(
                f"executive_summary references {len(invalid_exec_evidence)} non-current evidence item(s)"
            )
        if len(executive_categories) < required_exec_categories:
            failures.append(
                "executive_summary evidence covers "
                f"{len(executive_categories)} current categories "
                f"(minimum {required_exec_categories})"
            )

        for index, topic in enumerate(top_topics if isinstance(top_topics, list) else []):
            if not isinstance(topic, dict):
                failures.append(f"top_topics[{index}] is not an object")
                continue
            representative_items = topic.get("representative_items") or []
            invalid_topic_evidence = [
                item_id for item_id in representative_items
                if item_id not in current_item_categories
            ]
            evidence_categories = {
                current_item_categories[item_id]
                for item_id in representative_items
                if item_id in current_item_categories
            }
            declared_categories = {
                category
                for category, count in (topic.get("category_breakdown") or {}).items()
                if int(count or 0) > 0
                and category in active_categories
            }
            if invalid_topic_evidence:
                failures.append(
                    f"top_topics[{index}] references non-current evidence item(s)"
                )
            if len(evidence_categories) < 2:
                failures.append(
                    f"top_topics[{index}] is not cross-category: evidence covers "
                    f"{len(evidence_categories)} current categories"
                )
            if len(declared_categories) < 2:
                failures.append(
                    f"top_topics[{index}] category_breakdown has fewer than two non-empty categories"
                )
    else:
        warnings.append("current item evidence catalog missing; synthesis grounding cannot be verified")

    # 7) Date sanity: published report should match the requested date.
    if report_date and report_date != date_str:
        warnings.append(f"report date {report_date!r} != requested {date_str!r}")

    # Non-fatal quality signals.
    if not summary.get("hero_image_url"):
        warnings.append("hero_image_url missing (hero fallback or failure)")

    # Current generators always publish this score. Older reports remain
    # inspectable, but only scored reports can exercise the numeric gate.
    computed_quality = calculate_quality_score(
        summary,
        report_threshold=MIN_REPORT_QUALITY_SCORE,
        category_threshold=MIN_CATEGORY_QUALITY_SCORE,
    )
    if isinstance(published_quality_score, dict):
        if computed_quality["score"] < MIN_REPORT_QUALITY_SCORE:
            failures.append(
                f"report quality score is {computed_quality['score']:.1f} "
                f"(min {MIN_REPORT_QUALITY_SCORE:.1f})"
            )
        for category in computed_quality["failed_categories"]:
            category_score = computed_quality["categories"][category]["score"]
            failures.append(
                f"{category} quality score is {category_score:.1f} "
                f"(min {MIN_CATEGORY_QUALITY_SCORE:.1f})"
            )
    else:
        warnings.append("quality_score missing; numeric quality gate not available")

    return {
        "valid": len(failures) == 0,
        "failures": failures,
        "warnings": warnings,
        "stats": {
            "date": report_date,
            "schema_version": schema_version,
            "exec_summary_chars": len(exec_summary),
            "top_topics": len(top_topics) if isinstance(top_topics, list) else 0,
            "total_items_collected": collected,
            "total_items_analyzed": analyzed,
            "hero_image_url": summary.get("hero_image_url"),
            "max_analysis_fallback_rate": MAX_ANALYSIS_FALLBACK_RATE,
            "quality_score": computed_quality["score"],
            "min_quality_score": MIN_REPORT_QUALITY_SCORE,
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Validate a daily report's summary.json")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--web-dir", help="Local web dir containing data/<date>/summary.json")
    src.add_argument(
        "--url",
        help="Base URL of the published site, e.g. https://radar.wiredframe.xyz",
    )
    p.add_argument("--date", help="Report date YYYY-MM-DD (default: today in America/New_York)")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON result")
    args = p.parse_args()

    if not args.web_dir and not args.url:
        args.web_dir = "./web"

    date_str = args.date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    # Load the report; load failure is its own exit code (2) so callers can tell
    # "couldn't check" apart from "checked and it's bad".
    try:
        if args.url:
            summary = _load_url(args.url, date_str)
            source = args.url.rstrip("/") + f"/data/{date_str}/summary.json"
        else:
            summary = _load_local(args.web_dir, date_str)
            source = f"{args.web_dir}/data/{date_str}/summary.json"
    except (FileNotFoundError, urllib.error.URLError, urllib.error.HTTPError, IOError, json.JSONDecodeError) as e:
        result = {"valid": False, "loaded": False, "error": str(e), "date": date_str}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"LOAD ERROR: could not load report for {date_str}: {e}", file=sys.stderr)
        return 2

    result = validate(summary, date_str)
    result["loaded"] = True
    result["source"] = source

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        stats = result["stats"]
        status = "VALID" if result["valid"] else "INVALID"
        print(f"[{status}] report {date_str} ({source})")
        print(
            f"  exec_summary={stats['exec_summary_chars']} chars | "
            f"topics={stats['top_topics']} | "
            f"analyzed={stats['total_items_analyzed']} | "
            f"collected={stats['total_items_collected']}"
        )
        for f in result["failures"]:
            print(f"  FAIL: {f}")
        for w in result["warnings"]:
            print(f"  warn: {w}")

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
