"""
Evidence Agreement Meter API endpoints
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.dependencies import get_current_user


# Rate limiter for evidence endpoints
class EvidenceRateLimiter:
    """Rate limiter for evidence API endpoints"""
    
    def __init__(self, max_requests: int = 60, window_minutes: int = 1):
        self.max_requests = max_requests
        self.window_minutes = window_minutes
        self.requests: Dict[str, List[datetime]] = {}
    
    def check_rate_limit(self, identifier: str) -> bool:
        """Check if request is allowed, raises HTTPException if not"""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)
        
        if identifier in self.requests:
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if req_time > window_start
            ]
        else:
            self.requests[identifier] = []
        
        if len(self.requests[identifier]) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_minutes} minute(s)."
            )
        
        self.requests[identifier].append(now)
        return True


evidence_rate_limiter = EvidenceRateLimiter(max_requests=60, window_minutes=1)


async def rate_limit_dependency(request: Request):
    """Dependency to enforce rate limiting"""
    client_ip = request.client.host if request.client else "unknown"
    evidence_rate_limiter.check_rate_limit(client_ip)
    return True
from ...models.evidence import StanceClassificationModel
from ...services.evidence import (
    EvidenceCacheService,
    StanceClassifier, 
    ConsensusCalculator
)
from .schemas import (
    EvidenceMeter,
    EvidenceBreakdown,
    StanceBreakdownItem,
    EvidenceMeterRequest,
    EvidenceBreakdownRequest,
    Stance,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
cache_service = EvidenceCacheService()
stance_classifier = StanceClassifier(cache_service)
consensus_calculator = ConsensusCalculator()


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
        classifications = await stance_classifier.classify_sources_batch(
            claim=claim,
            claim_hash=claim_hash, 
            sources=sources_data
        )
        
        # Get retracted sources
        retracted_source_ids = await get_retracted_sources(source_id_strings, db)
        
        # Calculate consensus
        evidence_meter = consensus_calculator.calculate_consensus(
            claim=claim,
            classifications=classifications,
            retracted_source_ids=retracted_source_ids
        )
        
        # Store in database (create stance classification records)
        for classification in classifications:
            if classification:
                stance_record = StanceClassificationModel.from_classification(
                    classification, claim_hash, stance_classifier.model_version
                )
                db.add(stance_record)
        
        try:
            db.commit()
            logger.info(f"Saved {len([c for c in classifications if c])} stance classifications")
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
        classifications = await stance_classifier.classify_sources_batch(
            claim=claim,
            claim_hash=claim_hash,
            sources=sources_data
        )
        
        # Store results in database
        saved_count = 0
        for classification in classifications:
            if classification:
                stance_record = StanceClassificationModel.from_classification(
                    classification, claim_hash, stance_classifier.model_version
                )
                db.add(stance_record)
                saved_count += 1
        
        db.commit()
        
        return {
            "status": "completed",
            "claim_hash": claim_hash,
            "classifications_created": saved_count,
            "total_sources": len(source_ids),
            "model_version": stance_classifier.model_version
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to classify sources: {e}")
        raise HTTPException(status_code=500, detail="Classification failed")


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check for evidence meter service"""
    
    try:
        # Check cache service
        cache_connected = await cache_service._ensure_connected()
        
        # Check if we can generate a claim hash
        test_hash = consensus_calculator._generate_claim_hash("test claim")
        
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