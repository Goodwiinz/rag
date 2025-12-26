"""
A/B Testing System Models for Multimodal Enterprise RAG

This module provides comprehensive data models for A/B testing search improvements,
including experiment management, query routing, metrics collection, and statistical analysis.
"""

import uuid
import json
import math
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime,
    ForeignKey, Index, Enum, JSON, CheckConstraint, UniqueConstraint,
    desc, asc, and_, or_, func, case, extract
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from .base import BaseModel, GUID
from .utils import StringArray


class ExperimentStatus(PyEnum):
    """Experiment lifecycle status"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ANALYZED = "analyzed"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class ExperimentType(PyEnum):
    """Types of A/B experiments"""
    SEARCH_ALGORITHM = "search_algorithm"
    RANKING_MODEL = "ranking_model"
    QUERY_PROCESSING = "query_processing"
    FILTER_CONFIGURATION = "filter_configuration"
    MULTIMODAL_WEIGHTING = "multimodal_weighting"
    RESPONSE_FORMAT = "response_format"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    UI_EXPERIENCE = "ui_experience"


class TrafficSplitType(PyEnum):
    """Traffic distribution strategies"""
    UNIFORM = "uniform"  # Equal distribution
    WEIGHTED = "weighted"  # Custom weights
    GRADUAL_ROLLOUT = "gradual_rollout"  # Slow percentage increase
    BANDIT = "bandit"  # Adaptive allocation based on performance


class StatisticalTest(PyEnum):
    """Statistical significance tests"""
    Z_TEST = "z_test"  # For large samples
    T_TEST = "t_test"  # For small samples
    CHI_SQUARE = "chi_square"  # For categorical data
    MANN_WHITNEY = "mann_whitney"  # Non-parametric
    WELCH_T_TEST = "welch_t_test"  # Unequal variances
    BAYESIAN_AB = "bayesian_ab"  # Bayesian approach


class MetricType(PyEnum):
    """Types of metrics tracked"""
    RELEVANCE_SCORE = "relevance_score"
    CLICK_THROUGH_RATE = "click_through_rate"
    RESPONSE_TIME = "response_time"
    USER_SATISFACTION = "user_satisfaction"
    CONVERSION_RATE = "conversion_rate"
    RESULT_COUNT = "result_count"
    QUERY_SUCCESS_RATE = "query_success_rate"
    BOUNCE_RATE = "bounce_rate"
    DIVERSITY_SCORE = "diversity_score"
    NOVELTY_SCORE = "novelty_score"
    COVERAGE_SCORE = "coverage_score"


class SuccessCriterion(PyEnum):
    """Success criteria for experiments"""
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    TARGET_RANGE = "target_range"
    STATISTICAL_SIGNIFICANCE = "statistical_significance"


class Experiment(BaseModel):
    """
    Core A/B test experiment configuration and management
    """
    __tablename__ = "ab_experiments"

    # Basic information
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    hypothesis = Column(Text, nullable=False)  # What we're testing and why

    # Experiment configuration
    experiment_type = Column(Enum(ExperimentType), nullable=False, index=True)
    status = Column(Enum(ExperimentStatus), default=ExperimentStatus.DRAFT, nullable=False, index=True)

    # Timing
    start_time = Column(DateTime(timezone=True), nullable=True, index=True)
    end_time = Column(DateTime(timezone=True), nullable=True, index=True)
    scheduled_start = Column(DateTime(timezone=True), nullable=True)
    scheduled_end = Column(DateTime(timezone=True), nullable=True)

    # Traffic configuration
    traffic_split_type = Column(Enum(TrafficSplitType), default=TrafficSplitType.UNIFORM, nullable=False)
    traffic_percentage = Column(Float, default=100.0, nullable=False)  # % of total traffic
    max_participants = Column(Integer, nullable=True)  # Hard cap on participants

    # Statistical configuration
    confidence_level = Column(Float, default=0.95, nullable=False)  # 95% confidence
    minimum_sample_size = Column(Integer, default=1000, nullable=False)
    statistical_test = Column(Enum(StatisticalTest), default=StatisticalTest.Z_TEST, nullable=False)
    expected_effect_size = Column(Float, nullable=True)  # Minimum detectable effect

    # Targeting configuration
    target_user_segments = Column(JSONB, nullable=True)  # User segment filters
    target_query_patterns = Column(JSONB, nullable=True)  # Query pattern filters
    target_organization_ids = Column(ARRAY(UUID), nullable=True)

    # Success criteria
    primary_metric = Column(Enum(MetricType), nullable=False, index=True)
    success_criteria = Column(Enum(SuccessCriterion), default=SuccessCriterion.HIGHER_IS_BETTER, nullable=False)
    target_improvement = Column(Float, nullable=True)  # % improvement expected
    minimum_duration_days = Column(Integer, default=7, nullable=False)

    # Results and analysis
    winning_variant_id = Column(GUID(), ForeignKey("ab_variants.id"), nullable=True)
    statistical_significance = Column(Float, nullable=True)  # P-value or Bayes factor
    effect_size = Column(Float, nullable=True)  # Actual effect size measured
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)

    # Organization and ownership
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False, index=True)
    created_by = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # Metadata
    tags = Column(StringArray, nullable=True)
    external_references = Column(JSONB, nullable=True)  # Links to external resources

    # Relationships
    organization = relationship("Organization", back_populates="ab_experiments")
    creator = relationship("User", back_populates="created_experiments")
    variants = relationship(
        "Variant",
        back_populates="experiment",
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="Variant.experiment_id"
    )
    assignments = relationship("ExperimentAssignment", back_populates="experiment", lazy="dynamic")
    metrics = relationship("ExperimentMetric", back_populates="experiment", lazy="dynamic")
    segments = relationship("ExperimentSegment", back_populates="experiment", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint('confidence_level > 0 AND confidence_level < 1', name='valid_confidence_level'),
        CheckConstraint('traffic_percentage > 0 AND traffic_percentage <= 100', name='valid_traffic_percentage'),
        CheckConstraint('minimum_sample_size > 0', name='valid_sample_size'),
        CheckConstraint('target_improvement IS NULL OR target_improvement > 0', name='valid_target_improvement'),
        CheckConstraint('minimum_duration_days > 0', name='valid_duration'),
        Index('idx_experiments_org_status', 'organization_id', 'status'),
        Index('idx_experiments_type_status', 'experiment_type', 'status'),
        Index('idx_experiments_timing', 'start_time', 'end_time'),
        Index('idx_experiments_creator', 'created_by'),
        UniqueConstraint('organization_id', 'name', name='unique_experiment_name_per_org'),
    )

    def __repr__(self):
        return f"<Experiment(name={self.name}, status={self.status.value}, type={self.experiment_type.value})>"

    @validates('start_time', 'end_time')
    def validate_timing(self, key, value):
        if key == 'end_time' and value and self.start_time and value <= self.start_time:
            raise ValueError("End time must be after start time")
        return value

    @hybrid_property
    def is_active(self) -> bool:
        """Check if experiment is currently active"""
        now = datetime.utcnow()
        return (
            self.status == ExperimentStatus.RUNNING and
            self.start_time and
            self.end_time and
            self.start_time <= now <= self.end_time
        )

    @is_active.expression
    def is_active(cls):
        now = datetime.utcnow()
        return and_(
            cls.status == ExperimentStatus.RUNNING,
            cls.start_time <= now,
            now <= cls.end_time
        )

    @hybrid_property
    def duration_days(self) -> Optional[float]:
        """Get experiment duration in days"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 86400
        return None

    @hybrid_property
    def actual_sample_size(self) -> int:
        """Get total number of participants"""
        return sum(variant.participant_count for variant in self.variants)

    def can_start(self) -> Tuple[bool, str]:
        """Check if experiment can be started"""
        if self.status not in [ExperimentStatus.DRAFT, ExperimentStatus.SCHEDULED]:
            return False, f"Cannot start experiment in {self.status.value} status"

        if not self.variants or len(self.variants) < 2:
            return False, "Experiment must have at least 2 variants"

        if not self.start_time or not self.end_time:
            return False, "Start and end times must be set"

        if self.end_time <= self.start_time:
            return False, "End time must be after start time"

        if self.end_time <= datetime.utcnow():
            return False, "End time must be in the future"

        # Check if variants have valid configurations
        for variant in self.variants:
            if not variant.config or not variant.is_valid_config():
                return False, f"Variant {variant.name} has invalid configuration"

        return True, "Ready to start"

    def can_stop(self) -> Tuple[bool, str]:
        """Check if experiment can be stopped"""
        if self.status != ExperimentStatus.RUNNING:
            return False, f"Cannot stop experiment in {self.status.value} status"

        if self.actual_sample_size < self.minimum_sample_size:
            return False, f"Minimum sample size not reached ({self.actual_sample_size} < {self.minimum_sample_size})"

        return True, "Can be stopped"

    def calculate_statistical_power(self) -> float:
        """Calculate statistical power of the experiment"""
        # Simplified power calculation - in practice, use scipy.stats.power
        if not self.expected_effect_size or self.actual_sample_size == 0:
            return 0.0

        # Basic power calculation (simplified)
        n_per_group = self.actual_sample_size / len(self.variants)
        alpha = 1 - self.confidence_level

        # This is a simplified version - use proper statistical functions in production
        power = 1 - math.exp(-n_per_group * (self.expected_effect_size ** 2) / 4)
        return min(power, 1.0)

    def get_participant_stats(self) -> Dict[str, Any]:
        """Get participant statistics across variants"""
        total_participants = sum(v.participant_count for v in self.variants)
        if total_participants == 0:
            return {"total": 0, "variants": []}

        variant_stats = []
        for variant in self.variants:
            percentage = (variant.participant_count / total_participants) * 100
            variant_stats.append({
                "variant_id": str(variant.id),
                "variant_name": variant.name,
                "participant_count": variant.participant_count,
                "percentage": round(percentage, 2)
            })

        return {
            "total": total_participants,
            "variants": variant_stats
        }

    def to_dict(self, include_results: bool = False) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        data = super().to_dict()

        # Convert enums
        for field in ['experiment_type', 'status', 'traffic_split_type', 'statistical_test',
                     'primary_metric', 'success_criteria']:
            if hasattr(self, field) and getattr(self, field):
                data[field] = getattr(self, field).value

        # Add computed properties
        data['is_active'] = self.is_active
        data['duration_days'] = self.duration_days
        data['actual_sample_size'] = self.actual_sample_size
        data['statistical_power'] = self.calculate_statistical_power()

        # Add variant information
        data['variants'] = [variant.to_dict() for variant in self.variants]
        data['participant_stats'] = self.get_participant_stats()

        if include_results:
            data['results'] = {
                'winning_variant': self.winning_variant_id,
                'statistical_significance': self.statistical_significance,
                'effect_size': self.effect_size,
                'confidence_interval': {
                    'lower': self.confidence_interval_lower,
                    'upper': self.confidence_interval_upper
                }
            }

        return data


