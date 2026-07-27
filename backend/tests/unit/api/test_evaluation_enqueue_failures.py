"""A queue failure must reach the caller, not vanish after the response.

Every evaluation endpoint committed its rows and then handed the Celery
``.delay`` to ``background_tasks.add_task``. FastAPI runs background tasks
*after* the response is sent, so a broker outage raised inside a task whose
exception nobody sees: the caller got ``200`` with a ``job_id``, the row sat
at ``pending`` forever, and no error was ever surfaced.

The file already documented that exact swallow — the note above
``trigger_evaluation_report`` explains a name-shadowing bug that produced an
"AttributeError inside BackgroundTasks, swallowed post-response" and meant
"reports would never be generated". That bug was only invisible *because* the
enqueue was deferred.

Enqueue inline instead, after the row is durable (so a worker's claim always
finds it) and inside ``try`` (so a broker failure marks the job failed and
returns 503). Mirrors the dispatch in ``api/agent/execute.py`` and the
sibling ``/real-time`` endpoint, which always called ``.delay`` directly.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROUTER = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "api"
    / "infrastructure"
    / "evaluation.py"
)


class TestNoDeferredEnqueue:
    def test_no_endpoint_defers_a_celery_dispatch(self) -> None:
        source = _ROUTER.read_text()

        # The call form, not the bare name: the explanatory comments in that
        # module mention ``background_tasks.add_task`` on purpose.
        assert "add_task(" not in source, (
            "background_tasks.add_task runs after the response, so an enqueue "
            "failure cannot be reported — the caller polls a pending row forever"
        )

    def test_background_tasks_dependency_is_gone(self) -> None:
        """An unused BackgroundTasks param invites the pattern back."""
        source = _ROUTER.read_text()

        assert "background_tasks: BackgroundTasks" not in source


class TestEnqueueFailureIsReported:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "create_evaluation_job",
            "create_batch_evaluation_job",
            "create_evaluation_comparison",
            "trigger_evaluation_report",
        ],
    )
    def test_dispatch_is_guarded_and_returns_503(self, endpoint: str) -> None:
        from src.api.infrastructure import evaluation

        source = inspect.getsource(getattr(evaluation, endpoint))

        assert ".delay(" in source, f"{endpoint} should dispatch inline"
        assert "503" in source, (
            f"{endpoint} must tell the caller the queue is unavailable rather "
            "than reporting a job it never enqueued"
        )

    @pytest.mark.parametrize(
        "endpoint",
        ["create_evaluation_job", "create_batch_evaluation_job"],
    )
    def test_a_created_job_row_is_marked_failed(self, endpoint: str) -> None:
        """These two commit a job row first, so it must not be left pending."""
        from src.api.infrastructure import evaluation

        source = inspect.getsource(getattr(evaluation, endpoint))

        assert "fail_job(" in source, (
            f"{endpoint} commits a job row before enqueueing; if the enqueue "
            "fails the row must not stay 'pending' with no worker behind it"
        )


class TestOrderingIsPersistThenEnqueue:
    @pytest.mark.parametrize(
        "endpoint",
        ["create_evaluation_job", "create_batch_evaluation_job"],
    )
    def test_commit_precedes_dispatch(self, endpoint: str) -> None:
        """Enqueueing before the row is visible races the worker's lookup."""
        from src.api.infrastructure import evaluation

        source = inspect.getsource(getattr(evaluation, endpoint))

        assert source.index("db.commit()") < source.index(".delay("), (
            "the worker resolves the job by id, so the row has to be durable "
            "before the task is queued"
        )
