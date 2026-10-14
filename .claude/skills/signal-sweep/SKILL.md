---
name: signal-sweep
description: Sweep ZoomInfo scoops for fresh trigger events (plant expansions, product launches, funding, new engineering/sourcing leaders) across Cohesive's target segments and return a dated "why now" list. Free to run. Use for weekly signal reviews or when asked what's happening in a market.
argument-hint: [segment|all] [days=30]
---

# /signal-sweep

Arguments: `$ARGUMENTS`. The segment defaults to `all`. The lookback defaults to 30 days.

1. Read `config/icp.yaml`. For each segment:
   - Call `search_scoops` (free) with:
     - `publishedStartDate` set to today minus the lookback.
     - `industryCodes`: the segment's `zoominfo.industry_ids`.
     - `scoopTypes`: from `signals.scoop_types`.
     - `country`: the default countries.
     - `employeeRangeMin` and `employeeRangeMax`: the segment's range.
     - `pageSize: 50`.
   - Run a second pass with `scoopTopics` mapped from the segment's `scoop_topic_keys` through
     `signals.scoop_topic_ids`.
   - Keep only scoops whose company description or scoop text is plausibly about the segment's
     products. Check against the sub-segment keywords.
2. Call `search_intent` (free) with `signals.intent_topics`, `signalScoreMin: 75`, and the
   segment's industries and country. Cross-reference the results with the scoops. A company
   with both a scoop and an intent signal goes to the top of the list.
3. Run a read-only check in HubSpot for the matched domains (use the `crm-sync` subagent).
   Label each company "net-new" or "in CRM (owner, stage)".
4. Write `output/signals/<today>.md`. Include a table per segment: Company · Event · Date ·
   Source link · Net-new or CRM · Suggested action. Return the top 10 across segments in chat.
   Offer to run `/hunt` with the net-new companies as seeds.
