---
name: hunt
description: Run an outbound prospecting pass for a Cohesive target segment (data_center, medical, aerospace_defense). Finds ICP accounts in ZoomInfo, checks them against HubSpot, scores and tiers them, maps the buying committee, and drafts outreach for human review. Use when asked to prospect, hunt, build a target list, or find new accounts in Cohesive's markets.
argument-hint: <segment|all> [sub_segment] [accounts_per_segment]
---

# /hunt: outbound prospecting pass

Arguments: `$ARGUMENTS`. Parse them as `segment` (required: `data_center`, `medical`,
`aerospace_defense`, or `all`), an optional `sub_segment` key, and an optional account count.
The count defaults to `run_defaults.accounts_per_segment`. If no segment is given, ask for one.
For `all`, run the steps below once per segment, each with its own run folder.

## 0. Set up

1. Read `config/icp.yaml` and `playbooks/<segment>.md`.
2. Run `python -m prospector validate`.
3. Create the run folder `output/runs/<today>-<segment>[-<sub_segment>]/` and write `meta.json`.
4. Call ZoomInfo `get_gtm_context` once to confirm the tenant's offerings. Call HubSpot
   `get_user_details` to see whether COMPANY and CONTACT writes are `AVAILABLE`. Write that
   status to `meta.json` as `hubspot_write`.

## 1. Find accounts (free): use the `account-scout` subagent

Give the scout the segment block from icp.yaml and the target count. For each sub-segment,
the scout runs `search_companies` (free, no `redeem`) once per `description_keywords` entry:

- `companyDescription`: the keyword phrase. Short phrases of 1–3 words work best, because
  every word must match.
- `industryList`: the segment's `zoominfo.industry_ids`. If a keyword returns fewer than 5
  results, run it again without `industryList`, because niche OEMs are often misclassified.
- `country`: `run_defaults.default_countries`, joined with commas.
- `employeeRangeMinimum` and `employeeRangeMaximum`: the segment's `employee_min` and `employee_max`.
- `pageSize` 25, `underManagement: true`.

The scout merges results by ZoomInfo id. For each account it records `sub_segment` and every
`matched_keywords` phrase that found it. Aim for about 3× the target count before scoring.

## 2. Check HubSpot first: use the `crm-sync` subagent (read only)

For each candidate domain, search HubSpot COMPANY on `domain`. Batch the domains with the `IN`
operator, up to 100 values per filter. Then run the **name-token check** described in
`crm-sync.md`. On the first live run, the domain filter alone missed 3 of the 15 accounts that
were already in the CRM. Write every matching domain to `crm_domains.json`. Also record each
match's `lifecyclestage` and `hs_lead_status`. Include those in the final summary as
"already in CRM".

If research rules an account out (it's a contractor or operator rather than an OEM, its
parent is already a customer, or its HQ and engineering are outside the territory), set
`disqualify_reason` on the account in `accounts.json`. Do not delete it. `process` lists it
under Dropped with the reason.

## 3. First scoring pass (free data)

Write the candidates to `accounts.json` and run `python -m prospector process <run_dir>`.
The free search fields alone (industry, keyword match, size, geography) are enough for a
provisional score. Take the top accounts that score at least `min_fit_score_to_enrich`, up to
the target count.

## 4. Enrich the shortlist (costs credits, within the budget)

For the shortlist only:

1. Call `enrich_company_signals` in batches of 10 ids with `signalTypes: ["SCOOP", "NEWS"]`
   to get trigger events. Read every signal before using it:
   - Count one event once, even when several outlets cover it.
   - Drop name collisions. For example, "Wright Line" is also an NLRB legal doctrine.
   - Treat negative news (cost cuts, layoffs) as context for the angle, not as a buying trigger.
   - Watch for ownership changes, such as an acquisition by an existing customer.
   - Add each scoop or news item from the last `scoring.signal_lookback_days` to the account's
     `signals` list as `{type, title, date, url}`.
2. Optionally, call `search_intent` with `signals.intent_topics` (free) and add any matches with
   a score of 70 or higher as `{type: "intent", topic, score, date}`.
3. Call `enrich_companies`, or use `search_companies` with `redeem: true`, only for accounts
   where the description is needed to confirm fit and that are under management, or while the
   credit budget allows. Store the result in `description`.
4. Increase `meta.json.credits_used` after each paid call. Stop enriching when the cap is reached.

## 5. Map the buying committee: use the `buying-committee-mapper` subagent

For each shortlisted account, find up to `contacts_per_account` people across the segment's
`personas`. Search contacts for free first. Redeem contacts only for the final shortlist, and
only for contacts with `hasEmail` set, within the credit budget. Tag each contact with its
`persona` key.

## 6. Final score, draft and review

1. Update `accounts.json` with the signals, descriptions and contacts. Write a one-line
   `why_now` for each account that cites the strongest dated signal.
2. Run `python -m prospector process <run_dir>` again.
3. Use the `outreach-writer` subagent to draft a 3-step sequence for each tier A and tier B
   account. The writer saves the drafts to `outreach.json`. Then run `process` one more time,
   which merges the drafts into `scored.json` and `report.md`.

## 7. Hand off

Run `node scripts/report_docx.js <run_dir>` to build `report.docx`, the Word review copy with approve/edit/reject boxes under every draft. Send that file to the user along with the CSVs.

Show the user:

- The ranked table from `report.md`: account, sub-segment, score, tier, why now.
- The number of credits used and the budget.
- How many accounts were dropped, grouped by reason (already in HubSpot, cooldown, low score).
- The paths to `report.md`, `hubspot_companies.csv` and `hubspot_contacts.csv`.

Then ask whether to push the approved accounts to HubSpot.

- If HubSpot writes are available, use `crm-sync` to create the companies and contacts and
  associate each contact with its company. Show the confirmation table first and wait for
  approval.
- If writes are not available, tell the user to either reauthorize the HubSpot connector with
  write scopes, or import the two CSVs manually (Contacts → Import → two files with an
  association, matched on "Company Domain Name").

After the user approves, run `python -m prospector commit <run_dir>`.
