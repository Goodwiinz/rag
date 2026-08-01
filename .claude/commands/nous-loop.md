---
description: Run one self-improvement tick — find one real bug, fix it in a tight tested PR, review, merge when green
---

# /nous-loop — autonomous self-improvement tick

A single iteration of the standing NOUS self-improvement loop: find **one** real,
live bug, fix it in a small tested PR, review it before merge, merge when green.
One tick = one merged PR (or a deliberate "nothing safe to ship, here's why").

Run with the bundled `/loop` skill to schedule repeats
(`/loop by doing self improvement`), or invoke `/nous-loop` directly for a single tick.

Branch from `develop`; PRs target `develop` (ArgoCD auto-syncs `dev`; staging/prod
apps were retired in #442).

## Environment reality (check this before trusting any signal)

- **GitHub Actions has been dead since 2026-07-29** — every job fails in seconds
  with `steps: []` and 404 logs, on `develop` too. **A red PR is not a broken PR.**
  The real gate is local: `scripts/ci/run_local_ci.sh --base origin/develop`
  (repo `.venv` on PATH). Never block a PR on a red check without reproducing the
  failure locally, and never claim CI-green when Actions is the only evidence.
- **`/home/clawdbot/rag-clean` is a stale shared checkout** (two loops share it and
  nobody pulls). **Fresh-clone for every PR** and hand audit subagents that path:
  `git clone --depth 30 -b develop https://github.com/Goodwiinz/rag.git`
  into the scratchpad. An audit run against the stale tree reports bugs that were
  fixed days ago.
- **`gh pr create` fails** ("Permission denied" statting the worktree). Build the
  JSON and pipe it: `… | gh api -X POST repos/Goodwiinz/rag/pulls --input -`.
  `--input <path>` also fails — only `-` (stdin) works.
- Frontend: pnpm workspace is `node-linker=hoisted`, so binaries live at the **repo
  root** — run `../node_modules/.bin/vitest` from `frontend/`. `pnpm install` at the
  frontend dir alone installs almost nothing; install from the repo root.

## Coordination (multiple loops share this repo)

More than one loop may run at once (e.g. `clawd` + `zcode`). They collide in the
**pick → open-PR window**: `gh pr list` only shows work that already has a PR, so
two loops can pick the same bug before either opens one. Use the shared claims
bridge (`scripts/loop_bridge.py`, storage `$LOOP_BRIDGE_DIR`, default
`/home/clawdbot/.loop-bridge`) — flock-guarded, on the shared filesystem both
agents see. Set `LOOP_AGENT` to your name (`clawd` / `zcode`).

> **macOS**: the default bridge dir doesn't exist — always
> `export LOOP_BRIDGE_DIR="$HOME/.loop-bridge" LOOP_AGENT=<name>` first.
> The script also resolves paths relative to CWD; run it from the repo root.

- **Before picking** a bug: `loop_bridge.py list` to see what the other loop holds.
- **Before touching code** (right after you've chosen): `loop_bridge.py claim
--branch <b> --area "<bug/subsystem>" --files <a,b>`. If it prints `CONFLICT`
  (exit 2 — same area or an overlapping file is already claimed), **pick something
  else**. The claim is the reservation; `gh pr list` is the second check.
- **Each tick while the PR is open**: `loop_bridge.py heartbeat --branch <b>` so
  the claim doesn't expire (TTL 45m; a crashed loop's claims auto-expire).
- **On merge or abandon**: `loop_bridge.py release --branch <b> --reason merged`.

```bash
git -C <shared-checkout> fetch origin develop   # bridge + scripts only; do NOT
                                                # write code here, it is stale
loop_bridge=scripts/loop_bridge.py
python3 $loop_bridge list                                     # what is the other loop on?
gh pr list --repo Goodwiinz/rag --state open --author '@me'   # any green loop PR to merge first?
```

1. **Merge first.** If a previous tick's PR is green + approved, squash-merge it
   (`gh pr merge <n> --squash --delete-branch`), sync `develop`, update memory, done.
   Only merge **loop-opened** PRs — never the Palette/Sentinel bot-fleet or
   unrelated human PRs without explicit consent.
   In interactive Claude Code sessions the permission classifier blocks
   self-merging PRs authored in the same session — expected; hand the merge
   to the human with a status line instead of retrying.

2. **Find ONE bug.** In priority order:
   - **Trace-driven** — a real failure in `rag-agent-dev` LangSmith traces from the
     synthetic-traffic CronJob (the canonical source).
   - **Backlog** — a verified-open item from the auto-memory hunt backlogs.
   - **Fresh hunt** — an adversarial bug-hunt (`Workflow` tool) on an unmined
     subsystem when the backlogs are dry.

   **Look for the fake-success shape first** — it is this codebase's dominant bug
   class: the work does not happen, and something reports success anyway (a 200 with
   a job that never ran, a flag set without the artifact, an endpoint that cannot
   succeed by construction, a test that mocks away the very gate it claims to test).
   Verify against the artifact — query the DB row, read the delivered payload — not
   the status flag. The best finds come from **running** the system, not reading it.

3. **Verify it's real AND live.** Re-read the cited code — memory drifts (wrong
   file/line, already-fixed, **dead/unmounted code**). Confirm the path is mounted
   and reachable in `src/main.py` before treating a finding as a live bug. Then
   **claim it** (`loop_bridge.py claim ...`) before writing any code; on `CONFLICT`,
   go back to step 2 and pick another.

4. **Ultra-code debug it.** For non-trivial or security-class bugs, run the
   `Workflow` tool: parallel adversarial lenses verify exploitability + fix
   completeness + hunt sibling paths, then synthesize a crisp fix spec.

   **Delegation shape that works** (proven on the 2026-07-29 auth sweep, 5 findings
   → 5 PRs): parallel **Fable** scouts, one per subsystem slice, read-only, each
   told to report `FILE:LINE | what happens | user-visible symptom | how a user
   triggers it | confidence` **and to name what it checked and found CLEAN**; then a
   Fable planner that re-verifies each finding and splits AUTONOMOUS-SAFE from
   NEEDS-A-HUMAN-DECISION; then **Opus** to implement, one branch per coherent
   group. Give the implementer the plan plus "the plan is a plan, not scripture —
   if a step is wrong when you see the real code, say so and do the right thing".
   Two scouts independently ranking the same finding #1 is a strong signal.
   Always hand subagents the **fresh clone** path, and tell them not to push or
   open PRs — you review the diff and open it yourself.

5. **Fix in a tight, tested PR.** Smallest change that closes it. Add a regression
   test that fails before / passes after — and **prove it**: revert the production
   change alone, paste the failing output, restore, show it green. A test that
   passes both ways is a contract lock, not a proof; say so explicitly rather than
   presenting it as evidence. Never assert "verified" without pasted command
   output. Match surrounding style (Black 88, isort,
   structlog; tenant scope mandatory — org from the authenticated user, never client
   input). `cd backend && python3 -m black <touched>`.
   On a workstation with the main-repo venv (`backend/.venv`, py3.12,
   includes `langgraph`), agent unit tests run locally through it
   (`backend/.venv/bin/python -m pytest tests/unit/agent/...`). Only if a specific
   import is missing fall back to standalone validation (`python3 -c ...`);
   CI confirms either way.
   Alembic gotcha: when adding a migration, parse `down_revision` as a
   literal (it can be a TUPLE on merge migrations) before picking a chain
   point — chain onto a leaf whose ancestry contains every column you
   touch, never onto an already-merged internal node (PR #986 review).

   Test-shape gotchas that have burned ticks:
   - Frontend store tests live in the **singular** `frontend/src/store/__tests__/`;
     `src/components/auth/__tests__/LoginPage.test.tsx` covers the react-router
     `src/page-components/…`, **not** the app-router `app/(auth)/…` page. Check
     which component a test file actually imports before extending it.
   - A route-existence assertion that walks `app.routes` passes even when the route
     exists — this FastAPI version keeps `include_router` results as lazy
     `_IncludedRouter` entries. Assert against `app.openapi()`.
   - Removing a backend route means regenerating `backend/openapi.json` **and**
     `frontend/src/types/generated/api.d.ts`; both are checked in and CI-enforced
     (`openapi-contract` job runs `generate_openapi.py --check`, then
     `pnpm generate:api-types` + `git diff --exit-code`).
   - Supabase provisioning: `supabase/migrations/…_handle_new_user_trigger.sql`
     installs `on_auth_user_created`, which provisions `public.users` /
     `organizations` **before** the backend ever sees a token. Check whether that
     trigger already handles a case before calling a provisioning bug "live".

6. **Review before merge** (mandatory):
   - `pr-review-toolkit:code-reviewer` agent on the diff.
   - `security-review` skill for any security-class fix (tenant scope, authz,
     secrets, injection) — **in addition** to the code-reviewer.
   - Read CodeRabbit's PR comments.
     Address real findings; a clean review is the gate, not a formality.

7. **Merge when green.** Normally: full CI (lint → unit → integration → e2e), then
   squash-merge + delete branch at `mergeStateStatus: CLEAN`. **While Actions is
   down** (see Environment reality) the checks are red for everyone including
   `develop` — substitute `scripts/ci/run_local_ci.sh --base origin/develop` as the
   gate, say in the PR which gate you actually ran, and leave the merge to the human
   rather than merging past red checks on your own. While the PR is open across
   ticks, `loop_bridge.py heartbeat --branch <b>` keeps the claim live.
   Stacked PRs are CI-blind: a base other than `develop` gets zero real checks and
   no CodeRabbit, retargeting does not re-trigger CI (close/reopen does), and
   merging a child right after its parent lands it on the stale branch — verify the
   files exist on `develop` after merging a stack.

8. **Record + reschedule.** `loop_bridge.py release --branch <b> --reason merged`.
   Mark the item done in auto-memory (`memory/nous-*.md` + `MEMORY.md` index); note
   any sibling bugs found for next tick. If looping, `ScheduleWakeup` (~1500s idle,
   ~270s when polling CI to keep the prompt cache warm).

## Guardrails

- No autonomous `kubectl` secret dumps; no prod merges or bulk operations without
  explicit per-action consent.
- Never ship a "fix" for dead/unmounted code as if it were live — say so and pick
  something real instead.
- Report outcomes faithfully: if a review finds a problem in your own fix, fix it;
  if a tick is dry, say so with the reason rather than shipping a marginal PR.
- A pasted LangSmith / API token must be rotated, not reused.
- Never run heavy analysis via `kubectl exec` in the live backend pod — it has
  OOM-killed dev.
- Subagent reports are leads, not facts. Two agents this session asserted things
  that were wrong on inspection (a "squash-merged" branch that was never merged;
  a severity that a DB trigger already covered). Spot-check the diff and the
  claim that carries the most weight before it reaches the PR body.

## Commit / PR footers

- Commit: end with
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
- PR body: end with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
