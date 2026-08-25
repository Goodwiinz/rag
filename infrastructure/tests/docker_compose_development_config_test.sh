#!/usr/bin/env bash
#
# Focused configuration assertions for the local development Compose file
# (R6-M12).  The root compose path is a symlink to the tracked config file;
# inspect service environment blocks rather than command interpolation so the
# Celery worker's shell-level WORKER_CONCURRENCY remains valid.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.development.yml"

docker compose -f "${COMPOSE_FILE}" config --quiet

service_environment() {
  local service="$1"
  awk -v service="${service}" '
    $0 == "  " service ":" { in_service = 1; next }
    in_service && $0 ~ /^  [[:alnum:]_-]+:/ { exit }
    in_service && $0 == "    environment:" { in_environment = 1; next }
    in_service && in_environment && $0 ~ /^    [[:alnum:]_-]+:/ { exit }
    in_service && in_environment { print }
  ' "${COMPOSE_FILE}"
}

backend_env="$(service_environment backend)"
worker_env="$(service_environment celery-worker)"

assert_contains() {
  local haystack="$1"
  local needle="$2"
  if ! grep -Fq -- "${needle}" <<<"${haystack}"; then
    echo "missing Compose environment entry: ${needle}" >&2
    exit 1
  fi
}

assert_not_contains() {
  local haystack="$1"
  local needle="$2"
  if grep -Fq -- "${needle}" <<<"${haystack}"; then
    echo "dead Compose environment entry remains: ${needle}" >&2
    exit 1
  fi
}

assert_contains "${backend_env}" '- MAX_FILE_SIZE_MB=${MAX_FILE_SIZE_MB:-100}'
assert_contains "${backend_env}" '- LLM_CACHE_ENABLED=${LLM_CACHE_ENABLED:-true}'
assert_contains "${backend_env}" '- LLM_CACHE_TTL_SECONDS=${LLM_CACHE_TTL_SECONDS:-3600}'
assert_contains "${worker_env}" '- LLM_CACHE_ENABLED=${LLM_CACHE_ENABLED:-true}'
assert_contains "${worker_env}" '- LLM_CACHE_TTL_SECONDS=${LLM_CACHE_TTL_SECONDS:-3600}'

for dead_entry in \
  '- MAX_FILE_SIZE=' \
  '- ENABLE_VIRUS_SCANNING=' \
  '- ENABLE_AI_PROCESSING=' \
  '- ENABLE_CACHING=' \
  '- CACHE_TTL_SECONDS=' \
  '- WORKER_CONCURRENCY=' \
  '- API_RATE_LIMIT='; do
  assert_not_contains "${backend_env}" "${dead_entry}"
done

echo "docker-compose development config test: PASSED"
