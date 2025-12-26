"""
Comprehensive Evaluation Metrics model for RAG system performance tracking
"""

import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Enum, ForeignKey, Text, JSON, Index, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY
from enum import Enum as PyEnum
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, List, Dict, Any, Union

from .base import BaseModel, GUID

class MetricType(PyEnum):
    """Types of evaluation metrics"""
    RAG_TRIAD = "rag_triad"           # Faithfulness, Answer Relevancy, Context Relevancy
    RETRIEVAL_QUALITY = "retrieval_quality"
    GENERATION_QUALITY = "generation_quality"
    PERFORMANCE = "performance"
    USER_SATISFACTION = "user_satisfaction"
    SYSTEM_HEALTH = "system_health"
    MULTIMODAL_QUALITY = "multimodal_quality"

class EvaluationStatus(PyEnum):
    """Status of evaluation runs"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MetricLevel(PyEnum):
    """Levels of metrics aggregation"""
    QUERY = "query"                   # Individual query metrics
    SESSION = "session"               # Session-level metrics
    USER = "user"                     # User-level metrics
    ORGANIZATION = "organization"     # Organization-level metrics
    SYSTEM = "system"                 # System-wide metrics
    TIME_WINDOW = "time_window"       # Time-based aggregated metrics

class EvaluationRun(BaseModel):
    """Evaluation run for comprehensive system assessment"""

    __tablename__ = "evaluation_runs"

    # Run identification
    run_name = Column(String(255), nullable=False, index=True)
    run_description = Column(Text, nullable=True)
    run_type = Column(String(50), nullable=False, index=True)  # scheduled, manual, triggered, continuous
    evaluation_framework = Column(String(50), nullable=False, default="deepeval")  # deepeval, custom, etc.

    # Run scope
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=True, index=True)
    user_ids = Column(ARRAY(GUID()), nullable=True)  # Specific users to evaluate
    document_ids = Column(ARRAY(GUID()), nullable=True)  # Specific documents to evaluate
    query_batch_id = Column(String(255), nullable=True)  # Batch of queries for evaluation

    # Time window
    evaluation_period_start = Column(DateTime(timezone=True), nullable=True)
    evaluation_period_end = Column(DateTime(timezone=True), nullable=True)
    sample_size = Column(Integer, nullable=True)  # Number of items to evaluate
    sampling_method = Column(String(50), nullable=True)  # random, stratified, recent

    # Configuration
    evaluation_config = Column(JSON, nullable=True)  # Evaluation parameters and settings
    metrics_to_evaluate = Column(JSON, nullable=True)  # List of metrics to compute
    baseline_run_id = Column(GUID(), ForeignKey("evaluation_runs.id"), nullable=True)  # Comparison baseline

    # Execution status
    status = Column(Enum(EvaluationStatus), nullable=False, default=EvaluationStatus.PENDING, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Progress tracking
    total_items = Column(Integer, nullable=False, default=0)
    processed_items = Column(Integer, nullable=False, default=0)
    failed_items = Column(Integer, nullable=False, default=0)
    current_stage = Column(String(100), nullable=True)
    progress_percentage = Column(Float, default=0.0, nullable=False)

    # Resource usage
    cpu_time_seconds = Column(Float, nullable=True)
    memory_peak_mb = Column(Float, nullable=True)
    tokens_consumed = Column(Integer, nullable=True)
    api_calls_made = Column(Integer, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # Results summary
    overall_score = Column(Float, nullable=True, index=True)
    metrics_summary = Column(JSON, nullable=True)  # Summary of all computed metrics
    statistical_significance = Column(JSON, nullable=True)  # Statistical analysis of results
    improvement_over_baseline = Column(JSON, nullable=True)  # Comparison with baseline

    # Relationships
    organization = relationship("Organization")
    baseline_run = relationship("EvaluationRun", remote_side=[id])
    individual_metrics = relationship("MetricMeasurement", back_populates="evaluation_run", cascade="all, delete-orphan")
    metric_aggregations = relationship("MetricAggregation", back_populates="evaluation_run", cascade="all, delete-orphan")
    evaluation_artifacts = relationship("EvaluationArtifact", back_populates="evaluation_run", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_evaluation_runs_org_status', 'organization_id', 'status'),
        Index('idx_evaluation_runs_period', 'evaluation_period_start', 'evaluation_period_end'),
        Index('idx_evaluation_runs_score', 'overall_score'),
        Index('idx_evaluation_runs_created', 'created_at'),
    )

    def __repr__(self):
        return f"<EvaluationRun(name={self.run_name}, status={self.status.value}, score={self.overall_score})>"

    @property
    def is_completed(self) -> bool:
        """Check if evaluation is completed"""
        return self.status == EvaluationStatus.COMPLETED

    @property
    def is_running(self) -> bool:
        """Check if evaluation is currently running"""
        return self.status == EvaluationStatus.RUNNING

    @property
    def success_rate(self) -> float:
        """Get success rate of processed items"""
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100

    def start_evaluation(self):
        """Start evaluation run"""
        self.status = EvaluationStatus.RUNNING
        self.started_at = datetime.utcnow()

    def update_progress(self, processed_items: int, current_stage: str = None):
        """Update evaluation progress"""
        self.processed_items = processed_items
        if current_stage:
            self.current_stage = current_stage
        if self.total_items > 0:
            self.progress_percentage = (processed_items / self.total_items) * 100

    def complete_evaluation(self, overall_score: float, metrics_summary: Dict[str, Any]):
        """Mark evaluation as completed"""
        self.status = EvaluationStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.overall_score = overall_score
        self.metrics_summary = metrics_summary
        self.progress_percentage = 100.0

        # Calculate duration
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def fail_evaluation(self, error_message: str, error_details: Dict[str, Any] = None):
        """Mark evaluation as failed"""
        self.status = EvaluationStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        if error_details:
            self.error_details = error_details

        # Calculate duration
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict()

        # Convert enum values
        data['status'] = self.status.value if self.status else None

        # Add computed properties
        data.update({
            'is_completed': self.is_completed,
            'is_running': self.is_running,
            'success_rate': self.success_rate
        })

        return data


class MetricMeasurement(BaseModel):
    """Individual metric measurements for queries, documents, or other entities"""

    __tablename__ = "metric_measurements"

    # Measurement identification
    evaluation_run_id = Column(GUID(), ForeignKey("evaluation_runs.id"), nullable=False, index=True)
    metric_type = Column(Enum(MetricType), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_level = Column(Enum(MetricLevel), nullable=False, index=True)

    # Entity being measured
    entity_type = Column(String(50), nullable=False, index=True)  # query, document, user, session
    entity_id = Column(String(255), nullable=False, index=True)
    entity_metadata = Column(JSON, nullable=True)  # Additional entity context

    # Measurement values
    metric_value = Column(Numeric(10, 4), nullable=False)  # Precise metric value
    metric_score = Column(Float, nullable=False, index=True)  # Normalized score (0-1)
    confidence_interval = Column(JSON, nullable=True)  # Statistical confidence interval
    sample_size = Column(Integer, nullable=True)  # Sample size for this measurement

    # Quality classification
    quality_threshold = Column(Float, nullable=True)  # Threshold for "good" quality
    meets_threshold = Column(Boolean, nullable=True, index=True)
    quality_grade = Column(String(10), nullable=True)  # A, B, C, D, F

    # Measurement metadata
    measurement_method = Column(String(100), nullable=True)  # How metric was computed
    model_used = Column(String(100), nullable=True)  # Model used for evaluation
    evaluation_timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    computation_time_ms = Column(Float, nullable=True)

    # Detailed breakdown
    metric_components = Column(JSON, nullable=True)  # Components that make up the metric
    supporting_evidence = Column(JSON, nullable=True)  # Evidence supporting the measurement
    error_analysis = Column(JSON, nullable=True)  # Analysis of errors or issues

    # Comparison data
    baseline_value = Column(Numeric(10, 4), nullable=True)
    improvement_percentage = Column(Float, nullable=True)
    percentile_rank = Column(Float, nullable=True)  # Rank within population

    # Relationships
    evaluation_run = relationship("EvaluationRun", back_populates="individual_metrics")

    # Indexes
    __table_args__ = (
        Index('idx_measurements_run_type', 'evaluation_run_id', 'metric_type'),
        Index('idx_measurements_entity', 'entity_type', 'entity_id'),
        Index('idx_measurements_score', 'metric_score'),
        Index('idx_measurements_threshold', 'meets_threshold'),
        Index('idx_measurements_timestamp', 'evaluation_timestamp'),
    )

    def __repr__(self):
        return f"<MetricMeasurement(name={self.metric_name}, value={self.metric_value}, score={self.metric_score})>"

    @property
    def is_high_quality(self) -> bool:
        """Check if measurement meets quality threshold"""
        return self.meets_threshold or (self.quality_threshold and self.metric_score >= self.quality_threshold)

    @property
    def quality_description(self) -> str:
        """Get quality description based on grade"""
        grade_descriptions = {
            'A': 'Excellent',
            'B': 'Good',
            'C': 'Fair',
            'D': 'Poor',
            'F': 'Very Poor'
        }
        return grade_descriptions.get(self.quality_grade, 'Unknown')

    def calculate_quality_grade(self, score_thresholds: Dict[str, float] = None):
        """Calculate quality grade based on score"""
        if not score_thresholds:
            score_thresholds = {
                'A': 0.9,
                'B': 0.8,
                'C': 0.7,
                'D': 0.6
            }

        if self.metric_score >= score_thresholds.get('A', 0.9):
            self.quality_grade = 'A'
        elif self.metric_score >= score_thresholds.get('B', 0.8):
            self.quality_grade = 'B'
        elif self.metric_score >= score_thresholds.get('C', 0.7):
            self.quality_grade = 'C'
        elif self.metric_score >= score_thresholds.get('D', 0.6):
            self.quality_grade = 'D'
        else:
            self.quality_grade = 'F'

        # Check if meets threshold
        if self.quality_threshold:
            self.meets_threshold = self.metric_score >= self.quality_threshold

    def calculate_improvement(self, baseline_value: Union[float, None]):
        """Calculate improvement over baseline"""
        if baseline_value is not None and baseline_value != 0:
            self.baseline_value = baseline_value
            improvement = (float(self.metric_value) - baseline_value) / abs(baseline_value) * 100
            self.improvement_percentage = improvement

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict()

        # Convert enum values
        data.update({
            'metric_type': self.metric_type.value if self.metric_type else None,
            'metric_level': self.metric_level.value if self.metric_level else None
        })

        # Add computed properties
        data.update({
            'is_high_quality': self.is_high_quality,
            'quality_description': self.quality_description
        })

        # Convert numeric to float for JSON serialization
        if 'metric_value' in data and data['metric_value'] is not None:
            data['metric_value'] = float(data['metric_value'])
        if 'baseline_value' in data and data['baseline_value'] is not None:
            data['baseline_value'] = float(data['baseline_value'])

        return data


class MetricAggregation(BaseModel):
    """Aggregated metrics at different levels (user, org, system, time windows)"""

    __tablename__ = "metric_aggregations"

    # Aggregation identification
    evaluation_run_id = Column(GUID(), ForeignKey("evaluation_runs.id"), nullable=True, index=True)
    metric_type = Column(Enum(MetricType), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    aggregation_level = Column(Enum(MetricLevel), nullable=False, index=True)

    # Aggregation scope
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=True, index=True)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    entity_id = Column(String(255), nullable=True, index=True)  # Session ID, document ID, etc.

    # Time window
    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_end = Column(DateTime(timezone=True), nullable=False, index=True)
    window_duration_hours = Column(Integer, nullable=False)

    # Aggregated values
    avg_score = Column(Float, nullable=False, index=True)
    min_score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    median_score = Column(Float, nullable=False)
    std_deviation = Column(Float, nullable=False)
    percentile_25 = Column(Float, nullable=False)
    percentile_75 = Column(Float, nullable=False)
    percentile_90 = Column(Float, nullable=False)
    percentile_95 = Column(Float, nullable=False)

    # Sample information
    sample_count = Column(Integer, nullable=False)
    population_size = Column(Integer, nullable=True)  # Total population if sampled
    sampling_rate = Column(Float, nullable=True)  # Proportion of population sampled
    confidence_level = Column(Float, nullable=True)  # Statistical confidence level
    margin_of_error = Column(Float, nullable=True)  # Statistical margin of error

    # Distribution analysis
    distribution_type = Column(String(50), nullable=True)  # normal, skewed, bimodal, etc.
    skewness = Column(Float, nullable=True)
    kurtosis = Column(Float, nullable=True)
    outliers_count = Column(Integer, nullable=False, default=0)
    outliers_percentage = Column(Float, nullable=False, default=0.0)

    # Trend analysis
    trend_direction = Column(String(20), nullable=True)  # improving, declining, stable, volatile
    trend_strength = Column(Float, nullable=True)  # Strength of trend (0-1)
    seasonality_detected = Column(Boolean, default=False, nullable=False)
    change_points = Column(JSON, nullable=True)  # Detected change points in time series

    # Quality classification
    quality_threshold_met = Column(Boolean, nullable=True, index=True)
    quality_trend = Column(String(20), nullable=True)  # improving, declining, stable

    # Relationships
    evaluation_run = relationship("EvaluationRun", back_populates="metric_aggregations")
    organization = relationship("Organization")
    user = relationship("User")

    # Indexes
    __table_args__ = (
        Index('idx_aggregations_level_window', 'aggregation_level', 'window_start', 'window_end'),
        Index('idx_aggregations_org_metric', 'organization_id', 'metric_name'),
        Index('idx_aggregations_user_metric', 'user_id', 'metric_name'),
        Index('idx_aggregations_score', 'avg_score'),
    )

    def __repr__(self):
        return f"<MetricAggregation(name={self.metric_name}, level={self.aggregation_level.value}, avg={self.avg_score})>"

    @property
    def performance_rating(self) -> str:
        """Get performance rating based on average score"""
        if self.avg_score >= 0.9:
            return "Excellent"
        elif self.avg_score >= 0.8:
            return "Good"
        elif self.avg_score >= 0.7:
            return "Fair"
        elif self.avg_score >= 0.6:
            return "Poor"
        else:
            return "Very Poor"

    @property
    def data_quality(self) -> str:
        """Get data quality assessment based on sample size"""
        if self.sample_count >= 1000:
            return "High"
        elif self.sample_count >= 100:
            return "Medium"
        elif self.sample_count >= 30:
            return "Low"
        else:
            return "Insufficient"

    def calculate_trend(self, historical_data: List[float]) -> Dict[str, Any]:
        """Calculate trend from historical data points"""
        if len(historical_data) < 2:
            return {"direction": "stable", "strength": 0.0}

        # Simple linear trend calculation
        n = len(historical_data)
        x_values = list(range(n))

        # Calculate slope
        x_mean = sum(x_values) / n
        y_mean = sum(historical_data) / n

        numerator = sum((x_values[i] - x_mean) * (historical_data[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator

        # Determine trend direction and strength
        if abs(slope) < 0.01:
            trend_direction = "stable"
            trend_strength = 0.0
        elif slope > 0:
            trend_direction = "improving"
            trend_strength = min(1.0, abs(slope) * 10)  # Normalize to 0-1
        else:
            trend_direction = "declining"
            trend_strength = min(1.0, abs(slope) * 10)

        self.trend_direction = trend_direction
        self.trend_strength = trend_strength

        return {
            "direction": trend_direction,
            "strength": trend_strength,
            "slope": slope
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict()

        # Convert enum values
        data.update({
            'metric_type': self.metric_type.value if self.metric_type else None,
            'metric_level': self.metric_level.value if self.metric_level else None
        })

        # Add computed properties
        data.update({
            'performance_rating': self.performance_rating,
            'data_quality': self.data_quality
        })

        return data


class EvaluationArtifact(BaseModel):
    """Artifacts generated during evaluation (logs, reports, visualizations)"""

    __tablename__ = "evaluation_artifacts"

    evaluation_run_id = Column(GUID(), ForeignKey("evaluation_runs.id"), nullable=False)

    # Artifact information
    artifact_type = Column(String(50), nullable=False)  # report, chart, log, data_export, visualization
    artifact_name = Column(String(255), nullable=False)
    artifact_description = Column(Text, nullable=True)

    # Storage information
    file_path = Column(String(1000), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    storage_type = Column(String(50), nullable=True)  # local, s3, gcs, azure

    # Content information
    content_data = Column(JSON, nullable=True)  # For small artifacts stored directly
    content_preview = Column(Text, nullable=True)  # Preview of content
    data_schema = Column(JSON, nullable=True)  # Schema of data if applicable

    # Generation information
    generated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    generator_model = Column(String(100), nullable=True)
    generation_parameters = Column(JSON, nullable=True)

    # Usage tracking
    download_count = Column(Integer, default=0, nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    is_public = Column(Boolean, default=False, nullable=False)

    # Relationships
    evaluation_run = relationship("EvaluationRun", back_populates="evaluation_artifacts")

    def record_download(self):
        """Record artifact download"""
        self.download_count += 1
        self.last_accessed_at = datetime.utcnow()


class PerformanceThreshold(BaseModel):
    """Performance thresholds and alerting configurations"""

    __tablename__ = "performance_thresholds"

    # Threshold identification
    metric_name = Column(String(100), nullable=False, index=True)
    threshold_type = Column(String(50), nullable=False)  # minimum, maximum, target, warning, critical
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=True)  # Organization-specific thresholds

    # Threshold values
    threshold_value = Column(Float, nullable=False)
    threshold_operator = Column(String(10), nullable=False)  # <, <=, >, >=, ==, !=
    grace_period_minutes = Column(Integer, default=5, nullable=False)

    # Alerting configuration
    alert_enabled = Column(Boolean, default=True, nullable=False)
    alert_channels = Column(JSON, nullable=True)  # email, webhook, slack, etc.
    alert_severity = Column(String(20), nullable=False, default="warning")
    alert_cooldown_minutes = Column(Integer, default=60, nullable=False)

    # Auto-remediation
    auto_remediation_enabled = Column(Boolean, default=False, nullable=False)
    remediation_actions = Column(JSON, nullable=True)  # Actions to take when threshold breached

    # Relationships
    organization = relationship("Organization")

    def check_threshold(self, current_value: float) -> bool:
        """Check if current value breaches threshold"""
        operators = {
            '<': lambda a, b: a < b,
            '<=': lambda a, b: a <= b,
            '>': lambda a, b: a > b,
            '>=': lambda a, b: a >= b,
            '==': lambda a, b: a == b,
            '!=': lambda a, b: a != b
        }

        operator_func = operators.get(self.threshold_operator)
        if operator_func:
            return operator_func(current_value, self.threshold_value)
        return False

    @classmethod
    def get_active_thresholds(cls, organization_id: Optional[uuid.UUID] = None) -> List:
        """Get active performance thresholds"""
        query = cls.query.filter(
            cls.alert_enabled == True,
            cls.is_deleted == False
        )

        if organization_id:
            query = query.filter(
                (cls.organization_id == organization_id) |
                (cls.organization_id.is_(None))  # Include global thresholds
            )
        else:
            query = query.filter(cls.organization_id.is_(None))  # Only global thresholds

        return query.all()