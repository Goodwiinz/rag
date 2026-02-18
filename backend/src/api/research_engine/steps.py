"""Research Engine step endpoints."""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.research_step import ResearchStep
from src.models.user import User
from src.schemas.research_engine import StepResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/research-engine",
    tags=["research-engine"],
)


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
    return StepResponse.model_validate(step)
