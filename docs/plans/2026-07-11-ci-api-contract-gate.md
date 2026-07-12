# CI API Contract Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the API contract lane execute successfully and propagate pytest failures to the blocking test summary.

**Architecture:** Keep the repair inside the existing GitHub Actions job. A static unit test extracts the `api-contract-tests` workflow block and guards the two semantic requirements: Faker is installed and the pytest step cannot suppress failures.

**Tech Stack:** GitHub Actions YAML, Python 3.11, pytest, actionlint

---

### Task 1: Add the workflow regression test

**Files:**
- Create: `backend/tests/unit/ci/test_api_contract_workflow.py`
- Test: `backend/tests/unit/ci/test_api_contract_workflow.py`

**Step 1: Write the failing test**

Create a test helper that reads `.github/workflows/test-pipeline.yml`, extracts
the text between `api-contract-tests:` and `e2e-tests:`, and then extracts the
`Run contract tests` step. Add these assertions:

```python
def test_contract_job_installs_its_faker_dependency() -> None:
    assert "faker==25.2.0" in _contract_job()


def test_contract_pytest_failure_is_blocking() -> None:
    assert "continue-on-error" not in _contract_test_step()
```

**Step 2: Run the test to verify it fails**

Run:

```bash
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  backend/tests/unit/ci/test_api_contract_workflow.py -q
```

Expected: two assertion failures: Faker is absent and the contract step contains
`continue-on-error`.

**Step 3: Commit the red test**

```bash
git add backend/tests/unit/ci/test_api_contract_workflow.py
git commit -m "test(ci): guard blocking API contract lane"
```

### Task 2: Repair the contract job

**Files:**
- Modify: `.github/workflows/test-pipeline.yml:527-540`
- Test: `backend/tests/unit/ci/test_api_contract_workflow.py`

**Step 1: Implement the minimal workflow change**

Change the job-specific install line to:

```yaml
pip install schemathesis faker==25.2.0
```

Delete the `continue-on-error: true` line from `Run contract tests`.

**Step 2: Run the focused test to verify it passes**

Run the Task 1 pytest command.

Expected: `2 passed`.

**Step 3: Validate workflow syntax**

Run `actionlint .github/workflows/test-pipeline.yml` when actionlint is available.
If it is unavailable locally, parse the file with Ruby's YAML parser and rely on
the required `Validate GitHub Actions Workflows` PR check for actionlint.

**Step 4: Run the contract suite in the available backend environment**

Run:

```bash
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/api_contract/ -c backend/pytest.ini --collect-only -q
```

Expected: collection succeeds. The PR's `API Contract Tests` job is the full
PostgreSQL-backed verification.

**Step 5: Commit the fix**

```bash
git add .github/workflows/test-pipeline.yml
git commit -m "fix(ci): make API contract lane blocking"
```

### Task 3: Review and publish the draft PR

**Files:**
- Review: `.github/workflows/test-pipeline.yml`
- Review: `backend/tests/unit/ci/test_api_contract_workflow.py`
- Review: `docs/plans/2026-07-11-ci-api-contract-gate-design.md`
- Review: `docs/plans/2026-07-11-ci-api-contract-gate.md`

**Step 1: Run fresh verification**

Repeat the focused regression test, contract collection, workflow parser/lint,
and `git diff origin/develop...HEAD --check`.

**Step 2: Review the full diff**

Check that no lane except `api-contract-tests` changed and that the test asserts
behavior rather than workflow line numbers.

**Step 3: Push and open a draft PR**

```bash
git push -u origin fix/ci-api-contract-gate
gh pr create --draft --base develop --head fix/ci-api-contract-gate
```

**Step 4: Verify PR checks and update the audit ledger**

Confirm the contract job now fails on real pytest failures, all required checks
are green, and then change CI3 from `claimed` to `pr` with the PR number. Stop
before merge or deployment.
