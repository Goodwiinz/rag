"""Turn classification for the synthetic-traffic generator.

``expect_interrupt`` marks the scenarios whose whole point is driving a
destructive tool (project creation, arXiv ingest). The HITL interrupt is the
observable proof the tool was reached, so a run without one is a failure of
the scenario even though nothing raised. Before ``classify_turn`` the field
was declared, set on two scenarios, and never read — a live ingest run that
called zero tools logged ``flag=ok, errored=0``.
"""

from typing import Optional

import pytest

from scripts.synthetic_traffic import (
    MISSING_INTERRUPT_FLAG,
    SCENARIOS,
    Scenario,
    TurnResult,
    classify_turn,
)

pytestmark = pytest.mark.unit


def _result(
    *,
    scenario: str = "ingest",
    interrupted: bool = False,
    resumes: int = 0,
    tool_executions: int = 0,
    error: Optional[str] = None,
) -> TurnResult:
    """A turn shaped like the live 00:40 ingest run: nothing happened."""
    return TurnResult(
        scenario=scenario,
        wall_clock_s=6.33,
        interrupted=interrupted,
        resumes=resumes,
        intent="research",
        tool_executions=tool_executions,
        assistant_preview="",
        error=error,
    )


_INTERRUPTING = Scenario(
    key="ingest", prompt="ingest something", budget_s=60.0, expect_interrupt=True
)
_PLAIN = Scenario(key="general_qa", prompt="hi", budget_s=15.0)


def test_expected_interrupt_that_never_happened_is_not_ok() -> None:
    """The regression: 0 tools, 0 resumes, no interrupt, no exception."""
    assert classify_turn(_INTERRUPTING, _result()) == MISSING_INTERRUPT_FLAG


def test_same_shape_is_ok_when_no_interrupt_was_expected() -> None:
    assert classify_turn(_PLAIN, _result(scenario="general_qa")) == "ok"


def test_interrupt_awaiting_confirmation() -> None:
    assert classify_turn(_INTERRUPTING, _result(interrupted=True)) == "INTERRUPT"


def test_confirmed_after_resume() -> None:
    result = _result(interrupted=False, resumes=2, tool_executions=3)
    assert classify_turn(_INTERRUPTING, result) == "confirmed(2)"


def test_still_interrupted_after_resuming_is_not_ok() -> None:
    """MAX_HITL_RESUMES exhausted with the interrupt still pending.

    The old expression fell through to ``ok`` here as well — a turn that
    never finished confirming reported success.
    """
    result = _result(interrupted=True, resumes=3)
    assert classify_turn(_INTERRUPTING, result) == "INTERRUPT-UNRESOLVED(3)"
    # Not specific to interrupt-expecting scenarios.
    assert classify_turn(_PLAIN, result) == "INTERRUPT-UNRESOLVED(3)"


def test_error_outranks_the_unmet_expectation() -> None:
    """An exception is the more actionable fact; do not mask it."""
    flag = classify_turn(_INTERRUPTING, _result(error="IngestionError: timed out"))
    assert flag == "ERROR IngestionError: timed out"


def test_result_carries_its_flag_for_the_sweep_summary() -> None:
    """``sweep_done`` counts off ``TurnResult.flag``.

    It used to re-derive the flag from the scenario key, so a scenario that
    was not in the catalogue (an ad-hoc prompt, say) would KeyError in the
    summary — after every agent call had already run, and before the
    ``cleanup()`` pass that soft-deletes the synthetic projects.
    """
    assert TurnResult.__dataclass_fields__["flag"].default == ""
    result = _result()
    result.flag = classify_turn(_INTERRUPTING, result)
    assert result.flag == MISSING_INTERRUPT_FLAG


def test_catalogue_still_declares_interrupting_scenarios() -> None:
    """If these lose the flag, the assertion above silently stops applying."""
    keys = {s.key for s in SCENARIOS if s.expect_interrupt}
    assert keys == {"create_project", "ingest"}
