"""R5-M25: the triad task reads metadata keys the writer never wrote.

`evaluate_search_pipeline` built the metadata dict for each RAGTriadMetrics
result with `search_time_ms`/`results_count`/`search_response` — never
`generated_answer`/`retrieved_context`. Both call sites that later read
`metrics.metadata.get("generated_answer", "")` /
`.get("retrieved_context", [])` (evaluation_tasks.py, in
run_rag_triad_evaluation's no-context branch and in run_batch_evaluation's
metric-saving loop) always got the "" / [] defaults — contexts were silently
empty even after a successful search, and once R5-H7 made this code path
reachable at all, the LLM judges would have scored against blank strings.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_evaluate_search_pipeline_metadata_carries_answer_and_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime, timezone

    from src.models.document import DocumentType
    from src.models.search_schemas import SearchResponse, SearchResult, SearchType
    from src.services.evaluation import rag_evaluation_service as svc

    service = svc.RAGEvaluationService()

    now = datetime.now(timezone.utc)
    result = SearchResult(
        document_id="doc-1",
        title="t",
        document_type=DocumentType.TEXT,
        content_preview="Paris is the capital of France.",
        relevance_score=0.9,
        file_size_bytes=100,
        created_at=now,
        updated_at=now,
        processing_status="completed",
        is_public=False,
        uploaded_by_user_id="user-1",
        organization_id="org-1",
    )
    fake_search_response = SearchResponse(
        query="capital of france?",
        search_id="s1",
        search_type=SearchType.HYBRID,
        results=[result],
        total_results=1,
        returned_results=1,
        search_time_ms=12.5,
        limit=5,
        offset=0,
        has_more=False,
    )
    monkeypatch.setattr(
        svc.hybrid_search_service,
        "search",
        MagicMock(return_value=fake_search_response),
    )
    monkeypatch.setattr(svc, "SessionLocal", MagicMock(return_value=MagicMock()))

    captured: dict[str, Any] = {}

    async def _fake_run_rag_triad_evaluation(
        evaluation_input: Any, job_id: Any, organization_id: Any, db: Any
    ) -> Any:
        captured["evaluation_input"] = evaluation_input
        out = MagicMock()
        out.metadata = evaluation_input.metadata
        return out

    monkeypatch.setattr(
        service, "run_rag_triad_evaluation", _fake_run_rag_triad_evaluation
    )

    results = await service.evaluate_search_pipeline(
        queries=["capital of france?"],
        organization_id="org-1",
        user_id="user-1",
    )

    metadata = results[0].metadata
    evaluation_input = captured["evaluation_input"]

    assert metadata["generated_answer"] == evaluation_input.generated_answer
    assert metadata["retrieved_context"] == evaluation_input.retrieved_context
    assert metadata["retrieved_context"] == [result.content_preview]
    assert metadata["generated_answer"], "generated_answer must not be blank"


def test_run_batch_evaluation_metric_write_reads_the_now_populated_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The task-side read (evaluation_tasks.run_batch_evaluation) must pull
    generated_answer/retrieved_context from metrics.metadata and persist
    retrieved_context as JSON text (the column is Text, not JSON) — a plain
    list would previously have been silently mis-typed once M25's key was
    actually populated."""
    from src.tasks import evaluation_tasks as et

    job = MagicMock()
    job.id = "job-1"
    job.organization_id = "org-1"
    job.user_id = "user-1"
    job.status = "pending"
    job.parameters = {"search_type": "hybrid", "search_limit": 5}

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = job

    metrics_result = MagicMock()
    metrics_result.overall_score = 0.8
    metrics_result.answer_relevancy = 0.8
    metrics_result.faithfulness = 0.8
    metrics_result.contextual_relevancy = 0.8
    metrics_result.hallucination_rate = 0.1
    metrics_result.response_time_ms = 42.0
    metrics_result.metadata = {
        "generated_answer": "Paris is the capital of France.",
        "retrieved_context": ["Paris is the capital of France."],
    }

    async def _fake_evaluate_search_pipeline(*args: Any, **kwargs: Any) -> Any:
        return [metrics_result]

    monkeypatch.setattr(et, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        et.rag_evaluation_service,
        "evaluate_search_pipeline",
        _fake_evaluate_search_pipeline,
    )

    et.run_batch_evaluation.apply(args=("job-1", ["capital of france?"])).result

    added = [c.args[0] for c in db.add.call_args_list]
    metric_rows = [
        m for m in added if getattr(m, "metric_type", None) == "rag_triad_overall"
    ]
    assert metric_rows, "expected a rag_triad_overall EvaluationMetric to be added"
    metric = metric_rows[0]
    assert metric.generated_answer == "Paris is the capital of France."
    # Text column: must be a JSON string, not a raw Python list.
    import json

    assert json.loads(metric.retrieved_context) == ["Paris is the capital of France."]
    assert metric.metric_metadata["answer_relevancy"] == 0.8
