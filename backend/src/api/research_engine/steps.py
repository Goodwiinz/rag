"""Research Engine step endpoints."""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.research_blueprint import ResearchBlueprint
from src.models.research_project import ResearchProject
from src.models.research_run import ResearchRun
from src.models.research_step import ResearchStep
from src.models.user import User
from src.schemas.research_engine import StepResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/research-engine",
    tags=["research-engine"],
)


async def _verify_run_access(
    run_id: UUID, user_id: UUID, db: AsyncSession
) -> ResearchRun:
    """Verify user owns the project for this run. Returns the run."""
    run_query = select(ResearchRun).where(ResearchRun.id == run_id)
    run_result = await db.execute(run_query)
    run = run_result.scalars().first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    bp_query = select(ResearchBlueprint).where(
        ResearchBlueprint.id == run.blueprint_id
    )
    bp_result = await db.execute(bp_query)
    blueprint = bp_result.scalars().first()
    if not blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    proj_query = select(ResearchProject).where(
        ResearchProject.id == blueprint.project_id,
        ResearchProject.owner_id == user_id,
    )
    proj_result = await db.execute(proj_query)
    if not proj_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )
    return run


@router.get(
    "/runs/{run_id}/steps",
    response_model=List[StepResponse],
)
async def list_steps(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[StepResponse]:
    """List steps for a run, ordered by step_index."""
    await _verify_run_access(run_id, current_user.id, db)
    query = (
        select(ResearchStep)
        .where(ResearchStep.run_id == run_id)
        .order_by(ResearchStep.step_index)
    )
    result = await db.execute(query)
    steps = result.scalars().all()
    return [StepResponse.model_validate(s) for s in steps]


@router.get(
    "/steps/{step_id}",
    response_model=StepResponse,
)
async def get_step(
    step_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StepResponse:
    """Get a single step."""
    query = select(ResearchStep).where(ResearchStep.id == step_id)
    result = await db.execute(query)
    step = result.scalars().first()
    if not step:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Step not found",
        )
    await _verify_run_access(step.run_id, current_user.id, db)
    return StepResponse.model_validate(step)
