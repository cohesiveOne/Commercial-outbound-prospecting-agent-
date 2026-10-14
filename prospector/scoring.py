"""Deterministic account fit scoring against a segment in icp.yaml.

Input account shape (what the agent writes to accounts.json):

    {
      "zoominfo_id": "346021735",
      "name": "Coolcentric",
      "website": "www.coolcentric.com",
      "employee_count": 569,
      "country": "United States",
      "industries": ["mfg.industrialmachinery"],
      "description": "...",                 # optional, from redeem/enrich
      "sub_segment": "cdu",                 # which sub-segment search found it
      "matched_keywords": ["coolant distribution"],
      "signals": [{"type": "scoop", "title": "...", "date": "2026-09-01"}],
      "contacts": [{"persona": "engineering", ...}]
    }

Every field except name is optional; missing data scores conservatively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class ScoreResult:
    score: int
    tier: str
    breakdown: dict[str, float]
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"score": self.score, "tier": self.tier,
                "breakdown": self.breakdown, "reasons": self.reasons}


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _industry_score(account: dict, seg: dict) -> tuple[float, str | None]:
    targets = {i.lower() for i in seg["zoominfo"]["industry_ids"]}
    industries = {str(i).lower() for i in account.get("industries") or []}
    if not industries:
        # Found by a keyword search without an industry filter: unknown, not a miss.
        return 0.5, None
    hit = targets & industries
    if hit:
        return 1.0, f"target industry ({', '.join(sorted(hit))})"
    return 0.0, None


def _keyword_score(account: dict, seg: dict) -> tuple[float, str | None]:
    description = (account.get("description") or "").lower()
    phrases = [kw.lower() for sub in seg["sub_segments"].values()
               for kw in sub["description_keywords"]]
    hits = sorted({p for p in phrases if p in description})
    if hits:
        return 1.0, f"description mentions {', '.join(hits[:3])}"
    matched = account.get("matched_keywords") or []
    if matched:
        return 0.7, f"found by ZoomInfo keyword search ({', '.join(matched[:3])})"
    return 0.0, None


def _size_score(account: dict, seg: dict) -> tuple[float, str | None]:
    employees = _to_int(account.get("employee_count"))
    zi = seg["zoominfo"]
    if employees is None:
        return 0.3, None
    lo, hi = zi["sweet_spot"]
    if lo <= employees <= hi:
        return 1.0, f"{employees:,} employees (sweet spot)"
    if zi["employee_min"] <= employees <= zi["employee_max"]:
        return 0.5, f"{employees:,} employees (in range)"
    return 0.0, None


def _geo_score(account: dict, icp: dict) -> tuple[float, str | None]:
    country = account.get("country")
    if not country:
        return 0.5, None
    targets = {c.lower() for c in icp["run_defaults"]["default_countries"]}
    if country.lower() in targets:
        return 1.0, None
    return 0.0, None


def _signal_score(account: dict, icp: dict, today: date) -> tuple[float, str | None]:
    lookback = icp["scoring"]["signal_lookback_days"]
    recent = []
    for sig in account.get("signals") or []:
        d = _parse_date(sig.get("date"))
        if d is None or (today - d).days > lookback or d > today:
            continue
        if sig.get("type") == "intent" and (sig.get("score") or 0) < 70:
            continue
        recent.append(sig)
    n = len(recent)
    if n == 0:
        return 0.0, None
    value = {1: 0.5, 2: 0.75}.get(n, 1.0)
    top = recent[0].get("title") or recent[0].get("topic") or recent[0].get("type")
    return value, f"{n} recent signal(s), e.g. {top}"


def _persona_score(account: dict, seg: dict) -> tuple[float, str | None]:
    covered = {c.get("persona") for c in account.get("contacts") or [] if c.get("persona")}
    covered &= set(seg["personas"])
    needed = min(len(seg["personas"]), 3)
    if not covered:
        return 0.0, None
    value = min(len(covered) / needed, 1.0)
    return value, f"buying committee: {', '.join(sorted(covered))}"


def tier_for(score: int, icp: dict) -> str:
    for tier, threshold in sorted(icp["scoring"]["tiers"].items(), key=lambda kv: -kv[1]):
        if score >= threshold:
            return tier
    return "D"


def score_account(account: dict, segment_key: str, icp: dict,
                  today: date | None = None) -> ScoreResult:
    seg = icp["segments"][segment_key]
    weights = icp["scoring"]["weights"]
    today = today or date.today()

    components = {
        "industry_match": _industry_score(account, seg),
        "keyword_match": _keyword_score(account, seg),
        "size_fit": _size_score(account, seg),
        "geography": _geo_score(account, icp),
        "signals": _signal_score(account, icp, today),
        "persona_coverage": _persona_score(account, seg),
    }
    breakdown = {k: round(weights[k] * v, 1) for k, (v, _) in components.items()}
    score = round(sum(breakdown.values()))
    reasons = [r for _, r in components.values() if r]
    return ScoreResult(score=score, tier=tier_for(score, icp),
                       breakdown=breakdown, reasons=reasons)