class Variant(BaseModel):
    """
    Individual test variants within an experiment
    """
    __tablename__ = "ab_variants"

    # Basic information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_control = Column(Boolean, default=False, nullable=False, index=True)

    # Experiment relationship
    experiment_id = Column(GUID(), ForeignKey("ab_experiments.id"), nullable=False, index=True)

    # Configuration
    config = Column(JSONB, nullable=False)  # Variant-specific configuration
    weight = Column(Float, default=1.0, nullable=False)  # Traffic weight for this variant

    # Participation metrics
    participant_count = Column(Integer, default=0, nullable=False, index=True)
    query_count = Column(Integer, default=0, nullable=False)

    # Performance metrics
    primary_metric_value = Column(Float, nullable=True, index=True)
    conversion_count = Column(Integer, default=0, nullable=False)
    click_count = Column(Integer, default=0, nullable=False)
    total_response_time_ms = Column(Integer, default=0, nullable=False)
    user_satisfaction_score = Column(Float, nullable=True)

    # Statistical metrics
    standard_error = Column(Float, nullable=True)
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)
    p_value = Column(Float, nullable=True)

    # Relationships
    experiment = relationship("Experiment", back_populates="variants", foreign_keys=[experiment_id])
    assignments = relationship("ExperimentAssignment", back_populates="variant", lazy="dynamic")
    metrics = relationship("ExperimentMetric", back_populates="variant", lazy="dynamic")

    # Constraints
    __table_args__ = (
        CheckConstraint('weight > 0', name='valid_weight'),
        CheckConstraint('participant_count >= 0', name='valid_participant_count'),
        UniqueConstraint('experiment_id', 'name', name='unique_variant_name_per_experiment'),
        Index('idx_variants_experiment_control', 'experiment_id', 'is_control'),
        Index('idx_variants_experiment_participants', 'experiment_id', 'participant_count'),
    )

    def __repr__(self):
        return f"<Variant(name={self.name}, experiment={self.experiment_id}, control={self.is_control})>"

    @hybrid_property
    def traffic_percentage(self) -> float:
        """Calculate actual traffic percentage based on weights"""
        if not self.experiment:
            return 0.0

        total_weight = sum(v.weight for v in self.experiment.variants if v.is_deleted == False)
        if total_weight == 0:
            return 0.0

        return (self.weight / total_weight) * 100

    @hybrid_property
    def conversion_rate(self) -> Optional[float]:
        """Calculate conversion rate"""
        if self.query_count == 0:
            return None
        return (self.conversion_count / self.query_count) * 100

    @hybrid_property
    def click_through_rate(self) -> Optional[float]:
        """Calculate click-through rate"""
        if self.query_count == 0:
            return None
        return (self.click_count / self.query_count) * 100

    @hybrid_property
    def average_response_time_ms(self) -> Optional[float]:
        """Calculate average response time"""
        if self.query_count == 0:
            return None
        return self.total_response_time_ms / self.query_count

    def is_valid_config(self) -> bool:
        """Validate variant configuration based on experiment type"""
        if not self.config or not self.experiment:
            return False

        experiment_type = self.experiment.experiment_type

        if experiment_type == ExperimentType.SEARCH_ALGORITHM:
            required_fields = ['algorithm', 'parameters']
        elif experiment_type == ExperimentType.RANKING_MODEL:
            required_fields = ['model_name', 'model_version', 'parameters']
        elif experiment_type == ExperimentType.MULTIMODAL_WEIGHTING:
            required_fields = ['modality_weights']
        elif experiment_type == ExperimentType.FILTER_CONFIGURATION:
            required_fields = ['filter_settings']
        else:
            required_fields = []

        return all(field in self.config for field in required_fields)

    def update_metrics(self, metrics_data: Dict[str, Any]):
        """Update variant metrics from new data"""
        if 'response_time_ms' in metrics_data:
            self.total_response_time_ms += metrics_data['response_time_ms']

        if 'conversion' in metrics_data and metrics_data['conversion']:
            self.conversion_count += 1

        if 'click' in metrics_data and metrics_data['click']:
            self.click_count += 1

        if 'user_satisfaction' in metrics_data:
            # Update running average
            current_avg = self.user_satisfaction_score or 0
            current_count = self.query_count
            new_rating = metrics_data['user_satisfaction']

            if current_count == 0:
                self.user_satisfaction_score = new_rating
            else:
                self.user_satisfaction_score = ((current_avg * current_count) + new_rating) / (current_count + 1)

        self.query_count += 1

    def calculate_confidence_interval(self, confidence_level: float = 0.95) -> Tuple[float, float]:
        """Calculate confidence interval for primary metric"""
        if self.query_count == 0 or self.standard_error is None:
            return None, None

        # Z-score for confidence level (simplified)
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z_score = z_scores.get(confidence_level, 1.96)

        margin_of_error = z_score * self.standard_error
        lower = self.primary_metric_value - margin_of_error
        upper = self.primary_metric_value + margin_of_error

        return lower, upper

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        data = super().to_dict()

        # Add computed properties
        data['traffic_percentage'] = self.traffic_percentage
        data['conversion_rate'] = self.conversion_rate
        data['click_through_rate'] = self.click_through_rate
        data['average_response_time_ms'] = self.average_response_time_ms

        # Add confidence interval
        lower, upper = self.calculate_confidence_interval()
        data['confidence_interval'] = {'lower': lower, 'upper': upper}

        return data


