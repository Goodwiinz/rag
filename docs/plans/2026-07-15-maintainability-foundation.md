# Maintainability Foundation and Pilot Refactors Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish enforceable backend/frontend maintenance contracts, then prove them by decomposing the workspace API and chat surface without changing public behavior.

**Architecture:** Deliver six independently mergeable PRs. First align the toolchain and add debt ratchets; then extend the existing OpenAPI contract pipeline; finally refactor the backend workspace and frontend chat pilots behind stable exports and behavior-characterization tests. FastAPI/Pydantic remains the HTTP source of truth, backend services remain the canonical persistence writer, and the frontend keeps one terminal reconciliation path.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, pytest, Ruff, Black, isort, MyPy, Node 24, pnpm 10.18.2, Next.js 16.2.9, React 18.3.1, TypeScript, ESLint 9, Vitest, Playwright, Zustand, TanStack Query, OpenAPI TypeScript.

**Approved design:** `docs/plans/2026-07-15-maintainability-foundation-design.md`

---

## Delivery rules

- Create each PR branch from the latest `origin/develop`; do not stack all six PRs in one branch.
- Target `develop` and keep each PR independently deployable and revertible.
- Use tests before movement: add a failing characterization or contract test, make the smallest change, and rerun the focused lane.
- Preserve endpoint paths, status codes, schemas, persistence ownership, and visible chat behavior unless a separate product change is approved.
- Never weaken tenant filters or convert an `AsyncSession` into shared concurrent state.
- Keep compatibility exports until all callers are migrated and focused tests pass.
- If current baseline measurements differ from this plan, record the measured value in the PR and ratchet from that value; do not invent a cleaner baseline.
- Before each commit run `git diff --check`; before each PR run the verification block listed for that PR.

## Dependency map

| PR | Branch | Depends on | Rollback boundary |
| --- | --- | --- | --- |
| 1 | `chore/toolchain-contract` | current `develop` | runtime/package-manager files only |
| 2 | `ci/quality-ratchets` | PR 1 | CI, pre-commit, and baseline files |
| 3 | `feat/generated-workspace-contract` | PR 2 | generated-type enforcement and workspace client typing |
| 4 | `refactor/workspace-api-boundaries` | PR 3 | backend workspace modules behind stable router exports |
| 5 | `refactor/chat-composition` | PR 4 | frontend chat composition/store modules behind stable exports |
| 6 | `docs/engineering-standards` | PR 5 | standards, ownership, and architectural guards |

---

## PR 1: Toolchain consistency

### Task 1.1: Add a failing toolchain contract test

**Files:**

- Create: `backend/tests/unit/ci/test_toolchain_contract.py`
- Read: `.nvmrc`
- Read: `package.json`
- Read: `frontend/package.json`
- Read: `pnpm-workspace.yaml`
- Read: `.github/workflows/test-pipeline.yml`
- Read: `docker-bake.hcl`
- Read: `frontend/Dockerfile`
- Read: `frontend/Dockerfile.prod`
- Read: `frontend/Dockerfile.production`

**Step 1: Write the failing contract.**

Use stdlib `json`, `re`, and `pathlib`. Assert:

```python
CANONICAL_NODE = "24"
CANONICAL_PNPM = "pnpm@10.18.2"
CANONICAL_NEXT = "16.2.9"
CANONICAL_REACT = "18.3.1"

def test_active_javascript_surfaces_share_one_toolchain() -> None:
    root = json.loads((REPO_ROOT / "package.json").read_text())
    frontend = json.loads((REPO_ROOT / "frontend/package.json").read_text())
    workflow = (REPO_ROOT / ".github/workflows/test-pipeline.yml").read_text()
    bake = (REPO_ROOT / "docker-bake.hcl").read_text()

    assert (REPO_ROOT / ".nvmrc").read_text().strip() == CANONICAL_NODE
    assert root["packageManager"] == frontend["packageManager"] == CANONICAL_PNPM
    assert root["engines"]["node"] == frontend["engines"]["node"] == "24.x"
    assert 'NODE_VERSION: "24"' in workflow
    assert 'default = "24"' in bake
```

Also assert that root/frontend scripts do not contain `npm run`, active Dockerfiles use `corepack` plus `pnpm`, `frontend/pnpm-lock.yaml` does not exist, and the Next/React overrides equal the frontend declarations.

**Step 2: Run the test and confirm current drift is detected.**

Run:

```bash
pytest -q backend/tests/unit/ci/test_toolchain_contract.py
```

Expected: FAIL on CI Node 20, Docker Node 25, npm scripts, framework override drift, and the nested lockfile.

**Step 3: Commit the red test.**

```bash
git add backend/tests/unit/ci/test_toolchain_contract.py
git commit -m "test(ci): define the JavaScript toolchain contract"
```

### Task 1.2: Align package metadata, scripts, and lock authority

**Files:**

- Modify: `package.json`
- Modify: `frontend/package.json`
- Modify: `pnpm-workspace.yaml`
- Delete: `frontend/pnpm-lock.yaml`
- Modify: `pnpm-lock.yaml`
- Delete: `frontend/.eslintrc.json`
- Delete: `frontend/.eslintrc.cjs`
- Create: `frontend/eslint.config.mjs`

**Step 1: Replace root npm wrappers with pnpm workspace commands.**

Use these scripts:

