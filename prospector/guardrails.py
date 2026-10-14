"""Deterministic checks on outreach drafts before a human sees them."""

from __future__ import annotations

import re
from typing import Any


def check_drafts(drafts: list[dict[str, Any]], icp: dict[str, Any]) -> list[str]:
    """Return human-readable issues for a single account's drafts (empty = clean)."""
    rules = icp.get("outreach_guardrails") or {}
    banned = [t for t in rules.get("banned_terms") or [] if t]
    marker = rules.get("placeholder_marker") or ""
    issues = []
    for d in drafts:
        label = f"step {d.get('step', '?')} ({d.get('channel', 'email')})"
        text = f"{d.get('subject', '')}\n{d.get('body', '')}"
        for term in banned:
            # Whole-word match: "nVent" must not fire on "Innventure".
            if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE):
                issues.append(f"{label}: banned term '{term}'")
        if marker and marker in text:
            issues.append(f"{label}: unresolved placeholder '{marker}...'")
    return issues
