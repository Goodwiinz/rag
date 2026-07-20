# Nightly CI Failures Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore the frontend typecheck lane after the TypeScript 7 dependency update and prevent stale permissions from blocking the scheduled agent regression checkout.

**Architecture:** Ship two independent changes. First, make the frontend compiler configuration valid under both the current TypeScript 5.9 lock and the proposed TypeScript 7 update, and align GitHub Actions with the repository's Node 24 contract. Second, add a guarded, tested pre-job cleanup hook for the persistent self-hosted runner, deploy it operationally, and verify the eval workflow reaches the regression tests.

**Tech Stack:** GitHub Actions, pnpm 10.18.2, Node.js 24, TypeScript 5.9/7, Bash, GitHub Actions self-hosted runner hooks

---

## Scope and evidence

- Observed: `Test Pipeline` run `29230637820`, job `Lint Frontend`, failed in `Run type check` on SHA `08d6feaa6e301eb54c9356484272df7eda43f8d7` with `TS5108` for `target=ES5` and `TS5102` for `downlevelIteration` and `baseUrl`.
- Observed: that SHA raises `frontend/package.json` from TypeScript 5 to `^7.0.2`; its root workspace lock resolves `typescript@7.0.2`.
- Observed: `.github/workflows/test-pipeline.yml` runs Node 20, while the root and frontend package manifests declare Node `24.x`.
- Observed: `Agent Regression Eval` run `29231195443` failed before tests in checkout with `fatal: --local can only be used inside a git repository`, followed by `EACCES` unlinking `.git/objects`.
- Observed: `.github/workflows/agent-eval.yml` selects `[self-hosted, linux]`, and `infrastructure/runner/README.md` documents that matching runner as a persistent droplet runner.
- Suspected: the eval failure came from stale or foreign-owned files in the persistent runner workspace. Confirm ownership on the host before applying the one-time repair.
- Out of scope: the Dependabot updater's `digitalocean/action-doctl | unknown_error | null`. Revisit only if it blocks a required update or repeats with actionable logs.

## Wiki-derived constraints

- `[[nous-ci-and-devops]]` identifies frontend typecheck as a hard merge gate and says frontend CI must use root-workspace `pnpm`; do not substitute `npm`, create a second lockfile, or move overrides out of `pnpm-workspace.yaml`.
- `[[nous-workflow-conventions]]` requires implementation work to start from fresh `origin/develop` in an isolated worktree. Do not base the fix on a drifting local `develop`, and do not use `git pull`, `git checkout`, or `git reset` to prepare it.
- In a worktree, use the root workspace dependency graph. Prefer a frozen root `pnpm` install; if reusing an existing install, verify that root `node_modules` is available rather than trusting a partial `frontend/node_modules`.
- The wiki's `nous-ci-and-devops` validation section still lists `npm` commands, which conflicts with its explicit pnpm-only rule and the current repository's `packageManager: pnpm@10.18.2`. Treat those command spellings as stale and use the `corepack pnpm` commands in this plan.
- Canonical source checkout recorded by the wiki: `/Users/goodwiinz/development/RAG_system`. Execute this plan in a dedicated worktree created from that repository, not directly in the canonical checkout.

## Delivery boundaries

- PR 1: frontend compiler compatibility and Node version alignment.
- PR 2: runner cleanup hook, tests, and operations documentation.
- Operational rollout: install the hook and repair the runner only after PR 2 is reviewed. Do not combine host mutations with the frontend PR.

Before either PR, run:

```bash
git fetch origin
git worktree add -b codex/fix-nightly-ci \
  ../rag-fix-nightly-ci origin/develop
```

Expected: the new worktree is clean and its merge base is the current `origin/develop`. Use a separate `codex/harden-eval-runner` branch/worktree for PR 2 so the two tracks remain independently reviewable.

### Task 1: Make the TypeScript configuration forward-compatible

**Files:**

- Modify: `frontend/tsconfig.json:3`
- Modify: `frontend/tsconfig.json:12`
- Modify: `frontend/tsconfig.json:26`

**Step 1: Capture the existing failure contract**

