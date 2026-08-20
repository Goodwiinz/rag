"""Integrity API Router - AI authorship detection for documents."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from src.core.database import get_db
from src.core.dependencies import get_current_organization, get_current_user
from src.core.rate_limit import create_rate_limiter
from src.models.document import Document
from src.models.integrity_score import IntegrityScore
from src.models.organization import Organization
from src.models.user import User
from src.services.documents.integrity_detection_service import IntegrityDetectionService
from src.shared.scispace_schemas import IntegrityScoreResponse, IntegritySegmentScore

logger = get_logger()
router = APIRouter(prefix="/api/v1/documents", tags=["integrity"])

_service = IntegrityDetectionService()

# Per-user rate limiter for the heavy RoBERTa integrity-check route (R4-L5).
# Reuses the same Redis-backed/in-memory-fallback limiter as agent/execute.py
# rather than inventing new infrastructure.
_INTEGRITY_RATE_LIMIT_RPM = 5
_integrity_rate_limiter = create_rate_limiter(
    max_attempts=_INTEGRITY_RATE_LIMIT_RPM,
    window_minutes=1,
)


def build_integrity_upsert_stmt(document_id: UUID, result: dict, analyzed_at: datetime):
    """Build an INSERT ... ON CONFLICT DO UPDATE statement for IntegrityScore.

    Conflicts on the (document_id, method) unique constraint (uq_integrity_doc_method),
    so re-running a check for the same document+method updates the existing row
    atomically instead of racing a select-then-update/insert.
    """
    insert_stmt = pg_insert(IntegrityScore).values(
        document_id=document_id,
        ai_probability=result["ai_probability"],
        human_probability=result["human_probability"],
        method=result["method"],
        analyzed_at=analyzed_at,
        segment_scores=result["segment_scores"],
    )
    return insert_stmt.on_conflict_do_update(
        index_elements=[IntegrityScore.document_id, IntegrityScore.method],
        set_={
            "ai_probability": insert_stmt.excluded.ai_probability,
            "human_probability": insert_stmt.excluded.human_probability,
            "analyzed_at": insert_stmt.excluded.analyzed_at,
            "segment_scores": insert_stmt.excluded.segment_scores,
        },
    )


# ============================================================================
# POST /api/v1/documents/{document_id}/integrity-check
# ============================================================================


@router.post("/{document_id}/integrity-check", status_code=status.HTTP_202_ACCEPTED)
async def trigger_integrity_check(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI authorship detection for a document.

    Analyzes the document text using a RoBERTa-based classifier and stores
    the resulting integrity score. Returns 202 Accepted since analysis may
    take time for large documents.
    """
    _allowed, _retry_after = await _integrity_rate_limiter.check_rate_limit(
        str(current_user.id), prefix="integrity_check"
    )
    if not _allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {_retry_after}s.",
        )
    await _integrity_rate_limiter.record_attempt(
        str(current_user.id), prefix="integrity_check"
    )

    # Verify document exists and belongs to current user's organization
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

    # Determine text to analyze (prefer content_text field, fall back to title)
    text = document.content_text or document.title or ""

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

    # Upsert on the (document_id, method) unique constraint in one statement.
    # A prior select-then-update/insert raced under concurrent requests for
    # the same document (two requests could both see "no row" and both try
    # to INSERT, raising IntegrityError, or both UPDATE the same row via a
    # non-unique select -> MultipleResultsFound once duplicates existed).
    upsert_stmt = build_integrity_upsert_stmt(document_id, result, analyzed_at)
    await db.execute(upsert_stmt)
    await db.commit()

    score_result = await db.execute(
        select(IntegrityScore).where(
            and_(
                IntegrityScore.document_id == document_id,
                IntegrityScore.method == result["method"],
            )
        )
    )
    score = score_result.scalar_one()

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
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the stored AI integrity score for a document.

    Returns the most recent integrity analysis result. Returns 404 if no
    analysis has been run for this document yet.
    """
    # Verify document exists and belongs to current user's organization
    doc_result = await db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.organization_id == organization.id,
                Document.is_deleted == False,
            )
        )
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

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
