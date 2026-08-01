#!/usr/bin/env bash
# Run the BLOCKING gates from .github/workflows/test-pipeline.yml across the
# whole branch, before pushing.
#
# This is NOT a replacement for .pre-commit-config.yaml, which already runs the
# same pinned ruff/black/isort (plus eslint and gitleaks) on *staged* files.
# The gap this fills: pre-commit only sees what you are committing right now,
# so a file formatted in an earlier commit and edited later slips through --
# which is exactly how Lint Backend fails on an otherwise clean branch. This
# ratchets every changed file against the base branch, the way CI does, and
# adds the blocking gates pre-commit does not run at all: full-tree ruff, the
# directory-docs lint, mypy on added files, the alembic head check, the
# API-contract gates (OpenAPI snapshot + generated TS types), the
# alembic upgrade-from-empty probe, and the unit suite.
#
# The three contract gates, and when each one runs:
#   * OpenAPI snapshot drift        — ALWAYS (offline: in-memory SQLite + placeholder env)
#   * generated frontend TS types   — only when backend/openapi.json or
#                                     frontend/src/types/generated/ changed
#   * alembic upgrade from empty DB — only when backend/alembic/versions/ changed
# A conditional gate that cannot run is reported as SKIPPED, never as a pass:
# the summary line lists skips separately so "not verified" never reads green.
#
# It cannot replace CodeQL, or the Integration/E2E/Golden Replay jobs that need
# live Postgres/Redis services.
#
# Usage:  scripts/ci/run_local_ci.sh [--base origin/develop] [--skip-tests] [--frontend]
#
# Match CI's pinned linters or results will not agree:
#   pip install ruff==0.15.15 black==26.5.1 isort==5.13.2 mypy==1.7.1
set -uo pipefail

BASE="origin/develop"
SKIP_TESTS=0
DO_FRONTEND=0
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2;;
    --skip-tests) SKIP_TESTS=1; shift;;
    --frontend) DO_FRONTEND=1; shift;;
    *) echo "unknown arg: $1"; exit 2;;
  esac
done

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
PY="${PYTHON:-python3}"
FAILED=()
SKIPPED=()
MERGE_BASE=""
step() { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }
check() { if [ "$1" -ne 0 ]; then FAILED+=("$2"); printf '\033[31m  ✗ %s\033[0m\n' "$2"; else printf '\033[32m  ✓ %s\033[0m\n' "$2"; fi; }
# A gate that could not run. Recorded separately from FAILED so it never reads
# as a pass, and never turns the run red either (exit code is unchanged).
skipped() { SKIPPED+=("$1"); printf '\033[33m  ⊘ %s — SKIPPED (%s)\033[0m\n' "$1" "$2"; }
warn() { printf '\033[33m%s\033[0m\n' "$1"; }

# Paths changed since merge-base(BASE, HEAD), the same window
# scripts/ci/changed_source_files.py uses: committed + staged + unstaged, plus
# untracked files (a brand-new migration or a freshly generated api.d.ts is
# untracked until `git add`, and a trigger that misses it would silently skip
# the gate it is meant to arm). Prints "<unresolved-base>" when the base does
# not resolve, so conditional gates fire instead of quietly passing.
changed_paths() {
  if [ -z "$MERGE_BASE" ]; then echo "<unresolved-base>"; return 0; fi
  {
    git diff --name-only "$MERGE_BASE" -- "$@"
    git ls-files --others --exclude-standard -- "$@"
  } | sort -u
}

step "Ruff (full tree, blocking)"
ruff check backend/src; check $? "ruff backend/src"

step "Directory docs lint (blocking)"
$PY scripts/docs/check_dir_docs.py; check $? "check_dir_docs"

step "Changed-file quality ratchet (blocking) — base=$BASE"
if ! MERGE_BASE="$(git merge-base "$BASE" HEAD 2>/dev/null)"; then
  MERGE_BASE=""
  printf '\033[31m  ✗ cannot resolve merge-base(%s, HEAD) — conditional gates below will run unconditionally\033[0m\n' "$BASE"
  FAILED+=("merge-base $BASE")
