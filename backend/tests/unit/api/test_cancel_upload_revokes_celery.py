"""R4-M6 regression: cancel_upload never revoked the underlying Celery task.

The processing-job branch of ``cancel_upload`` set the ProcessingJob row to
CANCELLED and committed, but (unlike the equivalent path in
``src/api/documents/processing.py``) never called
``current_app.control.revoke(...)`` — so the Celery worker kept running the
job after the API told the caller it was cancelled. Mocked DB/session, no
real Postgres or Celery broker.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.processing import JobStatus, ProcessingJob
from src.models.user import User, UserRole

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _mock_db_with_job(job: ProcessingJob) -> AsyncMock:
    db = AsyncMock()

    job_result = MagicMock()
    job_result.scalars.return_value.first.return_value = job
    db.execute = AsyncMock(return_value=job_result)
    db.commit = AsyncMock()
    return db


async def test_cancel_upload_revokes_celery_task_when_present() -> None:
    from src.api.documents.files import cancel_upload

    user_id = uuid4()
    job_id = uuid4()
    upload_id = str(uuid4())

    job = ProcessingJob(
        id=job_id,
        created_by_user_id=user_id,
        status=JobStatus.RUNNING,
        celery_task_id="celery-task-abc123",
    )

    db = _mock_db_with_job(job)
    user = User(id=user_id, role=UserRole.USER)

    with patch("src.tasks.processing_tasks.current_app") as mock_app:
        result = await cancel_upload(
            upload_id=upload_id,
            current_user=user,
            db=db,
            file_service=MagicMock(),
        )

    mock_app.control.revoke.assert_called_once_with(
        "celery-task-abc123", terminate=True
    )
    assert result["message"] == "Upload cancelled successfully"


async def test_cancel_upload_skips_revoke_when_no_celery_task_id() -> None:
    from src.api.documents.files import cancel_upload

    user_id = uuid4()
    job = ProcessingJob(
        id=uuid4(),
        created_by_user_id=user_id,
        status=JobStatus.PENDING,
        celery_task_id=None,
    )

    db = _mock_db_with_job(job)
    user = User(id=user_id, role=UserRole.USER)

    with patch("src.tasks.processing_tasks.current_app") as mock_app:
        await cancel_upload(
            upload_id=str(uuid4()),
            current_user=user,
            db=db,
            file_service=MagicMock(),
        )

    mock_app.control.revoke.assert_not_called()