```json
{
  "dev": "pnpm --filter multimodal-rag-frontend dev",
  "build": "pnpm --filter multimodal-rag-frontend build",
  "build:frontend": "pnpm --filter multimodal-rag-frontend build",
  "start": "pnpm --filter multimodal-rag-frontend start",
  "lint": "pnpm -r --if-present lint",
  "test": "pnpm -r --if-present test",
  "test:e2e": "pnpm --filter ./tests/e2e test:e2e",
  "validate": "pnpm --filter multimodal-rag-frontend validate",
  "install:all": "pnpm install"
}
```

Keep the existing Trigger.dev scripts. Remove the npm engine declaration; `packageManager` is the package-manager authority.

**Step 2: Align the frontend framework/tool versions.**

- `next`: `16.2.9`
- `react` and `react-dom`: `18.3.1`
- `eslint`: a current ESLint 9 release accepted by `eslint-config-next@16.2.9`
- `eslint-config-next`: `16.2.9`
- keep `@typescript-eslint/*` on the current 8.x line
- replace `npx eslint` and `npm run` in scripts with direct binaries or `pnpm run`
- set `validate` to `pnpm lint && pnpm type-check && pnpm test`

Convert the duplicate legacy ESLint configs to one flat config:

```js
import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  // Preserve the current warning rules here.
  globalIgnores(['.next/**', 'out/**', 'src/types/generated/**']),
]);
```

Do not silently retain the current broad test/source ignores; exclusions are handled explicitly in PR 2.

**Step 3: Make root `pnpm-lock.yaml` the only lockfile.**

Set the workspace overrides to `next: 16.2.9`, `react: 18.3.1`, and `react-dom: 18.3.1`; then run:

```bash
corepack enable
corepack prepare pnpm@10.18.2 --activate
pnpm install
pnpm install --frozen-lockfile
```

Expected: both commands succeed and only root `pnpm-lock.yaml` changes.

**Step 4: Verify package resolution.**

```bash
pnpm --filter multimodal-rag-frontend exec next --version
pnpm --filter multimodal-rag-frontend exec eslint --version
pnpm why next react react-dom eslint eslint-config-next
```

Expected: one resolved Next version, one React/React DOM version, and a peer-compatible ESLint/config pair.

**Step 5: Commit.**

```bash
git add package.json frontend/package.json pnpm-workspace.yaml pnpm-lock.yaml frontend/eslint.config.mjs
git add -u frontend/pnpm-lock.yaml frontend/.eslintrc.json frontend/.eslintrc.cjs
git commit -m "chore(frontend): align pnpm and framework metadata"
```

### Task 1.3: Align CI and active container builds on Node 24/pnpm

**Files:**

- Modify: `.github/workflows/test-pipeline.yml`
- Modify: `docker-bake.hcl`
- Modify: `frontend/Dockerfile`
- Modify: `frontend/Dockerfile.prod`
- Modify: `frontend/Dockerfile.production`
- Modify: `docker-compose.development.yml`
- Modify if referenced: `docker-compose.prod.yml`

**Step 1: Set CI and bake to Node 24.**

Change `NODE_VERSION` from 20 to 24 in the workflow and bake file. Keep `pnpm/action-setup` and root `pnpm-lock.yaml` as cache authority.

**Step 2: Make Docker builds consume the root workspace lock.**

For the active `frontend/Dockerfile.prod` root-context build:

```dockerfile
ARG NODE_VERSION=24
FROM node:${NODE_VERSION}-alpine AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable && corepack prepare pnpm@10.18.2 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY frontend/package.json frontend/package.json
COPY tests/e2e/package.json tests/e2e/package.json
RUN pnpm install --frozen-lockfile --filter multimodal-rag-frontend...
```

Build the frontend with `pnpm --filter multimodal-rag-frontend build`. Adjust standalone copy paths only to match the output produced by the verified build; do not guess.

For frontend-context development/legacy Dockerfiles, either convert them to pnpm with an explicitly copied root lock via root context or mark/remove them if `rg` proves no active compose/workflow references them. Do not leave an npm fallback in an active file.

**Step 3: Run the contract and build checks.**

```bash
pytest -q backend/tests/unit/ci/test_toolchain_contract.py
pnpm --filter multimodal-rag-frontend lint
pnpm --filter multimodal-rag-frontend type-check
docker buildx bake -f docker-bake.hcl --print frontend
docker build -f frontend/Dockerfile.prod --target builder \
  --build-arg NEXT_PUBLIC_SUPABASE_URL=http://localhost:8999 \
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=test-key-not-real .
```

Expected: toolchain contract passes; lint/type-check pass or expose only pre-existing debt to be baselined in PR 2; the active image builds from the root lock.

**Step 4: Commit.**

```bash
git add .github/workflows/test-pipeline.yml docker-bake.hcl frontend/Dockerfile* docker-compose*.yml
git commit -m "build(frontend): use Node 24 and pnpm everywhere"
```

### Task 1.4: Correct current developer commands

**Files:**

- Modify: `README.md`
- Modify: `AGENTS.md`

Replace Next 15/Node 18/npm instructions with the verified Node 24/pnpm/Next 16 commands. Keep historical reports unchanged unless they claim to be current instructions.

Verify:

```bash
rg -n 'npm (install|run)|Next\.js 15|Node\.js 18' README.md AGENTS.md
```

Expected: no stale current-workflow instructions.

Commit:

```bash
git add README.md AGENTS.md
git commit -m "docs: align local commands with the active toolchain"
```

### PR 1 verification

```bash
pytest -q backend/tests/unit/ci/test_toolchain_contract.py
pnpm install --frozen-lockfile
pnpm --filter multimodal-rag-frontend lint
pnpm --filter multimodal-rag-frontend type-check
pnpm --filter multimodal-rag-frontend test
docker build -f frontend/Dockerfile.prod --target builder \
  --build-arg NEXT_PUBLIC_SUPABASE_URL=http://localhost:8999 \
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=test-key-not-real .
git diff --check origin/develop...HEAD
```

