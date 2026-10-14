---
name: account-brief
description: Deep-dive research brief on one named target account for Cohesive (fit, product lines that use gaskets/TIMs/EMI/die-cuts, trigger events, buying committee, HubSpot history, suggested opener). Use when a rep asks to research, brief, or prep for a specific company.
argument-hint: <company name or domain>
---

# /account-brief

Target: `$ARGUMENTS`

1. Read `config/icp.yaml`. Find the company with ZoomInfo `search_companies` (`companyName`
   or `companyWebsite`). If more than one company matches, confirm which one with the user.
2. Call `account_research` on the company for a narrative overview. Call
   `enrich_company_signals` (SCOOP, NEWS, INTENT) to get dated trigger events. This costs
   credits only if the company is not under management, so mention that before running it.
3. Classify the company into a segment and sub-segment from icp.yaml. Explain why it fits.
   If it fits none, say so plainly.
4. Pick the 2–4 product lines most likely to use Cohesive components, with the specific
   applications (from the sub-segment's `applications`).
5. Use the `buying-committee-mapper` subagent to map the contacts. Search only; do not redeem
   unless the user asks.
6. Use HubSpot `search_crm_objects` to find the existing company, contacts, deals and owner.
   Summarize the history.
7. Write `output/briefs/<domain>.md` with these sections: Snapshot · Why Cohesive fits ·
   Trigger events (dated, with sources) · Buying committee · CRM history · Suggested opener ·
   Open questions. Then score the account. Write a one-account `accounts.json` to a temp run
   folder and run `python -m prospector process` on it. Include the score and tier in the brief.
