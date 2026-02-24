"""Tone Engine API Router - text rewriting with academic tone adjustment."""

from fastapi import APIRouter, Depends, HTTPException, status
from structlog import get_logger

from src.models.user import User
from src.services.research.tone_engine_service import ToneEngineService
from src.services.security.user_management import get_current_user
from src.shared.scispace_schemas import RewriteRequest, RewriteResponse

logger = get_logger()
router = APIRouter(prefix="/api/v1/research", tags=["tone-engine"])

_service = ToneEngineService()


@router.post("/rewrite", response_model=RewriteResponse)
async def rewrite_text(
    request: RewriteRequest,
    current_user: User = Depends(get_current_user),
):
    """Rewrite text with the specified academic tone."""
    try:
        result = await _service.rewrite(
            text=request.text,
            tone=request.tone.value,
            model=request.model,
            preserve_citations=request.preserve_citations,
        )
        return RewriteResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("rewrite_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rewrite text",
        )