On a temporary worktree at failed SHA `08d6feaa6e301eb54c9356484272df7eda43f8d7`, run:

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm --filter multimodal-rag-frontend run type-check
```

Expected: failure includes exactly the three configuration diagnostics `TS5108`/`TS5102` before normal project diagnostics. Preserve the complete output in the task notes because additional TypeScript 7 errors may be masked by invalid compiler options.

**Step 2: Apply the minimal compiler-option changes**

Change the relevant section to:

```json
{
  "compilerOptions": {
    "target": "es2015",
    "lib": [
      "dom",
      "dom.iterable",
      "es6"
    ],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true
  }
}
```

Keep all existing options not shown above. Specifically:

- Raise `target` from `es5` to `es2015`.
- Delete `downlevelIteration`; ES2015 output already has native iteration support.
- Delete `baseUrl`; every existing `paths` target is already explicitly relative (`./...`).
- Do not change aliases, `include`, or `exclude` in this task.

**Step 3: Verify against the current lock**

Run from the repository root:

```bash
corepack pnpm install --frozen-lockfile
corepack pnpm --filter multimodal-rag-frontend run type-check
```

Expected: the current TypeScript 5.9 typecheck passes and all `@/...` aliases still resolve.

**Step 4: Verify against the TypeScript 7 dependency branch**

Apply the same `tsconfig.json` change on top of SHA `08d6feaa6e301eb54c9356484272df7eda43f8d7`, then run:

```bash
corepack pnpm install --frozen-lockfile
corepack pnpm --filter multimodal-rag-frontend run type-check
```

Expected: the three removed-option diagnostics are absent. If new TypeScript 7 source diagnostics appear, record and triage them as a separate compatibility task; do not broaden this configuration patch without concrete errors.

**Step 5: Commit**

```bash
git add frontend/tsconfig.json
git commit -m "fix(frontend): modernize TypeScript compiler options"
```

### Task 2: Align the CI runtime with the package contract

**Files:**

- Modify: `.github/workflows/test-pipeline.yml:31`

**Step 1: Update the workflow runtime**

Change:

```yaml
NODE_VERSION: "20"
```

to:

```yaml
NODE_VERSION: "24"
```

Do not alter package manager setup or cache paths. The repository already pins `pnpm@10.18.2` and both package manifests require Node `24.x`.

**Step 2: Validate the workflow and frontend lane**

Run:

```bash
actionlint .github/workflows/test-pipeline.yml
corepack pnpm install --frozen-lockfile
corepack pnpm --filter multimodal-rag-frontend run type-check
corepack pnpm --filter multimodal-rag-frontend run lint
```

Expected: `actionlint` and typecheck pass. Lint may report the repository's allowed warnings but must not fail due to the Node change.

**Step 3: Commit**

```bash
git add .github/workflows/test-pipeline.yml
git commit -m "ci: align frontend jobs with Node 24"
```

**Step 4: Verify PR 1 in GitHub Actions**

Push PR 1 and wait for `Lint Frontend` to pass. Confirm downstream frontend, integration, and E2E jobs are scheduled rather than skipped by the former lint gate. If the dependency-update PR is still open, rebase it after PR 1 lands and re-run its checks.

### Task 3: Add a guarded runner workspace cleanup hook

**Files:**

- Create: `infrastructure/runner/hooks/cleanup-workspace.sh`
- Create: `infrastructure/runner/tests/test_cleanup_workspace.sh`
- Create: `.github/workflows/runner-smoke.yml`
- Modify: `infrastructure/runner/README.md:68`

**Step 1: Write the failing shell test**

Create a test that covers these contracts:

```bash
#!/usr/bin/env bash
set -euo pipefail

HOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/hooks/cleanup-workspace.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

WORK_ROOT="$TMP/_work"
WORKSPACE="$WORK_ROOT/rag/rag"
mkdir -p "$WORKSPACE/.git/objects"
touch "$WORKSPACE/.git/objects/stale"

RUNNER_WORK_ROOT="$WORK_ROOT" GITHUB_WORKSPACE="$WORKSPACE" bash "$HOOK"
test -d "$WORKSPACE"
test -z "$(find "$WORKSPACE" -mindepth 1 -print -quit)"

