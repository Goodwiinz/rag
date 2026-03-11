"""
Extraction Matrix API Router
Literature review extraction matrix management and data extraction endpoints.

Security: All endpoints require authentication. Project-scoped endpoints
validate project ownership before granting access.
"""

import asyncio
import uuid
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from src.core.database import get_db
from src.models import Collection, CollectionDocument, Workspace
from src.models.document import Document
from src.models.extraction_matrix import ExtractionCell, ExtractionMatrix
from src.models.user import User
from src.services.research.extraction_matrix_service import ExtractionMatrixService
from src.services.security.user_management import get_current_user
from src.shared.scispace_schemas import (
    CreateMatrixRequest,
    ExtractionCellResponse,
    TriggerExtractionRequest,
    UpdateMatrixRequest,
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
# List Matrices for Project
# ============================================================================


@router.get("/projects/{project_id}/matrices")
async def list_matrices(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all extraction matrices for a project."""
    await _validate_project_ownership(project_id, current_user, db)

    query = (
        select(ExtractionMatrix)
        .where(ExtractionMatrix.project_id == project_id)
        .order_by(ExtractionMatrix.created_at.desc())
    )
    result = await db.execute(query)
    matrices = result.scalars().all()

    return {
        "matrices": [
            {
                "id": str(m.id),
                "project_id": str(m.project_id),
                "name": m.name,
                "columns": m.columns,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in matrices
        ],
        "total": len(matrices),
    }


# ============================================================================
# Create Matrix (with auto-extraction)
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
    Automatically triggers extraction for all existing project documents.
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

    # Auto-extract: query all documents in the project
    extraction_task_id = None
    doc_query = select(CollectionDocument.document_id).where(
        CollectionDocument.collection_id == project_id
    )
    doc_result = await db.execute(doc_query)
    document_ids = [row[0] for row in doc_result.all()]

    if document_ids:
        extraction_task_id = f"auto-create-{uuid.uuid4().hex[:12]}"
        service = ExtractionMatrixService()
        asyncio.create_task(
            service.run_background_extraction(
                matrix_id=matrix.id,
                document_ids=document_ids,
                columns=matrix.columns,
                task_id=extraction_task_id,
            )
        )
        logger.info(
            "auto_extraction_started",
            matrix_id=str(matrix.id),
            task_id=extraction_task_id,
            document_count=len(document_ids),
        )

    return {
        "id": str(matrix.id),
        "project_id": str(matrix.project_id),
        "name": matrix.name,
        "columns": matrix.columns,
        "created_at": matrix.created_at.isoformat() if matrix.created_at else None,
        "extraction_task_id": extraction_task_id,
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
# Update Matrix (PATCH)
# ============================================================================


@router.patch("/matrices/{matrix_id}")
async def update_matrix(
    matrix_id: UUID,
    request: UpdateMatrixRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an extraction matrix (rename, add/remove/reorder columns).

    When clear_stale_cells is true and columns changed, cells whose
    column_name no longer matches any column are deleted.
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

    await _validate_project_ownership(matrix.project_id, current_user, db)

    columns_changed = False
    stale_document_ids: List[str] = []

    if request.name is not None:
        matrix.name = request.name

    if request.columns is not None:
        old_col_names = {c["name"] for c in matrix.columns}
        new_col_names = {c.name for c in request.columns}
        columns_changed = old_col_names != new_col_names

        matrix.columns = [col.model_dump() for col in request.columns]

        if request.clear_stale_cells and columns_changed:
            stale_cells = [
                cell
                for cell in matrix.cells
                if not cell.is_deleted and cell.column_name not in new_col_names
            ]
            stale_doc_set = set()
            for cell in stale_cells:
                cell.is_deleted = True
                stale_doc_set.add(str(cell.document_id))
            stale_document_ids = list(stale_doc_set)

    await db.commit()
    await db.refresh(matrix)

    logger.info(
        "matrix_updated",
        matrix_id=str(matrix_id),
        user_id=str(current_user.id),
        columns_changed=columns_changed,
    )

    return {
        "id": str(matrix.id),
        "project_id": str(matrix.project_id),
        "name": matrix.name,
        "columns": matrix.columns,
        "columns_changed": columns_changed,
        "stale_document_ids": stale_document_ids,
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

    # Fetch documents and run extraction inline
    extraction_service = ExtractionMatrixService()

    from src.core.config import settings
    import openai

    azure_key = settings.AZURE_OPENAI_CHAT_API_KEY or settings.AZURE_OPENAI_API_KEY
    azure_endpoint = settings.AZURE_OPENAI_CHAT_ENDPOINT or settings.AZURE_OPENAI_ENDPOINT
    azure_deployment = getattr(settings, "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o")
    azure_api_version = getattr(settings, "AZURE_OPENAI_CHAT_API_VERSION", "2024-05-01-preview")
    openai_key = settings.OPENAI_API_KEY

    if azure_key and azure_endpoint:
        client = openai.AsyncAzureOpenAI(
            api_key=azure_key,
            azure_endpoint=azure_endpoint,
            api_version=azure_api_version,
        )
        model = azure_deployment
    elif openai_key:
        client = openai.AsyncOpenAI(api_key=openai_key)
        model = "gpt-4o-mini"
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No OpenAI or Azure OpenAI API key configured.",
        )
    extracted_count = 0

    for doc_id in request.document_ids:
        doc_result = await db.execute(
            select(Document).where(Document.id == doc_id)
        )
        document = doc_result.scalar_one_or_none()
        if not document or not document.content_text:
            logger.warning(
                "extraction_skip_no_text",
                document_id=str(doc_id),
            )
            continue

        # Truncate to ~12k chars to fit context window
        doc_text = document.content_text[:12000]

        prompt = extraction_service._build_extraction_prompt(
            matrix.columns, doc_text
        )

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000,
            )
            raw_json = response.choices[0].message.content or ""
            logger.info(
                "extraction_llm_response",
                document_id=str(doc_id),
                raw_preview=raw_json[:500],
            )
            parsed = extraction_service._parse_extraction_result(
                raw_json, matrix.columns
            )
        except Exception as e:
            logger.error(
                "extraction_llm_failed",
                document_id=str(doc_id),
                error=str(e),
            )
            continue

        # Upsert cells
        for col_name, cell_data in parsed.items():
            existing = await db.execute(
                select(ExtractionCell).where(
                    and_(
                        ExtractionCell.matrix_id == matrix_id,
                        ExtractionCell.document_id == doc_id,
                        ExtractionCell.column_name == col_name,
                    )
                )
            )
            existing_cell = existing.scalar_one_or_none()

            if existing_cell:
                existing_cell.value = cell_data.get("value")
                existing_cell.citation_snippet = cell_data.get("citation")
                existing_cell.confidence = 0.8
            else:
                db.add(ExtractionCell(
                    matrix_id=matrix_id,
                    document_id=doc_id,
                    column_name=col_name,
                    value=cell_data.get("value"),
                    citation_snippet=cell_data.get("citation"),
                    confidence=0.8,
                ))

        extracted_count += 1

    await db.commit()

    logger.info(
        "extraction_complete",
        matrix_id=str(matrix_id),
        extracted_count=extracted_count,
    )

    return {
        "matrix_id": str(matrix_id),
        "document_ids": [str(d) for d in request.document_ids],
        "status": "completed",
        "message": f"Extraction completed for {extracted_count} document(s)",
    }


# ============================================================================
# Extraction Task Status
# ============================================================================


@router.get("/extraction-tasks/{task_id}")
async def get_extraction_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get the status of a background extraction task."""
    task_status = ExtractionMatrixService.get_extraction_status(task_id)

    if not task_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction task not found",
        )

    return task_status


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
