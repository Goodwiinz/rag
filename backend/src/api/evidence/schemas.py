"""
Evidence Agreement Meter Pydantic schemas
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class Stance(str, Enum):
    """Stance classification options"""
    SUPPORTING = "supporting"
    OPPOSING = "opposing"
    NEUTRAL = "neutral"
    NOT_ADDRESSED = "not_addressed"


class ConsensusLevel(str, Enum):
    """Consensus level categories"""
    STRONG_AGREEMENT = "strong_agreement"      # >80% agreement
    MODERATE_AGREEMENT = "moderate_agreement"  # 60-80% agreement
    MIXED = "mixed"                           # 40-60% agreement
    LOW_AGREEMENT = "low_agreement"           # 20-40% agreement
    INSUFFICIENT_DATA = "insufficient_data"    # <3 sources


class StanceClassification(BaseModel):
    """Individual source stance classification"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[UUID] = None
    claim_hash: str = Field(..., description="SHA256 hash of normalized claim")
    source_id: UUID = Field(..., description="UUID of the source document")
    stance: Stance = Field(..., description="Classification of source's stance on claim")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    justification_excerpt: Optional[str] = Field(None, description="Text excerpt justifying classification")
    model_version: str = Field(..., description="Model version used for classification")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StanceBreakdownItem(BaseModel):
    """Stance classification with source metadata for breakdown view"""
    model_config = ConfigDict(from_attributes=True)
    
    source_id: UUID
    title: str
    stance: Stance
    confidence: float = Field(..., ge=0.0, le=1.0)
    justification_excerpt: Optional[str] = None
    is_retracted: bool = False


class EvidenceMeter(BaseModel):
    """Evidence agreement meter summary"""
    model_config = ConfigDict(from_attributes=True)
    
    claim: str = Field(..., description="Original claim text")
    claim_hash: str = Field(..., description="SHA256 hash of normalized claim")
    total_sources: int = Field(..., ge=0, description="Total number of evaluated sources")
    supporting: int = Field(..., ge=0, description="Number of sources supporting the claim")
    opposing: int = Field(..., ge=0, description="Number of sources opposing the claim")
    neutral: int = Field(..., ge=0, description="Number of neutral sources")
    not_addressed: int = Field(..., ge=0, description="Number of sources not addressing the claim")
    consensus_level: ConsensusLevel = Field(..., description="Overall consensus level")
    average_confidence: float = Field(..., ge=0.0, le=1.0, description="Average classification confidence")
    retracted_sources: int = Field(..., ge=0, description="Number of retracted sources (excluded)")
    cached: bool = Field(..., description="Whether result was served from cache")
    reproducibility_hash: str = Field(..., description="Hash for reproducibility tracking")


class EvidenceBreakdown(BaseModel):
    """Detailed breakdown of source stances"""
    model_config = ConfigDict(from_attributes=True)
    
    claim: str = Field(..., description="Original claim text")
    claim_hash: str = Field(..., description="SHA256 hash of normalized claim")
    sources: List[StanceBreakdownItem] = Field(..., description="List of source classifications")


# Request/Response schemas
class EvidenceMeterRequest(BaseModel):
    """Request parameters for evidence meter endpoint"""
    claim: str = Field(..., description="Claim to evaluate")
    source_ids: Optional[List[UUID]] = Field(None, description="Optional list of specific source IDs")
    query_id: Optional[str] = Field(None, description="Optional query ID for context")


class EvidenceBreakdownRequest(BaseModel):
    """Request parameters for evidence breakdown endpoint"""
    claim_hash: str = Field(..., description="SHA256 hash of claim")
    stance_filter: Optional[Stance] = Field(None, description="Filter by specific stance")


class ClassificationCacheInfo(BaseModel):
    """Cache information for stance classifications"""
    cache_key: str
    cached: bool
    cache_ttl: Optional[int] = None
    model_version: str