---

## PR 2: Honest, gradual quality gates

### Task 2.1: Add changed-file and exclusion ratchet tests

**Files:**

- Create: `scripts/ci/changed_source_files.py`
- Create: `scripts/ci/check_tsconfig_exclusions.py`
- Create: `backend/tests/unit/ci/test_changed_source_files.py`
- Create: `backend/tests/unit/ci/test_tsconfig_exclusions.py`
- Create: `frontend/quality-baseline.json`
- Modify: `frontend/tsconfig.json`

**Step 1: Test base selection and changed-file classification.**

The helper must accept `--base`, fall back to the PR base SHA, then to `github.event.before`, and fail clearly if no trustworthy base can be found. It returns separate changed Python and frontend TypeScript/JavaScript paths and ignores generated files.

Test rename, deletion, spaces, an all-zero `before` SHA, and workflow-dispatch fallback using a temporary git repository.

**Step 2: Test the TypeScript exclusion ratchet.**

Record the exact current production exclusions in `frontend/quality-baseline.json`. The checker must fail when:

- an exclusion is added without updating the reviewed baseline;
- a changed production file remains excluded;
- a baseline entry points to a missing file.

It should pass when a touched file is removed from both `tsconfig.json` and the baseline.

**Step 3: Run red tests, implement the helpers, and rerun.**

```bash
pytest -q \
  backend/tests/unit/ci/test_changed_source_files.py \
  backend/tests/unit/ci/test_tsconfig_exclusions.py
```

Expected: FAIL before helpers; PASS after implementation.

**Step 4: Commit.**

```bash
git add scripts/ci/changed_source_files.py scripts/ci/check_tsconfig_exclusions.py \
  backend/tests/unit/ci/test_changed_source_files.py \
  backend/tests/unit/ci/test_tsconfig_exclusions.py \
  frontend/quality-baseline.json frontend/tsconfig.json
git commit -m "test(ci): add changed-source quality ratchets"
```

### Task 2.2: Make critical Python correctness checks blocking

**Files:**

- Modify: `pyproject.toml`
- Modify: `.github/workflows/test-pipeline.yml`
- Modify: Python files reported by `ruff check backend/src --select F821,F823`

**Step 1: Capture the real baseline.**

```bash
ruff check backend/src --select F821,F823 --output-format=concise
```

Save the command output in the PR description, not the repository. Classify every hit; do not call undefined names false positives without proving it.

**Step 2: Remove global and API-wide `F821`/`F823` ignores.**

Fix real violations and retain only narrow per-file ignores with an inline reason. The blocking Ruff lane must reject undefined names and referenced-before-assignment errors globally.

**Step 3: Add a changed-file blocking formatter/type lane.**

Use `changed_source_files.py` so changed Python files run:

```bash
ruff check <changed-python-files>
black --check <changed-python-files>
isort --check-only <changed-python-files>
mypy --ignore-missing-imports <changed-python-files>
```

Keep existing full-tree Black/isort/MyPy lanes advisory until their debt reaches zero, and label them `Advisory ...` in the job summary. The new changed-file lane is blocking.

**Step 4: Verify.**

```bash
ruff check backend/src --select F821,F823
pytest -q backend/tests/unit/ci
```

Expected: zero critical Ruff findings; CI helper tests pass.

**Step 5: Commit.**

```bash
git add pyproject.toml .github/workflows/test-pipeline.yml backend/src
git commit -m "ci(backend): block new correctness and formatting debt"
```

### Task 2.3: Make frontend lint/type debt non-increasing

**Files:**

- Create: `scripts/ci/check_frontend_quality.mjs`
- Create: `frontend/src/test/quality/checkFrontendQuality.test.ts`
- Modify: `frontend/package.json`
- Modify: `.github/workflows/test-pipeline.yml`
- Modify: `frontend/quality-baseline.json`

**Step 1: Write tests for the baseline comparator.**

The comparator consumes ESLint JSON and fails on:

- any error in a changed file;
- any warning in a changed file unless an existing warning was removed in the same file;
- a global error/warning count above the committed baseline;
- growth in `tsconfig.json` production exclusions.

**Step 2: Add repository-owned scripts.**

Add:

```json
{
  "lint": "eslint app src",
  "lint:changed": "node ../scripts/ci/check_frontend_quality.mjs",
  "quality:exclusions": "python3 ../scripts/ci/check_tsconfig_exclusions.py",
  "validate": "pnpm lint && pnpm type-check && pnpm test"
}
```

CI runs full lint for visibility and `lint:changed` as the blocking ratchet. Remove `continue-on-error` from the blocking changed-file step; keep any full-tree advisory step explicitly named advisory.

**Step 3: Verify.**

```bash
pnpm --filter multimodal-rag-frontend test -- checkFrontendQuality
pnpm --filter multimodal-rag-frontend lint
python3 scripts/ci/check_tsconfig_exclusions.py --base origin/develop
```

Expected: comparator tests pass; current totals do not exceed the recorded baseline.

**Step 4: Commit.**

```bash
git add scripts/ci/check_frontend_quality.mjs frontend/src/test/quality \
  frontend/package.json frontend/quality-baseline.json .github/workflows/test-pipeline.yml
git commit -m "ci(frontend): prevent new lint and type exclusions"
```

### Task 2.4: Add a measured frontend coverage ratchet

**Files:**

