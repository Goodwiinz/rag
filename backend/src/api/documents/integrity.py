"""Integrity API Router - AI authorship detection for documents."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.core.database import get_db
from src.models.document import Document
from src.models.integrity_score import IntegrityScore
from src.models.user import User
from src.services.documents.integrity_detection_service import IntegrityDetectionService
from src.services.security.user_management import get_current_user
from src.shared.scispace_schemas import IntegrityScoreResponse, IntegritySegmentScore

logger = get_logger()
router = APIRouter(prefix="/api/v1/documents", tags=["integrity"])

_service = IntegrityDetectionService()


# ============================================================================
# POST /api/v1/documents/{document_id}/integrity-check
# ============================================================================


@router.post("/{document_id}/integrity-check", status_code=status.HTTP_202_ACCEPTED)
async def trigger_integrity_check(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI authorship detection for a document.

    Analyzes the document text using a RoBERTa-based classifier and stores
    the resulting integrity score. Returns 202 Accepted since analysis may
    take time for large documents.
    """
    # Verify document exists and belongs to current user
    doc_result = await db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.uploaded_by_user_id == current_user.id,
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

    # Determine text to analyze (prefer content field, fall back to title)
    text = getattr(document, "content", None) or getattr(document, "extracted_text", None) or document.title or ""

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document has no analyzable text content",
        )

    try:
        result = await _service.analyze(text)
    except Exception as exc:
        logger.error(
            "integrity_analysis_failed",
            document_id=str(document_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze document integrity",
        )

    analyzed_at = datetime.now(timezone.utc)

    # Upsert: delete existing score for this document then insert new one
    existing_result = await db.execute(
        select(IntegrityScore).where(IntegrityScore.document_id == document_id)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        existing.ai_probability = result["ai_probability"]
        existing.human_probability = result["human_probability"]
        existing.method = result["method"]
        existing.analyzed_at = analyzed_at
        existing.segment_scores = result["segment_scores"]
        score = existing
    else:
        score = IntegrityScore(
            document_id=document_id,
            ai_probability=result["ai_probability"],
            human_probability=result["human_probability"],
            method=result["method"],
            analyzed_at=analyzed_at,
            segment_scores=result["segment_scores"],
        )
        db.add(score)

    await db.commit()
    await db.refresh(score)

    logger.info(
        "integrity_check_complete",
        document_id=str(document_id),
        ai_probability=result["ai_probability"],
    )

    return {
        "document_id": str(document_id),
        "status": "accepted",
        "ai_probability": result["ai_probability"],
        "human_probability": result["human_probability"],
        "method": result["method"],
        "analyzed_at": analyzed_at.isoformat(),
    }


# ============================================================================
# GET /api/v1/documents/{document_id}/integrity-score
# ============================================================================


@router.get(
    "/{document_id}/integrity-score",
    response_model=IntegrityScoreResponse,
)
async def get_integrity_score(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the stored AI integrity score for a document.

    Returns the most recent integrity analysis result. Returns 404 if no
    analysis has been run for this document yet.
    """
    result = await db.execute(
        select(IntegrityScore).where(
            and_(
                IntegrityScore.document_id == document_id,
                IntegrityScore.is_deleted == False,
            )
        )
    )
    score = result.scalar_one_or_none()

    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No integrity score found for this document. Run a check first.",
        )

    return IntegrityScoreResponse(
        document_id=str(score.document_id),
        ai_probability=score.ai_probability,
        human_probability=score.human_probability,
        method=score.method,
        analyzed_at=score.analyzed_at,
        segment_scores=[
            IntegritySegmentScore(
                text_preview=seg["text_preview"],
                ai_probability=seg["ai_probability"],
            )
            for seg in (score.segment_scores or [])
        ],
    )
