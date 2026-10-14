"""Remove accounts already in HubSpot, excluded, or prospected recently."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from .domains import normalize_domain

LEDGER_PATH = Path(__file__).resolve().parent.parent / "output" / "ledger.json"


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, str]:
    """Ledger maps normalized domain -> ISO date it was last surfaced."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_ledger(ledger: dict[str, str], path: Path = LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, sort_keys=True), encoding="utf-8")


def dedupe_accounts(accounts: Iterable[dict[str, Any]], *,
                    crm_domains: Iterable[str] = (),
                    excluded_domains: Iterable[str] = (),
                    ledger: dict[str, str] | None = None,
                    cooldown_days: int = 90,
                    today: date | None = None) -> tuple[list[dict], list[dict]]:
    """Split accounts into (keep, dropped). Dropped items carry a `drop_reason`."""
    today = today or date.today()
    crm = {normalize_domain(d) for d in crm_domains if d}
    excluded = {normalize_domain(d) for d in excluded_domains if d}
    ledger = ledger or {}
    seen: set[str] = set()
    keep, dropped = [], []

    for acct in accounts:
        domain = normalize_domain(acct.get("website") or acct.get("domain"))
        key = domain or (acct.get("zoominfo_id") and f"zi:{acct['zoominfo_id']}") or acct.get("name", "").lower()
        reason = None
        if key in seen:
            reason = "duplicate in run"
        elif domain and domain in excluded:
            reason = "excluded domain"
        elif domain and domain in crm:
            reason = "already in HubSpot"
        elif domain in ledger:
            last = datetime.strptime(ledger[domain], "%Y-%m-%d").date()
            if (today - last).days < cooldown_days:
                reason = f"surfaced {ledger[domain]} (cooldown {cooldown_days}d)"
        seen.add(key)
        if reason:
            dropped.append({**acct, "drop_reason": reason})
        else:
            keep.append({**acct, "domain": domain})
    return keep, dropped
