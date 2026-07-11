"""
Per-item analysis cache backed by JSONL.
"""

import hashlib
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from agents.base import AnalyzedItem, CollectedItem

logger = logging.getLogger(__name__)


class AnalysisCache:
    def __init__(
        self,
        cache_path: Path,
        interests_path: Path,
        ttl_days: int = 7,
    ):
        self.cache_path = cache_path
        self.interests_path = interests_path
        self.ttl = timedelta(days=ttl_days)
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._interests_hash = self._hash_text(self._read_text(interests_path))
        self._load()

    @staticmethod
    def _read_text(path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    @staticmethod
    def make_cache_key(item: "CollectedItem") -> str:
        base = f"{item.url}:{item.title}:{item.published}"
        return hashlib.md5(base.encode("utf-8")).hexdigest()

    def _load(self) -> None:
        if not self.cache_path.exists():
            return
        for line in self.cache_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = entry.get("cache_key")
            if not key:
                continue
            self._entries[key] = entry

    def _is_fresh(self, analyzed_at: str) -> bool:
        try:
            ts = datetime.fromisoformat(analyzed_at.replace("Z", "+00:00"))
        except Exception:
            return False
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - ts <= self.ttl

    def get(self, item: "CollectedItem") -> Optional[Dict[str, Any]]:
        cache_key = self.make_cache_key(item)
        entry = self._entries.get(cache_key)
        if not entry:
            return None
        if entry.get("interests_hash") != self._interests_hash:
            return None
        if not self._is_fresh(str(entry.get("analyzed_at") or "")):
            return None
        analysis = entry.get("analysis")
        return analysis if isinstance(analysis, dict) else None

    def set(self, item: "CollectedItem", analysis: Any) -> None:
        if hasattr(analysis, "summary") and hasattr(analysis, "importance_score") and hasattr(analysis, "themes"):
            payload = {
                "summary": analysis.summary,
                "importance_score": analysis.importance_score,
                "reasoning": analysis.reasoning,
                "themes": analysis.themes,
                "sentiment": analysis.sentiment,
            }
        elif is_dataclass(analysis):
            payload = asdict(analysis)
        elif isinstance(analysis, dict):
            payload = analysis
        else:
            return

        entry = {
            "cache_key": self.make_cache_key(item),
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "analysis": payload,
            "interests_hash": self._interests_hash,
        }
        self._entries[entry["cache_key"]] = entry
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