fi
mapfile -t FILES < <($PY scripts/ci/changed_source_files.py --base "$BASE" --kind python)
if [ "${#FILES[@]}" -eq 0 ]; then
  echo "  no changed Python files"
else
  printf '  %d changed file(s)\n' "${#FILES[@]}"
  ruff check "${FILES[@]}";        check $? "ruff (changed)"
  black --check "${FILES[@]}";     check $? "black (changed)"
  isort --check-only "${FILES[@]}"; check $? "isort (changed)"
fi
mapfile -t ADDED < <($PY scripts/ci/changed_source_files.py --base "$BASE" --kind python-added)
if [ "${#ADDED[@]}" -gt 0 ]; then
  printf '  %d added file(s) — mypy\n' "${#ADDED[@]}"
  mypy --ignore-missing-imports --follow-imports=silent "${ADDED[@]}"; check $? "mypy (added)"
fi

# --------------------------------------------------------------------------
# API contract ratchet (mirrors the openapi-contract job). The FastAPI app is
# the single source of truth for the REST contract; backend/openapi.json is its
# committed snapshot and frontend/src/types/generated/api.d.ts is generated
# from that snapshot. Both halves must travel with the change that alters them.
# --------------------------------------------------------------------------
step "OpenAPI snapshot drift (blocking)"
# Always run: generate_openapi.py rebuilds app.openapi() offline (it setdefaults
# ENVIRONMENT=testing + an in-memory SQLite URL + placeholder Azure creds), so
# there is no service to be unavailable and nothing to condition on.
$PY scripts/ci/generate_openapi.py --check; check $? "openapi drift"

step "Generated TypeScript types (blocking when the contract moves) — base=$BASE"
mapfile -t CONTRACT_FILES < <(changed_paths backend/openapi.json frontend/src/types/generated)
if [ "${#CONTRACT_FILES[@]}" -eq 0 ]; then
  skipped "generated api types" "backend/openapi.json + frontend/src/types/generated unchanged since $BASE"
else
  printf '  %d contract file(s) changed\n' "${#CONTRACT_FILES[@]}"
  # corepack first: package.json pins packageManager=pnpm@10.18.2.
  PNPM=()
  if command -v corepack >/dev/null 2>&1; then PNPM=(corepack pnpm)
  elif command -v pnpm >/dev/null 2>&1; then PNPM=(pnpm); fi
  # node_modules is hoisted to the repo root (.npmrc node-linker=hoisted), so
  # the openapi-typescript binary lands in the ROOT bin dir, not frontend's.
  HAS_DEPS=0
  [ -x node_modules/.bin/openapi-typescript ] && HAS_DEPS=1
  [ -x frontend/node_modules/.bin/openapi-typescript ] && HAS_DEPS=1
  if ! command -v node >/dev/null 2>&1 || [ "${#PNPM[@]}" -eq 0 ]; then
    # A missing toolchain is NOT a skip here: the contract moved, and letting it
    # through unverified is how api.d.ts silently lags the spec.
    warn "  the API contract changed but the frontend toolchain is unavailable:"
    warn "    node:  $(command -v node || echo 'NOT FOUND')"
    warn "    pnpm:  ${PNPM[*]:-NOT FOUND (install corepack, or pnpm on PATH)}"
    warn "  cannot verify frontend/src/types/generated/api.d.ts was regenerated."
    check 1 "generated api types (frontend toolchain missing)"
  elif [ "$HAS_DEPS" -eq 0 ]; then
    warn "  the API contract changed but frontend dependencies are not installed"
    warn "  (no node_modules/.bin/openapi-typescript). Run:"
    warn "    corepack pnpm install --frozen-lockfile"
    check 1 "generated api types (node_modules missing)"
  else
    # `check:api-types` = regenerate api.d.ts, then `git diff --exit-code` over
    # both committed artifacts — same pair the CI job diffs.
    ( cd frontend && "${PNPM[@]}" run check:api-types ); check $? "pnpm check:api-types"
  fi
fi

step "Alembic single head + revision-id length (blocking)"
( cd backend && $PY ../scripts/ci/check_alembic.py ); check $? "check_alembic"

