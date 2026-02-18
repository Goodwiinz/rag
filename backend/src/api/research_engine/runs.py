"""Research Engine run endpoints."""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.research_blueprint import ResearchBlueprint
from src.models.research_run import ResearchRun, RunStatus
from src.models.user import User
from src.schemas.research_engine import RunCreate, RunResponse
from src.services.research_engine.engine import WorkflowEngine
from src.services.research_engine.step_executor import StepExecutor

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/research-engine",
    tags=["research-engine"],
)


@router.post(
    "/blueprints/{blueprint_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_run(
    blueprint_id: UUID,
    body: RunCreate = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Start a new research run from a blueprint."""
    if body is None:
        body = RunCreate()

    # Look up the blueprint
    query = select(ResearchBlueprint).where(
        ResearchBlueprint.id == blueprint_id,
    )
    result = await db.execute(query)
    blueprint = result.scalars().first()
    if not blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blueprint not found",
        )

    # Mark blueprint as immutable
    blueprint.is_immutable = True

    # Create the run
    run = ResearchRun(
        blueprint_id=blueprint_id,
        blueprint_version=blueprint.version,
        status=RunStatus.PENDING.value,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return RunResponse.model_validate(run)


@router.get(
    "/runs/{run_id}",
    response_model=RunResponse,
)
async def get_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Get run status."""
    query = select(ResearchRun).where(ResearchRun.id == run_id)
    result = await db.execute(query)
    run = result.scalars().first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    return RunResponse.model_validate(run)


@router.post(
    "/runs/{run_id}/pause",
    response_model=RunResponse,
)
async def pause_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Pause a running run."""
    query = select(ResearchRun).where(ResearchRun.id == run_id)
    result = await db.execute(query)
    run = result.scalars().first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    if run.status != RunStatus.RUNNING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run is not currently running",
        )
    run.status = RunStatus.PAUSED.value
    await db.commit()
    await db.refresh(run)
    return RunResponse.model_validate(run)


@router.post(
    "/runs/{run_id}/resume",
    response_model=RunResponse,
)
async def resume_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    """Resume a paused run."""
    query = select(ResearchRun).where(ResearchRun.id == run_id)
    result = await db.execute(query)
    run = result.scalars().first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    if run.status != RunStatus.PAUSED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run is not currently paused",
        )
    run.status = RunStatus.RUNNING.value
    await db.commit()
    await db.refresh(run)
    return RunResponse.model_validate(run)


@router.get(
    "/runs/{run_id}/manifest",
)
async def get_manifest(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get reproducibility manifest for a completed run."""
    query = select(ResearchRun).where(ResearchRun.id == run_id)
    result = await db.execute(query)
    run = result.scalars().first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    if run.status != RunStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run is not completed",
        )
    return run.reproducibility_manifest or {}


@router.post(
    "/runs/{run_id}/stream",
)
async def stream_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream research run execution via SSE.

    Accepts runs in PENDING or PAUSED status. Returns 404 for missing runs,
    409 for runs in non-streamable states (completed, failed, running).
    """
    query = select(ResearchRun).where(ResearchRun.id == run_id)
    result = await db.execute(query)
    run = result.scalars().first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    # Only pending or paused runs can be streamed
    streamable = {RunStatus.PENDING.value, RunStatus.PAUSED.value}
    if run.status not in streamable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run is in '{run.status}' state and cannot be streamed",
        )

    # Look up the blueprint
    bp_query = select(ResearchBlueprint).where(
        ResearchBlueprint.id == run.blueprint_id,
    )
    bp_result = await db.execute(bp_query)
    blueprint = bp_result.scalars().first()
    if not blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blueprint not found",
        )

    async def event_generator():
        """Yield SSE-formatted events from the workflow engine."""
        executor = StepExecutor(providers={}, connectors={})
        engine = WorkflowEngine(executor=executor)

        start_from = 0
        if run.status == RunStatus.PAUSED.value:
            # Resume from the next step after the last completed one
            start_from = 0  # Engine handles resume internally

        async for event in engine.run(
            blueprint=blueprint,
            run_id=run_id,
            start_from_step=start_from,
        ):
            event_type = event.get("event", "message")
            data = json.dumps(event)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