- Create: `scripts/ci/check_frontend_coverage.mjs`
- Create: `frontend/src/test/quality/checkFrontendCoverage.test.ts`
- Modify: `frontend/vitest.config.mts`
- Modify: `frontend/quality-baseline.json`
- Modify: `.github/workflows/test-pipeline.yml`

**Step 1: Generate `json-summary` coverage and measure the current baseline.**

```bash
pnpm --dir frontend test:coverage -- --coverage.reporter=json-summary
```

Commit the exact measured lines/branches/functions/statements values. Do not use the stale promised `50/40/45/50` comment as evidence.

**Step 2: Test and implement a no-regression comparator.**

The comparator fails if any global metric falls below its committed value. It prints the old/new metric and the update command. Raising a baseline requires an intentional JSON edit in the same PR.

**Step 3: Remove zero thresholds and stale comments.**

Keep Vitest thresholds at the measured floor or let the comparator own the ratchet, but do not maintain two divergent sources of truth.

**Step 4: Verify and commit.**

```bash
pnpm --filter multimodal-rag-frontend test -- checkFrontendCoverage
pnpm --dir frontend test:coverage -- --coverage.reporter=json-summary
node scripts/ci/check_frontend_coverage.mjs frontend/coverage/coverage-summary.json
```

```bash
git add scripts/ci/check_frontend_coverage.mjs frontend/src/test/quality \
  frontend/vitest.config.mts frontend/quality-baseline.json .github/workflows/test-pipeline.yml
git commit -m "ci(frontend): ratchet measured test coverage"
```

### Task 2.5: Make pre-commit call the same repository checks

**Files:**

- Modify: `.pre-commit-config.yaml`
- Create: `scripts/ci/check_tool_versions.py`
- Create: `backend/tests/unit/ci/test_tool_versions.py`

Replace stale duplicated Black/isort/flake8/mypy/ESLint hooks with local hooks that invoke the same pinned commands used by CI. The version test compares workflow pins and pre-commit commands.

Verify:

```bash
pytest -q backend/tests/unit/ci/test_tool_versions.py
pre-commit run --all-files
```

Commit:

```bash
git add .pre-commit-config.yaml scripts/ci/check_tool_versions.py \
  backend/tests/unit/ci/test_tool_versions.py
git commit -m "chore: align pre-commit with CI checks"
```

### PR 2 verification

```bash
ruff check backend/src
pytest -q backend/tests/unit/ci
pnpm --filter multimodal-rag-frontend lint
pnpm --filter multimodal-rag-frontend type-check
pnpm --dir frontend test:coverage -- --coverage.reporter=json-summary
node scripts/ci/check_frontend_coverage.mjs frontend/coverage/coverage-summary.json
pre-commit run --all-files
git diff --check origin/develop...HEAD
```

---

## PR 3: Finish the generated workspace contract

### Task 3.1: Make generated TypeScript drift blocking

**Files:**

- Modify: `backend/tests/unit/ci/test_generate_openapi.py`
- Modify: `.github/workflows/test-pipeline.yml`
- Modify: `frontend/package.json`

**Step 1: Add a failing workflow contract test.**

Assert the `openapi-contract` job:

- sets up Node 24 and pnpm 10.18.2;
- installs from root `pnpm-lock.yaml` with `--frozen-lockfile`;
- runs `pnpm --dir frontend generate:api-types`;
- runs `git diff --exit-code -- backend/openapi.json frontend/src/types/generated/api.d.ts`.

Run:

```bash
pytest -q backend/tests/unit/ci/test_generate_openapi.py
```

Expected: FAIL because CI currently checks only `backend/openapi.json`.

**Step 2: Extend the existing job; do not create a duplicate job.**

After the Python schema check, install the frontend generator, regenerate, and diff both committed artifacts. Add `check:api-types` locally if useful, but CI remains authoritative.

**Step 3: Verify and commit.**

```bash
python scripts/ci/generate_openapi.py --check
pnpm --dir frontend generate:api-types
git diff --exit-code -- backend/openapi.json frontend/src/types/generated/api.d.ts
pytest -q backend/tests/unit/ci/test_generate_openapi.py
```

```bash
git add .github/workflows/test-pipeline.yml frontend/package.json \
  backend/tests/unit/ci/test_generate_openapi.py
git commit -m "ci(openapi): verify generated TypeScript drift"
```

### Task 3.2: Type the workspace HTTP boundary from OpenAPI

**Files:**

- Create: `frontend/src/types/api/workspace-contract.ts`
- Modify: `frontend/src/services/workspaceService.ts`
- Modify: `frontend/src/types/workspace.ts`
- Create: `frontend/src/services/__tests__/workspaceService.contract.test.ts`
- Modify: `frontend/src/types/README.md`

**Step 1: Add contract aliases.**

Use generated `components` aliases for every request/response used by `workspaceService`, including the qualified schema key for chat `ThreadListResponse`:

```ts
import type { components } from '@/types/generated/api';

export type ApiWorkspace = components['schemas']['WorkspaceResponse'];
export type ApiWorkspaceCreate = components['schemas']['WorkspaceCreate'];
export type ApiConversation = components['schemas']['ConversationResponse'];
export type ApiThreadList =
  components['schemas']['src__schemas__chat__ThreadListResponse'];
export type ApiMessage = components['schemas']['ChatMessageResponse'];
```

Keep frontend-only enums, streaming frames, planner steps, optimistic IDs, and view-model concepts handwritten. If the wire type needs normalization, add an explicit mapper; do not use `as unknown as` to hide mismatches.

**Step 2: Write service contract tests before changing imports.**

Mock `api`, call representative workspace/conversation/thread/message methods, and assert exact URL, request body, and normalized response. Include nullable/optional fields and the `source_project_id` binding.

