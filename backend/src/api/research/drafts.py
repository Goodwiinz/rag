"""
Drafts API Router
Literature review draft generation and management endpoints

Security: All endpoints validate project ownership before granting access.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.services.security.user_management import get_current_user
from src.models.user import User
from src.models import Collection, Workspace
from src.services.research.draft_generation_service import DraftGenerationService, DraftGenerationStatus
from structlog import get_logger

logger = get_logger()
router = APIRouter(prefix="/api/v1/projects/{project_id}/drafts", tags=["drafts"])


# ============================================================================
# Security Helper
# ============================================================================


async def _validate_project_ownership(
    project_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Collection:
    """
    Validate that the current user owns the project.

    Args:
        project_id: Project ID to validate
        current_user: Authenticated user
        db: Database session

    Returns:
        Project (Collection) if authorized

    Raises:
        HTTPException: 403 if not authorized, 404 if not found
    """
    query = (
        select(Collection)
        .join(Workspace, Collection.workspace_id == Workspace.id)
        .where(
            and_(
                Collection.id == project_id,
                Workspace.user_id == current_user.id,
            )
        )
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        logger.warning(
            "draft_access_denied",
            project_id=str(project_id),
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    return project


# ============================================================================
# Draft Generation (T079)
# ============================================================================


@router.post("", status_code=202)
async def generate_draft(
    project_id: UUID,
    themes: List[str] = Query(..., description="Themes to focus on"),
    document_ids: Optional[List[UUID]] = Query(None, description="Specific documents to include"),
    style: str = Query("academic", description="Writing style: academic, technical, summary"),
    max_sections: int = Query(5, ge=2, le=10, description="Maximum number of sections"),
    include_abstract: bool = Query(True, description="Include an abstract"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a literature review draft from project documents.

    Returns a task_id that can be used to check generation status.
    Generation runs asynchronously in the background.
    """
    # Validate project ownership
    await _validate_project_ownership(project_id, current_user, db)

    service = DraftGenerationService(db)

    result = await service.generate_draft(
        project_id=project_id,
        user_id=current_user.id,
        themes=themes,
        document_ids=document_ids,
        style=style,
        max_sections=max_sections,
        include_abstract=include_abstract,
    )

    return result


# ============================================================================
# Draft Listing (T080)
# ============================================================================


