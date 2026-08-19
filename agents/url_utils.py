"""Small, strict URL helpers shared by network and publishing code."""

from urllib.parse import urlsplit


def hostname_matches(url: object, expected_domain: str, *, allow_subdomains: bool = True) -> bool:
    """Return whether *url* belongs to an expected DNS domain.

    Comparing parsed hostnames prevents suffix-confusion values such as
    ``github.com.attacker.example`` from passing a substring check.
    """
    if not isinstance(url, str) or not url.strip():
        return False

    try:
        parsed = urlsplit(url.strip())
        hostname = (parsed.hostname or "").rstrip(".").lower()
    except (TypeError, ValueError):
        return False

    domain = expected_domain.strip().rstrip(".").lower()
    if not hostname or not domain or parsed.scheme.lower() not in {"http", "https"}:
        return False
    return hostname == domain or (allow_subdomains and hostname.endswith(f".{domain}"))