if RUNNER_WORK_ROOT="$WORK_ROOT" GITHUB_WORKSPACE="$TMP/outside" bash "$HOOK"; then
  echo "hook accepted a workspace outside the runner work root" >&2
  exit 1
fi
```

**Step 2: Run the test to verify it fails**

```bash
bash infrastructure/runner/tests/test_cleanup_workspace.sh
```

Expected: failure because the hook does not exist.

**Step 3: Implement the hook**

Create a Bash hook with this behavior:

```bash
#!/usr/bin/env bash
set -euo pipefail

RAW_WORK_ROOT="${RUNNER_WORK_ROOT:-$HOME/actions-runner/_work}"
RAW_WORKSPACE="${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}"
mkdir -p "$RAW_WORK_ROOT"
if [[ ! -d "$RAW_WORKSPACE" ]]; then
  echo "::error::Runner workspace does not exist: $RAW_WORKSPACE" >&2
  exit 1
fi
WORK_ROOT="$(cd "$RAW_WORK_ROOT" && pwd -P)"
WORKSPACE="$(cd "$RAW_WORKSPACE" && pwd -P)"

case "$WORKSPACE/" in
  "$WORK_ROOT/"*) ;;
  *)
    echo "::error::Refusing to clean workspace outside $WORK_ROOT: $WORKSPACE" >&2
    exit 1
    ;;
esac

FOREIGN_FILE="$(find "$WORKSPACE" -xdev ! -user "$(id -un)" -print -quit)"
if [[ -n "$FOREIGN_FILE" ]]; then
  echo "::error::Runner workspace contains files not owned by $(id -un): $FOREIGN_FILE" >&2
  echo "::error::Stop the runner and repair ownership before retrying." >&2
  exit 1
fi

find "$WORKSPACE" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
```

The allowlist prevents accidental deletion outside the runner's `_work` tree. The ownership check fails clearly instead of attempting privileged cleanup from a workflow. Use a pre-job hook because GitHub runs it before checkout; a workflow step cannot reliably repair checkout's own working tree.

**Step 4: Add a manual-only runner smoke workflow**

Create `.github/workflows/runner-smoke.yml`:

```yaml
name: Self-hosted Runner Smoke

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  checkout:
    runs-on: [self-hosted, linux]
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4
      - name: Verify workspace ownership
        run: |
          FOREIGN_FILE="$(find "$GITHUB_WORKSPACE" -xdev ! -user "$(id -un)" -print -quit)"
          if [[ -n "$FOREIGN_FILE" ]]; then
            echo "::error::Foreign-owned workspace file: $FOREIGN_FILE"
            exit 1
          fi
```

This workflow has no schedule, secrets, dependency install, or live-model calls. It exists only to verify the pre-job hook and checkout path cheaply.

**Step 5: Run focused tests and static checks**

```bash
bash infrastructure/runner/tests/test_cleanup_workspace.sh
shellcheck infrastructure/runner/hooks/cleanup-workspace.sh infrastructure/runner/tests/test_cleanup_workspace.sh
actionlint .github/workflows/runner-smoke.yml
```

Expected: all commands pass.

**Step 6: Document installation and recovery**

Add a `Workspace hygiene` section to `infrastructure/runner/README.md` that documents:

- Install the reviewed hook at `/opt/actions-runner-hooks/cleanup-workspace.sh`, outside the runner application directory.
- Set `ACTIONS_RUNNER_HOOK_JOB_STARTED=/opt/actions-runner-hooks/cleanup-workspace.sh` in `~/actions-runner/.env`.
- Restart the runner after changing `.env`.
- Inspect `Set up runner` in job logs to confirm the hook ran.
- Never run repository build commands as root on the persistent runner.
- For foreign-owned files, stop the runner and perform the one-time ownership repair in Task 4.
- Link to GitHub's official pre/post-job hook documentation: `https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/run-scripts`.

**Step 7: Commit**

```bash
git add infrastructure/runner/hooks/cleanup-workspace.sh \
  infrastructure/runner/tests/test_cleanup_workspace.sh \
  infrastructure/runner/README.md \
  .github/workflows/runner-smoke.yml