**Step 3: Migrate the service boundary.**

Make `workspaceService` inputs/outputs use generated aliases. Re-export compatible domain names from `types/workspace.ts` temporarily so store/components do not all move in the same commit.

**Step 4: Fix the contradictory generated-types documentation.**

Remove the stale `No generated types` section and document the adopt-on-touch rule plus regeneration commands.

**Step 5: Verify and commit.**

```bash
pnpm --filter multimodal-rag-frontend test -- workspaceService.contract
pnpm --filter multimodal-rag-frontend type-check
pnpm --dir frontend generate:api-types
git diff --exit-code -- frontend/src/types/generated/api.d.ts
```

```bash
git add frontend/src/types/api/workspace-contract.ts frontend/src/services/workspaceService.ts \
  frontend/src/types/workspace.ts frontend/src/services/__tests__/workspaceService.contract.test.ts \
  frontend/src/types/README.md
git commit -m "refactor(frontend): adopt generated workspace contracts"
```

### PR 3 verification

```bash
python scripts/ci/generate_openapi.py --check
pnpm --dir frontend generate:api-types
git diff --exit-code -- backend/openapi.json frontend/src/types/generated/api.d.ts
pnpm --filter multimodal-rag-frontend lint
pnpm --filter multimodal-rag-frontend type-check
pnpm --filter multimodal-rag-frontend test -- workspaceService.contract
git diff --check origin/develop...HEAD
```

---

## PR 4: Backend workspace API pilot

### Task 4.1: Freeze the public workspace route contract

**Files:**

- Create: `backend/tests/unit/api/test_workspace_route_contract.py`
- Modify only if gaps exist: existing tests under `backend/tests/api/threads/`
- Read: `backend/openapi.json`
- Read: `backend/src/main.py`

**Step 1: Characterize every workspace/flat route.**

Build the FastAPI app and assert the `(method, path)` set currently exported by `router` and `standalone_router`, including route order where `/api/v2/threads/*` could collide. Assert operation response models from the OpenAPI snapshot for workspaces, members, conversations, threads, messages, and collections.

**Step 2: Add missing behavior tests.**

Cover:

- owner/admin/editor/viewer permissions;
- cross-organization denial;
- soft-deleted member restoration;
- soft-deleted parent denial;
- list/count filter parity;
- rollback when a mutation fails;
- enqueue only after authoritative state commits.

Reuse fixtures from `backend/tests/api/threads/`; do not introduce a separate fake authorization model.

**Step 3: Run the characterization suite.**

```bash
pytest -q \
  backend/tests/unit/api/test_workspace_route_contract.py \
  backend/tests/unit/api/test_workspace_member_readd.py \
  backend/tests/unit/api/test_workspace_tenant_scope.py \
  backend/tests/api/threads
```

Expected: existing behavior passes; any discovered mismatch is fixed in a separate bug commit before structural movement.

**Step 4: Commit.**

```bash
git add backend/tests/unit/api/test_workspace_route_contract.py backend/tests/api/threads
git commit -m "test(workspaces): characterize the public API contract"
```

### Task 4.2: Split the 2,517-line router behind stable exports

**Files:**

- Create: `backend/src/api/threads/workspace_routes/__init__.py`
- Create: `backend/src/api/threads/workspace_routes/dependencies.py`
- Create: `backend/src/api/threads/workspace_routes/presenters.py`
- Create: `backend/src/api/threads/workspace_routes/workspaces.py`
- Create: `backend/src/api/threads/workspace_routes/members.py`
- Create: `backend/src/api/threads/workspace_routes/conversations.py`
- Create: `backend/src/api/threads/workspace_routes/threads.py`
- Create: `backend/src/api/threads/workspace_routes/messages.py`
- Create: `backend/src/api/threads/workspace_routes/collections.py`
- Modify: `backend/src/api/threads/workspaces.py`
- Preserve: `backend/src/api/threads/__init__.py`
- Preserve: `backend/src/main.py`

**Step 1: Move helpers first with no logic changes.**

Move scoped loaders to `dependencies.py` and response conversion to `presenters.py`. Keep organization/user arguments mandatory. Run route characterization after each move.

**Step 2: Move endpoints by resource.**

Each module exports nested and/or flat routers. `workspace_routes/__init__.py` composes them in the current order. Reduce `backend/src/api/threads/workspaces.py` to a compatibility export:

```python
from .workspace_routes import router, standalone_router

__all__ = ["router", "standalone_router"]
```

Do not change `backend/src/main.py` registration in this task.

**Step 3: Verify after each resource move.**

```bash
pytest -q backend/tests/unit/api/test_workspace_route_contract.py backend/tests/api/threads
python scripts/ci/generate_openapi.py --check
```

Expected: route and OpenAPI diffs remain clean.

**Step 4: Commit.**

```bash
git add backend/src/api/threads/workspaces.py backend/src/api/threads/workspace_routes
git commit -m "refactor(workspaces): split routes by resource"
```

### Task 4.3: Consolidate the duplicate router and `ChatService` logic

**Files:**

- Create: `backend/src/services/threads/workspace_access.py`
- Create: `backend/src/services/threads/workspace_service.py`
- Create: `backend/src/services/threads/conversation_service.py`
- Create: `backend/src/services/threads/thread_service.py`
- Create: `backend/src/services/threads/message_service.py`
- Create: `backend/src/services/threads/collection_service.py`
- Modify: `backend/src/services/threads/chat_service.py`
- Modify: `backend/src/api/threads/workspace_routes/*.py`
- Create: `backend/tests/unit/services/threads/test_workspace_access.py`
- Create: `backend/tests/unit/services/threads/test_workspace_service.py`
- Create: `backend/tests/unit/services/threads/test_conversation_service.py`
- Create: `backend/tests/unit/services/threads/test_thread_service.py`
- Create: `backend/tests/unit/services/threads/test_message_service.py`
- Create: `backend/tests/unit/services/threads/test_collection_service.py`

