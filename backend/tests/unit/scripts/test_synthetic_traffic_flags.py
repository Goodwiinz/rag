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
    SUCCESS_TOOL_STATUSES,
    TOOL_FAILED_FLAG,
    Scenario,
    TurnResult,
    classify_turn,
    failed_tool_names,
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


def test_a_failure_without_a_confirmed_interrupt_stays_missing_interrupt() -> None:
    """A failed tool must not mask the "never reached" diagnosis.

    An arXiv hiccup on the search step followed by a prose answer means no
    interrupt ever fired — MISSING-INTERRUPT is the honest flag, and the
    TOOL-FAILED warning would otherwise claim an interrupt that did not
    happen.
    """
    result = _result(resumes=0, failed_tools=("search_arxiv",))
    assert classify_turn(_INTERRUPTING, result) == MISSING_INTERRUPT_FLAG


def test_no_interrupt_no_expectation_is_still_ok() -> None:
    result = _result(scenario="research_arxiv", failed_tools=("search_arxiv",))
    assert classify_turn(_PLAIN, result) == "ok"


def test_writing_draft_shaped_run_is_covered_despite_no_expect_interrupt() -> None:
    """create_draft / create_project_note are destructive and do interrupt.

    writing_draft does not declare expect_interrupt, so gating on that field
    would have left an identical fake-success hole one scenario over.
    """
    result = _result(
        scenario="writing_draft", resumes=1, failed_tools=("create_draft",)
    )
    assert classify_turn(_PLAIN, result) == "TOOL-FAILED(create_draft)"


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


def test_deduped_is_a_success_not_a_failure() -> None:
    """``deduped`` means an identical call already succeeded this turn.

    ``tool_dedupe`` only caches ``completed`` results, and the agent's own
    reflection guard counts ``("completed", "deduped")`` as success. Reading
    it as failure would flag a healthy run whenever the agent repeated a
    call — which the live ingest trace does (two ``list_projects``).
    """
    assert SUCCESS_TOOL_STATUSES == ("completed", "deduped")
    executions = [
        {"tool_name": "list_projects", "status": "completed"},
        {"tool_name": "list_projects", "status": "deduped"},
    ]
    assert failed_tool_names(executions) == ()


def test_extraction_picks_out_real_failures() -> None:
    executions = [
        {"tool_name": "ingest_arxiv_papers", "status": "failed"},
        {"tool_name": "list_projects", "status": "completed"},
    ]
    assert failed_tool_names(executions) == ("ingest_arxiv_papers",)


def test_extraction_skips_transient_failures() -> None:
    """arXiv 429s and upstream timeouts say nothing about the agent.

    Same predicate the reflection guard uses: result.error_type == transient.
    """
    executions = [
        {
            "tool_name": "search_arxiv",
            "status": "failed",
            "result": {"error_type": "transient", "error": "429"},
        },
        {
            "tool_name": "ingest_arxiv_papers",
            "status": "failed",
            "result": {"error_type": "recoverable", "error": "Invalid project_id"},
        },
    ]
    assert failed_tool_names(executions) == ("ingest_arxiv_papers",)


def test_zero_document_ingest_counts_even_though_status_is_completed() -> None:
    """The incident this flag is named for, which status alone misses.

    ``_tool_ingest_arxiv`` returns ``{"status": "ingestion_failed",
    "ingested_count": 0}`` with **no** top-level ``error`` key, and
    ``_nodes_tools`` only downgrades to ``status="failed"`` when
    ``"error" in result``. So a run that imported nothing records
    ``completed`` and would otherwise sail through as ``confirmed(n)``.
    """
    executions = [
        {
            "tool_name": "ingest_arxiv_papers",
            "status": "completed",
            "result": {"status": "ingestion_failed", "ingested_count": 0},
        }
    ]
    assert failed_tool_names(executions) == ("ingest_arxiv_papers",)


def test_partial_ingest_also_counts() -> None:
    executions = [
        {
            "tool_name": "ingest_arxiv_papers",
            "status": "completed",
            "result": {"status": "ingestion_partial", "ingested_count": 1},
        }
    ]
    assert failed_tool_names(executions) == ("ingest_arxiv_papers",)


def test_successful_ingest_is_not_flagged() -> None:
    executions = [
        {
            "tool_name": "ingest_arxiv_papers",
            "status": "completed",
            "result": {"status": "ingestion_complete", "ingested_count": 1},
        }
    ]
    assert failed_tool_names(executions) == ()


