"""B4: background RAG triad evaluation must not run on the event loop thread.

`_background_evaluate_rag` drives sync DB work (`get_db_sync`, sync ORM
writes inside `run_rag_triad_evaluation`). Like ThreadSummarizationService,
that work must be driven from a worker thread, never inline on the loop.
"""

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch


def _make_contexts():
    from src.api.research.chat import RetrievedContext

    return [
        RetrievedContext(
            document_id="doc-1",
            title="Paper",
            content="Relevant passage.",
            score=0.9,
        )
    ]


def test_background_evaluate_runs_in_worker_thread():
    from src.api.research import chat as chat_module
    from src.core import database as database_module
    from src.services.evaluation import rag_evaluation_service as rag_eval_module

    caller_thread = threading.get_ident()
    seen = {}

    async def fake_evaluation(*args, **kwargs):
        seen["thread"] = threading.get_ident()
        metrics = MagicMock()
        metrics.answer_relevancy = 0.9
        metrics.faithfulness = 0.8
        metrics.contextual_relevancy = 0.7
        metrics.overall_score = 0.8
        metrics.hallucination_rate = 0.1
        return metrics

    def fake_get_db_sync():
        yield MagicMock()

    with (
        patch.object(
            rag_eval_module.rag_evaluation_service,
            "run_rag_triad_evaluation",
            side_effect=fake_evaluation,
        ),
        patch.object(
            database_module,
            "get_db_sync",
            fake_get_db_sync,
        ),
        patch(
            "src.services.diagnostics.diagnostics_store.diagnostics_store.update_trace_evaluation",
            new_callable=AsyncMock,
        ),
    ):
        asyncio.run(
            chat_module._background_evaluate_rag(
                query="what is rag?",
                answer="retrieval augmented generation",
                contexts=_make_contexts(),
                trace_id="trace-1",
                organization_id="org-1",
            )
        )

    assert (
        seen["thread"] != caller_thread
    ), "evaluation must run off the event loop thread"


def test_background_evaluate_swallows_and_logs_exceptions(caplog):
    """Refactor guard: failures must still be logged, never raised to the caller."""
    from src.api.research import chat as chat_module
    from src.core import database as database_module
    from src.services.evaluation import rag_evaluation_service as rag_eval_module

    async def failing_evaluation(*args, **kwargs):
        raise RuntimeError("triad exploded")

    def fake_get_db_sync():
        yield MagicMock()

    with (
        patch.object(
            rag_eval_module.rag_evaluation_service,
            "run_rag_triad_evaluation",
            side_effect=failing_evaluation,
        ),
        patch.object(database_module, "get_db_sync", fake_get_db_sync),
    ):
        with caplog.at_level("WARNING"):
            asyncio.run(  # must not raise
                chat_module._background_evaluate_rag(
                    query="q",
                    answer="a",
                    contexts=_make_contexts(),
                    trace_id="trace-2",
                    organization_id="org-1",
                )
            )

    assert any(
        "Background RAG evaluation failed for trace trace-2" in rec.message
        for rec in caplog.records
    )


def test_background_evaluate_closes_db_session():
    """Session acquired via get_db_sync must be closed even on success path."""
    from src.api.research import chat as chat_module
    from src.core import database as database_module
    from src.services.evaluation import rag_evaluation_service as rag_eval_module

    db_mock = MagicMock()

    def fake_get_db_sync():
        yield db_mock

    async def fake_evaluation(*args, **kwargs):
        metrics = MagicMock()
        metrics.overall_score = 0.5
        return metrics

    with (
        patch.object(
            rag_eval_module.rag_evaluation_service,
            "run_rag_triad_evaluation",
            side_effect=fake_evaluation,
        ),
        patch.object(database_module, "get_db_sync", fake_get_db_sync),
        patch(
            "src.services.diagnostics.diagnostics_store.diagnostics_store.update_trace_evaluation",
            new_callable=AsyncMock,
        ),
    ):
        asyncio.run(
            chat_module._background_evaluate_rag(
                query="q",
                answer="a",
                contexts=_make_contexts(),
                trace_id="trace-3",
                organization_id="org-1",
            )
        )

    db_mock.close.assert_called_once()
