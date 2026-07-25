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
    TOOL_FAILED_FLAG,
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
    failed_tools: tuple[str, ...] = (),
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
        failed_tools=failed_tools,
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


def test_the_06_26_run_that_confirmed_but_ingested_nothing() -> None:
    """Exact shape of the live run on image 1a34508, verified against the DB.

    ``flag=confirmed(1) resumes=1 tool_executions=3`` — HITL fired and was
    confirmed, so it read as success. The tool record showed
    ``ingest_arxiv_papers`` **failed** ("Invalid project_id …; expected a
    UUID"), the agent then called ``list_projects`` twice and stopped, and
    ``documents`` gained zero rows. ``confirmed(n)`` must not outrank that.
    """
    result = _result(
        interrupted=False,
        resumes=1,
        tool_executions=3,
        failed_tools=("ingest_arxiv_papers",),
    )
    assert classify_turn(_INTERRUPTING, result) == "TOOL-FAILED(ingest_arxiv_papers)"


def test_transient_tool_failure_is_not_flagged_outside_interrupt_scenarios() -> None:
    """research_arxiv hits arXiv 429/timeouts routinely.

    Flagging those would rebuild the noise floor this signal exists to stay
    below, so the check is scoped to expect_interrupt scenarios.
    """
    result = _result(scenario="research_arxiv", failed_tools=("search_arxiv",))
    assert classify_turn(_PLAIN, result) == "ok"


def test_a_raised_exception_still_outranks_a_failed_tool() -> None:
    result = _result(
        error="IngestionError: boom", failed_tools=("ingest_arxiv_papers",)
    )
    assert classify_turn(_INTERRUPTING, result) == "ERROR IngestionError: boom"


def test_pending_interrupt_outranks_a_failed_tool() -> None:
    """Awaiting confirmation is the state to report; the turn isn't over."""
    result = _result(interrupted=True, failed_tools=("ingest_arxiv_papers",))
    assert classify_turn(_INTERRUPTING, result) == "INTERRUPT"


def test_all_tools_completed_still_confirms() -> None:
    """The fix must not label a genuinely successful run as failed."""
    result = _result(resumes=1, tool_executions=2, failed_tools=())
    assert classify_turn(_INTERRUPTING, result) == "confirmed(1)"


def test_flag_prefix_is_stable_for_the_sweep_counter() -> None:
    """sweep_done counts unmet expectations with ``startswith``."""
    result = _result(resumes=1, failed_tools=("a", "b"))
    flag = classify_turn(_INTERRUPTING, result)
    assert flag.startswith(TOOL_FAILED_FLAG)
    assert flag == "TOOL-FAILED(a,b)"


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
