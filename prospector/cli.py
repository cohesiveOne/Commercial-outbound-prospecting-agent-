"""Command line entry point used by the agent between research steps.

    python -m prospector validate
    python -m prospector process output/runs/2026-10-14-data_center
    python -m prospector commit  output/runs/2026-10-14-data_center
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .dedupe import dedupe_accounts, load_ledger, save_ledger
from .export import write_hubspot_csvs, write_report
from .guardrails import check_drafts
from .icp import get_segment, load_icp
from .scoring import score_account


def _read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def cmd_validate(args) -> int:
    icp = load_icp(args.icp)
    print(f"icp.yaml OK — segments: {', '.join(icp['segments'])}")
    return 0


def cmd_process(args) -> int:
    """Score, dedupe, rank and export a run directory.

    Reads   <run>/accounts.json      (list of raw accounts, see scoring.py)
            <run>/meta.json          ({"segment": "data_center", ...})
            <run>/crm_domains.json   (optional: domains already in HubSpot)
            <run>/outreach.json      (optional: {domain: [draft, ...]} from outreach-writer)
    Writes  <run>/scored.json, dropped.json, hubspot_*.csv, report.md
    """
    icp = load_icp(args.icp)
    run = Path(args.run_dir)
    meta = _read_json(run / "meta.json", {})
    segment_key = args.segment or meta.get("segment")
    if not segment_key:
        print("segment missing: pass --segment or set it in meta.json", file=sys.stderr)
        return 2
    seg = get_segment(icp, segment_key)
    accounts = _read_json(run / "accounts.json", [])
    crm_domains = _read_json(run / "crm_domains.json", [])

    keep, dropped = dedupe_accounts(
        accounts,
        crm_domains=crm_domains,
        excluded_domains=icp.get("exclusions", {}).get("domains") or [],
        ledger=load_ledger(),
        cooldown_days=args.cooldown_days,
    )

    outreach = _read_json(run / "outreach.json", {})
    personas = icp["personas"]
    for acct in keep:
        if acct.get("domain") in outreach:
            acct["outreach"] = outreach[acct["domain"]]
            acct["draft_issues"] = check_drafts(acct["outreach"], icp)
        result = score_account(acct, segment_key, icp)
        sub = seg["sub_segments"].get(acct.get("sub_segment") or "", {})
        acct.update(result.as_dict())
        acct["segment"] = segment_key
        acct["segment_label"] = seg["label"]
        acct["sub_segment_label"] = sub.get("label", "")
        acct.setdefault("applications", sub.get("applications", []))
        for c in acct.get("contacts") or []:
            c.setdefault("persona_label", personas.get(c.get("persona"), {}).get("label", ""))

    keep.sort(key=lambda a: a["score"], reverse=True)
    min_tier_score = icp["scoring"]["tiers"]["C"]
    below = [a | {"drop_reason": f"score {a['score']} below tier C"} for a in keep
             if a["score"] < min_tier_score]
    keep = [a for a in keep if a["score"] >= min_tier_score]
    dropped += below

    meta = {**meta, "segment": segment_key, "segment_label": seg["label"],
            "run_date": meta.get("run_date") or date.today().isoformat()}
    (run / "scored.json").write_text(json.dumps(keep, indent=2), encoding="utf-8")
    (run / "dropped.json").write_text(json.dumps(dropped, indent=2), encoding="utf-8")
    write_hubspot_csvs(keep, run)
    report = write_report(keep, dropped, meta, run)

    tiers = {t: sum(1 for a in keep if a["tier"] == t) for t in ("A", "B", "C")}
    draft_issues = sum(len(a.get("draft_issues") or []) for a in keep)
    print(json.dumps({"kept": len(keep), "dropped": len(dropped), "tiers": tiers,
                      "draft_issues": draft_issues, "report": str(report)}, indent=2))
    return 0


def cmd_commit(args) -> int:
    """Record surfaced accounts in the ledger so later runs skip them."""
    run = Path(args.run_dir)
    scored = _read_json(run / "scored.json", [])
    ledger = load_ledger()
    today = date.today().isoformat()
    for acct in scored:
        if acct.get("domain"):
            ledger[acct["domain"]] = today
    save_ledger(ledger)
    print(f"ledger updated with {len(scored)} accounts")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prospector")
    parser.add_argument("--icp", help="path to icp.yaml (default: config/icp.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="validate config/icp.yaml").set_defaults(func=cmd_validate)

    p = sub.add_parser("process", help="score, dedupe and export a run directory")
    p.add_argument("run_dir")
    p.add_argument("--segment")
    p.add_argument("--cooldown-days", type=int, default=90)
    p.set_defaults(func=cmd_process)

    c = sub.add_parser("commit", help="add a run's accounts to the ledger")
    c.add_argument("run_dir")
    c.set_defaults(func=cmd_commit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