def test_failed_then_retried_successfully_is_not_a_failure() -> None:
    """Recovering from a bad argument is the behaviour we want, not a fault."""
    executions = [
        {"tool_name": "ingest_arxiv_papers", "status": "failed"},
        {"tool_name": "list_projects", "status": "completed"},
        {"tool_name": "ingest_arxiv_papers", "status": "completed"},
    ]
    assert failed_tool_names(executions) == ()


def test_circuit_broken_duplicate_is_not_counted_twice() -> None:
    """``tool_dedupe`` caps repeated identical failures with a stub entry.

    It carries ``status="failed"`` and ``result=None``, so the transient
    skip cannot see through it — counting it would double-report the
    failure it caps and resurrect a transient one that was skipped.
    """
    executions = [
        {
            "tool_name": "search_arxiv",
            "status": "failed",
            "result": {"error_type": "transient", "error": "429"},
        },
        {
            "tool_name": "search_arxiv",
            "status": "failed",
            "result": None,
            "capped_from": "call_1",
        },
    ]
    assert failed_tool_names(executions) == ()


def test_extraction_tolerates_junk_entries() -> None:
    assert failed_tool_names(None) == ()
    assert failed_tool_names([None, "nonsense", 7]) == ()
    assert failed_tool_names([{"status": "failed"}]) == ("?",)


def test_catalogue_still_declares_interrupting_scenarios() -> None:
    """If these lose the flag, the assertion above silently stops applying."""
    keys = {s.key for s in SCENARIOS if s.expect_interrupt}
    # writing_draft joined them: create_draft / create_project_note are in
    # WRITING_DESTRUCTIVE_TOOLS, so a genuine save raises the interrupt. It
    # previously ran zero tools and logged flag=ok.
    assert keys == {"create_project", "ingest", "writing_draft"}


def test_ingest_prompt_rotates_its_paper_id() -> None:
    """A fixed id makes the scenario unsatisfiable after its first success.

    Content-hash dedup (uq_documents_org_checksum_live) correctly rejects a
    second copy of the same paper, so hardcoding 1706.03762 meant every run
    after 2026-07-18 reported a failure for a pipeline that was working.
    """
    from scripts.synthetic_traffic import (
        INGEST_PAPER_IDS,
        SCENARIOS_BY_KEY,
        _expand_prompt,
    )

    assert len(set(INGEST_PAPER_IDS)) > 1, "one id is the bug this fixes"

    expanded = _expand_prompt(SCENARIOS_BY_KEY["ingest"])
    assert "{paper}" not in expanded and "{ts}" not in expanded
    assert any(pid in expanded for pid in INGEST_PAPER_IDS)


def test_rotation_is_deterministic_within_a_window() -> None:
    """Two pods in the same window must agree; consecutive windows must not."""
    from scripts.synthetic_traffic import INGEST_PAPER_IDS, _rotating_paper_id

    assert _rotating_paper_id() == _rotating_paper_id()
    assert _rotating_paper_id() in INGEST_PAPER_IDS


def test_the_writing_run_that_did_nothing_and_said_ok() -> None:
    """Live shape from dev: writing_draft, 0 tools, flag=ok.

    create_draft and create_project_note are in WRITING_DESTRUCTIVE_TOOLS, so
    a genuine save always raises the HITL interrupt. The scenario declared no
    expectation, so a run that wrote prose and saved nothing was
    indistinguishable from one that saved a note — the same fake-success shape
    as the ingest scenario, one scenario over.
    """
    from scripts.synthetic_traffic import SCENARIOS_BY_KEY

    writing = SCENARIOS_BY_KEY["writing_draft"]
    assert writing.expect_interrupt

    result = _result(scenario="writing_draft", resumes=0, tool_executions=0)
    assert classify_turn(writing, result) == MISSING_INTERRUPT_FLAG


def test_the_writing_prompt_asks_for_something_only_a_tool_can_do() -> None:
    """An ambiguous prompt makes the expectation unfair.

    "Draft a short note" is satisfiable with prose, so demanding an interrupt
    would flag honest behaviour. The prompt has to ask for persistence.
    """
    from scripts.synthetic_traffic import SCENARIOS_BY_KEY

    prompt = SCENARIOS_BY_KEY["writing_draft"].prompt.lower()
    assert "save" in prompt or "library" in prompt