class ExperimentAssignment(BaseModel):
    """
    Individual user assignments to experiment variants
    """
    __tablename__ = "ab_assignments"

    # Assignment information
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    experiment_id = Column(GUID(), ForeignKey("ab_experiments.id"), nullable=False, index=True)
    variant_id = Column(GUID(), ForeignKey("ab_variants.id"), nullable=False, index=True)

    # Assignment metadata
    assigned_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)
    assignment_source = Column(String(100), nullable=True)  # How assignment was made

    # Context information
    user_segment = Column(JSONB, nullable=True)  # User segment at time of assignment
    query_context = Column(JSONB, nullable=True)  # Query context for assignment
    device_info = Column(JSONB, nullable=True)

    # Relationships
    user = relationship("User")
    experiment = relationship("Experiment", back_populates="assignments")
    variant = relationship("Variant", back_populates="assignments")

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'experiment_id', name='unique_user_experiment_assignment'),
        UniqueConstraint('session_id', 'experiment_id', name='unique_session_experiment_assignment'),
        Index('idx_assignments_user_experiment', 'user_id', 'experiment_id'),
        Index('idx_assignments_variant_time', 'variant_id', 'assigned_at'),
        Index('idx_assignments_experiment_time', 'experiment_id', 'assigned_at'),
    )

    def __repr__(self):
        return f"<ExperimentAssignment(user={self.user_id}, experiment={self.experiment_id}, variant={self.variant_id})>"


