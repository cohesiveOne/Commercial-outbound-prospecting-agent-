"""Domain normalization used for dedupe against HubSpot and exclusions."""

from __future__ import annotations

from urllib.parse import urlparse


def normalize_domain(value: str | None) -> str:
    """Return a bare lowercase domain: 'https://www.Acme.com/x' -> 'acme.com'."""
    if not value:
        return ""
    value = value.strip().lower()
    if "://" not in value:
        value = "http://" + value
    host = urlparse(value).hostname or ""
    if host.startswith("www."):
        host = host[4:]
    return host.rstrip(".")