**Step 1: Extract the mandatory scope/access funnel.**

Every getter accepts `organization_id` and `user_id` (plus the resource ID) and fails closed. Parent-resource access must include soft-delete state. Test cross-org resources with identical child IDs/titles to prove the predicate, not just a 404 happy path.

**Step 2: Extract one resource service at a time.**

For each resource:

1. write service tests for authorization, transaction order, and response loading;
2. move the existing `ChatService` implementation into the resource service;
3. replace duplicate router SQL with a service call;
4. make `ChatService` delegate to the new service for compatibility;
5. run focused tests before proceeding to the next resource.

Do not create generic CRUD repositories. Keep specialized query helpers where filter/count parity or eager-loading rules are important.

**Step 3: Make transaction ownership explicit.**

- routers never call `commit`, `rollback`, `flush`, or `refresh`;
- one service method owns one transaction boundary;
- commit before enqueueing work that reads committed state;
- on external storage failure, use the existing compensation helper and restore quota/state;
- do not share an `AsyncSession` across concurrently awaited tasks.

**Step 4: Run resource-focused tests after each extraction.**

```bash
pytest -q backend/tests/unit/services/threads/test_workspace_access.py
pytest -q backend/tests/unit/services/threads/test_workspace_service.py
pytest -q backend/tests/unit/services/threads/test_conversation_service.py
pytest -q backend/tests/unit/services/threads/test_thread_service.py
pytest -q backend/tests/unit/services/threads/test_message_service.py
pytest -q backend/tests/unit/services/threads/test_collection_service.py
pytest -q backend/tests/api/threads backend/tests/unit/api/test_workspace_*.py
```

**Step 5: Commit in resource-sized commits.**

Example sequence:

```bash
git commit -m "refactor(workspaces): centralize scoped access"
git commit -m "refactor(workspaces): move workspace and member rules to services"
git commit -m "refactor(workspaces): move conversation and thread rules to services"
git commit -m "refactor(workspaces): move message and collection rules to services"
```

### Task 4.4: Add an architectural regression test

**Files:**

- Create: `backend/tests/unit/architecture/test_workspace_boundaries.py`

Parse the workspace route modules with `ast` and fail if they call `.commit()`, `.rollback()`, `select()`, or import SQLAlchemy models/query constructors. Also assert compatibility exports still resolve to the composed routers.

Run:

```bash
pytest -q backend/tests/unit/architecture/test_workspace_boundaries.py
```

Commit:

```bash
git add backend/tests/unit/architecture/test_workspace_boundaries.py
git commit -m "test(architecture): enforce workspace route boundaries"
```

### PR 4 verification

```bash
ruff check backend/src/api/threads backend/src/services/threads
black --check backend/src/api/threads backend/src/services/threads
isort --check-only backend/src/api/threads backend/src/services/threads
mypy backend/src/api/threads backend/src/services/threads --ignore-missing-imports
pytest -q backend/tests/unit/architecture/test_workspace_boundaries.py
pytest -q backend/tests/unit/api/test_workspace_*.py backend/tests/api/threads
pytest -q backend/tests/unit/services/threads
python scripts/ci/generate_openapi.py --check
pnpm --dir frontend generate:api-types
git diff --exit-code -- backend/openapi.json frontend/src/types/generated/api.d.ts
git diff --check origin/develop...HEAD
```

---

## PR 5: Frontend chat pilot

### Task 5.1: Freeze chat behavior before movement

**Files:**

- Modify: `frontend/src/components/chat/__tests__/ChatPage.auth.test.tsx`
- Modify: `frontend/src/components/chat/__tests__/ChatPage.threadSelect.test.tsx`
- Modify: `frontend/src/components/chat/__tests__/ChatPage.turnPersistence.test.tsx`
- Modify: `frontend/src/hooks/__tests__/useChatSession.threadSwitchBleed.test.tsx`
- Modify: `frontend/src/store/__tests__/chat-store-refresh.test.ts`
- Create: `frontend/src/components/chat/__tests__/ChatPage.commands.test.tsx`
- Create: `frontend/src/components/chat/__tests__/ChatPage.citations.test.tsx`

Add missing characterization for cold initialization, first message, command output/actions, project context, citation panel, stop/retry/regenerate, HITL approve/reject/error, pagination, and server-canonical reload.

Run:

```bash
pnpm --dir frontend test -- \
  ChatPage.auth ChatPage.threadSelect ChatPage.turnPersistence \
  ChatPage.commands ChatPage.citations \
  useChatSession.threadSwitchBleed chat-store-refresh
```

Expected: PASS before structural changes.

Commit:

```bash
git add frontend/src/components/chat/__tests__ frontend/src/hooks/__tests__ \
  frontend/src/store/__tests__
git commit -m "test(chat): characterize page and reconciliation behavior"
```

### Task 5.2: Extract page orchestration into focused hooks

**Files:**

- Create: `frontend/src/hooks/chat/useSlashCommands.ts`
- Create: `frontend/src/hooks/chat/useCitationPanel.ts`
- Create: `frontend/src/hooks/chat/useChatDrawer.ts`
- Create: `frontend/src/hooks/chat/useChatComposerActions.ts`
- Create: `frontend/src/hooks/chat/__tests__/useSlashCommands.test.tsx`
- Create: `frontend/src/hooks/chat/__tests__/useCitationPanel.test.tsx`
- Create: `frontend/src/hooks/chat/__tests__/useChatDrawer.test.tsx`
- Modify: `frontend/app/(dashboard)/chat/page.tsx`