class ExperimentMetric(BaseModel):
    """
    Detailed metrics collected for experiment analysis
    """
    __tablename__ = "ab_experiment_metrics"

    # Metric information
    experiment_id = Column(GUID(), ForeignKey("ab_experiments.id"), nullable=False, index=True)
    variant_id = Column(GUID(), ForeignKey("ab_variants.id"), nullable=False, index=True)
    metric_type = Column(Enum(MetricType), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)

    # Context information
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    query_id = Column(GUID(), nullable=True, index=True)  # Link to search_queries

    # Additional data
    metric_metadata = Column(JSONB, nullable=True)  # Additional metric-specific data
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)

    # Aggregation helpers
    date_hour = Column(String(13), nullable=False, index=True)  # YYYY-MM-DDTHH
    date_day = Column(String(10), nullable=False, index=True)   # YYYY-MM-DD

    # Relationships
    experiment = relationship("Experiment", back_populates="metrics")
    variant = relationship("Variant", back_populates="metrics")
    user = relationship("User")

    # Constraints
    __table_args__ = (
        Index('idx_metrics_experiment_variant_type', 'experiment_id', 'variant_id', 'metric_type'),
        Index('idx_metrics_variant_time', 'variant_id', 'timestamp'),
        Index('idx_metrics_type_time', 'metric_type', 'timestamp'),
        Index('idx_metrics_experiment_day', 'experiment_id', 'date_day'),
        Index('idx_metrics_user_experiment', 'user_id', 'experiment_id'),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.timestamp:
            self.date_day = self.timestamp.strftime('%Y-%m-%d')
            self.date_hour = self.timestamp.strftime('%Y-%m-%dT%H')

    def __repr__(self):
        return f"<ExperimentMetric(type={self.metric_type.value}, value={self.metric_value}, variant={self.variant_id})>"


class UserSegment(BaseModel):
    """
    User segments for targeted experiments
    """
    __tablename__ = "ab_user_segments"

    # Segment information
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False, index=True)

    # Segment definition
    segment_criteria = Column(JSONB, nullable=False)  # Rules for segment membership
    segment_type = Column(String(100), nullable=True, index=True)  # behavioral, demographic, technical

    # Membership tracking
    user_count = Column(Integer, default=0, nullable=False)
    active_user_count = Column(Integer, default=0, nullable=False)

    # Metadata
    created_by = Column(GUID(), ForeignKey("users.id"), nullable=False)
    is_dynamic = Column(Boolean, default=True, nullable=False)  # Auto-update membership
    last_updated = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Relationships
    organization = relationship("Organization")
    creator = relationship("User")
    memberships = relationship("UserSegmentMembership", back_populates="segment", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint('user_count >= 0', name='valid_user_count'),
        CheckConstraint('active_user_count >= 0', name='valid_active_user_count'),
        UniqueConstraint('organization_id', 'name', name='unique_segment_name_per_org'),
        Index('idx_segments_org_type', 'organization_id', 'segment_type'),
    )

    def __repr__(self):
        return f"<UserSegment(name={self.name}, org={self.organization_id}, users={self.user_count})>"

    def update_membership_counts(self):
        """Update user count statistics"""
        self.user_count = self.memberships.count()
        self.active_user_count = self.memberships.filter(
            UserSegmentMembership.is_active == True
        ).count()
        self.last_updated = datetime.utcnow()


