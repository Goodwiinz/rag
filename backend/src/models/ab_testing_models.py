"""
A/B Testing Models for Multimodal Enterprise RAG System

This module provides SQLAlchemy models for A/B testing functionality,
including experiment management, user assignment, metrics collection,
and statistical analysis.

Key Features:
- High-performance query routing with sub-10ms lookups
- Time-series optimized metrics collection
- Statistical significance calculation
- User segmentation and targeting
- Real-time experiment management
"""

import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Union
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Enum, ForeignKey,
    Text, JSON, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

from .base import BaseModel, GUID
from .utils import StringArray

# ====================================================================
# Enums
# ====================================================================

class ExperimentStatus(PyEnum):
    """Experiment lifecycle status"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class VariantStatus(PyEnum):
    """Variant status"""
    ACTIVE = "active"
    DISABLED = "disabled"
    PAUSED = "paused"

class SegmentType(PyEnum):
    """User segment types"""
    STATIC = "static"
    DYNAMIC = "dynamic"
    BEHAVIORAL = "behavioral"
    DEMOGRAPHIC = "demographic"

class QueryType(PyEnum):
    """Query types in RAG system"""
    SEARCH = "search"
    REASONING = "reasoning"
    MULTIMODAL = "multimodal"

class EventType(PyEnum):
    """Event types for tracking"""
    QUERY_COMPLETION = "query_completion"
    USER_FEEDBACK = "user_feedback"
    ERROR = "error"
    TIMEOUT = "timeout"

class EvaluationMethod(PyEnum):
    """Quality evaluation methods"""
    AUTOMATED = "automated"
    HUMAN = "human"
    HYBRID = "hybrid"

class StatisticalTest(PyEnum):
    """Statistical test types"""
    TWO_SAMPLE_T_TEST = "two_sample_t_test"
    MANN_WHITNEY = "mann_whitney"
    CHI_SQUARE = "chi_square"
    BOOTSTRAP = "bootstrap"

# ====================================================================
# Core Models
# ====================================================================

class Experiment(BaseModel):
    """A/B Test Experiment Configuration"""

    __tablename__ = "ab_experiments"

    # Basic Information
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    hypothesis = Column(Text, nullable=True)
    status = Column(Enum(ExperimentStatus), nullable=False, index=True)

    # Traffic Configuration
    traffic_percentage = Column(Integer, nullable=False, default=100)
    is_ramp_enabled = Column(Boolean, default=False)
    ramp_schedule = Column(JSON, default=dict)

    # Targeting Configuration
    target_segments = Column(JSON, default=list)
    exclude_segments = Column(JSON, default=list)

    # Statistical Configuration
    confidence_level = Column(Float, nullable=False, default=0.95)
    minimum_sample_size = Column(Integer, nullable=False, default=1000)
    expected_improvement = Column(Float, nullable=False, default=5.0)
    test_duration_days = Column(Integer, nullable=False, default=14)

    # Metrics Configuration
    primary_metric = Column(String(100), nullable=False, default="answer_relevancy")
    secondary_metrics = Column(JSON, default=list)

    # Time Management
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(GUID(), nullable=True)

    # Metadata
    tags = Column(JSON, default=list)
    metadata = Column(JSON, default=dict)

    # Constraints
    __table_args__ = (
        CheckConstraint('traffic_percentage >= 0 AND traffic_percentage <= 100'),
        CheckConstraint('confidence_level > 0 AND confidence_level <= 1'),
        CheckConstraint('test_duration_days > 0'),
        CheckConstraint('expected_improvement >= 0'),
        Index('idx_ab_experiments_status', 'status', postgresql_where=func.not_(BaseModel.is_deleted)),
        Index('idx_ab_experiments_active_time', 'start_time', 'end_time',
              postgresql_where=func.and_(
                  func.not_(BaseModel.is_deleted),
                  func.text('status') == 'running'
              )),
        Index('idx_ab_experiments_tags', 'tags', postgresql_where=func.not_(BaseModel.is_deleted)),
    )

    # Relationships
    variants = relationship("Variant", back_populates="experiment", cascade="all, delete-orphan")
    user_assignments = relationship("UserAssignment", back_populates="experiment")
    query_events = relationship("QueryEvent", back_populates="experiment")
    statistical_analyses = relationship("StatisticalAnalysis", back_populates="experiment")
    targetings = relationship("ExperimentTargeting", back_populates="experiment", cascade="all, delete-orphan")

    @validates('start_time', 'end_time')
    def validate_time_range(self, key, value):
        """Validate that end_time is after start_time"""
        if key == 'end_time' and value and self.start_time and value <= self.start_time:
            raise ValueError("End time must be after start time")
        return value

    @validates('traffic_percentage')
    def validate_traffic_percentage(self, key, value):
        """Validate traffic percentage range"""
        if not (0 <= value <= 100):
            raise ValueError("Traffic percentage must be between 0 and 100")
        return value

    @property
    def is_active(self) -> bool:
        """Check if experiment is currently active"""
        if self.status != ExperimentStatus.RUNNING:
            return False

        now = datetime.utcnow()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now >= self.end_time:
            return False

        return True

    @property
    def control_variant(self) -> Optional['Variant']:
        """Get the control variant for this experiment"""
        for variant in self.variants:
            if variant.is_control and variant.is_active:
                return variant
        return None

    @property
    def treatment_variants(self) -> List['Variant']:
        """Get all treatment variants for this experiment"""
        return [v for v in self.variants if not v.is_control and v.is_active]

    def get_variant_by_id(self, variant_id: uuid.UUID) -> Optional['Variant']:
        """Get variant by ID"""
        for variant in self.variants:
            if variant.id == variant_id:
                return variant
        return None

    def should_include_user(self, user_context: Dict[str, Any]) -> bool:
        """Check if user should be included in experiment based on targeting"""
        # Simple implementation - expand based on segment logic
        if not self.target_segments:
            return True

        # TODO: Implement segment matching logic
        return True

    def get_remaining_days(self) -> int:
        """Get remaining days for experiment"""
        if not self.end_time:
            return self.test_duration_days

        remaining = self.end_time - datetime.utcnow()
        return max(0, remaining.days)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with computed fields"""
        data = super().to_dict()
        data.update({
            'is_active': self.is_active,
            'control_variant_id': self.control_variant.id if self.control_variant else None,
            'treatment_variant_count': len(self.treatment_variants),
            'remaining_days': self.get_remaining_days()
        })
        return data

