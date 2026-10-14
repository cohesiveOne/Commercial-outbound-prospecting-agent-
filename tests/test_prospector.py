import csv
import json
from datetime import date

import pytest

from prospector import cli
from prospector.dedupe import dedupe_accounts
from prospector.domains import normalize_domain
from prospector.icp import ICPError, load_icp, validate_icp
from prospector.scoring import score_account

TODAY = date(2026, 10, 14)


@pytest.fixture(scope="module")
def icp():
    return load_icp()


def strong_cdu_account():
    return {
        "zoominfo_id": "346021735",
        "name": "Coolcentric",
        "website": "www.coolcentric.com",
        "employee_count": "569",
        "country": "United States",
        "industries": ["mfg.industrialmachinery"],
        "description": "Maker of rear-door heat exchangers and coolant distribution units.",
        "sub_segment": "cdu",
        "signals": [
            {"type": "scoop", "title": "Opening new plant in NC", "date": "2026-09-20"},
            {"type": "scoop", "title": "Launches 1MW CDU", "date": "2026-08-02"},
            {"type": "news", "title": "Old news", "date": "2024-01-01"},
        ],
        "contacts": [{"persona": "engineering"}, {"persona": "sourcing"},
                     {"persona": "operations"}],
    }


@pytest.mark.parametrize("raw,expected", [
    ("https://www.Acme.com/about", "acme.com"),
    ("www.acme.com", "acme.com"),
    ("acme.co.uk", "acme.co.uk"),
    ("", ""),
    (None, ""),
])
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


def test_icp_loads_and_segments_present(icp):
    assert set(icp["segments"]) == {"data_center", "medical", "aerospace_defense"}
    assert set(icp["segments"]["data_center"]["sub_segments"]) == {"cdu", "chillers", "aisle_containment"}
    assert set(icp["segments"]["medical"]["sub_segments"]) == {"wearables", "wound_care"}


def test_validate_rejects_bad_weights(icp):
    bad = json.loads(json.dumps(icp))
    bad["scoring"]["weights"]["signals"] = 50
    with pytest.raises(ICPError):
        validate_icp(bad)


def test_validate_rejects_unknown_persona(icp):
    bad = json.loads(json.dumps(icp))
    bad["segments"]["medical"]["personas"].append("astronaut")
    with pytest.raises(ICPError):
        validate_icp(bad)


def test_strong_account_scores_tier_a(icp):
    result = score_account(strong_cdu_account(), "data_center", icp, today=TODAY)
    assert result.tier == "A"
    assert result.breakdown["signals"] == pytest.approx(15.0)  # 2 recent signals; stale one ignored
    assert any("coolant distribution" in r for r in result.reasons)


def test_sparse_account_scores_low(icp):
    acct = {"name": "Unknown Co", "country": "Germany", "employee_count": 5}
    result = score_account(acct, "medical", icp, today=TODAY)
    assert result.score < icp["scoring"]["tiers"]["C"]
    assert result.tier == "D"


def test_keyword_search_credit_without_description(icp):
    acct = {"name": "X", "matched_keywords": ["wound dressings"]}
    result = score_account(acct, "medical", icp, today=TODAY)
    assert result.breakdown["keyword_match"] == pytest.approx(25 * 0.7)


def test_unknown_industry_gets_partial_credit_but_mismatch_gets_none(icp):
    unknown = score_account({"name": "X"}, "data_center", icp, today=TODAY)
    mismatch = score_account({"name": "X", "industries": ["retail.sports"]}, "data_center",
                             icp, today=TODAY)
    assert unknown.breakdown["industry_match"] == pytest.approx(12.5)
    assert mismatch.breakdown["industry_match"] == 0


def test_low_intent_signal_ignored(icp):
    acct = {"name": "X", "signals": [{"type": "intent", "score": 62, "date": "2026-10-01"}]}
    assert score_account(acct, "medical", icp, today=TODAY).breakdown["signals"] == 0


def test_dedupe_drops_crm_excluded_dupes_and_cooldown():
    accounts = [
        {"name": "A", "website": "https://www.a.com"},
        {"name": "A again", "website": "a.com"},
        {"name": "B", "website": "b.com"},
        {"name": "C", "website": "c.com"},
        {"name": "D", "website": "d.com"},
        {"name": "E", "website": "e.com"},
    ]
    keep, dropped = dedupe_accounts(
        accounts, crm_domains=["www.b.com"], excluded_domains=["c.com"],
        ledger={"d.com": "2026-09-01", "e.com": "2025-01-01"}, today=TODAY)
    assert [a["name"] for a in keep] == ["A", "E"]
    reasons = {d["name"]: d["drop_reason"] for d in dropped}
    assert reasons["A again"] == "duplicate in run"
    assert reasons["B"] == "already in HubSpot"
    assert reasons["C"] == "excluded domain"
    assert "cooldown" in reasons["D"]


def test_process_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_ledger", lambda: {})
    weak = {"name": "Tiny", "website": "tiny.io", "employee_count": 3, "country": "Peru"}
    strong = strong_cdu_account()
    strong["contacts"][0].update({"first_name": "Dana", "last_name": "Lee",
                                  "title": "Mechanical Engineer", "email": "dana@coolcentric.com"})
    (tmp_path / "accounts.json").write_text(json.dumps([weak, strong]))
    (tmp_path / "meta.json").write_text(json.dumps({"segment": "data_center"}))
    (tmp_path / "crm_domains.json").write_text("[]")
    (tmp_path / "outreach.json").write_text(json.dumps({"coolcentric.com": [
        {"step": 1, "to": "Dana", "subject": "CDU manifold seals", "body": "Hi {{first_name}}"}]}))

    assert cli.main(["process", str(tmp_path)]) == 0

    scored = json.loads((tmp_path / "scored.json").read_text())
    assert [a["name"] for a in scored] == ["Coolcentric"]
    assert scored[0]["sub_segment_label"].startswith("Coolant Distribution")
    with open(tmp_path / "hubspot_contacts.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["Email"] == "dana@coolcentric.com"
    assert rows[0]["Buying Role"] == "Design / Mechanical Engineering"
    assert rows[0]["Company Domain Name"] == "coolcentric.com"
    report = (tmp_path / "report.md").read_text()
    assert "Coolcentric" in report and "Tiny" in report  # Tiny listed under Dropped
    assert scored[0]["outreach"][0]["subject"] == "CDU manifold seals"
    assert "Subject: CDU manifold seals" in report