class UserSegmentMembership(BaseModel):
    """
    Individual user segment memberships
    """
    __tablename__ = "ab_user_segment_memberships"

    # Membership information
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    segment_id = Column(GUID(), ForeignKey("ab_user_segments.id"), nullable=False, index=True)

    # Membership status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    joined_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    left_at = Column(DateTime(timezone=True), nullable=True)

    # Membership context
    membership_criteria = Column(JSONB, nullable=True)  # Why user belongs to segment

    # Relationships
    user = relationship("User")
    segment = relationship("UserSegment", back_populates="memberships")

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'segment_id', name='unique_user_segment_membership'),
        Index('idx_segment_memberships_active', 'segment_id', 'is_active'),
        Index('idx_segment_memberships_user', 'user_id', 'is_active'),
    )

    def __repr__(self):
        return f"<UserSegmentMembership(user={self.user_id}, segment={self.segment_id}, active={self.is_active})>"


class ExperimentSegment(BaseModel):
    """
    Segment-specific experiment configurations
    """
    __tablename__ = "ab_experiment_segments"

    # Segment configuration
    experiment_id = Column(GUID(), ForeignKey("ab_experiments.id"), nullable=False, index=True)
    segment_id = Column(GUID(), ForeignKey("ab_user_segments.id"), nullable=False, index=True)

    # Segment-specific settings
    traffic_percentage = Column(Float, nullable=True)  # Override global traffic percentage
    variant_weights = Column(JSONB, nullable=True)  # Segment-specific variant weights
    custom_success_criteria = Column(JSONB, nullable=True)  # Segment-specific success criteria

    # Relationships
    experiment = relationship("Experiment", back_populates="segments")
    segment = relationship("UserSegment")

    # Constraints
    __table_args__ = (
        UniqueConstraint('experiment_id', 'segment_id', name='unique_experiment_segment'),
        CheckConstraint('traffic_percentage IS NULL OR (traffic_percentage > 0 AND traffic_percentage <= 100)',
                       name='valid_segment_traffic_percentage'),
    )

    def __repr__(self):
        return f"<ExperimentSegment(experiment={self.experiment_id}, segment={self.segment_id})>"


