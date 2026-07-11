"""job_store → agent_runs write-through wiring (audit P1.2).

Pins that every status write path schedules the durable projection with a
*snapshotted* payload (status/owner/org/error/thread), and that the
scheduling helper is safe with no running loop and with statusless payloads.
The projection body itself is covered in test_agent_run_service.py.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.services.agent import job_store as js
from src.shared.enums import JobStatus

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_store():
    js._l1.clear()
    yield
    js._l1.clear()


async def _drain_projection_tasks():
    if js._projection_tasks:
        await asyncio.gather(*list(js._projection_tasks), return_exceptions=True)


@pytest.mark.asyncio
async def test_set_job_schedules_projection_with_snapshot():
    recorded = AsyncMock()
    with (
        patch.object(js, "_get_redis", AsyncMock(return_value=None)),
        patch("src.services.agent.agent_run_service.record_job_status", new=recorded),
    ):
        await js.set_job(
            "job-1",
            {
                "status": JobStatus.RUNNING,
                "user_id": "u-1",
                "organization_id": "org-1",
                "request": {"thread_id": "t-1"},
            },
        )
        await _drain_projection_tasks()

    recorded.assert_awaited_once()
    job_id, payload = recorded.await_args.args
    assert job_id == "job-1"
    assert payload["status"] == JobStatus.RUNNING
    assert payload["user_id"] == "u-1"
    assert payload["organization_id"] == "org-1"
    assert payload["thread_id"] == "t-1"  # snapshotted out of nested request


@pytest.mark.asyncio
async def test_cas_in_memory_projects_the_claimed_transition():
    """confirm's awaiting→running claim reaches the projection (via set_job)."""
    recorded = AsyncMock()
    js._l1["job-2"] = {
        "status": "awaiting_confirmation",
        "user_id": "u-2",
        "created_at": time.time(),
    }
    with (
        patch.object(js, "_get_redis", AsyncMock(return_value=None)),
        patch("src.services.agent.agent_run_service.record_job_status", new=recorded),
    ):
        outcome = await js.compare_and_set_status(
            "job-2", JobStatus.AWAITING_CONFIRMATION, JobStatus.RUNNING
        )
        await _drain_projection_tasks()

    assert outcome == "claimed"
    statuses = [call.args[1]["status"] for call in recorded.await_args_list]
    assert JobStatus.RUNNING in statuses


def test_schedule_is_noop_without_running_loop():
    """Sync caller outside async context — must not raise, must not schedule."""
    with patch(
        "src.services.agent.agent_run_service.record_job_status", new=AsyncMock()
    ) as recorded:
        js.schedule_run_projection("job-3", {"status": "running", "user_id": "u"})
    recorded.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_skips_statusless_payload():
    with patch(
        "src.services.agent.agent_run_service.record_job_status", new=AsyncMock()
    ) as recorded:
        js.schedule_run_projection("job-4", {"user_id": "u"})
        await _drain_projection_tasks()
    recorded.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduling_failure_never_breaks_the_write_path():
    """A broken loop/create_task must degrade to a logged skip, not an error."""
    with (
        patch.object(js, "_get_redis", AsyncMock(return_value=None)),
        patch.object(asyncio, "get_running_loop", side_effect=RuntimeError("no loop")),
    ):
        await js.set_job("job-5", {"status": JobStatus.FAILED, "user_id": "u"})
    assert js._l1["job-5"]["status"] == JobStatus.FAILED
