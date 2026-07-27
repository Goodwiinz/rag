"""A queue failure must reach the caller, not vanish after the response.

Every evaluation endpoint committed its rows and then handed the Celery
``.delay`` to ``background_tasks.add_task``. FastAPI runs background tasks
*after* the response is sent, so a broker outage raised inside a task whose
exception nobody sees: the caller got ``200`` with a ``job_id``, the row sat
at ``pending`` forever, and no error was ever surfaced.

The file already documented that exact swallow — the note above
``trigger_evaluation_report`` describes a name-shadowing bug that produced an
"AttributeError inside BackgroundTasks, swallowed post-response" and meant
"reports would never be generated". That bug was only invisible *because* the
enqueue was deferred.

These are behavioural tests against a real router. An earlier version of this
file asserted on ``inspect.getsource`` strings (``"503" in source``), which
passes when the raise is unreachable, when the status is converted to a 500 by
the outer handler, or when ``fail_job`` runs on the wrong object — every
failure mode actually worth testing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from kombu.exceptions import OperationalError

pytestmark = pytest.mark.unit


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Router mounted bare, with auth and the DB session overridden."""
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


def _broken_task(exc: BaseException) -> MagicMock:
    task = MagicMock()
    task.delay.side_effect = exc
    return task


class TestBrokerOutageIsReported:
    def test_batch_job_returns_503_and_marks_the_row_failed(
        self, client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api.infrastructure import evaluation

        test_client, db = client
        monkeypatch.setattr(
            evaluation,
            "run_batch_evaluation",
            _broken_task(OperationalError("broker down")),
        )

        response = test_client.post(
            "/evaluation/jobs/batch",
            json={"name": "n", "queries": ["q1"]},
        )

        assert (
            response.status_code == 503
        ), "a job that was never enqueued must not be reported as created"
        # The row was committed before the dispatch, so it must not be left
        # 'pending' with no worker behind it.
        added = [c.args[0] for c in db.add.call_args_list]
        assert added, "expected a job row to have been added"
        assert added[0].status == "failed"

    def test_report_trigger_returns_503(
        self, client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api.infrastructure import evaluation
        from src.models.evaluation import EvaluationStatus

        test_client, db = client
        job = MagicMock()
        job.status = EvaluationStatus.COMPLETED.value
        db.query.return_value.filter.return_value.first.return_value = job

        monkeypatch.setattr(
            evaluation,
            "generate_evaluation_report",
            _broken_task(OperationalError("broker down")),
        )

        response = test_client.post(
            f"/evaluation/jobs/{uuid4()}/reports/summary",
        )

        assert response.status_code == 503


class TestCodeBugsAreNotReportedAsOutages:
    """503 says "retry"; a code defect retried forever is worse than a 500."""

    def test_attribute_error_is_not_converted_to_503(
        self, client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.api.infrastructure import evaluation

        test_client, _db = client
        # The exact hazard the module comments about: a shadowed global with
        # no .delay attribute.
        monkeypatch.setattr(
            evaluation,
            "run_batch_evaluation",
            _broken_task(AttributeError("'function' object has no attribute 'delay'")),
        )

        response = test_client.post(
            "/evaluation/jobs/batch",
            json={"name": "n", "queries": ["q1"]},
        )

        assert (
            response.status_code == 500
        ), "a permanent defect must not be advertised as a retryable outage"


class TestNoDeferredEnqueue:
    """Cheap guard against the pattern coming back."""

    def test_no_celery_dispatch_is_deferred(self) -> None:
        source = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "api"
            / "infrastructure"
            / "evaluation.py"
        ).read_text()

        assert "add_task(" not in source, (
            "background_tasks.add_task runs after the response, so an enqueue "
            "failure cannot be reported — the caller polls a pending row forever"
        )


class TestPublishIsBounded:
    def test_broker_socket_timeouts_are_configured(self) -> None:
        """Inline publishing is only safe if it cannot block indefinitely.

        Kombu's Redis transport reads socket timeouts from
        broker_transport_options, not broker_connection_timeout; without them
        a blackholed broker falls through to OS TCP retries (~130s) while
        holding the request.
        """
        from src.tasks.celery_app import celery_app

        options = celery_app.conf.broker_transport_options or {}

        assert options.get("socket_connect_timeout"), "unbounded connect"
        assert options.get("socket_timeout"), "unbounded read"
        assert celery_app.conf.task_publish_retry_policy["max_retries"] <= 2
