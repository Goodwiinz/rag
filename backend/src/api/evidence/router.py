"""
Evidence Agreement Meter API endpoints
"""

import logging
import threading
import time
from typing import Dict, List, Optional
from uuid import UUID

import redis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...core.dependencies import get_current_user
from ...middleware.rate_limiting import get_rate_limiter
from ...models.evidence import StanceClassificationModel
from ...services.evidence import (
    BatchClassificationLimitError,
    BatchClassificationTimeoutError,
    ConsensusCalculator,
    EvidenceCacheService,
    StanceClassifier,
)
from .schemas import (
    EvidenceBreakdown,
    EvidenceMeter,
    Stance,
    StanceBreakdownItem,
)

logger = logging.getLogger(__name__)


# Rate limiter for evidence endpoints
class EvidenceRateLimiter:
    """Rate limiter for evidence API endpoints"""
    
    def __init__(self, max_requests: int = 60, window_minutes: int = 1):
        self.max_requests = max_requests
        self.window_minutes = window_minutes
        self._rate_limiter = None
        self._lock = threading.Lock()
    
    def check_rate_limit(self, identifier: str) -> bool:
        """Check if request is allowed, raises HTTPException if not."""
        rate_limiter = self._get_rate_limiter()
        allowed, info = rate_limiter.is_allowed(
            key=identifier,
            limit=self.max_requests,
            window=self.window_minutes * 60,
        )

        if not allowed:
            retry_after = info.get("retry_after", self.window_minutes * 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded. Max {self.max_requests} requests "
                    f"per {self.window_minutes} minute(s)."
                ),
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(
                        int(info.get("reset_time", time.time() + (self.window_minutes * 60)))
                    ),
                    "Retry-After": str(retry_after),
                },
            )

        return True

    def _get_rate_limiter(self):
        """Initialize rate limiter once; prefer Redis for multi-worker safety."""
        if self._rate_limiter is None:
            with self._lock:
                if self._rate_limiter is None:
                    try:
                        redis_client = redis.Redis.from_url(
                            settings.REDIS_URL or "redis://localhost:6379/0",
                            decode_responses=True,
                        )
                        redis_client.ping()
                        self._rate_limiter = get_rate_limiter(redis_client)
                        logger.info("Evidence rate limiter initialized with Redis")
                    except Exception as e:
                        logger.warning(
                            f"Redis unavailable for evidence rate limiting, using in-memory: {e}"
                        )
                        self._rate_limiter = get_rate_limiter(None)
        return self._rate_limiter


evidence_rate_limiter = EvidenceRateLimiter(max_requests=60, window_minutes=1)


async def rate_limit_dependency(request: Request):
    """Dependency to enforce rate limiting"""
    client_ip = request.client.host if request.client else "unknown"
    route_name = request.url.path.rsplit("/", 1)[-1]
    rate_key = f"evidence:ip:{client_ip}:{route_name}"
    evidence_rate_limiter.check_rate_limit(rate_key)
    return True
router = APIRouter()

# Initialize services
cache_service = EvidenceCacheService()
stance_classifier = StanceClassifier(cache_service)
consensus_calculator = ConsensusCalculator()


def _save_stance_classifications(
    db: Session,
    classifications: List[Optional[Dict]],
    claim_hash: str,
    model_version: str,
) -> int:
    """
    Persist stance classifications with upsert semantics to avoid duplicate-key races.

    Uses PostgreSQL ON CONFLICT when available and a safe ORM fallback otherwise.
    """
    valid_classifications = [classification for classification in classifications if classification]
    if not valid_classifications:
        return 0

    def _as_uuid(value) -> UUID:
        return value if isinstance(value, UUID) else UUID(str(value))

    rows = [
        {
            "claim_hash": claim_hash,
            "source_id": _as_uuid(classification["source_id"]),
            "stance": classification["stance"],
            "confidence": classification["confidence"],
            "justification_excerpt": classification.get("justification_excerpt"),
            "model_version": model_version,
        }
        for classification in valid_classifications
    ]

    dialect_name = db.bind.dialect.name if db.bind is not None else ""

    if dialect_name == "postgresql":
        insert_stmt = pg_insert(StanceClassificationModel).values(rows)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["claim_hash", "source_id", "model_version"],
            set_={
                "stance": insert_stmt.excluded.stance,
                "confidence": insert_stmt.excluded.confidence,
                "justification_excerpt": insert_stmt.excluded.justification_excerpt,
                "updated_at": func.now(),
            },
        )
        db.execute(upsert_stmt)
        return len(rows)

    # SQLite/test fallback
    for row in rows:
        existing = (
            db.query(StanceClassificationModel)
            .filter(
                StanceClassificationModel.claim_hash == row["claim_hash"],
                StanceClassificationModel.source_id == row["source_id"],
                StanceClassificationModel.model_version == row["model_version"],
            )
            .one_or_none()
        )
        if existing:
            existing.stance = row["stance"]
            existing.confidence = row["confidence"]
            existing.justification_excerpt = row["justification_excerpt"]
        else:
            db.add(StanceClassificationModel(**row))

    return len(rows)


