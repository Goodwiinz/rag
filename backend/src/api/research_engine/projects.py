"""Research Engine project endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.research_project import ResearchProject
from src.models.user import User
from src.schemas.research_engine import ProjectCreate, ProjectResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/research-engine/projects",
    tags=["research-engine"],
)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new research project."""
    project = ResearchProject(
        name=body.name,
        description=body.description,
        owner_id=current_user.id,
        settings=body.settings,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get(
    "",
    response_model=List[ProjectResponse],
)
async def list_projects(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ProjectResponse]:
    """List research projects for the current user."""
    query = select(ResearchProject).where(
        ResearchProject.owner_id == current_user.id,
        ResearchProject.is_deleted == False,
    )
    if status_filter:
        query = query.where(ResearchProject.status == status_filter)
    query = query.order_by(ResearchProject.updated_at.desc())

    result = await db.execute(query)
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Get a single research project."""
    query = select(ResearchProject).where(
        ResearchProject.id == project_id,
        ResearchProject.owner_id == current_user.id,
        ResearchProject.is_deleted == False,
    )
    result = await db.execute(query)
    project = result.scalars().first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return ProjectResponse.model_validate(project)
