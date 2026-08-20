"""Deterministic guardrails for generated editorial copy."""

import re
from typing import Any, Iterable


# These names were originally used only as an internal style reference.  They
# must never leak into report headings or generated briefing copy.
FORBIDDEN_EDITORIAL_BRANDS = ("QuantumBlack", "McKinsey")
_FORBIDDEN_RE = re.compile(r"\b(?:QuantumBlack|McKinsey)\b", re.IGNORECASE)
_EVIDENCE_ID = r"[0-9a-f]{12}"
_EVIDENCE_TOKEN = rf"(?:\[?{_EVIDENCE_ID}\]?)"
_LEAKED_EVIDENCE_METADATA_RE = re.compile(
    rf"(?:"
    rf"\[(?:{_EVIDENCE_ID})(?:\s*,\s*{_EVIDENCE_ID})*\]"
    rf"|\((?:{_EVIDENCE_TOKEN})(?:\s*,\s*{_EVIDENCE_TOKEN})*\)"
    rf")",
    re.IGNORECASE,
)


def contains_forbidden_brand(text: Any) -> bool:
    """Return True when generated editorial text contains a forbidden brand."""
    return bool(_FORBIDDEN_RE.search(str(text or "")))


def strip_leaked_evidence_suffixes(text: Any) -> str:
    """Remove machine evidence lists accidentally inserted into visible copy."""
    value = _LEAKED_EVIDENCE_METADATA_RE.sub("", str(text or ""))
    # Removing an inline marker may leave doubled prose spaces or a space
    # before punctuation. Preserve leading indentation in Markdown artifacts.
    value = re.sub(r"(?<=\S)[ \t]{2,}(?=\S)", " ", value)
    value = re.sub(r"[ \t]+([,;:.!?])", r"\1", value)
    return re.sub(r"[ \t]+$", "", value, flags=re.MULTILINE)


def contains_leaked_evidence_metadata(text: Any) -> bool:
    """Return True when visible copy still contains a machine evidence list."""
    return bool(_LEAKED_EVIDENCE_METADATA_RE.search(str(text or "")))


def sanitize_editorial_text(text: Any) -> str:
    """Remove internal generation metadata while preserving readable copy."""
    value = str(text or "")
    # Evidence IDs belong to structured JSON fields. Some models duplicate
    # them at the end of bullets or inline beside the supported phrase. Remove
    # only containers made entirely of machine IDs, leaving links untouched.
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
    value = re.sub(r"(?<=\S)[ \t]{2,}(?=\S)", " ", value)
    value = re.sub(r":\s*$", "", value, flags=re.MULTILINE)
    return value


def find_forbidden_editorial_fields(values: Iterable[tuple[str, Any]]) -> list[str]:
    """Return field names whose generated copy still contains leaked brands."""
    return [name for name, value in values if contains_forbidden_brand(value)]


def find_leaked_evidence_fields(values: Iterable[tuple[str, Any]]) -> list[str]:
    """Return visible editorial fields containing machine evidence metadata."""
    return [
        name for name, value in values if contains_leaked_evidence_metadata(value)
    ]