# --------------------------------------------------------------------------
# Alembic upgrade-from-empty. check_alembic.py above is a STATIC read of the
# revision graph — it never executes env.py, so it cannot see a migration that
# fails to apply. This runs the real `alembic upgrade head` against a THROWAWAY
# database, using whichever of these is available (in order):
#   (a) a Postgres already listening locally — a scratch database is created and
#       dropped again in a trap, so a failure cannot leave it behind;
#   (b) a disposable `docker run --rm -d postgres:16-alpine` on a free port;
#   (c) neither — a loud SKIPPED, deliberately NOT a failure (this box may have
#       no Postgres and no docker), but never reported as a pass.
# --------------------------------------------------------------------------
ALEMBIC_PROBE_PG_PORTS="${ALEMBIC_PROBE_PG_PORTS:-5432 54322}"

_pg_port_ready() {
  if command -v pg_isready >/dev/null 2>&1; then
    pg_isready -h 127.0.0.1 -p "$1" -q >/dev/null 2>&1
  else
    $PY -c 'import socket,sys; socket.create_connection(("127.0.0.1", int(sys.argv[1])), 1).close()' "$1" >/dev/null 2>&1
  fi
}

_free_port() {
  $PY -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()'
}

# env.py resolves SUPABASE_DB_URL first, so it must be cleared or the probe
# would silently migrate whatever that points at (Supabase dev, in this repo).
_alembic_upgrade_head() {
  ( cd backend && env -u SUPABASE_DB_URL DATABASE_URL="$1" "$PY" -m alembic upgrade head )
}

# 0 = upgrade clean, 1 = upgrade failed, 2 = no throwaway database available.
alembic_upgrade_from_empty() (
  CLEAN_KIND=""; CLEAN_PORT=""; CLEAN_DB=""; CLEAN_CID=""
  PG_USER="${PGUSER:-postgres}"; PG_PW="${PGPASSWORD:-postgres}"
  # shellcheck disable=SC2329  # invoked indirectly, by the trap below
  cleanup() {
    case "$CLEAN_KIND" in
      db) PGPASSWORD="$PG_PW" psql -h 127.0.0.1 -p "$CLEAN_PORT" -U "$PG_USER" \
            -d postgres -q -c "DROP DATABASE IF EXISTS \"$CLEAN_DB\"" >/dev/null 2>&1 || true;;
      docker) docker rm -f "$CLEAN_CID" >/dev/null 2>&1 || true;;
    esac
  }
  trap cleanup EXIT INT TERM

  # (a) a Postgres that is already up.
  for port in $ALEMBIC_PROBE_PG_PORTS; do
    _pg_port_ready "$port" || continue
    if ! command -v psql >/dev/null 2>&1; then
      printf '  Postgres is up on :%s but psql is not installed — trying docker\n' "$port"
      break
    fi
    db="ci_alembic_from_empty_$$"
    if ! PGPASSWORD="$PG_PW" psql -h 127.0.0.1 -p "$port" -U "$PG_USER" -d postgres \
        -v ON_ERROR_STOP=1 -q -c "DROP DATABASE IF EXISTS \"$db\"" \
        -c "CREATE DATABASE \"$db\"" >/dev/null 2>&1; then
      printf '  could not create a scratch database on :%s (auth/permissions?) — trying next\n' "$port"
      continue
    fi
    CLEAN_KIND="db"; CLEAN_PORT="$port"; CLEAN_DB="$db"
    printf '  using local Postgres 127.0.0.1:%s (scratch database %s, dropped on exit)\n' "$port" "$db"
    # Normalise to 0/1: rc 2 is reserved for "no database available" and must
    # never be produced by a failed upgrade, or a failure would read as a skip.
    if _alembic_upgrade_head "postgresql://$PG_USER:$PG_PW@127.0.0.1:$port/$db"; then exit 0; else exit 1; fi
  done

  # (b) a throwaway container.
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    port="$(_free_port)"
    if [ -n "$port" ]; then
      printf '  starting throwaway postgres:16-alpine on 127.0.0.1:%s\n' "$port"
      cid="$(docker run --rm -d -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
             -e POSTGRES_DB=postgres -p "127.0.0.1:$port:5432" postgres:16-alpine 2>&1 | tail -1)"
      if [ -n "$cid" ] && docker inspect "$cid" >/dev/null 2>&1; then
        CLEAN_KIND="docker"; CLEAN_CID="$cid"
        ready=0
        for _ in $(seq 1 60); do
          if docker exec "$cid" pg_isready -U postgres -q >/dev/null 2>&1; then ready=1; break; fi
          sleep 1
        done
        if [ "$ready" -eq 1 ]; then
          printf '  container %s ready\n' "${cid:0:12}"
          if _alembic_upgrade_head "postgresql://postgres:postgres@127.0.0.1:$port/postgres"; then exit 0; else exit 1; fi
        fi
        printf '  throwaway container never became ready (60s)\n'
      else
        printf '  docker run failed: %s\n' "$cid"
      fi
    fi
  fi
  exit 2
)

