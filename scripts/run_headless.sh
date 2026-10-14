#!/usr/bin/env bash
# Unattended prospecting run, e.g. from cron or a CI schedule:
#   scripts/run_headless.sh data_center
#   scripts/run_headless.sh medical wearables 10
#
# Runs /hunt with read-only HubSpot access: the run researches, scores, drafts
# and stages CSVs, but cannot write to HubSpot (manage_crm_objects is not
# allowed). A human reviews output/runs/<run>/report.md and pushes approved
# accounts from an interactive session.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <segment|all> [sub_segment] [count]" >&2
  exit 2
fi

ALLOWED_TOOLS=(
  Read Write Edit Glob Grep Agent Skill
  "Bash(python3 -m prospector:*)" "Bash(python -m prospector:*)" "Bash(mkdir:*)"
  mcp__ZoomInfo__lookup mcp__ZoomInfo__get_gtm_context
  mcp__ZoomInfo__search_companies mcp__ZoomInfo__search_contacts
  mcp__ZoomInfo__search_scoops mcp__ZoomInfo__search_intent
  mcp__ZoomInfo__find_similar_companies mcp__ZoomInfo__get_recommended_contacts
  mcp__ZoomInfo__account_research
  mcp__ZoomInfo__enrich_company_signals mcp__ZoomInfo__enrich_companies
  mcp__ZoomInfo__enrich_contacts
  mcp__HubSpot__get_user_details mcp__HubSpot__search_crm_objects
  mcp__HubSpot__search_properties
)

claude -p "/hunt $* — this is an unattended run: do not ask questions, skip the HubSpot push step, and finish by printing the report summary." \
  --allowedTools "${ALLOWED_TOOLS[@]}" \
  --output-format text
