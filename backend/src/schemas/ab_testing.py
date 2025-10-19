"""
A/B Testing Pydantic Schemas for Multimodal Enterprise RAG System

This module defines Pydantic schemas for A/B testing API request/response models,
providing comprehensive data validation and serialization for experiment management,
variant configuration, metrics collection, and statistical analysis.
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime, timezone
from uuid import UUID
from enum import Enum

from ..models.ab_testing import (
    ExperimentStatus, ExperimentType, TrafficSplitType, MetricType,
    StatisticalTest, SuccessCriterion
)


# ============================================================================
# ENUMS FOR SCHEMAS
# ============================================================================

class AssignmentType(str, Enum):
    """Types of experiment assignments"""
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    OVERRIDE = "override"
    NONE = "none"


class RoutingReason(str, Enum):
    """Reasons for routing decisions"""
    STANDARD_ASSIGNMENT = "standard_assignment"
    USER_SEGMENT_MATCH = "user_segment_match"
    QUERY_PATTERN_MATCH = "query_pattern_match"
    STICKY_ASSIGNMENT = "sticky_assignment"
    NO_ACTIVE_EXPERIMENTS = "no_active_experiments"
    ASSIGNMENT_FAILED = "assignment_failed"
    ERROR_FALLBACK = "error_fallback"


# ============================================================================
# EXPERIMENT SCHEMAS
# ============================================================================

class ExperimentCreateRequest(BaseModel):
    """Request schema for creating experiments"""
    name: str = Field(..., min_length=1, max_length=255, description="Experiment name")
    description: Optional[str] = Field(None, max_length=1000, description="Experiment description")
    hypothesis: str = Field(..., min_length=10, max_length=1000, description="Test hypothesis")

    experiment_type: ExperimentType = Field(..., description="Type of experiment")
    traffic_split_type: TrafficSplitType = Field(TrafficSplitType.UNIFORM, description="Traffic split strategy")
    traffic_percentage: float = Field(100.0, ge=1.0, le=100.0, description="Percentage of total traffic")
    max_participants: Optional[int] = Field(None, ge=1, description="Maximum number of participants")

    start_time: Optional[datetime] = Field(None, description="Start time for the experiment")
    end_time: Optional[datetime] = Field(None, description="End time for the experiment")
    scheduled_start: Optional[datetime] = Field(None, description="Scheduled start time")
    scheduled_end: Optional[datetime] = Field(None, description="Scheduled end time")

    confidence_level: float = Field(0.95, ge=0.8, le=0.99, description="Statistical confidence level")
    minimum_sample_size: int = Field(1000, ge=100, description="Minimum sample size")
    statistical_test: StatisticalTest = Field(StatisticalTest.Z_TEST, description="Statistical test")
    expected_effect_size: Optional[float] = Field(None, gt=0.0, description="Expected minimum effect size")

    target_user_segments: Optional[List[Dict[str, Any]]] = Field(None, description="Target user segments")
    target_query_patterns: Optional[List[str]] = Field(None, description="Target query patterns")
    target_organization_ids: Optional[List[UUID]] = Field(None, description="Target specific organizations")

    primary_metric: MetricType = Field(..., description="Primary success metric")
    success_criteria: SuccessCriterion = Field(SuccessCriterion.HIGHER_IS_BETTER, description="Success criteria")
    target_improvement: Optional[float] = Field(None, gt=0.0, description="Expected improvement percentage")
    minimum_duration_days: int = Field(7, ge=1, le=365, description="Minimum duration in days")

    tags: Optional[List[str]] = Field(None, description="Experiment tags")
    external_references: Optional[Dict[str, Any]] = Field(None, description="External resource references")

    variants: List[Dict[str, Any]] = Field(..., min_items=2, description="Experiment variants")

    @validator('end_time')
    def validate_end_time(cls, v, values):
        if v and 'start_time' in values and values['start_time']:
            if v <= values['start_time']:
                raise ValueError("End time must be after start time")
        return v

    @validator('scheduled_end')
    def validate_scheduled_end_time(cls, v, values):
        if v and 'scheduled_start' in values and values['scheduled_start']:
            if v <= values['scheduled_start']:
                raise ValueError("Scheduled end time must be after scheduled start time")
        return v

    @validator('variants')
    def validate_variants(cls, v):
        control_count = sum(1 for variant in v if variant.get('is_control', False))
        if control_count != 1:
            raise ValueError("Exactly one variant must be marked as control")

        for i, variant in enumerate(v):
            if 'name' not in variant or not variant['name']:
                raise ValueError(f"Variant {i} must have a name")
            if 'config' not in variant or not variant['config']:
                raise ValueError(f"Variant {i} must have configuration")

        return v

    class Config:
        schema_extra = {
            "example": {
                "name": "New Hybrid Search Algorithm",
                "description": "Testing improved hybrid search with better multimodal weighting",
                "hypothesis": "The new hybrid search algorithm will improve relevance scores by 15%",
                "experiment_type": "search_algorithm",
                "primary_metric": "relevance_score",
                "target_improvement": 15.0,
                "minimum_sample_size": 2000,
                "traffic_percentage": 50.0,
                "variants": [
                    {
                        "name": "Control",
                        "description": "Current hybrid search algorithm",
                        "is_control": True,
                        "weight": 1.0,
                        "config": {
                            "algorithm": "hybrid_search_v1",
                            "parameters": {
                                "vector_weight": 0.4,
                                "graph_weight": 0.3,
                                "fulltext_weight": 0.3
                            }
                        }
                    },
                    {
                        "name": "New Algorithm",
                        "description": "Improved hybrid search with adaptive weighting",
                        "is_control": False,
                        "weight": 1.0,
                        "config": {
                            "algorithm": "hybrid_search_v2",
                            "parameters": {
                                "adaptive_weighting": True,
                                "context_awareness": True,
                                "base_weights": {
                                    "vector_weight": 0.35,
                                    "graph_weight": 0.35,
                                    "fulltext_weight": 0.30
                                }
                            }
                        }
                    }
                ]
            }
        }


class ExperimentUpdateRequest(BaseModel):
    """Request schema for updating experiments"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    hypothesis: Optional[str] = Field(None, min_length=10, max_length=1000)

    experiment_type: Optional[ExperimentType] = None
    traffic_split_type: Optional[TrafficSplitType] = None
    traffic_percentage: Optional[float] = Field(None, ge=1.0, le=100.0)
    max_participants: Optional[int] = Field(None, ge=1)

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None

    confidence_level: Optional[float] = Field(None, ge=0.8, le=0.99)
    minimum_sample_size: Optional[int] = Field(None, ge=100)
    statistical_test: Optional[StatisticalTest] = None
    expected_effect_size: Optional[float] = Field(None, gt=0.0)

    target_user_segments: Optional[List[Dict[str, Any]]] = None
    target_query_patterns: Optional[List[str]] = None
    target_organization_ids: Optional[List[UUID]] = None

    primary_metric: Optional[MetricType] = None
    success_criteria: Optional[SuccessCriterion] = None
    target_improvement: Optional[float] = Field(None, gt=0.0)
    minimum_duration_days: Optional[int] = Field(None, ge=1, le=365)

    tags: Optional[List[str]] = None
    external_references: Optional[Dict[str, Any]] = None

    @validator('end_time')
    def validate_end_time(cls, v, values):
        if v and 'start_time' in values and values['start_time']:
            if v <= values['start_time']:
                raise ValueError("End time must be after start time")
        return v


