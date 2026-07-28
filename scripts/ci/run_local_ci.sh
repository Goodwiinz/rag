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
# directory-docs lint, mypy on added files, the alembic head check, and the
# unit suite.
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
step() { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }
check() { if [ "$1" -ne 0 ]; then FAILED+=("$2"); printf '\033[31m  ✗ %s\033[0m\n' "$2"; else printf '\033[32m  ✓ %s\033[0m\n' "$2"; fi; }

step "Ruff (full tree, blocking)"
ruff check backend/src; check $? "ruff backend/src"

step "Directory docs lint (blocking)"
$PY scripts/docs/check_dir_docs.py; check $? "check_dir_docs"

step "Changed-file quality ratchet (blocking) — base=$BASE"
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

step "Alembic single head + revision-id length (blocking)"
( cd backend && $PY ../scripts/ci/check_alembic.py ); check $? "check_alembic"

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
if [ "${#FAILED[@]}" -eq 0 ]; then
  printf '\033[32m✅ All local CI gates passed\033[0m\n'; exit 0
else
  printf '\033[31m❌ Failed: %s\033[0m\n' "${FAILED[*]}"; exit 1
fi
