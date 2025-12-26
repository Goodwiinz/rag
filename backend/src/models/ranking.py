"""
Ranking-related data models for the RAG system
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class RankingStrategy(str, Enum):
    """Ranking strategies"""
    PERSONALIZED = "personalized"
    COLLABORATIVE = "collaborative"
    CONTENT_BASED = "content_based"
    HYBRID = "hybrid"
    DIVERSITY_ENHANCED = "diversity_enhanced"
    FRESHNESS_WEIGHTED = "freshness_weighted"
    QUALITY_WEIGHTED = "quality_weighted"


class PersonalizationLevel(str, Enum):
    """Personalization levels"""
    NONE = "none"
    BASIC = "basic"
    ADVANCED = "advanced"
    HYPER_PERSONALIZED = "hyper_personalized"


class RankingFactors(BaseModel):
    """Feature factors for ranking calculation"""
    # Text features
    text_similarity: float = Field(0.0, ge=0.0, le=1.0, description="Text similarity score")
    keyword_match: float = Field(0.0, ge=0.0, le=1.0, description="Keyword match score")
    title_match: float = Field(0.0, ge=0.0, le=1.0, description="Title match score")

    # User preference features
    source_preference: float = Field(0.0, ge=0.0, le=1.0, description="Source preference score")
    modality_preference: float = Field(0.0, ge=0.0, le=1.0, description="Modality preference score")
    content_length_preference: float = Field(0.0, ge=0.0, le=1.0, description="Content length preference score")

    # Behavioral features
    historical_ctr: float = Field(0.0, ge=0.0, le=1.0, description="Historical click-through rate")
    recent_interactions: float = Field(0.0, ge=0.0, le=1.0, description="Recent interaction score")
    session_relevance: float = Field(0.0, ge=0.0, le=1.0, description="Session relevance score")

    # Quality features
    content_quality: float = Field(0.0, ge=0.0, le=1.0, description="Content quality score")
    source_authority: float = Field(0.0, ge=0.0, le=1.0, description="Source authority score")
    freshness: float = Field(0.0, ge=0.0, le=1.0, description="Freshness score")

    # Temporal features
    time_relevance: float = Field(0.0, ge=0.0, le=1.0, description="Time relevance score")
    recency_score: float = Field(0.0, ge=0.0, le=1.0, description="Recency score")

    # Social features
    popularity_score: float = Field(0.0, ge=0.0, le=1.0, description="Popularity score")
    engagement_score: float = Field(0.0, ge=0.0, le=1.0, description="Engagement score")

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return self.dict()


class PersonalizedScore(BaseModel):
    """Personalized score for a search result"""
    result_id: str = Field(..., description="Result ID")
    user_id: str = Field(..., description="User ID")
    base_score: float = Field(..., ge=0.0, description="Base relevance score")
    personalized_score: float = Field(..., ge=0.0, description="Personalized score")
    factors: RankingFactors = Field(..., description="Ranking factors")
    explanation: Optional[str] = Field(None, description="Score explanation")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="Score confidence")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserPreferences(BaseModel):
    """User preferences for personalization"""
    preferred_sources: List[str] = Field(default_factory=list, description="Preferred sources")
    preferred_modalities: List[str] = Field(default_factory=list, description="Preferred content modalities")
    content_length_preference: str = Field("medium", description="Content length preference")
    language_preference: str = Field("en", description="Language preference")
    quality_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Quality threshold")
    topic_preferences: Dict[str, float] = Field(default_factory=dict, description="Topic preferences")
    excluded_sources: List[str] = Field(default_factory=list, description="Excluded sources")
    excluded_topics: List[str] = Field(default_factory=list, description="Excluded topics")


class UserProfile(BaseModel):
    """User profile for personalization"""
    user_id: str = Field(..., description="User ID")
    preferences: UserPreferences = Field(..., description="User preferences")
    interests: List[str] = Field(default_factory=list, description="User interests")
    expertise_areas: List[str] = Field(default_factory=list, description="Areas of expertise")
    interaction_history: List[str] = Field(default_factory=list, description="Interaction history")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Update timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserBehavior(BaseModel):
    """User behavior data point"""
    user_id: str = Field(..., description="User ID")
    session_id: str = Field(..., description="Session ID")
    query: str = Field(..., description="Query")
    result_id: str = Field(..., description="Result ID")
    action: str = Field(..., description="Action (click, view, skip, etc.)")
    content_type: str = Field(..., description="Content type")
    dwell_time_ms: Optional[float] = Field(None, ge=0.0, description="Dwell time in milliseconds")
    position: int = Field(..., ge=0, description="Result position")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Action timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RankingFeedback(BaseModel):
    """Feedback for ranking quality"""
    user_id: str = Field(..., description="User ID")
    query_id: str = Field(..., description="Query ID")
    result_id: str = Field(..., description="Result ID")
    original_position: int = Field(..., ge=0, description="Original position")
    final_position: Optional[int] = Field(None, ge=0, description="Final position after user action")
    rating: int = Field(..., ge=1, le=5, description="User rating")
    helpful: bool = Field(..., description="Was result helpful")
    feedback_type: str = Field(..., description="Type of feedback")
    comments: Optional[str] = Field(None, max_length=1000, description="User comments")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RankingMetrics(BaseModel):
    """Ranking performance metrics"""
    total_rankings: int = Field(..., ge=0, description="Total rankings performed")
    avg_ranking_time_ms: float = Field(..., ge=0.0, description="Average ranking time")
    cache_hit_rate: float = Field(..., ge=0.0, le=1.0, description="Cache hit rate")
    personalization_effectiveness: float = Field(..., ge=0.0, le=1.0, description="Personalization effectiveness")
    strategy_distribution: Dict[RankingStrategy, float] = Field(..., description="Strategy usage distribution")
    user_satisfaction_rate: float = Field(..., ge=0.0, le=1.0, description="User satisfaction rate")
    click_through_rate: float = Field(..., ge=0.0, le=1.0, description="Click-through rate")
    dwell_time_avg_ms: float = Field(..., ge=0.0, description="Average dwell time")
    period_start: datetime = Field(..., description="Metrics period start")
    period_end: datetime = Field(..., description="Metrics period end")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RankingAblationTest(BaseModel):
    """Ablation test for ranking factors"""
    test_id: UUID = Field(default_factory=uuid4, description="Test ID")
    name: str = Field(..., description="Test name")
    description: str = Field(..., description="Test description")
    factors_to_test: List[str] = Field(..., description="Factors to test")
    baseline_metrics: Dict[str, float] = Field(..., description="Baseline metrics")
    test_metrics: Dict[str, float] = Field(..., description="Test metrics")
    improvement: float = Field(..., description="Improvement percentage")
    statistical_significance: float = Field(..., ge=0.0, le=1.0, description="Statistical significance")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    status: str = Field("active", description="Test status")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class DiversityMetrics(BaseModel):
    """Diversity metrics for ranked results"""
    source_diversity: float = Field(..., ge=0.0, le=1.0, description="Source diversity score")
    modality_diversity: float = Field(..., ge=0.0, le=1.0, description="Modality diversity score")
    topic_diversity: float = Field(..., ge=0.0, le=1.0, description="Topic diversity score")
    temporal_diversity: float = Field(..., ge=0.0, le=1.0, description="Temporal diversity score")
    overall_diversity: float = Field(..., ge=0.0, le=1.0, description="Overall diversity score")
    unique_sources_count: int = Field(..., ge=0, description="Number of unique sources")
    unique_modalities_count: int = Field(..., ge=0, description="Number of unique modalities")


class RankingDebugInfo(BaseModel):
    """Debug information for ranking process"""
    query: str = Field(..., description="Query")
    user_id: str = Field(..., description="User ID")
    strategy_used: RankingStrategy = Field(..., description="Ranking strategy used")
    processing_steps: List[str] = Field(..., description="Processing steps")
    feature_importance: Dict[str, float] = Field(..., description="Feature importance scores")
    intermediate_scores: List[Dict[str, float]] = Field(..., description="Intermediate scores")
    final_scores: List[float] = Field(..., description="Final scores")
    explanations: List[str] = Field(..., description="Ranking explanations")
    processing_time_ms: float = Field(..., ge=0.0, description="Processing time")
    cache_hit: bool = Field(..., description="Whether result was cached")
    debug_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional debug info")