class VariantResponse(BaseModel):
    """Response schema for variants"""
    id: UUID
    name: str
    description: Optional[str]
    is_control: bool
    experiment_id: UUID

    config: Dict[str, Any]
    weight: float
    traffic_percentage: float

    participant_count: int
    query_count: int

    primary_metric_value: Optional[float]
    conversion_count: int
    click_count: int
    total_response_time_ms: int
    user_satisfaction_score: Optional[float]

    conversion_rate: Optional[float]
    click_through_rate: Optional[float]
    average_response_time_ms: Optional[float]

    standard_error: Optional[float]
    confidence_interval: Optional[Dict[str, float]]
    p_value: Optional[float]

    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_variant(cls, variant):
        """Create response from variant model"""
        return cls(
            id=variant.id,
            name=variant.name,
            description=variant.description,
            is_control=variant.is_control,
            experiment_id=variant.experiment_id,
            config=variant.config,
            weight=variant.weight,
            traffic_percentage=variant.traffic_percentage,
            participant_count=variant.participant_count,
            query_count=variant.query_count,
            primary_metric_value=variant.primary_metric_value,
            conversion_count=variant.conversion_count,
            click_count=variant.click_count,
            total_response_time_ms=variant.total_response_time_ms,
            user_satisfaction_score=variant.user_satisfaction_score,
            conversion_rate=variant.conversion_rate,
            click_through_rate=variant.click_through_rate,
            average_response_time_ms=variant.average_response_time_ms,
            standard_error=variant.standard_error,
            confidence_interval={
                'lower': variant.confidence_interval_lower,
                'upper': variant.confidence_interval_upper
            } if variant.confidence_interval_lower is not None else None,
            p_value=variant.p_value,
            created_at=variant.created_at,
            updated_at=variant.updated_at
        )


