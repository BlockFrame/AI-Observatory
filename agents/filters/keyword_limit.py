"""
Limit number of items shown per keyword.
"""

from collections import defaultdict
from typing import Dict, List, Set

from agents.base import CollectedItem


def apply_keyword_limit(
    items: List[CollectedItem],
    keyword_matches: Dict[str, Set[str]],
    max_per_keyword: int,
) -> List[CollectedItem]:
    if max_per_keyword <= 0 or not keyword_matches:
        return items
    per_keyword_count = defaultdict(int)
    limited: List[CollectedItem] = []
    for item in items:
        matches = keyword_matches.get(item.id, set())
        if not matches:
            limited.append(item)
            continue
        allowed = True
        for keyword in sorted(matches):
            if per_keyword_count[keyword] >= max_per_keyword:
                allowed = False
                break
        if not allowed:
            continue
        limited.append(item)
        for keyword in matches:
            per_keyword_count[keyword] += 1
    return limited
