"""Deterministic guardrails for generated editorial copy."""

import re
from typing import Any, Iterable


# These names were originally used only as an internal style reference.  They
# must never leak into report headings or generated briefing copy.
FORBIDDEN_EDITORIAL_BRANDS = ("QuantumBlack", "McKinsey")
_FORBIDDEN_RE = re.compile(r"\b(?:QuantumBlack|McKinsey)\b", re.IGNORECASE)
_EVIDENCE_ID = r"[0-9a-f]{12}"
_LEAKED_EVIDENCE_SUFFIX_RE = re.compile(
    rf"[ \t]*(?:"
    rf"\[(?:{_EVIDENCE_ID})(?:\s*,\s*{_EVIDENCE_ID})*\]"
    rf"|\((?:\[{_EVIDENCE_ID}\])(?:\s*,\s*\[{_EVIDENCE_ID}\])*\)"
    rf")[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def contains_forbidden_brand(text: Any) -> bool:
    """Return True when generated editorial text contains a forbidden brand."""
    return bool(_FORBIDDEN_RE.search(str(text or "")))


def strip_leaked_evidence_suffixes(text: Any) -> str:
    """Remove machine evidence lists accidentally appended to visible lines."""
    return _LEAKED_EVIDENCE_SUFFIX_RE.sub("", str(text or ""))


def sanitize_editorial_text(text: Any) -> str:
    """Remove internal generation metadata while preserving readable copy."""
    value = str(text or "")
    # Evidence IDs belong to structured JSON fields. Some models duplicate
    # them at the end of visible bullets; remove only the exact machine-ID
    # suffix formats so normal Markdown links and prose remain untouched.
    value = strip_leaked_evidence_suffixes(value)
    value = re.sub(
        r"\bQuantumBlack\s+(?=Executive\s+Briefing)",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\bQuantumBlack\s*,?\s*AI\s+by\s+McKinsey\b",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\bQuantumBlack\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(?:AI\s+by\s+)?McKinsey(?:[- ]style)?\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[ \t]+([,:;])", r"\1", value)
    value = re.sub(r"([,:;])(?:\s*\1)+", r"\1", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r":\s*$", "", value, flags=re.MULTILINE)
    return value


def find_forbidden_editorial_fields(values: Iterable[tuple[str, Any]]) -> list[str]:
    """Return field names whose generated copy still contains leaked brands."""
    return [name for name, value in values if contains_forbidden_brand(value)]
