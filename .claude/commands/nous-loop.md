---
description: Run one self-improvement tick — find one real bug, fix it in a tight tested PR, review, merge when green
---

# /nous-loop — autonomous self-improvement tick

A single iteration of the standing NOUS self-improvement loop: find **one** real,
live bug, fix it in a small tested PR, review it before merge, merge when green.
One tick = one merged PR (or a deliberate "nothing safe to ship, here's why").

Run with the bundled `/loop` skill to schedule repeats
(`/loop by doing self improvement`), or invoke `/nous-loop` directly for a single tick.

Branch from `develop`; PRs target `develop` (ArgoCD auto-syncs `dev` + `staging`).

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
git checkout develop && git pull
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

3. **Verify it's real AND live.** Re-read the cited code — memory drifts (wrong
   file/line, already-fixed, **dead/unmounted code**). Confirm the path is mounted
   and reachable in `src/main.py` before treating a finding as a live bug. Then
   **claim it** (`loop_bridge.py claim ...`) before writing any code; on `CONFLICT`,
   go back to step 2 and pick another.

4. **Ultra-code debug it.** For non-trivial or security-class bugs, run the
   `Workflow` tool: parallel adversarial lenses verify exploitability + fix
   completeness + hunt sibling paths, then synthesize a crisp fix spec.

5. **Fix in a tight, tested PR.** Smallest change that closes it. Add a regression
   test that fails before / passes after. Match surrounding style (Black 88, isort,
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

6. **Review before merge** (mandatory):
   - `pr-review-toolkit:code-reviewer` agent on the diff.
   - `security-review` skill for any security-class fix (tenant scope, authz,
     secrets, injection) — **in addition** to the code-reviewer.
   - Read CodeRabbit's PR comments.
     Address real findings; a clean review is the gate, not a formality.

7. **Merge when green.** Wait for full CI (lint → unit → integration → e2e).
   Squash-merge + delete branch only at `mergeStateStatus: CLEAN`. While the PR is
   open across ticks, `loop_bridge.py heartbeat --branch <b>` keeps the claim live.

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

## Commit / PR footers

- Commit: end with
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- PR body: end with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