class QueryRouting(BaseModel):
    """
    Real-time query routing for experiment assignments
    """
    __tablename__ = "ab_query_routing"

    # Query information
    query_id = Column(GUID(), nullable=False, unique=True, index=True)  # Link to search_queries
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(255), nullable=True, index=True)

    # Routing decision
    experiment_id = Column(GUID(), ForeignKey("ab_experiments.id"), nullable=False, index=True)
    variant_id = Column(GUID(), ForeignKey("ab_variants.id"), nullable=False, index=True)
    routing_decision_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)

    # Routing context
    routing_reason = Column(String(255), nullable=True)  # Why this routing was chosen
    routing_confidence = Column(Float, nullable=True)  # Confidence in routing decision
    alternative_variants = Column(JSONB, nullable=True)  # Other variants considered

    # Performance tracking
    processing_overhead_ms = Column(Integer, nullable=True)  # Time for routing decision

    # Relationships
    user = relationship("User")
    experiment = relationship("Experiment")
    variant = relationship("Variant")

    # Constraints
    __table_args__ = (
        Index('idx_routing_experiment_time', 'experiment_id', 'routing_decision_at'),
        Index('idx_routing_variant_time', 'variant_id', 'routing_decision_at'),
        Index('idx_routing_user_time', 'user_id', 'routing_decision_at'),
        Index('idx_routing_session_time', 'session_id', 'routing_decision_at'),
    )

    def __repr__(self):
        return f"<QueryRouting(query={self.query_id}, experiment={self.experiment_id}, variant={self.variant_id})>"


# Update existing models to include A/B testing relationships
# These would be added to the respective model files

# Organization.ab_experiments relationship would be added to Organization model
# User.created_experiments and User.ab_assignments relationships would be added to User model