**Step 1: Move slash-command state and effects.**

Move `commandOutputs`, `/new`, `/retry`, `/threads`, `/projects`, `/papers`, `/remember`, `/memories`, and item actions to `useSlashCommands`. Inject services and navigation callbacks so tests do not require the full page.

**Step 2: Move citation and drawer state.**

`useCitationPanel` owns active citation/trace/panel state. `useChatDrawer` owns focus restore, Escape handling, and Tab trapping. Preserve WCAG behavior.

**Step 3: Move composer actions without creating a writer.**

`useChatComposerActions` coordinates attach, retry, regenerate, and submit, but delegates persistence/streaming to the existing `useChatStreaming`/store path. It must not call a second create-message endpoint.

**Step 4: Verify focused hooks and page behavior.**

```bash
pnpm --dir frontend test -- useSlashCommands useCitationPanel useChatDrawer ChatPage
```

**Step 5: Commit.**

```bash
git add frontend/src/hooks/chat frontend/app/'(dashboard)'/chat/page.tsx
git commit -m "refactor(chat): extract page orchestration hooks"
```

### Task 5.3: Make the route a composition root

**Files:**

- Create: `frontend/src/components/chat/ChatSurface.tsx`
- Create: `frontend/src/components/chat/ChatTranscriptState.tsx`
- Modify: `frontend/app/(dashboard)/chat/page.tsx`
- Modify: existing chat component tests as imports move

Move the visible shell into named components with explicit props. Keep the route responsible for Suspense, route-level auth/session wiring, and top-level composition only.

Targets:

- `page.tsx` under 150 lines;
- `ChatSurface.tsx` under 350 lines;
- transcript loading/empty/error branching in `ChatTranscriptState.tsx`;
- no service calls from presentation components.

Verify:

```bash
pnpm --dir frontend test -- ChatPage
pnpm --dir frontend type-check
```

Commit:

```bash
git add frontend/app/'(dashboard)'/chat/page.tsx frontend/src/components/chat
git commit -m "refactor(chat): reduce the route to composition"
```

### Task 5.4: Split the 1,863-line Zustand store behind its stable export

**Files:**

- Create: `frontend/src/store/chat/types.ts`
- Create: `frontend/src/store/chat/initialState.ts`
- Create: `frontend/src/store/chat/requestCoordinator.ts`
- Create: `frontend/src/store/chat/slices/selectionSlice.ts`
- Create: `frontend/src/store/chat/slices/workspaceSlice.ts`
- Create: `frontend/src/store/chat/slices/conversationSlice.ts`
- Create: `frontend/src/store/chat/slices/threadSlice.ts`
- Create: `frontend/src/store/chat/slices/messageSlice.ts`
- Create: `frontend/src/store/chat/slices/streamingSlice.ts`
- Create: `frontend/src/store/chat/selectors.ts`
- Modify: `frontend/src/store/chat-store.ts`
- Preserve: all imports from `@/store/chat-store`

**Step 1: Move pure types, selectors, and request coordination.**

Move code without changing behavior. Keep `AbortController`, request generations, and newest-page request identity outside Immer state.

**Step 2: Extract slices in dependency order.**

Selection/workspace/conversation/thread first, then messages, then streaming. Each slice uses typed `set/get` creators and calls the existing `workspaceService`/streaming adapter. Do not introduce Query-backed duplication for streaming state in this PR.

**Step 3: Keep `chat-store.ts` as the compatibility façade.**

It creates the persisted store, combines slices, applies rehydration migration, and re-exports selectors/types. Existing callers remain unchanged.

**Step 4: Run store tests after every slice.**

```bash
pnpm --dir frontend test -- chat-store
```

Commit after logical slice groups:

```bash
git commit -m "refactor(chat): extract store types and coordination"
git commit -m "refactor(chat): split workspace and thread store slices"
git commit -m "refactor(chat): split message and streaming store slices"
```

### Task 5.5: Mutation-verify the stale-response and terminal-reconciliation guards

**Files:**

- Modify: `frontend/src/hooks/__tests__/useChatSession.threadSwitchBleed.test.tsx`
- Modify: `frontend/src/store/__tests__/chat-store-refresh.test.ts`
- Create: `docs/testing/chat-mutation-checks.md`

Ensure the tests control resolution order: start thread A, switch to B, resolve B, then resolve A. Assert A cannot replace B or clear B's loading state. For terminal reconciliation, resolve the terminal persistence response after a newer optimistic turn and assert identity-based merge preserves the newer turn.

Manually mutation-verify both tests:

1. temporarily remove the request identity/generation guard;
2. run the named test and observe failure;
3. restore the guard;
4. rerun and observe pass;
5. confirm `git diff` contains no mutation.

Document the exact guard location and focused command in `docs/testing/chat-mutation-checks.md`.

Commit:

```bash
git add frontend/src/hooks/__tests__/useChatSession.threadSwitchBleed.test.tsx \
  frontend/src/store/__tests__/chat-store-refresh.test.ts docs/testing/chat-mutation-checks.md
git commit -m "test(chat): mutation-verify async reconciliation guards"
```

### Task 5.6: Add critical Playwright journeys

**Files:**

- Modify or create: `tests/e2e/tests/chat-thread-switch.spec.ts`
- Modify or create: `tests/e2e/tests/chat-hitl.spec.ts`

