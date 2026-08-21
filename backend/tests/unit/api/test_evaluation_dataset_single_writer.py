"""R5-H6: exactly one EvaluationDataset write per POST /evaluation/jobs.

Before the fix, `create_evaluation_job` (rag_evaluation_service.py) always
built its own `EvaluationDataset` from `EvaluationRequest.dataset` — but the
route (`api/infrastructure/evaluation.py`) called it with `dataset=[]` and
then inserted a SECOND `EvaluationDataset` itself, populated with the real
questions/answers/contexts. `run_rag_triad_evaluation` (evaluation_tasks.py)
then fetched the dataset for the job with an unordered `.first()` — whichever
of the two rows came back first from the heap usually won, and it was usually
the empty one, so the job failed with "No items were successfully processed".

The fix makes the route the caller that builds the real dataset items
(`RAGEvaluationInput` per question) and hands them to
`rag_evaluation_service.create_evaluation_job` as `EvaluationRequest.dataset`
— that service method is the ONLY place an `EvaluationDataset` row is ever
constructed. This test mocks `rag_evaluation_service.create_evaluation_job`
itself (so the service's own dataset-building logic, covered elsewhere, is
out of scope here) and asserts on two things through the seam:

  1. The route hands the service a `dataset` field with the real per-question
     items (not `[]`).
  2. The route no longer touches `db.add` at all — the old second insert is
     gone; the service (mocked out here) is the single writer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


@dataclass
class _FakeJob:
    """A concrete stand-in for the ORM EvaluationJob the mocked service
    would normally return — real attribute values, not MagicMocks, so the
    route's response dict (job.created_at.isoformat(), etc.) actually
    serializes."""

    id: Any
    name: str
    status: str
    created_at: datetime


@pytest.fixture
def client() -> Any:
    from src.api.infrastructure import evaluation
    from src.core.database import get_db_sync
    from src.core.dependencies import get_current_user

    user = MagicMock()
    user.id = uuid4()
    user.organization_id = uuid4()

    db = MagicMock()

    app = FastAPI()
    app.include_router(evaluation.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_sync] = lambda: db

    return TestClient(app, raise_server_exceptions=False), db


def test_create_job_hands_the_service_the_real_dataset_and_never_writes_its_own(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.api.infrastructure import evaluation

    test_client, db = client

    fake_job = _FakeJob(
        id=uuid4(),
        name="my eval",
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    captured: dict[str, Any] = {}

    async def _fake_create_evaluation_job(request: Any, db: Any) -> _FakeJob:
        captured["request"] = request
        return fake_job

    monkeypatch.setattr(
        evaluation.rag_evaluation_service,
        "create_evaluation_job",
        _fake_create_evaluation_job,
    )
    monkeypatch.setattr(
        evaluation, "run_rag_triad_evaluation", MagicMock(delay=MagicMock())
    )

    response = test_client.post(
        "/evaluation/jobs",
        json={
            "name": "my eval",
            # NOTE: the request model's own default ("rag_triad") is not a
            # valid EvaluationType member — a pre-existing, out-of-scope bug
            # this test sidesteps by passing a real one explicitly.
            "evaluation_type": "answer_relevancy",
            "questions": ["what is x?", "what is y?"],
            "reference_answers": ["x is x", "y is y"],
            "contexts": [["ctx-x"], ["ctx-y"]],
        },
    )

    assert response.status_code == 200, response.text

    # The service was handed the real dataset, not dataset=[].
    dataset = captured["request"].dataset
    assert len(dataset) == 2
    assert [item.query for item in dataset] == ["what is x?", "what is y?"]
    assert [item.reference_answer for item in dataset] == ["x is x", "y is y"]
    assert [item.retrieved_context for item in dataset] == [["ctx-x"], ["ctx-y"]]

    # The route itself must not be a second writer of EvaluationDataset (or
    # anything else) — with the service mocked out, nothing in the route
    # should call db.add.
    db.add.assert_not_called()


def test_create_job_dataset_items_default_missing_answers_and_contexts(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reference answers / contexts are optional on the request; the built
    dataset items must not blow up or misalign when they're omitted."""
    from src.api.infrastructure import evaluation

    test_client, _db = client

    fake_job = _FakeJob(
        id=uuid4(), name="n", status="pending", created_at=datetime.now(timezone.utc)
    )
    captured: dict[str, Any] = {}

    async def _fake_create_evaluation_job(request: Any, db: Any) -> _FakeJob:
        captured["request"] = request
        return fake_job

    monkeypatch.setattr(
        evaluation.rag_evaluation_service,
        "create_evaluation_job",
        _fake_create_evaluation_job,
    )
    monkeypatch.setattr(
        evaluation, "run_rag_triad_evaluation", MagicMock(delay=MagicMock())
    )

    response = test_client.post(
        "/evaluation/jobs",
        json={
            "name": "n",
            "evaluation_type": "answer_relevancy",
            "questions": ["q1"],
        },
    )

    assert response.status_code == 200, response.text
    dataset = captured["request"].dataset
    assert len(dataset) == 1
    assert dataset[0].query == "q1"
    assert dataset[0].reference_answer is None
    assert dataset[0].retrieved_context == []