class ExperimentResponse(BaseModel):
    """Response schema for experiments"""
    id: UUID
    name: str
    description: Optional[str]
    hypothesis: str

    experiment_type: ExperimentType
    status: ExperimentStatus

    start_time: Optional[datetime]
    end_time: Optional[datetime]
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]

    traffic_split_type: TrafficSplitType
    traffic_percentage: float
    max_participants: Optional[int]

    confidence_level: float
    minimum_sample_size: int
    statistical_test: StatisticalTest
    expected_effect_size: Optional[float]

    target_user_segments: Optional[List[Dict[str, Any]]]
    target_query_patterns: Optional[List[str]]
    target_organization_ids: Optional[List[UUID]]

    primary_metric: MetricType
    success_criteria: SuccessCriterion
    target_improvement: Optional[float]
    minimum_duration_days: int

    winning_variant_id: Optional[UUID]
    statistical_significance: Optional[float]
    effect_size: Optional[float]
    confidence_interval: Optional[Dict[str, float]]

    organization_id: UUID
    created_by: UUID

    tags: Optional[List[str]]
    external_references: Optional[Dict[str, Any]]

    is_active: bool
    duration_days: Optional[float]
    actual_sample_size: int
    statistical_power: float

    variants: List[VariantResponse]
    participant_stats: Dict[str, Any]

    results: Optional[Dict[str, Any]] = None

    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_experiment(cls, experiment, include_results: bool = False):
        """Create response from experiment model"""
        return cls(
            id=experiment.id,
            name=experiment.name,
            description=experiment.description,
            hypothesis=experiment.hypothesis,
            experiment_type=experiment.experiment_type,
            status=experiment.status,
            start_time=experiment.start_time,
            end_time=experiment.end_time,
            scheduled_start=experiment.scheduled_start,
            scheduled_end=experiment.scheduled_end,
            traffic_split_type=experiment.traffic_split_type,
            traffic_percentage=experiment.traffic_percentage,
            max_participants=experiment.max_participants,
            confidence_level=experiment.confidence_level,
            minimum_sample_size=experiment.minimum_sample_size,
            statistical_test=experiment.statistical_test,
            expected_effect_size=experiment.expected_effect_size,
            target_user_segments=experiment.target_user_segments,
            target_query_patterns=experiment.target_query_patterns,
            target_organization_ids=experiment.target_organization_ids,
            primary_metric=experiment.primary_metric,
            success_criteria=experiment.success_criteria,
            target_improvement=experiment.target_improvement,
            minimum_duration_days=experiment.minimum_duration_days,
            winning_variant_id=experiment.winning_variant_id,
            statistical_significance=experiment.statistical_significance,
            effect_size=experiment.effect_size,
            confidence_interval={
                'lower': experiment.confidence_interval_lower,
                'upper': experiment.confidence_interval_upper
            } if experiment.confidence_interval_lower is not None else None,
            organization_id=experiment.organization_id,
            created_by=experiment.created_by,
            tags=experiment.tags,
            external_references=experiment.external_references,
            is_active=experiment.is_active,
            duration_days=experiment.duration_days,
            actual_sample_size=experiment.actual_sample_size,
            statistical_power=experiment.calculate_statistical_power(),
            variants=[VariantResponse.from_variant(v) for v in experiment.variants],
            participant_stats=experiment.get_participant_stats(),
            results=None,  # Would be populated if include_results is True
            created_at=experiment.created_at,
            updated_at=experiment.updated_at
        )


# ============================================================================
# VARIANT SCHEMAS
# ============================================================================

