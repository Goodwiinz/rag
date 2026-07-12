"""Regression checks for the blocking API contract workflow lane."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/test-pipeline.yml"


def _contract_job() -> str:
    workflow = WORKFLOW_PATH.read_text()
    start = workflow.index("\n  api-contract-tests:")
    end = workflow.index("\n  e2e-tests:", start)
    return workflow[start:end]


def _contract_test_step() -> str:
    job = _contract_job()
    start = job.index("\n      - name: Run contract tests")
    return job[start:]


def test_contract_job_installs_its_faker_dependency() -> None:
    assert "faker==25.2.0" in _contract_job()


def test_contract_pytest_failure_is_blocking() -> None:
    assert "continue-on-error" not in _contract_test_step()
