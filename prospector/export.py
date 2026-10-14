"""Write HubSpot-ready import files and a human-readable run report."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

COMPANY_COLUMNS = [
    ("Company name", "name"),
    ("Company Domain Name", "domain"),
    ("City", "city"),
    ("State/Region", "state"),
    ("Country/Region", "country"),
    ("Number of Employees", "employee_count"),
    ("Annual Revenue", "revenue"),
    ("Lead Status", None),          # filled with "NEW"
    ("Lifecycle Stage", None),      # filled with "lead"
    ("Cohesive Segment", "segment_label"),
    ("Cohesive Sub-Segment", "sub_segment_label"),
    ("Prospect Fit Score", "score"),
    ("Prospect Tier", "tier"),
    ("Why Now", "why_now"),
    ("ZoomInfo Company ID", "zoominfo_id"),
]

CONTACT_COLUMNS = [
    ("First Name", "first_name"),
    ("Last Name", "last_name"),
    ("Job Title", "title"),
    ("Email", "email"),
    ("Phone Number", "phone"),
    ("LinkedIn URL", "linkedin"),
    ("Company Domain Name", "company_domain"),
    ("Company Name", "company_name"),
    ("Buying Role", "persona_label"),
    ("Lead Status", None),
    ("Lifecycle Stage", None),
    ("ZoomInfo Contact ID", "zoominfo_person_id"),
]

_FIXED = {"Lead Status": "NEW", "Lifecycle Stage": "lead"}


def _row(columns, record: dict[str, Any]) -> dict[str, Any]:
    return {header: (_FIXED.get(header, "") if key is None else record.get(key, ""))
            for header, key in columns}


def write_hubspot_csvs(accounts: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    companies_path = out_dir / "hubspot_companies.csv"
    contacts_path = out_dir / "hubspot_contacts.csv"

    with open(companies_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[h for h, _ in COMPANY_COLUMNS])
        writer.writeheader()
        for acct in accounts:
            writer.writerow(_row(COMPANY_COLUMNS, acct))

    with open(contacts_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[h for h, _ in CONTACT_COLUMNS])
        writer.writeheader()
        for acct in accounts:
            for contact in acct.get("contacts") or []:
                record = {**contact, "company_domain": acct.get("domain", ""),
                          "company_name": acct.get("name", "")}
                writer.writerow(_row(CONTACT_COLUMNS, record))
    return companies_path, contacts_path


def write_report(accounts: list[dict], dropped: list[dict], meta: dict[str, Any],
                 out_dir: Path) -> Path:
    lines = [
        f"# Prospecting run — {meta.get('segment_label', '')}",
        "",
        f"- Run date: {meta.get('run_date', '')}",
        f"- Accounts surfaced: {len(accounts)} (dropped {len(dropped)})",
        f"- ZoomInfo credits used: {meta.get('credits_used', 'n/a')}",
        "",
    ]
    flagged = [a for a in accounts if a.get("draft_issues")]
    if flagged:
        lines += ["## ⚠ Draft issues — fix before sending", ""]
        for a in flagged:
            for issue in a["draft_issues"]:
                lines.append(f"- {a.get('name', '')}: {issue}")
        lines.append("")
    lines += [
        "| # | Account | Sub-segment | Employees | Score | Tier | Why now |",
        "|---|---------|-------------|-----------|-------|------|---------|",
    ]
    for i, a in enumerate(accounts, 1):
        lines.append(
            f"| {i} | {a.get('name', '')} ({a.get('domain', '')}) | {a.get('sub_segment_label', '')} "
            f"| {a.get('employee_count') or '—'} | {a.get('score', '')} | {a.get('tier', '')} "
            f"| {a.get('why_now', '') or '—'} |"
        )

    for a in accounts:
        lines += ["", f"## {a.get('name', '')} — Tier {a.get('tier', '')} ({a.get('score', '')})", ""]
        for reason in a.get("reasons") or []:
            lines.append(f"- {reason}")
        if a.get("applications"):
            lines.append(f"- Likely applications: {', '.join(a['applications'])}")
        contacts = a.get("contacts") or []
        if contacts:
            lines += ["", "**Buying committee**", ""]
            for c in contacts:
                lines.append(f"- {c.get('first_name', '')} {c.get('last_name', '')}, "
                             f"{c.get('title', '')} — {c.get('persona_label', c.get('persona', ''))}")
        for draft in a.get("outreach") or []:
            lines += ["", f"**Draft — {draft.get('to', '')} (step {draft.get('step', 1)})**", "",
                      f"Subject: {draft.get('subject', '')}", "", draft.get("body", "")]

    if dropped:
        lines += ["", "## Dropped", ""]
        for d in dropped:
            lines.append(f"- {d.get('name', '')} ({d.get('website', '')}): {d.get('drop_reason', '')}")

    path = out_dir / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
