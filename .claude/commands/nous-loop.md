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

## Tick procedure

```bash
git checkout develop && git pull
gh pr list --repo Goodwiinz/rag --state open --author '@me'   # any green loop PR to merge first?
```

1. **Merge first.** If a previous tick's PR is green + approved, squash-merge it
   (`gh pr merge <n> --squash --delete-branch`), sync `develop`, update memory, done.
   Only merge **loop-opened** PRs — never the Palette/Sentinel bot-fleet or
   unrelated human PRs without explicit consent.

2. **Find ONE bug.** In priority order:
   - **Trace-driven** — a real failure in `rag-agent-dev` LangSmith traces from the
     synthetic-traffic CronJob (the canonical source).
   - **Backlog** — a verified-open item from the auto-memory hunt backlogs.
   - **Fresh hunt** — an adversarial bug-hunt (`Workflow` tool) on an unmined
     subsystem when the backlogs are dry.

3. **Verify it's real AND live.** Re-read the cited code — memory drifts (wrong
   file/line, already-fixed, **dead/unmounted code**). Confirm the path is mounted
   and reachable in `src/main.py` before treating a finding as a live bug.

4. **Ultra-code debug it.** For non-trivial or security-class bugs, run the
   `Workflow` tool: parallel adversarial lenses verify exploitability + fix
   completeness + hunt sibling paths, then synthesize a crisp fix spec.

5. **Fix in a tight, tested PR.** Smallest change that closes it. Add a regression
   test that fails before / passes after. Match surrounding style (Black 88, isort,
   structlog; tenant scope mandatory — org from the authenticated user, never client
   input). `cd backend && python3 -m black <touched>`.
   Local env lacks `langgraph`/`spacy`/`libpq` — `tests/unit/` pytest fails locally
   on those imports; validate test logic standalone (`python3 -c ...`), CI confirms.

6. **Review before merge** (mandatory):
   - `pr-review-toolkit:code-reviewer` agent on the diff.
   - `security-review` skill for any security-class fix (tenant scope, authz,
     secrets, injection) — **in addition** to the code-reviewer.
   - Read CodeRabbit's PR comments.
     Address real findings; a clean review is the gate, not a formality.

7. **Merge when green.** Wait for full CI (lint → unit → integration → e2e).
   Squash-merge + delete branch only at `mergeStateStatus: CLEAN`.

8. **Record + reschedule.** Mark the item done in auto-memory
   (`memory/nous-*.md` + `MEMORY.md` index); note any sibling bugs found for next
   tick. If looping, `ScheduleWakeup` (~1500s idle, ~270s when polling CI to keep
   the prompt cache warm).

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