Use accessible locators and web-first assertions. Cover a rapid thread switch with delayed responses and one approve/reject HITL journey. Keep network timing controlled through route interception; do not use fixed sleeps.

Run:

```bash
pnpm --dir tests/e2e exec playwright test \
  tests/chat-thread-switch.spec.ts tests/chat-hitl.spec.ts --project=chromium
```

Commit:

```bash
git add tests/e2e/tests/chat-thread-switch.spec.ts tests/e2e/tests/chat-hitl.spec.ts
git commit -m "test(chat): cover critical thread and HITL journeys"
```

### PR 5 verification

```bash
pnpm --dir frontend lint
pnpm --dir frontend type-check
pnpm --dir frontend test -- ChatPage useChatSession useChatStreaming chat-store
pnpm --dir frontend test:coverage -- --coverage.reporter=json-summary
node scripts/ci/check_frontend_coverage.mjs frontend/coverage/coverage-summary.json
pnpm --dir tests/e2e exec playwright test \
  tests/chat-thread-switch.spec.ts tests/chat-hitl.spec.ts --project=chromium
git diff --check origin/develop...HEAD
```

---

## PR 6: Durable engineering standards and ownership

### Task 6.1: Write concise backend/frontend standards

**Files:**

- Create: `docs/engineering/backend.md`
- Create: `docs/engineering/frontend.md`
- Create: `docs/engineering/testing.md`
- Create: `docs/engineering/api-contracts.md`
- Create: `docs/engineering/README.md`
- Modify: `AGENTS.md`
- Modify: `README.md`

Document only enforced practices:

- router/service/query ownership and transaction order;
- mandatory tenant scope and async session ownership;
- generated HTTP types vs frontend-only domain types;
- canonical chat writer and terminal reconciliation;
- state ownership across TanStack Query/Zustand/component state;
- changed-file and coverage ratchets;
- mutation verification for race/idempotency tests;
- pnpm/Node commands and local-to-CI parity.

Link the standards from `AGENTS.md` and the root README instead of duplicating long rules.

### Task 6.2: Add ownership and architecture guards

**Files:**

- Create or modify: `.github/CODEOWNERS`
- Create: `backend/tests/unit/architecture/test_maintenance_contracts.py`
- Create: `frontend/src/test/architecture/maintenanceContracts.test.ts`

Backend guards:

- workspace routers cannot own transactions or SQL queries;
- scope helpers require organization/user arguments;
- compatibility exports resolve.

Frontend guards:

- chat route does not import API services directly;
- `chat-store.ts` remains a façade, not a second monolith;
- generated files are never hand-authored imports into presentation components when a domain adapter exists;
- active scripts contain no npm fallback.

Keep guards semantic and narrow; avoid brittle snapshots of full source text.

### Task 6.3: Run the complete maintenance acceptance suite

```bash
ruff check backend/src
black --check backend/src
isort --check-only backend/src
pytest -q backend/tests/unit/ci backend/tests/unit/architecture
pytest -q backend/tests/unit/api/test_workspace_*.py backend/tests/api/threads
pytest -q backend/tests/unit/services/threads
python scripts/ci/generate_openapi.py --check
pnpm install --frozen-lockfile
pnpm --dir frontend generate:api-types
git diff --exit-code -- backend/openapi.json frontend/src/types/generated/api.d.ts
pnpm --dir frontend lint
pnpm --dir frontend type-check
pnpm --dir frontend test:coverage -- --coverage.reporter=json-summary
node scripts/ci/check_frontend_coverage.mjs frontend/coverage/coverage-summary.json
pnpm --dir tests/e2e exec playwright test \
  tests/chat-thread-switch.spec.ts tests/chat-hitl.spec.ts --project=chromium
pre-commit run --all-files
git diff --check origin/develop...HEAD
```

Run the full-tree MyPy report separately and record its baseline result; it remains
advisory until the baseline reaches zero:

```bash
mypy backend/src --ignore-missing-imports
```

Expected: all blocking checks pass; any remaining advisory full-tree debt is explicitly labeled and no worse than its committed baseline.

### Task 6.4: Commit and prepare handoff

```bash
git add docs/engineering README.md AGENTS.md .github/CODEOWNERS \
  backend/tests/unit/architecture frontend/src/test/architecture
git commit -m "docs: codify enforceable engineering standards"
```

In the PR description, include:

- the six merged PR links;
- before/after file sizes for the workspace router, `ChatService`, chat page, and chat store;
- quality baseline deltas;
- mutation checks performed and the tests they killed;
- any compatibility exports intentionally retained and their removal condition.

---

## Final completion checklist

- [ ] Node 24 and pnpm 10.18.2 agree across metadata, CI, docs, and active Docker builds.
- [ ] Root `pnpm-lock.yaml` is the only JavaScript lock authority.
- [ ] Next/React/ESLint packages resolve to one compatible version set.
- [ ] Critical Ruff errors and changed-file quality checks block merges.
- [ ] Existing lint/type/coverage debt cannot grow silently.
- [ ] OpenAPI and generated TypeScript drift are both blocking.
- [ ] Workspace HTTP clients use generated contract aliases.
- [ ] Workspace routers contain transport concerns, not SQL/transactions.
- [ ] `ChatService` compatibility delegates instead of duplicating business logic.
- [ ] Chat page and store are composition façades with stable public imports.
- [ ] Backend remains the sole persisted-chat writer.
- [ ] Stale-response and terminal-reconciliation tests are mutation-verified.
- [ ] Current engineering documentation describes commands that actually run.
- [ ] Every PR can be reverted without reverting the whole program.