git commit -m "ci: guard persistent runner workspace cleanup"
```

### Task 4: Repair and deploy the persistent runner

**Files:**

- Deploy reviewed file: `infrastructure/runner/hooks/cleanup-workspace.sh`
- Configure host file: `/home/runner/actions-runner/.env`

**Step 1: Stop the runner and inspect ownership**

On the runner host:

```bash
systemctl stop actions.runner.Goodwiinz-rag.do-droplet-runner
find /home/runner/actions-runner/_work -xdev ! -user runner -ls
```

Expected: either the command identifies the foreign-owned path responsible for `EACCES`, or it returns no files. If no foreign-owned files exist, preserve the prior run logs and investigate filesystem corruption before changing ownership.

**Step 2: Quarantine the stale repository workspace**

If foreign-owned files are confirmed, move the affected workspace rather than deleting it immediately:

```bash
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mv /home/runner/actions-runner/_work/rag/rag \
  "/home/runner/actions-runner/_work/rag/rag.corrupt.$STAMP"
chown -R runner:runner /home/runner/actions-runner/_work
```

Expected: `_work` contains no files not owned by `runner`. Delete the quarantined directory only after a successful eval run and any needed forensic inspection.

**Step 3: Install and enable the hook**

From a reviewed checkout of PR 2:

```bash
install -d -o runner -g runner -m 0755 /opt/actions-runner-hooks
install -o runner -g runner -m 0755 \
  infrastructure/runner/hooks/cleanup-workspace.sh \
  /opt/actions-runner-hooks/cleanup-workspace.sh
printf '%s\n' \
  'ACTIONS_RUNNER_HOOK_JOB_STARTED=/opt/actions-runner-hooks/cleanup-workspace.sh' \
  >> /home/runner/actions-runner/.env
systemctl start actions.runner.Goodwiinz-rag.do-droplet-runner
systemctl status actions.runner.Goodwiinz-rag.do-droplet-runner --no-pager
```

Before appending, check that `.env` does not already define the variable; replace the existing line if it does.

**Step 4: Run the low-cost checkout smoke test**

Dispatch the permanent manual-only smoke workflow:

```bash
gh workflow run runner-smoke.yml
RUN_ID="$(gh run list --workflow runner-smoke.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "$RUN_ID" --exit-status
```

Verify:

- `Set up runner` shows the pre-job hook.
- `actions/checkout` succeeds without `fatal: --local...` or `EACCES`.
- The checked-out files are owned by `runner`.

**Step 5: Run the real regression workflow**

With explicit approval for the live eval cost, dispatch:

```bash
gh workflow run agent-eval.yml -f experiment_prefix=agent-regression-runner-fix
RUN_ID="$(gh run list --workflow agent-eval.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run watch "$RUN_ID" --exit-status
```

Expected: checkout, environment setup, dataset sync, and regression sweep all execute. Any later test or service failure is a separate eval failure, not evidence that runner cleanup failed.

### Task 5: Final verification and rollback notes

**Step 1: Recheck both CI producers**

- Confirm `Test Pipeline` has a green `Lint Frontend` job on the final frontend SHA.
- Confirm `Agent Regression Eval` reaches `Run regression sweep` on the repaired runner.
- Do not classify skipped jobs from older failed runs as flaky.

**Step 2: Record rollback procedures**

- Frontend rollback: revert the two PR 1 commits if TypeScript 5.9 or browser support regresses.
- Runner rollback: remove `ACTIONS_RUNNER_HOOK_JOB_STARTED` from `.env`, restart the service, and retain the hook file for diagnosis.
- Workspace rollback: restore the quarantined workspace only for forensic recovery; do not make it the active workspace again.

**Step 3: Close only on evidence**

Close the TypeScript issue when the TypeScript 7 dependency branch passes typecheck. Close the runner issue when two consecutive scheduled/manual eval jobs pass checkout; one green run proves recovery, while two runs exercise cleanup across job boundaries.