class Variant(BaseModel):
    """Experiment Variant Configuration"""

    __tablename__ = "ab_variants"

    # Relationships
    experiment_id = Column(GUID(), ForeignKey("ab_experiments.id", ondelete="CASCADE"), nullable=False)

    # Basic Information
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Variant Configuration
    is_control = Column(Boolean, default=False)
    traffic_weight = Column(Integer, nullable=False, default=1)
    configuration = Column(JSON, nullable=False, default=dict)

    # RAG System Configuration
    retrieval_config = Column(JSON, default=dict)
    ranking_config = Column(JSON, default=dict)
    synthesis_config = Column(JSON, default=dict)
    agent_config = Column(JSON, default=dict)

    # Performance Metrics
    baseline_metrics = Column(JSON, default=dict)

    # Status
    status = Column(Enum(VariantStatus), default=VariantStatus.ACTIVE)

    # Metadata
    metadata = Column(JSON, default=dict)

    # Constraints
    __table_args__ = (
        CheckConstraint('traffic_weight > 0'),
        UniqueConstraint('experiment_id', 'name'),
        Index('idx_ab_variants_experiment_id', 'experiment_id', postgresql_where=func.not_(BaseModel.is_deleted)),
        Index('idx_ab_variants_experiment_active', 'experiment_id', 'status',
              postgresql_where=func.not_(BaseModel.is_deleted)),
        Index('idx_ab_variants_control', 'experiment_id', 'is_control',
              postgresql_where=func.not_(BaseModel.is_deleted)),
    )

    # Relationships
    experiment = relationship("Experiment", back_populates="variants")
    user_assignments = relationship("UserAssignment", back_populates="variant")
    query_events = relationship("QueryEvent", back_populates="variant")

    @validates('traffic_weight')
    def validate_traffic_weight(self, key, value):
        """Validate traffic weight is positive"""
        if value <= 0:
            raise ValueError("Traffic weight must be positive")
        return value

    @property
    def is_active(self) -> bool:
        """Check if variant is active"""
        return self.status == VariantStatus.ACTIVE and not self.is_deleted

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with fallback"""
        return self.configuration.get(key, default)

    def set_config_value(self, key: str, value: Any) -> None:
        """Set configuration value"""
        if not self.configuration:
            self.configuration = {}
        self.configuration[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with computed fields"""
        data = super().to_dict()
        data.update({
            'is_active': self.is_active,
            'total_traffic_weight': sum(v.traffic_weight for v in self.experiment.variants if v.is_active)
        })
        return data

