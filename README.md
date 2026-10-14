# Cohesive Outbound Prospecting Agent

An outbound prospecting agent built on **Claude Code**, modeled on Salesforce's Hunter.
It works with the **ZoomInfo** and **HubSpot** connectors to find, qualify, score and
draft outreach for OEM accounts in Cohesive's three target markets:

| Segment | Sub-segments |
|---|---|
| **Data center** | CDU / liquid cooling · chillers / precision cooling · aisle containment / racks |
| **Medical** | wearable devices · advanced wound care |
| **Aerospace / satellite / defense** | satellite and space · defense electronics and avionics · aircraft and UAV |

The agent does the research and writes the drafts. **People review and send.** The agent
never emails anyone. HubSpot writes always need explicit approval.

## How a run works (`/hunt`)

```
icp.yaml ─► account-scout ─► crm-sync (dedupe) ─► score (free data) ─► enrich shortlist
            ZoomInfo free      HubSpot read        prospector          ZoomInfo signals
            searches                                process             (credit-capped)
                                                                            │
report.md ◄─ prospector process ◄─ outreach-writer ◄─ buying-committee-mapper
HubSpot CSVs   (final rank)        3-step drafts       eng · sourcing · quality · ops
      │
      └─► human review ─► crm-sync push to HubSpot (on approval) ─► prospector commit (ledger)
```

1. **Find accounts.** Free ZoomInfo `search_companies` runs with each sub-segment's keyword
   phrases, ZoomInfo industry ids, size band and geography. It also runs
   `find_similar_companies` to find look-alikes.
2. **Check HubSpot.** Accounts that already exist in HubSpot are dropped and reported with
   their owner and lifecycle stage. Accounts surfaced in the last 90 days are skipped.
3. **Score.** `prospector process` scores each account from 0 to 100 and assigns a tier.
   The score combines industry, keyword match, size, geography, dated trigger signals and
   buying-committee coverage. The weights are in `config/icp.yaml`. Scoring is code, not
   model judgment, so rankings are consistent from run to run.
4. **Enrich the shortlist.** The agent pulls scoops, news and intent for the shortlist, and
   redeems contacts for engineering, sourcing, quality and operations roles. It stays under
   `max_redeem_credits_per_run`.
5. **Draft.** The agent writes a 3-step email sequence and a LinkedIn note for each tier A
   and tier B account. Each draft opens with the account's dated trigger event. Drafts use
   only the claims in `playbooks/`.
6. **Hand off.** The agent produces `report.md`, `hubspot_companies.csv` and
   `hubspot_contacts.csv`, then pushes to HubSpot after you approve.

## Commands

| Command | What it does |
|---|---|
| `/hunt data_center` | A full prospecting pass for one segment (`medical`, `aerospace_defense`, or `all`) |
| `/hunt medical wearables 10` | Limit the pass to one sub-segment and a target count |
| `/account-brief coolcentric.com` | A deep-dive brief on one account: fit, triggers, buying committee, CRM history |
| `/signal-sweep all 30` | Free trigger-event sweep (expansions, launches, funding, hires) for the last 30 days |
| `scripts/run_headless.sh data_center` | Unattended run for cron or CI. HubSpot is read-only in this mode. |

## Setup

1. **Connectors.** In Claude (claude.ai or Claude Code on the web), connect **ZoomInfo** and
   **HubSpot** under Settings → Connectors. For the local CLI, copy `.mcp.json.example` to
   `.mcp.json`. Keep the server names `ZoomInfo` and `HubSpot`, because the permissions in
   `.claude/settings.json` use those names. Confirm the endpoint URLs with each vendor.
2. **HubSpot write scope.** Right now the HubSpot connector can **read** companies and
   contacts, but writes report `REQUIRES_REAUTHORIZATION`. To push approved prospects
   directly, reconnect HubSpot and grant CRM write scopes. Until then, every run writes
   import-ready CSVs. To import them in HubSpot, go to Import → two files with an
   association, and match on *Company Domain Name*.
3. **Optional HubSpot properties.** Create these company properties so the scoring fields
   land in the CRM: `Cohesive Segment`, `Cohesive Sub-Segment`, `Prospect Fit Score`,
   `Prospect Tier`, `Why Now`, `ZoomInfo Company ID`. On contacts, create `Buying Role` and
   `ZoomInfo Contact ID`.
4. **Python helpers.** Run `pip install -e '.[dev]'`, then `pytest`.
5. **Approved claims.** `playbooks/_company.md` holds the confirmed facts: certifications by
   site, 2-day prototypes on in-stock materials, equipment, in-house testing, the approved
   material partners, and the anonymous data center CDU reference story. It also holds the
   never-say list. Update that file when facts change. `prospector process` flags any
   draft containing a banned term (`config/icp.yaml → outreach_guardrails`) or a leftover
   `[CONFIRM` placeholder.

## Tuning

Everything sales ops needs to change is in `config/icp.yaml`:

- **`segments.*.sub_segments.*.description_keywords`**: ZoomInfo matches every word in a
  phrase, so short phrases of 1–3 words work best.
- **`segments.*.zoominfo`**: industry ids, employee range and sweet spot. Industry ids must
  come from ZoomInfo `lookup`. Guessed ids break searches.
- **`personas`**: the titles and management levels for each buying role.
- **`scoring.weights` and `tiers`**: the weights must sum to 100.
- **`run_defaults`**: accounts per run, contacts per account, the credit cap, and the
  minimum contact accuracy.
- **`exclusions`**: domains and competitors to skip.

Run `python -m prospector validate` after editing.

## What we found while building this (2026-10-14)

- **ZoomInfo tenant.** Its GTM context lists Cohesive's offerings: die-cut components,
  EMI/RFI shielding, seals and gaskets, molded parts, and thermal interface materials. It
  has no ICPs or personas configured, so this repo supplies them. Only 5 intent topics are
  configured on the tenant (Supplier Management, Global Procurement, Supply Chain
  Management, Quality Management, Inventory Management). Adding topics such as liquid
  cooling, wound care and EMI shielding in ZoomInfo would make intent signals much more
  useful.
- **Smoke run.** A free test run on data center returned 18 candidate OEMs. The HubSpot check
  correctly dropped CoolIT Systems (customer), Green Revolution Cooling (SQL) and Pfannenberg
  (opportunity) as already in the CRM. The remaining 15 were scored: 9 tier B and 6 tier C.
  They include Coolcentric, Accelsius, ZutaCore, Wakefield Thermal, Legacy Chiller Systems,
  Subzero Engineering and Tate. No credits were spent.

## Repo layout

```
CLAUDE.md                     agent operating rules (read by Claude every session)
config/icp.yaml               segments, ZoomInfo filters, personas, scoring, guardrails
.claude/skills/               /hunt, /account-brief, /signal-sweep workflows
.claude/agents/               account-scout, buying-committee-mapper, crm-sync, outreach-writer
.claude/settings.json         pre-approved read-only tools; HubSpot writes always ask
playbooks/                    per-segment messaging, proof points, discovery questions
prospector/                   deterministic scoring, dedupe, HubSpot CSV export, ledger
scripts/run_headless.sh       scheduled, unattended runs
output/                       run folders, briefs, signal reports (gitignored: contains PII)
```
