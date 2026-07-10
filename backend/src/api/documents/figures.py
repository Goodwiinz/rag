"""Figures API Router - surface PyMuPDF-extracted figures for a document."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.core.database import get_db
from src.core.dependencies import get_current_organization, get_current_user
from src.models.document import Document
from src.models.document_processing import MultimodalContent
from src.models.organization import Organization
from src.models.user import User

logger = get_logger()
router = APIRouter(prefix="/api/v1/documents", tags=["figures"])


# ============================================================================
# GET /api/v1/documents/{document_id}/figures
# ============================================================================


@router.get("/{document_id}/figures")
async def list_figures(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """List PyMuPDF-extracted figures for a document, with signed crop URLs.

    Caption-only rows (vector figures with no raster crop) return
    ``image_url: null``.
    """
    doc_result = await db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.organization_id == organization.id,
                Document.is_deleted == False,
            )
        )
    )
    document = doc_result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    rows_result = await db.execute(
        select(MultimodalContent)
        .where(
            and_(
                MultimodalContent.document_id == document_id,
                MultimodalContent.organization_id == organization.id,
                MultimodalContent.extraction_method == "pymupdf_figures",
                MultimodalContent.is_deleted == False,
            )
        )
        .order_by(MultimodalContent.sequence_order)
    )
    rows = rows_result.scalars().all()

    helper = None
    try:
        from src.core.s3_client import S3StorageHelper

        helper = S3StorageHelper()
    except RuntimeError:
        logger.warning("figures_list_s3_unconfigured", document_id=str(document_id))

    figures = []
    for row in rows:
        meta = row.content_metadata or {}
        dims = row.media_dimensions or {}
        storage_key = meta.get("storage_key")

        image_url = None
        if helper is not None and storage_key:
            try:
                image_url = helper.create_signed_url(storage_key)
            except Exception as exc:
                logger.warning(
                    "figures_signed_url_failed",
                    document_id=str(document_id),
                    storage_key=storage_key,
                    error=str(exc),
                )

        figures.append(
            {
                "content_id": row.content_id,
                "page": meta.get("page"),
                "bbox": meta.get("bbox"),
                "figure_label": meta.get("figure_label"),
                "caption": row.processed_content,
                "width": dims.get("width"),
                "height": dims.get("height"),
                "image_url": image_url,
            }
        )

    return {
        "document_id": str(document_id),
        "figure_count": len(figures),
        "figures": figures,
    }
