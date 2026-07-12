"""Regression checks for honest workflow gate reporting."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/test-pipeline.yml"


def _test_summary_job() -> str:
    workflow = WORKFLOW_PATH.read_text()
    start = workflow.index("\n  test-summary:")
    return workflow[start:]


def test_dead_contract_suite_is_not_advertised_as_a_blocking_gate() -> None:
    workflow = WORKFLOW_PATH.read_text()
    summary = _test_summary_job()

    assert "\n  api-contract-tests:" not in workflow
    assert "api-contract-tests" not in summary
    assert "CONTRACT_RESULT" not in summary
    assert "API Contract Tests" not in summary
