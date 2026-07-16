# Maintainability Foundation — Plan Amendments (2026-07-16)

**Status:** Reviewed against the executed PRs 1–3, a four-agent recon pass over the
current tree, and direct file-existence verification. The base plan
(`2026-07-15-maintainability-foundation.md`) remains authoritative except where
amended below. Each amendment cites measured evidence, per the plan's own rule:
*"If current baseline measurements differ from this plan, record the measured
value and ratchet from that value."*

## Verified accurate (no change)

- Line counts exact: `workspaces.py` = 2,517; `chat-store.ts` = 1,863.
- Task 5.1's five "Modify" test files all exist at the named paths.
- `backend/tests/api/threads/` (12 files), `test_workspace_member_readd.py`,
  `test_workspace_tenant_scope.py` all exist — 4.1's reuse instruction is sound.
- `tests/e2e/package.json` exists with Playwright; 5.6's runner path is valid.
- The plan already accounts for `standalone_router` and the
  `/api/v2/threads/*` route-order collision (4.1 Step 1) — recon confirms both.
- Generated schema keys (incl. `src__schemas__chat__ThreadListResponse`) exact.

## A1 — Executed deviations in PRs 1–3 (historical record)

- **2.2 MyPy gate:** blocking changed-file mypy was unimplementable as written —
  mypy follows imports (5,248 tree-wide errors) and touched legacy files carry
  529 scoped errors. Implemented: **blocking for added `.py` files only**
  (`--follow-imports=silent`); modified files stay under the advisory full-tree
  lane. `changed_source_files.py` grew `--kind python-added`.
- **2.3:** tsconfig-exclusion growth is enforced by
  `scripts/ci/check_tsconfig_exclusions.py` (Task 2.1), not duplicated in the
  ESLint comparator.
- **2.1:** 18 of 63 recorded production exclusions matched nothing on disk
  (long-deleted files) — pruned rather than baselined.
- **Test placement:** frontend quality tests live under
  `src/test/quality/__tests__/` (vitest workspace include patterns), not the
  plan's exact paths.
- **Branching:** PRs 2+ stack on the previous PR's branch (shared files:
  `test-pipeline.yml`, `frontend/package.json`) instead of branching from
  `origin/develop` while predecessors are unmerged. The "do not stack" rule is
  interpreted as *one branch per PR*, with GitHub bases forming a merge train.

## A2 — Task 4.3: canonical-semantics rule (highest-risk correction)

Plan Step 2.2 says *"move the existing ChatService implementation into the
resource service"* and Step 2.3 *"replace duplicate router SQL with a service
call."* Applied literally, this **changes router behavior**, because router and
`ChatService` copies diverge in eight measured ways, including:

- `ChatService.list_workspaces` omits the `WorkspaceMember.is_deleted == False`
  join filter the router applies — a removed member would regain visibility;
- `ChatService.delete_*` never stamps `deleted_at` (router does);
- conversation list ordering differs (router: activity only; service:
  pinned-first);
- the `create_workspace` org-match guard exists only in the router.

**Amendment:** consolidation is per-concern. For endpoints the router serves,
**router semantics are canonical**. Pre-existing `ChatService` callers
(`conversations.py` delegating endpoints, `project_chat.py`, stream services)
keep their observed behavior — where a true conflict exists, the service method
takes an explicit flag defaulting to the old behavior for old callers. Every
divergence decision is recorded in the commit message. Characterization tests
for existing service callers are written **before** any move.

## A3 — Task 4.2/4.4: preservation additions

- The **lazy in-function `get_chat_service` imports** (workspaces.py L803,
  L2032) are deliberate circular-import avoidance — must remain in-function in
  whichever module receives them.
- Nested `create_message` carries `deprecated=True` asserted by an existing
  OpenAPI contract test — the flag must survive the split.
- `main.py` registration order is load-bearing (`threads_router` before
  `workspaces_standalone_router`); 4.1's contract test encodes it.
- 4.4's guard ("no `select()`/model imports in route modules") applies to the
  **post-4.3 end state**; encode the actual rule the code establishes, scoped
  to the modules 4.3 actually cleared, with the ratchet condition documented.

## A4 — Task 5.2: hooks directory already exists

`frontend/src/hooks/chat/` already contains `chatTypes.ts`, `useChatSession.ts`,
`useChatStreaming.ts`, `useChatThreadActions.ts` + `__tests__/`. New hooks join
this directory following its patterns. Where a concern is already owned by an
existing hook, adopt it — do not create a twin. `useChatStreaming.ts` guard
internals (16 recon-located guards) are not to be modified.

## A5 — Tasks 5.6 / 6.3: local execution limits

No Docker and no full stack run locally. Playwright journeys are validated by
`playwright test --list` + typecheck locally; **CI is the executing authority**.
`pre-commit run --all-files` in 6.3 will fail on full-tree Black/isort legacy
debt by design (hooks are staged-file-scoped); the acceptance run uses
changed-file scope and records full-tree results as the advisory baseline.

## A6 — PR 4 verification: mypy line

`mypy backend/src/api/threads backend/src/services/threads` over legacy modules
is expected red (subset of the 5,248 advisory baseline). Replace with the
implemented gate: mypy clean on **added** files; full-dir output recorded as
advisory baseline in the PR description.

## A7 — Tasks 6.1/6.4: AGENTS.md is untracked and stale

`AGENTS.md` exists only as an **untracked** file in the main checkout and its
content is outdated (claims staging is live; staging was retired in #442).
`git add AGENTS.md` would commit stale local-only instructions.
**Amendment:** standards link from `README.md` and `CLAUDE.md` (tracked);
`AGENTS.md` is not staged. Standards docs land at `docs/engineering/` exactly
as planned (backend, frontend, testing, api-contracts, README).

## A8 — Task 6.2: npm-fallback guard already exists

"Active scripts contain no npm fallback" is enforced by
`backend/tests/unit/ci/test_toolchain_contract.py` (PR 1). The frontend
maintenance-contract test references it instead of reimplementing it.

## A9 — PR 6 base

PR 6 branches from PR 4's tip and merges PR 5's branch (disjoint trees — the
merge must be conflict-free or the step aborts). Bases retarget as the train
merges.