async def get_retracted_sources(source_ids: List[str], db: Session) -> List[str]:
    """Get list of retracted source IDs (placeholder - integrate with actual retraction service)"""
    # TODO: Integrate with actual retraction checking service
    # For now, return empty list - retraction checking will be added in later phase
    return []


def _generate_reproducibility_hash(claim_hash: str, source_ids: List[str], model_version: str) -> str:
    """Generate reproducibility hash for API response"""
    return consensus_calculator._generate_reproducibility_hash(
        claim_hash, source_ids, model_version
    )


@router.get("/meter", response_model=EvidenceMeter)
async def get_evidence_meter(
    claim: str = Query(..., min_length=10, max_length=1000, description="The claim to evaluate"),
    source_ids: Optional[str] = Query(None, description="Comma-separated source IDs"),
    query_id: Optional[str] = Query(None, description="Optional query ID for context"),
    _rate_limit: bool = Depends(rate_limit_dependency),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get consensus meter for a claim across sources
    
    Returns aggregated stance statistics and consensus level
    """
    
    try:
        # Parse source IDs if provided
        parsed_source_ids = []
        if source_ids:
            try:
                parsed_source_ids = [UUID(s.strip()) for s in source_ids.split(",")]
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid source ID format: {e}")
        
        # For MVP, we need actual source data - this would integrate with existing source service
        # For now, return error if no sources provided
        if not parsed_source_ids:
            raise HTTPException(
                status_code=400, 
                detail="source_ids parameter required for MVP - integration with search API pending"
            )
        
        claim_hash = consensus_calculator._generate_claim_hash(claim)
        source_id_strings = [str(sid) for sid in parsed_source_ids]
        
        # Check cache first
        cached_meter = await cache_service.get_evidence_meter(
            claim_hash, source_id_strings, stance_classifier.model_version
        )
        
        if cached_meter:
            logger.info(f"Returning cached evidence meter for claim: {claim[:50]}...")
            cached_meter["cached"] = True
            return EvidenceMeter(**cached_meter)
        
        # TODO: Fetch source excerpts from actual source service
        # For MVP, this would integrate with the existing document/source retrieval system
        # Mock source data structure for now:
        sources_data = []
        for source_id in parsed_source_ids:
            # This would be replaced with actual source content retrieval
            sources_data.append({
                "source_id": source_id,
                "excerpt": f"Mock excerpt for source {source_id} - integrate with actual source service",
                "title": f"Source {source_id}"
            })
        
        logger.info(f"Classifying stances for {len(sources_data)} sources on claim: {claim[:50]}...")
        
        # Classify stances in parallel
        try:
            classifications = await stance_classifier.classify_sources_batch(
                claim=claim,
                claim_hash=claim_hash,
                sources=sources_data,
            )
        except BatchClassificationLimitError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except BatchClassificationTimeoutError as e:
            raise HTTPException(status_code=504, detail=str(e))
        
        # Get retracted sources
        retracted_source_ids = await get_retracted_sources(source_id_strings, db)
        
        # Calculate consensus
        evidence_meter = consensus_calculator.calculate_consensus(
            claim=claim,
            classifications=classifications,
            retracted_source_ids=retracted_source_ids
        )
        
        # Store in database (upsert to avoid duplicates/races)
        saved_count = _save_stance_classifications(
            db=db,
            classifications=classifications,
            claim_hash=claim_hash,
            model_version=stance_classifier.model_version,
        )

        try:
            db.commit()
            logger.info(f"Saved/upserted {saved_count} stance classifications")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save stance classifications: {e}")
        
        # Cache the result
        meter_dict = evidence_meter.model_dump()
        meter_dict["cached"] = False
        
        await cache_service.set_evidence_meter(
            claim_hash, source_id_strings, stance_classifier.model_version,
            meter_dict, ttl=86400  # 24 hour cache
        )
        
        logger.info(f"Evidence meter generated: {evidence_meter.consensus_level} consensus")
        return evidence_meter
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate evidence meter: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate evidence meter")


@router.get("/breakdown", response_model=EvidenceBreakdown)
async def get_evidence_breakdown(
    claim_hash: str = Query(..., description="SHA256 hash of claim"),
    stance_filter: Optional[Stance] = Query(None, description="Filter by specific stance"),
    limit: int = Query(20, ge=1, le=100, description="Maximum sources to return"),
    offset: int = Query(0, ge=0, description="Number of sources to skip"),
    _rate_limit: bool = Depends(rate_limit_dependency),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed breakdown of source stances for a claim
    
    Returns individual source classifications with excerpts and confidence scores
    """
    
    try:
        # Query stance classifications from database
        query = db.query(StanceClassificationModel).filter(
            StanceClassificationModel.claim_hash == claim_hash,
            StanceClassificationModel.model_version == stance_classifier.model_version
        )
        
        if stance_filter:
            query = query.filter(StanceClassificationModel.stance == stance_filter.value)
        
        # Apply pagination
        total_count = query.count()
        classifications = query.offset(offset).limit(limit).all()
        
        if not classifications:
            raise HTTPException(status_code=404, detail="No classifications found for this claim")
        
        # TODO: Fetch source titles from actual source service
        # For now, create breakdown items with placeholder titles
        sources = []
        for classification in classifications:
            # This would integrate with actual source metadata service
            source_title = f"Source {classification.source_id}"  # Placeholder
            is_retracted = False  # Would check retraction service
            
            breakdown_item = StanceBreakdownItem(
                source_id=classification.source_id,
                title=source_title,
                stance=Stance(classification.stance.value),
                confidence=classification.confidence,
                justification_excerpt=classification.justification_excerpt,
                is_retracted=is_retracted
            )
            sources.append(breakdown_item)
        
        # Sort by confidence (highest first) 
        sources.sort(key=lambda x: x.confidence, reverse=True)
        
        # Get original claim text (would come from database or cache)
        claim_text = "Original claim text"  # TODO: Retrieve from Claim node or cache
        
        breakdown = EvidenceBreakdown(
            claim=claim_text,
            claim_hash=claim_hash,
            sources=sources
        )
        
        logger.info(f"Evidence breakdown returned {len(sources)} sources for claim {claim_hash[:8]}...")
        return breakdown
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get evidence breakdown: {e}")
        raise HTTPException(status_code=500, detail="Failed to get evidence breakdown")


@router.post("/classify", status_code=201)
async def classify_sources_for_claim(
    claim: str,
    source_ids: List[UUID],
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Internal endpoint to classify sources for a claim
    
    This is used by other services to trigger stance classification
    """
    
    try:
        claim_hash = consensus_calculator._generate_claim_hash(claim)
        
        # TODO: Fetch source excerpts from actual source service
        sources_data = []
        for source_id in source_ids:
            sources_data.append({
                "source_id": source_id,
                "excerpt": f"Mock excerpt for source {source_id}",  # Placeholder
            })
        
        # Classify stances
        try:
            classifications = await stance_classifier.classify_sources_batch(
                claim=claim,
                claim_hash=claim_hash,
                sources=sources_data,
            )
        except BatchClassificationLimitError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except BatchClassificationTimeoutError as e:
            raise HTTPException(status_code=504, detail=str(e))
        
        # Store results in database (upsert to avoid duplicates/races)
        saved_count = _save_stance_classifications(
            db=db,
            classifications=classifications,
            claim_hash=claim_hash,
            model_version=stance_classifier.model_version,
        )

        db.commit()
        
        return {
            "status": "completed",
            "claim_hash": claim_hash,
            "classifications_created": saved_count,
            "total_sources": len(source_ids),
            "model_version": stance_classifier.model_version
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to classify sources: {e}")
        raise HTTPException(status_code=500, detail="Classification failed")


# Health check endpoint
@router.get("/health")
async def health_check(_current_user=Depends(get_current_user)):
    """Health check for evidence meter service"""
    
    try:
        # Check cache service
        cache_connected = cache_service._ensure_connected()
        
        return {
            "status": "healthy",
            "cache_connected": cache_connected,
            "model_version": stance_classifier.model_version,
            "components": {
                "stance_classifier": "operational",
                "consensus_calculator": "operational", 
                "cache_service": "operational" if cache_connected else "degraded"
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
