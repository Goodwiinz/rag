# CI API Contract Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stop CI from reporting a dead API contract suite as a passing blocking gate.

**Architecture:** Remove the dead job and its summary wiring while preserving the stale suite for a separately scoped rebuild. A static unit test guards that the job and all summary claims remain absent.

**Tech Stack:** GitHub Actions YAML, Python 3.11, pytest, actionlint

---

### Task 1: Add the workflow regression test

**Files:**
- Create: `backend/tests/unit/ci/test_api_contract_workflow.py`
- Test: `backend/tests/unit/ci/test_api_contract_workflow.py`

**Step 1: Write the failing test**

Create a test helper that reads `.github/workflows/test-pipeline.yml` and extracts
the `test-summary` job. Add these assertions:

```python
def test_dead_contract_suite_is_not_advertised_as_a_blocking_gate() -> None:
    workflow = WORKFLOW_PATH.read_text()
    summary = _test_summary_job()
    assert "\n  api-contract-tests:" not in workflow
    assert "api-contract-tests" not in summary
    assert "CONTRACT_RESULT" not in summary
    assert "API Contract Tests" not in summary
```

**Step 2: Run the test to verify it fails**

Run:

```bash
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  backend/tests/unit/ci/test_api_contract_workflow.py -q
```

Expected: failure because the dead contract job and summary wiring still exist.

**Step 3: Commit the red test**

```bash
git add backend/tests/unit/ci/test_api_contract_workflow.py
git commit -m "test(ci): guard blocking API contract lane"
```

### Task 2: Remove the dead contract gate

**Files:**
- Modify: `.github/workflows/test-pipeline.yml:527-540`
- Test: `backend/tests/unit/ci/test_api_contract_workflow.py`

**Step 1: Implement the minimal workflow change**

Delete `api-contract-tests` and remove its `needs`, `CONTRACT_RESULT`, summary
table, and blocking-loop references from `test-summary`.

**Step 2: Run the focused test to verify it passes**

Run the Task 1 pytest command.

Expected: `1 passed`.

**Step 3: Validate workflow syntax**

Run `actionlint .github/workflows/test-pipeline.yml` when actionlint is available.
If it is unavailable locally, parse the file with Ruby's YAML parser and rely on
the required `Validate GitHub Actions Workflows` PR check for actionlint.

**Step 4: Verify stale identifiers are gone**

Run `rg 'api-contract-tests|CONTRACT_RESULT|API Contract Tests' .github/workflows/test-pipeline.yml`.
Expected: no matches.

**Step 5: Commit the fix**

```bash
git add .github/workflows/test-pipeline.yml
git commit -m "fix(ci): remove false API contract gate"
```

### Task 3: Review and publish the draft PR

**Files:**
- Review: `.github/workflows/test-pipeline.yml`
- Review: `backend/tests/unit/ci/test_api_contract_workflow.py`
- Review: `docs/plans/2026-07-11-ci-api-contract-gate-design.md`
- Review: `docs/plans/2026-07-11-ci-api-contract-gate.md`

**Step 1: Run fresh verification**

Repeat the focused regression test, workflow parser/lint,
and `git diff origin/develop...HEAD --check`.

**Step 2: Review the full diff**

Check that no live lane changed and that the stale contract suite remains intact.

**Step 3: Push and open a draft PR**

```bash
git push -u origin fix/ci-api-contract-gate
gh pr create --draft --base develop --head fix/ci-api-contract-gate
```

**Step 4: Verify PR checks and update the audit ledger**

Confirm all required checks are green, then change CI3 from `claimed` to `pr`
with the PR number. Stop
before merge or deployment.
