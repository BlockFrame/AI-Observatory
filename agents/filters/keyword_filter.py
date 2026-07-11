"""
Regex-capable keyword filtering.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple

from agents.base import CollectedItem


@dataclass
class KeywordRules:
    required: List[str] = field(default_factory=list)
    excluded: List[str] = field(default_factory=list)
    regex_aliases: List[Tuple[re.Pattern, str]] = field(default_factory=list)
    global_filters: List[str] = field(default_factory=list)


class KeywordFilter:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.rules = self._load_rules(config_path)

    @staticmethod
    def _load_rules(path: Path) -> KeywordRules:
        rules = KeywordRules()
        if not path.exists():
            return rules
        in_global = False
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line == "[GLOBAL_FILTER]":
                in_global = True
                continue
            if in_global:
                rules.global_filters.append(line.lower())
                continue
            if line.startswith("+"):
                rules.required.append(line[1:].strip().lower())
                continue
            if line.startswith("!"):
                rules.excluded.append(line[1:].strip().lower())
                continue
            if line.startswith("/") and "=>" in line:
                pattern_part, alias_part = line.split("=>", 1)
                pattern = pattern_part.strip().strip("/")
                alias = alias_part.strip()
                rules.regex_aliases.append((re.compile(pattern, re.IGNORECASE), alias))
        return rules

    def filter_items(self, items: List[CollectedItem]) -> Tuple[List[CollectedItem], Dict[str, Set[str]]]:
        if not any([self.rules.required, self.rules.excluded, self.rules.regex_aliases, self.rules.global_filters]):
            return items, {}
        output: List[CollectedItem] = []
        matches: Dict[str, Set[str]] = {}
        for item in items:
            haystack = f"{item.title} {item.content}".lower()
            if any(bad in haystack for bad in self.rules.global_filters):
                continue
            if any(bad in haystack for bad in self.rules.excluded):
                continue
            matched = {kw for kw in self.rules.required if kw in haystack}
            for pattern, alias in self.rules.regex_aliases:
                if pattern.search(f"{item.title} {item.content}"):
                    matched.add(alias)
            if self.rules.required and not matched:
                continue
            output.append(item)
            if matched:
                matches[item.id] = matched
        return output, matches
