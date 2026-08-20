"""R5-M24: LLM-judge failures used to fabricate plausible-looking scores.

`_call_llm` returned the string "0.5" on any API error, and each
`_calculate_*` method independently caught its own exceptions and returned
0.5 (or 0.3 for hallucination_rate) "on error". A total LLM outage therefore
produced COMPLETED evaluation jobs full of fabricated midline scores,
indistinguishable from a real judgment of "somewhat relevant" / "some
hallucinations".

The fix makes `_call_llm` raise `LLMJudgeError` on a real API failure (a
missing client is not a failure — that's the deliberate heuristic fallback
path) and removes every `_calculate_*` fallback, letting the error propagate.
Callers (run_rag_triad_evaluation and, above that, the Celery tasks) already
drop failed items rather than record them, so a total outage now produces
either dropped items or a FAILED job — never a fabricated score.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.services.evaluation.rag_evaluation_service import (
    LLMJudgeError,
    RAGEvaluationService,
)

pytestmark = pytest.mark.unit


def _service_with_broken_openai_client() -> RAGEvaluationService:
    service = RAGEvaluationService()
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("API outage")
    service.openai_client = client
    service.anthropic_client = None
    return service


@pytest.mark.asyncio
async def test_call_llm_raises_on_api_failure_instead_of_returning_a_fake_score() -> (
    None
):
    service = _service_with_broken_openai_client()

    with pytest.raises(LLMJudgeError):
        await service._call_llm("some prompt")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method_name,args",
    [
        ("_calculate_answer_relevancy", ("query", "answer")),
        ("_calculate_faithfulness", ("answer", ["context"])),
        ("_calculate_contextual_relevancy", ("query", ["context"])),
        ("_calculate_hallucination_rate", ("answer", ["context"], None)),
    ],
)
async def test_each_metric_propagates_judge_failure_instead_of_defaulting(
    method_name: str, args: tuple
) -> None:
    service = _service_with_broken_openai_client()
    method = getattr(service, method_name)

    with pytest.raises(LLMJudgeError):
        await method(*args)


@pytest.mark.asyncio
async def test_missing_llm_client_is_not_a_judge_failure() -> None:
    """No configured client at all is the deliberate heuristic fallback
    path, not an outage — must not raise."""
    service = RAGEvaluationService()
    service.openai_client = None
    service.anthropic_client = None

    score = await service._calculate_answer_relevancy("q", "a")

    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_run_rag_triad_evaluation_does_not_record_a_fabricated_metric_on_judge_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end through run_rag_triad_evaluation: a judge outage must
    raise out of the whole evaluation (so the caller drops the item / fails
    the job), not silently persist a 0.5/0.3 EvaluationMetric row."""
    from src.services.evaluation.rag_evaluation_service import RAGEvaluationInput

    service = _service_with_broken_openai_client()
    db = MagicMock()

    evaluation_input = RAGEvaluationInput(
        query="q",
        generated_answer="a",
        retrieved_context=["c"],
    )

    with pytest.raises(Exception):
        await service.run_rag_triad_evaluation(evaluation_input, "job-1", "org-1", db)

    # No EvaluationMetric should have been added with a fabricated score.
    db.add.assert_not_called()
    db.commit.assert_not_called()
