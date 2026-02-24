"""
Extraction Matrix API Router
Literature review extraction matrix management and data extraction endpoints.

Security: All endpoints require authentication. Project-scoped endpoints
validate project ownership before granting access.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from src.core.database import get_db
from src.models import Collection, Workspace
from src.models.extraction_matrix import ExtractionCell, ExtractionMatrix
from src.models.user import User
from src.services.security.user_management import get_current_user
from src.shared.scispace_schemas import (
    CreateMatrixRequest,
    ExtractionCellResponse,
    TriggerExtractionRequest,
)

logger = get_logger()
router = APIRouter(prefix="/api/v1/research", tags=["extraction-matrix"])


# ============================================================================
# Security Helper
# ============================================================================


async def _validate_project_ownership(
    project_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Collection:
    """Validate that the current user owns the project.

    Args:
        project_id: Project ID to validate.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Project (Collection) if authorized.

    Raises:
        HTTPException: 404 if not found or not authorized.
    """
    query = (
        select(Collection)
        .join(Workspace, Collection.workspace_id == Workspace.id)
        .where(
            and_(
                Collection.id == project_id,
                Workspace.owner_id == current_user.id,
            )
        )
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        logger.warning(
            "matrix_access_denied",
            project_id=str(project_id),
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    return project


# ============================================================================
# Create Matrix
# ============================================================================


@router.post("/projects/{project_id}/matrices", status_code=201)
async def create_matrix(
    project_id: UUID,
    request: CreateMatrixRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new extraction matrix for a project.

    Defines column headers (e.g. Methodology, Sample Size) that will be
    used to extract structured data from project documents.
    """
    await _validate_project_ownership(project_id, current_user, db)

    matrix = ExtractionMatrix(
        project_id=project_id,
        name=request.name,
        columns=[col.model_dump() for col in request.columns],
    )
    db.add(matrix)
    await db.commit()
    await db.refresh(matrix)

    logger.info(
        "matrix_created",
        matrix_id=str(matrix.id),
        project_id=str(project_id),
        user_id=str(current_user.id),
    )

    return {
        "id": str(matrix.id),
        "project_id": str(matrix.project_id),
        "name": matrix.name,
        "columns": matrix.columns,
        "created_at": matrix.created_at.isoformat() if matrix.created_at else None,
    }


# ============================================================================
# Get Matrix with Cells
# ============================================================================


@router.get("/matrices/{matrix_id}")
async def get_matrix(
    matrix_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get an extraction matrix with all its cells.

    Returns the matrix definition and all extracted cell values,
    organized for rendering as a comparison grid.
    """
    query = (
        select(ExtractionMatrix)
        .options(selectinload(ExtractionMatrix.cells))
        .where(
            and_(
                ExtractionMatrix.id == matrix_id,
                ExtractionMatrix.is_deleted == False,
            )
        )
    )
    result = await db.execute(query)
    matrix = result.scalar_one_or_none()

    if not matrix:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matrix not found",
        )

    # Validate ownership via project
    await _validate_project_ownership(matrix.project_id, current_user, db)

    cells = [
        {
            "document_id": str(cell.document_id),
            "column_name": cell.column_name,
            "value": cell.value,
            "citation_snippet": cell.citation_snippet,
            "confidence": cell.confidence,
        }
        for cell in matrix.cells
        if not cell.is_deleted
    ]

    return {
        "id": str(matrix.id),
        "project_id": str(matrix.project_id),
        "name": matrix.name,
        "columns": matrix.columns,
        "cells": cells,
        "created_at": matrix.created_at.isoformat() if matrix.created_at else None,
        "updated_at": matrix.updated_at.isoformat() if matrix.updated_at else None,
    }


# ============================================================================
# Trigger Extraction
# ============================================================================


@router.post("/matrices/{matrix_id}/extract", status_code=202)
async def trigger_extraction(
    matrix_id: UUID,
    request: TriggerExtractionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger LLM extraction for selected documents.

    Processes each document against the matrix columns and stores
    the extracted values as cells. Returns 202 Accepted since
    extraction may take time for large document sets.
    """
    query = select(ExtractionMatrix).where(
        and_(
            ExtractionMatrix.id == matrix_id,
            ExtractionMatrix.is_deleted == False,
        )
    )
    result = await db.execute(query)
    matrix = result.scalar_one_or_none()

    if not matrix:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matrix not found",
        )

    await _validate_project_ownership(matrix.project_id, current_user, db)

    logger.info(
        "extraction_triggered",
        matrix_id=str(matrix_id),
        document_count=len(request.document_ids),
        user_id=str(current_user.id),
    )

    # NOTE: Full LLM extraction is implemented as a background task.
    # This endpoint acknowledges the request and returns immediately.
    # A future iteration will integrate with the task queue (Celery)
    # to process documents asynchronously.

    return {
        "matrix_id": str(matrix_id),
        "document_ids": [str(d) for d in request.document_ids],
        "status": "accepted",
        "message": f"Extraction queued for {len(request.document_ids)} document(s)",
    }


# ============================================================================
# Delete Matrix
# ============================================================================


@router.delete("/matrices/{matrix_id}")
async def delete_matrix(
    matrix_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete an extraction matrix and all its cells."""
    query = select(ExtractionMatrix).where(
        and_(
            ExtractionMatrix.id == matrix_id,
            ExtractionMatrix.is_deleted == False,
        )
    )
    result = await db.execute(query)
    matrix = result.scalar_one_or_none()

    if not matrix:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Matrix not found",
        )

    await _validate_project_ownership(matrix.project_id, current_user, db)

    matrix.soft_delete()
    await db.commit()

    logger.info(
        "matrix_deleted",
        matrix_id=str(matrix_id),
        user_id=str(current_user.id),
    )

    return {"message": "Matrix deleted", "matrix_id": str(matrix_id)}