class UserSegment(BaseModel):
    """User Segment Definition"""

    __tablename__ = "ab_user_segments"

    # Basic Information
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    # Segment Definition
    criteria = Column(JSON, nullable=False, default=dict)
    segment_type = Column(Enum(SegmentType), nullable=False)

    # Segment Properties
    size_estimate = Column(Integer, nullable=True)
    refresh_frequency = Column(String(50), default="daily")
    is_active = Column(Boolean, default=True)

    # Metadata
    metadata = Column(JSON, default=dict)

    created_by_user_id = Column(GUID(), nullable=True)

    # Constraints
    __table_args__ = (
        Index('idx_ab_user_segments_active', 'is_active', postgresql_where=func.not_(BaseModel.is_deleted)),
        Index('idx_ab_user_segments_type', 'segment_type', postgresql_where=func.not_(BaseModel.is_deleted)),
    )

    # Relationships
    targetings = relationship("ExperimentTargeting", back_populates="segment", cascade="all, delete-orphan")

    def matches_user(self, user_context: Dict[str, Any]) -> bool:
        """Check if user matches segment criteria"""
        # TODO: Implement segment matching logic based on criteria
        # This would depend on your user context structure
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict()
        data['segment_type'] = self.segment_type.value if self.segment_type else None
        return data

class UserAssignment(BaseModel):
    """User to Variant Assignment for Consistency"""

    __tablename__ = "ab_user_assignments"

    # Context
    user_id = Column(String(255), nullable=False)
    session_id = Column(String(255), nullable=True)

    # Relationships
    experiment_id = Column(GUID(), ForeignKey("ab_experiments.id"), nullable=False)
    variant_id = Column(GUID(), ForeignKey("ab_variants.id"), nullable=False)

    # Assignment Context
    assignment_context = Column(JSON, default=dict)
    segment_matches = Column(JSON, default=list)
    assignment_hash = Column(String(64), nullable=True)

    # Timestamps
    assigned_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Status
    is_active = Column(Boolean, default=True)

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'experiment_id'),
        CheckConstraint('assignment_hash IS NULL OR length(assignment_hash) = 64'),
        # Note: Partitioning is defined in the SQL schema
    )

    # Relationships
    experiment = relationship("Experiment", back_populates="user_assignments")
    variant = relationship("Variant", back_populates="user_assignments")

    @staticmethod
    def generate_assignment_hash(user_id: str, experiment_id: uuid.UUID, salt: str = "") -> str:
        """Generate consistent assignment hash"""
        hash_input = f"{user_id}:{experiment_id}:{salt}"
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def update_last_seen(self) -> None:
        """Update last seen timestamp"""
        self.last_seen_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict()
        # Remove sensitive information
        data.pop('assignment_context', None)
        data.pop('assignment_hash', None)
        return data

