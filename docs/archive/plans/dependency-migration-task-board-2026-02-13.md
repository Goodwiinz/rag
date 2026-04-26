# Dependency Migration Task Board (2026-02-13)

This board tracks dependency updates grouped by risk and execution wave.

## Progress Snapshot (2026-02-13)

- `#82` implemented locally: `dotenv` updated to `^17.0.0` in `tests/e2e/package.json`
- `#81` implemented locally: `@types/node` updated to `^25.0.0` in `frontend/package.json`
- `#80` implemented locally: `zod` updated to `^4.0.0` in `frontend/package.json`
- `#64` implemented locally: `next` and `eslint-config-next` updated to `^16.0.0` in `frontend/package.json`
- `#80` compatibility fixes applied:
  - `frontend/src/services/api-client.ts`: `result.error.errors` -> `result.error.issues`
  - `frontend/src/types/schemas.ts`: updated `z.record(...)` signatures for Zod v4
- `#64` compatibility fixes applied:
  - ESLint migration for Next 16 stack: added `frontend/eslint.config.mjs`
  - ESLint toolchain upgrades: `eslint` `^9.0.0`, `@typescript-eslint/*` `^8.0.0`
  - Removed legacy `frontend/.eslintignore` (migrated ignore rules into flat config)
  - Next-generated TS updates after build: `frontend/tsconfig.json`, `frontend/next-env.d.ts`
- Local validation completed:
  - `npm run type-check --workspace=frontend` passed
  - `npm run test --workspace=frontend -- --runInBand` passed
  - `npm run test:e2e --workspace=tests/e2e -- --list` passed (list mode)
  - `npm run build --workspace=frontend` passed (with existing lint warnings)
- Playwright config cleanup completed (pre-existing issue):
  - moved HTML report output outside `test-results/` to avoid reporter/outputDir collision
  - updated files: `tests/e2e/playwright.config.ts`, `tests/e2e/playwright-accessibility.config.ts`, `tests/e2e/playwright-mobile.config.ts`, `tests/e2e/playwright-performance.config.ts`, `tests/e2e/playwright-visual.config.ts`

## Status Legend

- `[ ]` Not started
- `[-]` In progress
- `[x]` Done
- `[!]` Blocked

## Owners

- Migration lead: `@TBD`
- Frontend owner: `@TBD`
- Backend owner: `@TBD`
- CI owner: `@TBD`
- Reviewer: `@TBD`

## Global Merge Gate (applies to every PR)

Run from repo root:

```bash
npm install
uv sync --group dev
npm run lint
npm run build
npm run test
./run-ci.sh --quick
./run-ci.sh unit-tests frontend-tests
```

Required before merge:

- [ ] CI green on GitHub
- [ ] No new high/critical security findings
- [ ] Migration notes added to PR description
- [ ] Rollback plan documented in PR description

## Phase 0: Baseline + Low-Risk Merge Queue

### Baseline Tasks

- [ ] Capture baseline on `main` (`git rev-parse --short HEAD`) - Owner: `@TBD`
- [ ] Save baseline test run artifacts (`./run-ci.sh --quick`) - Owner: `@TBD`
- [ ] Confirm release branch/tag strategy for rollback - Owner: `@TBD`

### Merge-Now PRs

- [ ] `#97` Sentinel SQL syntax fix - Owner: `@TBD`
- [ ] `#86` npm minor/patch group (24 updates) - Owner: `@TBD`
- [ ] `#66` pip minor/patch group (69 updates) - Owner: `@TBD`
- [ ] `#62` GitHub Actions group update - Owner: `@TBD`
- [ ] `#75` pre-commit `3.6 -> 4.5` - Owner: `@TBD`
- [ ] `#76` ipython `8.18 -> 9.10` - Owner: `@TBD`

Validation command (for each PR above):

```bash
./run-ci.sh --quick
```

## Phase 1: Pytest Major Bump (isolated)

### PR `#74` - `pytest 7.4 -> 9.0`

- [ ] Owner assigned - Owner: `@TBD`
- [ ] Upgrade branch rebased on latest `main`
- [ ] Fix deprecated flags/plugins if needed
- [ ] Backend tests pass locally
- [ ] CI green
- [ ] Merge

Validation commands:

```bash
uv sync --group dev
pytest backend/tests/ -c backend/pytest.ini
./run-ci.sh unit-tests resilience-tests
```

## Phase 2: Risky Major Migrations (Waves)

## Wave A: Runtime Base

Target PRs: `#61` (Node Docker), `#60` (Python Docker)

Checklist:

- [ ] `#61` owner assigned - Owner: `@TBD`
- [ ] `#60` owner assigned - Owner: `@TBD`
- [ ] Decide target runtime policy (prefer LTS if 25/3.14 causes ecosystem breaks)
- [ ] Docker images build successfully
- [ ] Local CI backend+frontend stages pass
- [ ] Smoke boot in compose
- [ ] Merge `#61`, then `#60`

Validation commands:

```bash
docker compose -f docker-compose.ci.yml build
./run-ci.sh lint-backend lint-frontend unit-tests frontend-tests
docker compose -f docker-compose.ci.yml up -d
docker compose -f docker-compose.ci.yml ps
docker compose -f docker-compose.ci.yml down -v
```

## Wave B: Framework and Validation

