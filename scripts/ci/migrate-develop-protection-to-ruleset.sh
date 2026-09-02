#!/usr/bin/env bash
# Move develop's required status checks from classic branch protection into a
# repository ruleset, so the Claude GitHub App can be a bypass actor.
#
# Why: the Release Dev workflow pushes a "[skip ci]" gitops bump straight to
# develop. That push reports no status checks, so classic protection rejects it
# with "GH006 ... 11 of 11 required status checks are expected". Classic
# protection can only exempt users/teams/apps via `restrictions` (push allow
# list), which does not waive required checks, and has no bypass list for apps
# at all. Rulesets do -- an Integration bypass actor skips the ruleset's rules
# entirely -- so the checks have to live in a ruleset instead.
#
# Idempotent: re-running updates the existing ruleset in place. Dry run by
# default; pass --apply to mutate.
#
# Usage:
#   CLAUDE_APP_ID=<app id> scripts/ci/migrate-develop-protection-to-ruleset.sh [--apply]
#   scripts/ci/migrate-develop-protection-to-ruleset.sh <app id> [--apply]
set -euo pipefail

REPO="${REPO:-Goodwiinz/rag}"
BRANCH="develop"
RULESET_NAME="develop required checks"
# GitHub Actions' app id -- the checks are all reported by Actions.
ACTIONS_APP_ID=15368

APPLY=0
APP_ID="${CLAUDE_APP_ID:-}"
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    [0-9]*) APP_ID="$arg" ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [ -z "$APP_ID" ]; then
  echo "error: app id required (set CLAUDE_APP_ID or pass it as an argument)" >&2
  echo "       find it at https://github.com/settings/apps/<slug> -> App ID" >&2
  exit 2
fi

CONTEXTS=(
  "Lint Backend"
  "Lint Frontend"
  "Unit Tests"
  "Frontend Tests"
  "Alembic Migration Check"
  "Golden Replay"
  "OpenAPI Contract Ratchet"
  "Security Scan"
  "Gitleaks"
  "Integration Tests"
  "Resilience Tests"
)

checks_json="$(printf '%s\n' "${CONTEXTS[@]}" |
  jq -R -s --argjson app "$ACTIONS_APP_ID" \
    'split("\n") | map(select(length > 0) | {context: ., integration_id: $app})')"

payload="$(jq -n \
  --arg name "$RULESET_NAME" \
  --arg ref "refs/heads/$BRANCH" \
  --argjson app_id "$APP_ID" \
  --argjson checks "$checks_json" \
  '{
    name: $name,
    target: "branch",
    enforcement: "active",
    bypass_actors: [
      {actor_id: $app_id, actor_type: "Integration", bypass_mode: "always"}
    ],
    conditions: {ref_name: {include: [$ref], exclude: []}},
    rules: [
      {
        type: "required_status_checks",
        parameters: {
          strict_required_status_checks_policy: false,
          required_status_checks: $checks
        }
      }
    ]
  }')"

existing_id="$(gh api "repos/$REPO/rulesets" |
  jq -r --arg name "$RULESET_NAME" 'map(select(.name == $name)) | .[0].id // empty')"

if [ -n "$existing_id" ]; then
  method=PUT
  endpoint="repos/$REPO/rulesets/$existing_id"
else
  method=POST
  endpoint="repos/$REPO/rulesets"
fi

echo "repo:            $REPO"
echo "bypass actor:    Integration app id $APP_ID (bypass_mode: always)"
echo "ruleset:         $method /$endpoint"
echo "$payload" | jq .
echo
echo "then: DELETE /repos/$REPO/branches/$BRANCH/protection/required_status_checks"

if [ "$APPLY" -ne 1 ]; then
  echo
  echo "dry run -- nothing changed. Re-run with --apply to migrate."
  exit 0
fi

echo
echo ">> writing ruleset"
echo "$payload" | gh api --method "$method" "$endpoint" --input - >/dev/null
echo ">> removing required_status_checks from classic protection"
gh api --method DELETE "repos/$REPO/branches/$BRANCH/protection/required_status_checks"
echo ">> done. Verify: gh api repos/$REPO/branches/$BRANCH/protection"