@router.get("")
async def list_drafts(
    project_id: UUID,
    include_content: bool = Query(False, description="Include full content"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all drafts for a project.

    Returns drafts ordered by version (newest first).
    """
    # Validate project ownership
    await _validate_project_ownership(project_id, current_user, db)

    service = DraftGenerationService(db)

    result = await service.list_drafts(
        project_id=project_id,
        include_content=include_content,
        skip=skip,
        limit=limit,
    )

    drafts = []
    for draft in result["drafts"]:
        draft_data = {
            "id": str(draft.id),
            "project_id": str(draft.project_id),
            "version": draft.version,
            "title": draft.title,
            "themes": draft.themes,
            "word_count": draft.word_count,
            "citation_count": draft.citation_count,
            "is_current": draft.is_current,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
        }
        if include_content:
            draft_data["content"] = draft.content
        drafts.append(draft_data)

    return {
        "drafts": drafts,
        "total": result["total"],
        "skip": result["skip"],
        "limit": result["limit"],
    }


# ============================================================================
# Draft Detail Endpoints (T081)
# ============================================================================


@router.get("/current")
async def get_current_draft(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current (latest) draft for a project."""
    # Validate project ownership
    await _validate_project_ownership(project_id, current_user, db)

    service = DraftGenerationService(db)

    draft = await service.get_draft(project_id, current_only=True)
    if not draft:
        raise HTTPException(status_code=404, detail="No current draft found")

    return {
        "id": str(draft.id),
        "project_id": str(draft.project_id),
        "version": draft.version,
        "title": draft.title,
        "content": draft.content,
        "themes": draft.themes,
        "word_count": draft.word_count,
        "citation_count": draft.citation_count,
        "generation_params": draft.generation_params,
        "is_current": draft.is_current,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }


@router.get("/{draft_id}")
async def get_draft(
    project_id: UUID,
    draft_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific draft by ID."""
    # Validate project ownership
    await _validate_project_ownership(project_id, current_user, db)

    service = DraftGenerationService(db)

    draft = await service.get_draft(project_id, draft_id=draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    return {
        "id": str(draft.id),
        "project_id": str(draft.project_id),
        "version": draft.version,
        "title": draft.title,
        "content": draft.content,
        "themes": draft.themes,
        "word_count": draft.word_count,
        "citation_count": draft.citation_count,
        "generation_params": draft.generation_params,
        "is_current": draft.is_current,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }


@router.delete("/{draft_id}")
async def delete_draft(
    project_id: UUID,
    draft_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific draft."""
    # Validate project ownership
    await _validate_project_ownership(project_id, current_user, db)

    service = DraftGenerationService(db)

    success = await service.delete_draft(project_id, draft_id)
    if not success:
        raise HTTPException(status_code=404, detail="Draft not found")

    return {"message": "Draft deleted", "draft_id": str(draft_id)}


# ============================================================================
# Draft Citations (T082)
# ============================================================================


@router.get("/{draft_id}/citations")
async def get_draft_citations(
    project_id: UUID,
    draft_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get citations mapped to [Doc N] indices for a draft."""
    # Validate project ownership
    await _validate_project_ownership(project_id, current_user, db)

    service = DraftGenerationService(db)

    citations = await service.get_draft_citations(project_id, draft_id)

    return {
        "citations": [
            {
                "id": str(c.id),
                "citation_index": c.citation_index,
                "document_id": str(c.document_id) if c.document_id else None,
                "citation_id": str(c.citation_id) if c.citation_id else None,
                "snippet": c.snippet,
                "context": c.context,
            }
            for c in citations
        ],
        "total": len(citations),
    }


# ============================================================================
# Draft Comparison (T083)
# ============================================================================


@router.get("/compare")
async def compare_drafts(
    project_id: UUID,
    version_a: int = Query(..., description="First version to compare"),
    version_b: int = Query(..., description="Second version to compare"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compare two draft versions."""
    # Validate project ownership
    await _validate_project_ownership(project_id, current_user, db)

    service = DraftGenerationService(db)

    result = await service.compare_drafts(project_id, version_a, version_b)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


# ============================================================================
# Draft Export (T084)
# ============================================================================


@router.post("/{draft_id}/export")
async def export_draft(
    project_id: UUID,
    draft_id: UUID,
    format: str = Query("markdown", description="Export format: markdown, latex"),
    include_bibliography: bool = Query(True, description="Include bibliography"),
    bib_format: str = Query("bibtex", description="Bibliography format"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export draft to LaTeX (.tex + .bib) or Markdown."""
    # Validate project ownership
    await _validate_project_ownership(project_id, current_user, db)

    service = DraftGenerationService(db)

    result = await service.export_draft(
        project_id=project_id,
        draft_id=draft_id,
        format=format,
        include_bibliography=include_bibliography,
        bib_format=bib_format,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ============================================================================
# Generation Status (T085)
# ============================================================================


@router.get("/status/{task_id}")
async def get_generation_status(
    project_id: UUID,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status of an ongoing draft generation."""
    # Validate project ownership
    await _validate_project_ownership(project_id, current_user, db)

    status = DraftGenerationService.get_status(task_id)

    if not status:
        raise HTTPException(status_code=404, detail="Task not found")

    return status


# ============================================================================
# Cancel Generation (T086)
# ============================================================================


@router.post("/cancel/{task_id}")
async def cancel_generation(
    project_id: UUID,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an ongoing draft generation."""
    # Validate project ownership
    await _validate_project_ownership(project_id, current_user, db)

    success = DraftGenerationService.cancel_generation(task_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel: task not found or already completed",
        )

    return {"message": "Generation cancelled", "task_id": task_id}