class VariantCreateRequest(BaseModel):
    """Request schema for creating variants"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_control: bool = Field(False, description="Whether this is the control variant")
    weight: float = Field(1.0, gt=0.0, description="Traffic weight for this variant")
    config: Dict[str, Any] = Field(..., description="Variant configuration")

    class Config:
        schema_extra = {
            "example": {
                "name": "New Algorithm",
                "description": "Improved hybrid search with adaptive weighting",
                "is_control": False,
                "weight": 1.0,
                "config": {
                    "algorithm": "hybrid_search_v2",
                    "parameters": {
                        "adaptive_weighting": True,
                        "context_awareness": True,
                        "base_weights": {
                            "vector_weight": 0.35,
                            "graph_weight": 0.35,
                            "fulltext_weight": 0.30
                        }
                    }
                }
            }
        }


class VariantUpdateRequest(BaseModel):
    """Request schema for updating variants"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    weight: Optional[float] = Field(None, gt=0.0)
    config: Optional[Dict[str, Any]] = None


# ============================================================================
# METRICS SCHEMAS
# ============================================================================

class MetricSubmissionRequest(BaseModel):
    """Request schema for submitting single metric"""
    experiment_id: UUID = Field(..., description="Experiment ID")
    variant_id: UUID = Field(..., description="Variant ID")
    metric_type: MetricType = Field(..., description="Type of metric")
    metric_value: float = Field(..., description="Metric value")

    user_id: Optional[UUID] = Field(None, description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID for anonymous users")
    query_id: Optional[UUID] = Field(None, description="Associated query ID")

    metric_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metric data")
    query_context: Optional[Dict[str, Any]] = Field(None, description="Query context")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")

    organization_id: UUID = Field(..., description="Organization ID")

    @root_validator
    def validate_user_or_session(cls, values):
        if not values.get('user_id') and not values.get('session_id'):
            raise ValueError("Either user_id or session_id must be provided")
        return values

    class Config:
        schema_extra = {
            "example": {
                "experiment_id": "550e8400-e29b-41d4-a716-446655440000",
                "variant_id": "550e8400-e29b-41d4-a716-446655440001",
                "metric_type": "relevance_score",
                "metric_value": 0.85,
                "user_id": "550e8400-e29b-41d4-a716-446655440002",
                "query_id": "550e8400-e29b-41d4-a716-446655440003",
                "metric_metadata": {
                    "result_count": 10,
                    "response_time_ms": 150
                }
            }
        }


class BulkMetricSubmissionRequest(BaseModel):
    """Request schema for submitting multiple metrics"""
    metrics: List[MetricSubmissionRequest] = Field(..., min_items=1, max_items=10000)
    batch_metadata: Optional[Dict[str, Any]] = Field(None, description="Batch-level metadata")


# ============================================================================
# QUERY ROUTING SCHEMAS
# ============================================================================

class QueryRoutingResponse(BaseModel):
    """Response schema for query routing"""
    experiment_id: Optional[UUID]
    variant_id: Optional[UUID]
    assignment_type: AssignmentType
    routing_reason: RoutingReason
    variant_config: Optional[Dict[str, Any]] = None
    routing_confidence: Optional[float] = None
    alternative_variants: Optional[List[Dict[str, Any]]] = None


# ============================================================================
# STATISTICAL ANALYSIS SCHEMAS
# ============================================================================

class StatisticalAnalysisRequest(BaseModel):
    """Request schema for statistical analysis"""
    metrics: Optional[List[MetricType]] = Field(None, description="Metrics to analyze")
    confidence_level: Optional[float] = Field(0.95, ge=0.8, le=0.99, description="Confidence level")
    statistical_test: Optional[StatisticalTest] = Field(None, description="Statistical test to use")
    segment_analysis: Optional[bool] = Field(False, description="Include segment-based analysis")
    time_series_analysis: Optional[bool] = Field(False, description="Include time series analysis")
    custom_parameters: Optional[Dict[str, Any]] = Field(None, description="Custom analysis parameters")


class StatisticalResult(BaseModel):
    """Individual statistical test result"""
    metric_type: MetricType
    control_mean: float
    variant_means: Dict[str, float]
    effect_sizes: Dict[str, float]
    p_values: Dict[str, float]
    confidence_intervals: Dict[str, Dict[str, float]]
    statistical_significance: Dict[str, bool]
    sample_sizes: Dict[str, int]
    standard_errors: Dict[str, float]


class StatisticalAnalysisResponse(BaseModel):
    """Response schema for statistical analysis"""
    experiment_id: UUID
    analysis_timestamp: datetime
    analysis_parameters: StatisticalAnalysisRequest

    overall_results: Dict[str, Any]
    detailed_results: List[StatisticalResult]

    winning_variant: Optional[Dict[str, Any]]
    confidence_level: float

    recommendations: List[str]
    assumptions: List[str]
    limitations: List[str]

    sample_adequacy: bool
    statistical_power: Dict[str, float]

    segment_results: Optional[Dict[str, Any]] = None
    time_series_results: Optional[Dict[str, Any]] = None


# ============================================================================
# EXPERIMENT SUMMARY SCHEMAS
# ============================================================================

class ExperimentSummaryRequest(BaseModel):
    """Request schema for experiment summary"""
    include_variants: bool = Field(True, description="Include variant details")
    include_metrics: bool = Field(True, description="Include metrics summary")
    include_insights: bool = Field(True, description="Include AI-generated insights")
    time_range_days: Optional[int] = Field(None, description="Time range for data")
    segments: Optional[List[str]] = Field(None, description="Specific segments to analyze")


class ExperimentSummaryResponse(BaseModel):
    """Response schema for experiment summary"""
    experiment_id: UUID
    experiment_name: str
    experiment_type: ExperimentType
    status: ExperimentStatus

    participant_statistics: Dict[str, Any]
    duration_statistics: Dict[str, Any]

    variant_performance: Optional[List[Dict[str, Any]]] = None
    metrics_summary: Optional[Dict[str, Any]] = None

    key_insights: List[str]
    recommendations: List[str]

    statistical_summary: Dict[str, Any]
    business_impact: Dict[str, Any]

    data_quality: Dict[str, Any]
    confidence_indicators: Dict[str, Any]


# ============================================================================
# USER SEGMENT SCHEMAS
# ============================================================================

class UserSegmentCreateRequest(BaseModel):
    """Request schema for creating user segments"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    segment_type: str = Field(..., description="Type of segment (behavioral, demographic, technical)")
    segment_criteria: Dict[str, Any] = Field(..., description="Rules for segment membership")
    is_dynamic: bool = Field(True, description="Auto-update membership")

    class Config:
        schema_extra = {
            "example": {
                "name": "Power Users",
                "description": "Users with high query frequency and engagement",
                "segment_type": "behavioral",
                "segment_criteria": {
                    "queries_per_day": {"min": 10},
                    "avg_response_rating": {"min": 4.0},
                    "account_age_days": {"min": 30}
                },
                "is_dynamic": True
            }
        }


class UserSegmentResponse(BaseModel):
    """Response schema for user segments"""
    id: UUID
    name: str
    description: Optional[str]
    segment_type: str
    organization_id: UUID

    segment_criteria: Dict[str, Any]
    user_count: int
    active_user_count: int

    is_dynamic: bool
    created_by: UUID
    last_updated: datetime

    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_segment(cls, segment):
        """Create response from segment model"""
        return cls(
            id=segment.id,
            name=segment.name,
            description=segment.description,
            segment_type=segment.segment_type,
            organization_id=segment.organization_id,
            segment_criteria=segment.segment_criteria,
            user_count=segment.user_count,
            active_user_count=segment.active_user_count,
            is_dynamic=segment.is_dynamic,
            created_by=segment.created_by,
            last_updated=segment.last_updated,
            created_at=segment.created_at,
            updated_at=segment.updated_at
        )


# ============================================================================
# ASSIGNMENT SCHEMAS
# ============================================================================

class ExperimentAssignmentResponse(BaseModel):
    """Response schema for experiment assignments"""
    id: UUID
    user_id: UUID
    experiment_id: UUID
    variant_id: UUID

    assignment_type: str
    assigned_at: datetime
    assignment_source: Optional[str]

    user_segment: Optional[Dict[str, Any]]
    query_context: Optional[Dict[str, Any]]
    device_info: Optional[Dict[str, Any]]


# ============================================================================
# HEALTH CHECK SCHEMAS
# ============================================================================

class HealthCheckComponent(BaseModel):
    """Individual component health status"""
    status: str = Field(..., regex="^(healthy|unhealthy|degraded)$")
    message: Optional[str] = None
    error: Optional[str] = None
    response_time_ms: Optional[float] = None


class HealthCheckResponse(BaseModel):
    """Overall health check response"""
    status: str = Field(..., regex="^(healthy|unhealthy|degraded)$")
    timestamp: datetime
    service: str = "A/B Testing System"
    components: Dict[str, HealthCheckComponent]
    uptime_seconds: Optional[float] = None
    version: Optional[str] = None