Target PRs: `#64` (next `15 -> 16`), `#80` (zod `3 -> 4`), `#82` (dotenv `16 -> 17`)

Checklist:

- [ ] `#64` owner assigned - Owner: `@TBD`
- [ ] `#80` owner assigned - Owner: `@TBD`
- [ ] `#82` owner assigned - Owner: `@TBD`
- [ ] Type errors resolved
- [ ] Next build output validated
- [ ] Schema validation behavior regression-tested
- [ ] Env loading order verified for local/dev/CI
- [ ] Merge in order: `#82` -> `#80` -> `#64`

Validation commands:

```bash
npm install
npm run lint --workspace=frontend
npm run type-check --workspace=frontend
npm run build --workspace=frontend
npm run test --workspace=frontend
./run-ci.sh lint-frontend frontend-tests
```

## Wave C: Backend Libraries

Target PRs: `#67` (neo4j `5 -> 6`), `#71` (bcrypt `4 -> 5`)

Checklist:

- [ ] `#67` owner assigned - Owner: `@TBD`
- [ ] `#71` owner assigned - Owner: `@TBD`
- [ ] Driver/session API migrations completed
- [ ] Native module build/runtime checks pass in Docker
- [ ] Auth and graph query integration tests pass
- [ ] Merge `#71`, then `#67`

Validation commands:

```bash
uv sync --group dev
./run-ci.sh lint-backend unit-tests integration-tests
docker compose -f docker-compose.ci.yml build
```

## Wave D: Frontend and Test Stack

Target PRs: `#65` (recharts `2 -> 3`), `#72` (`@testing-library/react 14 -> 16`), `#77` (jsdom `23 -> 28`), `#79` (pixelmatch `5 -> 7`), `#81` (`@types/node 20 -> 25`)

Checklist:

- [ ] `#65` owner assigned - Owner: `@TBD`
- [ ] `#72` owner assigned - Owner: `@TBD`
- [ ] `#77` owner assigned - Owner: `@TBD`
- [ ] `#79` owner assigned - Owner: `@TBD`
- [ ] `#81` owner assigned - Owner: `@TBD`
- [ ] Chart rendering regressions checked on key screens
- [ ] Jest + jsdom tests stabilized
- [ ] Visual snapshot updates reviewed
- [ ] TypeScript node type drift resolved
- [ ] Merge in order: `#81` -> `#72` -> `#77` -> `#79` -> `#65`

Validation commands:

```bash
npm install
npm run lint --workspace=frontend
npm run type-check --workspace=frontend
npm run test --workspace=frontend
npm run test:e2e --workspace=tests/e2e -- --grep=@smoke
./run-ci.sh frontend-tests e2e-tests
```

## PR Tracking Table

| PR | Package/Change | Risk | Wave | Owner | Status | Notes |
|---|---|---|---|---|---|---|
| #97 | Sentinel SQL syntax fix | Low | 0 | `@TBD` | `[ ]` | |
| #86 | npm minor/patch group | Low | 0 | `@TBD` | `[ ]` | |
| #66 | pip minor/patch group | Low | 0 | `@TBD` | `[ ]` | |
| #62 | GitHub Actions group | Low | 0 | `@TBD` | `[ ]` | |
| #75 | pre-commit 3.6 -> 4.5 | Low | 0 | `@TBD` | `[ ]` | |
| #76 | ipython 8.18 -> 9.10 | Low | 0 | `@TBD` | `[ ]` | |
| #74 | pytest 7.4 -> 9.0 | Medium | 1 | `@TBD` | `[ ]` | Isolated migration |
| #61 | Node 18 -> 25 Docker | High | A | `@TBD` | `[ ]` | Consider LTS target |
| #60 | Python 3.11 -> 3.14 Docker | High | A | `@TBD` | `[ ]` | Consider ecosystem support |
| #64 | next 15 -> 16 | High | B | `@TBD` | `[-]` | Local upgrade + lint config migration done |
| #80 | zod 3 -> 4 | High | B | `@TBD` | `[-]` | Local update + compatibility fixes done |
| #82 | dotenv 16 -> 17 | High | B | `@TBD` | `[-]` | Local update + validation done |
| #67 | neo4j 5 -> 6 | High | C | `@TBD` | `[ ]` | |
| #71 | bcrypt 4 -> 5 | High | C | `@TBD` | `[ ]` | Native builds |
| #65 | recharts 2 -> 3 | High | D | `@TBD` | `[ ]` | Visual regression risk |
| #72 | @testing-library/react 14 -> 16 | High | D | `@TBD` | `[ ]` | |
| #77 | jsdom 23 -> 28 | High | D | `@TBD` | `[ ]` | |
| #79 | pixelmatch 5 -> 7 | High | D | `@TBD` | `[ ]` | Snapshot diffs |
| #81 | @types/node 20 -> 25 | High | D | `@TBD` | `[-]` | Local update + validation done |

## Rollback Rules

- [ ] Keep each package major bump in a separate commit.
- [ ] If post-merge regression appears, revert only the offending commit/PR.
- [ ] Stop wave progression until regression root cause is confirmed and fixed.

## Definition of Done (Program Level)

- [ ] All PRs in this board marked `[x]`
- [ ] Main branch CI green for 3 consecutive runs
- [ ] No Sev1/Sev2 regressions in first 24h after final merge
- [ ] Final migration summary posted in release notes