step "Alembic upgrade head from an empty DB (blocking when migrations change) — base=$BASE"
mapfile -t MIGRATION_FILES < <(changed_paths backend/alembic/versions)
if [ "${#MIGRATION_FILES[@]}" -eq 0 ]; then
  skipped "alembic upgrade (from empty)" "backend/alembic/versions unchanged since $BASE"
else
  printf '  %d migration file(s) changed\n' "${#MIGRATION_FILES[@]}"
  alembic_upgrade_from_empty
  ALEMBIC_RC=$?
  if [ "$ALEMBIC_RC" -eq 2 ]; then
    warn "  ────────────────────────────────────────────────────────────────────"
    warn "  ⚠  NOT VERIFIED: alembic upgrade head from an empty database."
    warn "     This branch changes backend/alembic/versions/, but no throwaway"
    warn "     Postgres was reachable:"
    warn "       · nothing usable on 127.0.0.1: $ALEMBIC_PROBE_PG_PORTS"
    warn "         (not listening, psql missing, or CREATE DATABASE refused)"
    warn "       · docker is unavailable"
    warn "     The migration chain was checked STATICALLY ONLY (single head +"
    warn "     revision-id length). A migration that CANNOT APPLY from empty —"
    warn "     bad DDL, wrong down_revision target, missing dependency — will"
    warn "     NOT be caught by this run."
    warn "     To verify: start any local Postgres (or the dev compose stack),"
    warn "     or make docker available, then re-run this script."
    warn "  ────────────────────────────────────────────────────────────────────"
    skipped "alembic upgrade (from empty)" "no throwaway Postgres available — see the warning above"
  else
    check "$ALEMBIC_RC" "alembic upgrade (from empty)"
  fi
fi

if [ "$SKIP_TESTS" -eq 0 ]; then
  step "Unit tests (blocking)"
  pytest backend/tests/ -c backend/pytest.ini \
    -m "unit or not (integration or e2e or slow)" \
    -q -p no:cacheprovider --no-cov
  check $? "pytest"
fi

if [ "$DO_FRONTEND" -eq 1 ]; then
  step "Frontend type-check + lint (blocking)"
  ( cd frontend && pnpm run type-check ); check $? "pnpm type-check"
  ( cd frontend && pnpm run lint );       check $? "pnpm lint"
fi

printf '\n'
# Skips are reported before the verdict and never fold into it: "all gates
# passed" must not be able to mean "the gate never ran".
if [ "${#SKIPPED[@]}" -ne 0 ]; then
  SKIP_LIST="$(printf '%s; ' "${SKIPPED[@]}")"
  printf '\033[33m⚠️  SKIPPED (NOT verified): %s\033[0m\n' "${SKIP_LIST%; }"
fi
if [ "${#FAILED[@]}" -eq 0 ]; then
  if [ "${#SKIPPED[@]}" -eq 0 ]; then
    printf '\033[32m✅ All local CI gates passed\033[0m\n'
  else
    printf '\033[32m✅ All local CI gates that ran passed\033[0m\n'
  fi
  exit 0
else
  printf '\033[31m❌ Failed: %s\033[0m\n' "${FAILED[*]}"; exit 1
fi