class QueryEvent(BaseModel):
    """Individual Query Interaction Event"""

    __tablename__ = "ab_query_events"

    # Unique identifier
    event_id = Column(String(255), nullable=False, unique=True)

    # Context
    user_id = Column(String(255), nullable=True)
    session_id = Column(String(255), nullable=True)

    # Relationships
    experiment_id = Column(GUID(), ForeignKey("ab_experiments.id"), nullable=True)
    variant_id = Column(GUID(), ForeignKey("ab_variants.id"), nullable=True)

    # Query Information
    query_text = Column(Text, nullable=False)
    query_hash = Column(String(64), nullable=True)
    query_type = Column(Enum(QueryType), default=QueryType.SEARCH)

    # Performance Metrics
    query_latency_ms = Column(Integer, nullable=True)
    total_latency_ms = Column(Integer, nullable=True)
    retrieval_count = Column(Integer, nullable=True)
    rerank_count = Column(Integer, nullable=True)

    # System Metrics
    vector_search_latency_ms = Column(Integer, nullable=True)
    graph_search_latency_ms = Column(Integer, nullable=True)
    keyword_search_latency_ms = Column(Integer, nullable=True)
    synthesis_latency_ms = Column(Integer, nullable=True)

    # Query Features
    query_complexity_score = Column(Float, nullable=True)
    modality_types = Column(JSON, default=list)

    # Event Details
    event_type = Column(Enum(EventType), default=EventType.QUERY_COMPLETION)
    response_status = Column(String(50), default="success")
    error_details = Column(JSON, nullable=True)

    # Metadata
    metadata = Column(JSON, default=dict)

    # Constraints
    __table_args__ = (
        CheckConstraint('query_latency_ms IS NULL OR query_latency_ms >= 0'),
        CheckConstraint('total_latency_ms IS NULL OR total_latency_ms >= 0'),
        # Note: Partitioning is defined in the SQL schema
    )

    # Relationships
    experiment = relationship("Experiment", back_populates="query_events")
    variant = relationship("Variant", back_populates="query_events")
    quality_metrics = relationship("ABQualityMetric", back_populates="query_event", uselist=False)

    @staticmethod
    def generate_query_hash(query_text: str) -> str:
        """Generate query hash for deduplication"""
        return hashlib.sha256(query_text.encode()).hexdigest()

    @property
    def is_successful(self) -> bool:
        """Check if query was successful"""
        return self.response_status == "success"

    @property
    def total_processing_time_ms(self) -> Optional[int]:
        """Get total processing time"""
        if self.total_latency_ms:
            return self.total_latency_ms

        # Sum individual latencies if available
        latencies = [
            self.vector_search_latency_ms,
            self.graph_search_latency_ms,
            self.keyword_search_latency_ms,
            self.synthesis_latency_ms
        ]
        available_latencies = [l for l in latencies if l is not None]
        return sum(available_latencies) if available_latencies else None

    def add_latency_metric(self, metric_name: str, latency_ms: int) -> None:
        """Add latency metric"""
        setattr(self, f"{metric_name}_latency_ms", latency_ms)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with computed fields"""
        data = super().to_dict()
        data.update({
            'query_type': self.query_type.value if self.query_type else None,
            'event_type': self.event_type.value if self.event_type else None,
            'is_successful': self.is_successful,
            'total_processing_time_ms': self.total_processing_time_ms
        })
        return data

class ABQualityMetric(BaseModel):
    """Quality Metrics for Query Events (renamed to avoid conflict with existing QualityMetric)"""

    __tablename__ = "ab_quality_metrics"

    # Relationship
    query_event_id = Column(GUID(), ForeignKey("ab_query_events.id"), nullable=False, unique=True)

    # Core RAG Metrics
    answer_relevancy = Column(Float, nullable=True)
    faithfulness = Column(Float, nullable=True)
    contextual_relevancy = Column(Float, nullable=True)

    # Additional Quality Metrics
    response_coherence = Column(Float, nullable=True)
    completeness = Column(Float, nullable=True)
    conciseness = Column(Float, nullable=True)

    # User Experience Metrics
    user_satisfaction_score = Column(Integer, nullable=True)
    user_feedback = Column(Text, nullable=True)
    user_clicked_results = Column(Boolean, default=False)
    user_dwell_time_ms = Column(Integer, nullable=True)

    # Business Metrics
    task_completion_rate = Column(Float, nullable=True)
    conversion_rate = Column(Float, nullable=True)

    # Evaluation Details
    evaluation_method = Column(Enum(EvaluationMethod), default=EvaluationMethod.AUTOMATED)
    confidence_score = Column(Float, nullable=True)
    evaluation_model = Column(String(100), nullable=True)

    # Context
    ground_truth_data = Column(JSON, nullable=True)
    evaluation_parameters = Column(JSON, default=dict)

    # Constraints
    __table_args__ = (
        CheckConstraint('answer_relevancy IS NULL OR (answer_relevancy >= 0 AND answer_relevancy <= 100)'),
        CheckConstraint('faithfulness IS NULL OR (faithfulness >= 0 AND faithfulness <= 100)'),
        CheckConstraint('contextual_relevancy IS NULL OR (contextual_relevancy >= 0 AND contextual_relevancy <= 100)'),
        CheckConstraint('response_coherence IS NULL OR (response_coherence >= 0 AND response_coherence <= 100)'),
        CheckConstraint('completeness IS NULL OR (completeness >= 0 AND completeness <= 100)'),
        CheckConstraint('conciseness IS NULL OR (conciseness >= 0 AND conciseness <= 100)'),
        CheckConstraint('user_satisfaction_score IS NULL OR (user_satisfaction_score >= 1 AND user_satisfaction_score <= 5)'),
        CheckConstraint('confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)'),
        # Note: Partitioning is defined in the SQL schema
    )

    # Relationships
    query_event = relationship("QueryEvent", back_populates="quality_metrics")

    @property
    def rag_triad_score(self) -> Optional[float]:
        """Calculate average RAG triad score"""
        scores = [self.answer_relevancy, self.faithfulness, self.contextual_relevancy]
        available_scores = [s for s in scores if s is not None]
        return sum(available_scores) / len(available_scores) if available_scores else None

    @property
    def passes_thresholds(self) -> Dict[str, bool]:
        """Check if metrics pass quality thresholds"""
        thresholds = {
            'answer_relevancy': 70.0,
            'faithfulness': 90.0,
            'contextual_relevancy': 70.0
        }

        results = {}
        for metric, threshold in thresholds.items():
            value = getattr(self, metric)
            results[metric] = value is not None and value >= threshold

        return results

    def set_rag_triad_metrics(self, answer_relevancy: float, faithfulness: float, contextual_relevancy: float) -> None:
        """Set RAG triad metrics"""
        self.answer_relevancy = answer_relevancy
        self.faithfulness = faithfulness
        self.contextual_relevancy = contextual_relevancy

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with computed fields"""
        data = super().to_dict()
        data.update({
            'evaluation_method': self.evaluation_method.value if self.evaluation_method else None,
            'rag_triad_score': self.rag_triad_score,
            'passes_thresholds': self.passes_thresholds
        })
        return data

