"""
Push mode helpers: daily/current/incremental.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple


def _extract_urls(payload: Dict) -> Set[str]:
    urls: Set[str] = set()
    reports = payload.get("category_reports", {})
    for report in reports.values():
        for item in report.get("top_items", []):
            base = item.get("item", item)
            url = base.get("url")
            if url:
                urls.add(url)
    return urls


def _load_state(path: Path) -> Dict:
    if not path.exists():
        return {"last_push_date": "", "last_push_items": [], "last_run_date": ""}
    return json.loads(path.read_text(encoding="utf-8"))


def update_push_state(path: Path, payload: Dict) -> None:
    state = {
        "last_push_date": payload.get("date", ""),
        "last_push_items": sorted(_extract_urls(payload)),
        "last_run_date": datetime.utcnow().strftime("%Y-%m-%d"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_current_payload(payload: Dict) -> Dict:
    report = dict(payload)
    report["executive_summary"] = ""
    for category, category_report in report.get("category_reports", {}).items():
        report["category_reports"][category]["top_items"] = category_report.get("top_items", [])[:5]
    return report


def build_push_payload(mode: str, payload: Dict, state_path: Path) -> Tuple[Dict, bool]:
    mode = (mode or "daily").strip().lower()
    if mode == "daily":
        return payload, True
    if mode == "current":
        return _build_current_payload(payload), True

    state = _load_state(state_path)
    last_items = set(state.get("last_push_items") or [])
    report = dict(payload)
    changed = False
    for category, category_report in report.get("category_reports", {}).items():
        top_items = category_report.get("top_items", [])
        filtered = []
        for item in top_items:
            base = item.get("item", item)
            url = base.get("url")
            if url and url in last_items:
                continue
            filtered.append(item)
        report["category_reports"][category]["top_items"] = filtered
        changed = changed or bool(filtered)
    if not changed:
        report["executive_summary"] = "No new significant items since last run."
    return report, changed