class StatisticalAnalysis(BaseModel):
    """Statistical Significance Analysis Results"""

    __tablename__ = "ab_statistical_analyses"

    # Relationships
    experiment_id = Column(GUID(), ForeignKey("ab_experiments.id"), nullable=False)
    metric_name = Column(String(100), nullable=False)

    # Analysis Window
    analysis_period_start = Column(DateTime(timezone=True), nullable=False)
    analysis_period_end = Column(DateTime(timezone=True), nullable=False)
    sample_size = Column(Integer, nullable=False)

    # Statistical Results
    control_mean = Column(Float, nullable=True)
    control_std_dev = Column(Float, nullable=True)
    control_sample_size = Column(Integer, nullable=True)

    treatment_mean = Column(Float, nullable=True)
    treatment_std_dev = Column(Float, nullable=True)
    treatment_sample_size = Column(Integer, nullable=True)

    # Significance Testing
    effect_size = Column(Float, nullable=True)  # Cohen's d
    confidence_interval_lower = Column(Float, nullable=True)
    confidence_interval_upper = Column(Float, nullable=True)
    p_value = Column(Float, nullable=True)

    # Results
    is_significant = Column(Boolean, default=False)
    is_positive_impact = Column(Boolean, default=False)
    relative_improvement = Column(Float, nullable=True)
    absolute_improvement = Column(Float, nullable=True)

    # Test Configuration
    statistical_test = Column(Enum(StatisticalTest), default=StatisticalTest.TWO_SAMPLE_T_TEST)
    confidence_level = Column(Float, default=0.95)
    minimum_detectable_effect = Column(Float, nullable=True)

    # Metadata
    analysis_metadata = Column(JSON, default=dict)

    # Constraints
    __table_args__ = (
        CheckConstraint('analysis_period_end > analysis_period_start'),
        CheckConstraint('relative_improvement IS NULL OR relative_improvement >= -100'),
        CheckConstraint('p_value IS NULL OR (p_value >= 0 AND p_value <= 1)'),
        CheckConstraint('confidence_level > 0 AND confidence_level <= 1'),
        Index('idx_ab_statistical_analyses_experiment_metric', 'experiment_id', 'metric_name', 'created_at'),
        Index('idx_ab_statistical_analyses_significant', 'is_significant', 'created_at'),
    )

    # Relationships
    experiment = relationship("Experiment", back_populates="statistical_analyses")

    @property
    def is_conclusive(self) -> bool:
        """Check if analysis provides conclusive results"""
        return (self.is_significant and
                self.sample_size >= 1000 and
                self.p_value is not None)

    @property
    def business_impact(self) -> str:
        """Get business impact description"""
        if not self.is_conclusive:
            return "Inconclusive - more data needed"

        if not self.is_positive_impact:
            return f"Negative impact: {self.relative_improvement:.1f}% decrease"

        return f"Positive impact: {self.relative_improvement:.1f}% improvement"

    def calculate_effect_size(self) -> Optional[float]:
        """Calculate Cohen's d effect size"""
        if (self.control_mean is None or self.treatment_mean is None or
            self.control_std_dev is None or self.control_std_dev == 0):
            return None

        return (self.treatment_mean - self.control_mean) / self.control_std_dev

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with computed fields"""
        data = super().to_dict()
        data.update({
            'statistical_test': self.statistical_test.value if self.statistical_test else None,
            'is_conclusive': self.is_conclusive,
            'business_impact': self.business_impact,
            'effect_size_calculated': self.calculate_effect_size()
        })
        return data

class ExperimentTargeting(BaseModel):
    """Experiment to Segment Targeting Relationship"""

    __tablename__ = "ab_experiment_targeting"

    # Relationships
    experiment_id = Column(GUID(), ForeignKey("ab_experiments.id", ondelete="CASCADE"), nullable=False)
    segment_id = Column(GUID(), ForeignKey("ab_user_segments.id", ondelete="CASCADE"), nullable=False)

    # Targeting Configuration
    is_inclusion = Column(Boolean, default=True)
    priority = Column(Integer, default=1)
    traffic_percentage = Column(Integer, default=100)

    # Constraints
    __table_args__ = (
        UniqueConstraint('experiment_id', 'segment_id'),
        CheckConstraint('traffic_percentage >= 0 AND traffic_percentage <= 100'),
        CheckConstraint('priority > 0'),
        Index('idx_ab_experiment_targeting_experiment', 'experiment_id'),
        Index('idx_ab_experiment_targeting_segment', 'segment_id'),
        Index('idx_ab_experiment_targeting_priority', 'priority'),
    )

    # Relationships
    experiment = relationship("Experiment", back_populates="targetings")
    segment = relationship("UserSegment", back_populates="targetings")

    @validates('traffic_percentage')
    def validate_traffic_percentage(self, key, value):
        """Validate traffic percentage"""
        if not (0 <= value <= 100):
            raise ValueError("Traffic percentage must be between 0 and 100")
        return value

    @validates('priority')
    def validate_priority(self, key, value):
        """Validate priority"""
        if value <= 0:
            raise ValueError("Priority must be positive")
        return value

# ====================================================================
# Helper Classes and Functions
# ====================================================================

class AssignmentEngine:
    """Engine for assigning users to experiment variants"""

    @staticmethod
    def assign_user_to_variant(
        user_id: str,
        experiment: Experiment,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Variant]:
        """Assign user to a variant for an experiment"""

        # Check if experiment is active and user should be included
        if not experiment.is_active:
            return None

        if user_context and not experiment.should_include_user(user_context):
            return None

        # Check for existing assignment
        existing_assignment = UserAssignment.query.filter_by(
            user_id=user_id,
            experiment_id=experiment.id,
            is_active=True
        ).first()

        if existing_assignment:
            return existing_assignment.variant

        # Perform new assignment
        variants = [v for v in experiment.variants if v.is_active]
        if not variants:
            return None

        # Use consistent hashing for assignment
        hash_value = int(UserAssignment.generate_assignment_hash(user_id, experiment.id), 16)
        total_weight = sum(v.traffic_weight for v in variants)

        cumulative_weight = 0
        for variant in variants:
            cumulative_weight += variant.traffic_weight
            if hash_value % total_weight < cumulative_weight:
                # Create assignment
                assignment = UserAssignment(
                    user_id=user_id,
                    experiment_id=experiment.id,
                    variant_id=variant.id,
                    assignment_hash=UserAssignment.generate_assignment_hash(user_id, experiment.id),
                    assignment_context=user_context or {}
                )
                return variant

        return variants[0]  # Fallback

class MetricsCollector:
    """Helper class for collecting and processing metrics"""

    @staticmethod
    def create_query_event(
        event_id: str,
        query_text: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        experiment_id: Optional[uuid.UUID] = None,
        variant_id: Optional[uuid.UUID] = None,
        query_type: QueryType = QueryType.SEARCH,
        **kwargs
    ) -> QueryEvent:
        """Create a new query event"""
        return QueryEvent(
            event_id=event_id,
            user_id=user_id,
            session_id=session_id,
            experiment_id=experiment_id,
            variant_id=variant_id,
            query_text=query_text,
            query_hash=QueryEvent.generate_query_hash(query_text),
            query_type=query_type,
            **kwargs
        )

    @staticmethod
    def create_quality_metrics(
        query_event_id: uuid.UUID,
        answer_relevancy: Optional[float] = None,
        faithfulness: Optional[float] = None,
        contextual_relevancy: Optional[float] = None,
        **kwargs
    ) -> ABQualityMetric:
        """Create quality metrics for a query event"""
        metrics = ABQualityMetric(query_event_id=query_event_id, **kwargs)

        if answer_relevancy is not None or faithfulness is not None or contextual_relevancy is not None:
            metrics.set_rag_triad_metrics(
                answer_relevancy or 0.0,
                faithfulness or 0.0,
                contextual_relevancy or 0.0
            )

        return metrics

# ====================================================================
# Query Functions for Common Operations
# ====================================================================

def get_active_experiments_for_user(user_id: str, user_context: Optional[Dict[str, Any]] = None) -> List[Experiment]:
    """Get all active experiments for a user"""
    return Experiment.query.filter(
        Experiment.status == ExperimentStatus.RUNNING,
        Experiment.is_deleted == False
    ).all()  # Additional filtering would be done in application layer

def get_user_assignments(user_id: str, active_only: bool = True) -> List[UserAssignment]:
    """Get user's experiment assignments"""
    query = UserAssignment.query.filter(UserAssignment.user_id == user_id)
    if active_only:
        query = query.filter(UserAssignment.is_active == True)
    return query.all()

def get_experiment_metrics(experiment_id: uuid.UUID, metric_name: str, days: int = 7) -> List[ABQualityMetric]:
    """Get metrics for an experiment over time period"""
    start_date = datetime.utcnow() - timedelta(days=days)

    return ABQualityMetric.query.join(QueryEvent).filter(
        QueryEvent.experiment_id == experiment_id,
        ABQualityMetric.created_at >= start_date
    ).all()

def calculate_experiment_summary(experiment_id: uuid.UUID) -> Dict[str, Any]:
    """Calculate summary statistics for an experiment"""
    # This would aggregate data from multiple tables
    # Implementation would depend on specific requirements
    pass