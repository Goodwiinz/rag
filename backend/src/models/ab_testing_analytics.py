"""
A/B Testing Analytics and Statistical Analysis Models

This module provides advanced analytics models for statistical significance testing,
real-time metrics aggregation, and comprehensive reporting capabilities.
"""

import json
import math
import statistics
import uuid
from datetime import datetime, timedelta
from enum import Enum as PyEnum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    asc,
    case,
    desc,
    extract,
    func,
    or_,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, validates

from .ab_testing import (
    Experiment,
    ExperimentStatus,
    ExperimentType,
    MetricType,
    StatisticalTest,
    SuccessCriterion,
    Variant,
)
from .base import GUID, BaseModel
from .utils import StringArray


class AggregationType(PyEnum):
    """Types of metric aggregation"""

    SUM = "sum"
    AVERAGE = "average"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"
    PERCENTILE_50 = "percentile_50"
    PERCENTILE_75 = "percentile_75"
    PERCENTILE_90 = "percentile_90"
    PERCENTILE_95 = "percentile_95"
    PERCENTILE_99 = "percentile_99"
    COUNT = "count"
    DISTINCT_COUNT = "distinct_count"
    RATE = "rate"
    RATIO = "ratio"


class TimeBucket(PyEnum):
    """Time bucket sizes for aggregation"""

    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class StatisticalSignificance(BaseModel):
    """
    Statistical significance analysis results for experiments
    """

    __tablename__ = "ab_statistical_significance"

    # Analysis information
    experiment_id = Column(
        GUID(), ForeignKey("ab_experiments.id"), nullable=False, index=True
    )
    analysis_timestamp = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
    sample_size = Column(Integer, nullable=False, index=True)

    # Test configuration
    statistical_test = Column(Enum(StatisticalTest), nullable=False)
    confidence_level = Column(Float, nullable=False)
    test_type = Column(String(50), nullable=False)  # one_sided, two_sided

    # Results for primary comparison (usually vs control)
    control_variant_id = Column(
        GUID(), ForeignKey("ab_variants.id"), nullable=True, index=True
    )
    treatment_variant_id = Column(
        GUID(), ForeignKey("ab_variants.id"), nullable=True, index=True
    )

    # Statistical results
    test_statistic = Column(Float, nullable=False)  # t-statistic, z-score, etc.
    p_value = Column(Float, nullable=False, index=True)
    critical_value = Column(Float, nullable=False)
    is_statistically_significant = Column(Boolean, nullable=False, index=True)

    # Effect size metrics
    effect_size = Column(
        Float, nullable=False, index=True
    )  # Cohen's d, odds ratio, etc.
    effect_size_type = Column(
        String(50), nullable=False
    )  # cohens_d, odds_ratio, risk_ratio
    confidence_interval_lower = Column(Float, nullable=False)
    confidence_interval_upper = Column(Float, nullable=False)

    # Practical significance
    practical_significance_threshold = Column(Float, nullable=True)
    is_practically_significant = Column(Boolean, nullable=False)
    business_impact_score = Column(Float, nullable=True)  # 0-100 business impact score

    # Power analysis
    statistical_power = Column(Float, nullable=False)
    minimum_detectable_effect = Column(Float, nullable=False)
    achieved_sample_size = Column(Integer, nullable=False)
    required_sample_size = Column(Integer, nullable=False)

    # Additional metrics
    variance = Column(Float, nullable=True)
    standard_error = Column(Float, nullable=False)
    degrees_of_freedom = Column(Float, nullable=True)

    # Raw data snapshots
    control_mean = Column(Float, nullable=True)
    treatment_mean = Column(Float, nullable=True)
    control_std = Column(Float, nullable=True)
    treatment_std = Column(Float, nullable=True)
    control_n = Column(Integer, nullable=False)
    treatment_n = Column(Integer, nullable=False)

    # Analysis metadata
    analysis_version = Column(String(50), nullable=False, default="1.0")
    assumptions = Column(JSONB, nullable=True)  # Statistical assumptions made
    limitations = Column(JSONB, nullable=True)  # Analysis limitations

    # Relationships
    experiment = relationship("Experiment")
    control_variant = relationship("Variant", foreign_keys=[control_variant_id])
    treatment_variant = relationship("Variant", foreign_keys=[treatment_variant_id])

    # Detailed significance results
    variant_comparisons = relationship(
        "VariantComparison",
        back_populates="significance_analysis",
        cascade="all, delete-orphan",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "confidence_level > 0 AND confidence_level < 1",
            name="valid_confidence_level",
        ),
        CheckConstraint("p_value >= 0 AND p_value <= 1", name="valid_p_value"),
        CheckConstraint(
            "statistical_power >= 0 AND statistical_power <= 1",
            name="valid_statistical_power",
        ),
        CheckConstraint("control_n > 0 AND treatment_n > 0", name="valid_sample_sizes"),
        Index(
            "idx_significance_experiment_timestamp",
            "experiment_id",
            "analysis_timestamp",
        ),
        Index("idx_significance_p_value", "p_value"),
        Index("idx_significance_effect_size", "effect_size"),
    )

    def __repr__(self):
        return f"<StatisticalSignificance(experiment={self.experiment_id}, p_value={self.p_value:.4f}, significant={self.is_statistically_significant})>"

    def calculate_cohens_d(
        self,
        control_mean: float,
        treatment_mean: float,
        control_std: float,
        treatment_std: float,
    ) -> float:
        """Calculate Cohen's d effect size"""
        pooled_std = math.sqrt(
            (
                (control_n - 1) * control_std**2
                + (treatment_n - 1) * treatment_std**2
            )
            / (control_n + treatment_n - 2)
        )
        if pooled_std == 0:
            return 0.0
        return (treatment_mean - control_mean) / pooled_std

    def calculate_odds_ratio(
        self,
        control_successes: int,
        control_failures: int,
        treatment_successes: int,
        treatment_failures: int,
    ) -> float:
        """Calculate odds ratio"""
        if control_failures == 0 or treatment_failures == 0:
            return float("inf")

        control_odds = control_successes / control_failures
        treatment_odds = treatment_successes / treatment_failures

        return treatment_odds / control_odds

    def interpret_effect_size(self, effect_size: float, effect_type: str) -> str:
        """Interpret effect size magnitude"""
        if effect_type == "cohens_d":
            abs_d = abs(effect_size)
            if abs_d < 0.2:
                return "negligible"
            elif abs_d < 0.5:
                return "small"
            elif abs_d < 0.8:
                return "medium"
            else:
                return "large"

        elif effect_type == "odds_ratio":
            if 0.9 <= effect_size <= 1.1:
                return "negligible"
            elif 0.7 <= effect_size < 0.9 or 1.1 < effect_size <= 1.5:
                return "small"
            elif 0.5 <= effect_size < 0.7 or 1.5 < effect_size <= 2.0:
                return "medium"
            else:
                return "large"

        return "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        data = super().to_dict()

        # Convert enums
        if hasattr(self, "statistical_test") and self.statistical_test:
            data["statistical_test"] = self.statistical_test.value

        # Add interpretations
        data["effect_size_interpretation"] = self.interpret_effect_size(
            self.effect_size, self.effect_size_type
        )

        # Add confidence interval
        data["confidence_interval"] = {
            "lower": self.confidence_interval_lower,
            "upper": self.confidence_interval_upper,
            "width": self.confidence_interval_upper - self.confidence_interval_lower,
        }

        # Add variant comparisons
        data["variant_comparisons"] = [
            comp.to_dict() for comp in self.variant_comparisons
        ]

        return data


class VariantComparison(BaseModel):
    """
    Detailed variant-to-variant statistical comparisons
    """

    __tablename__ = "ab_variant_comparisons"

    # Comparison information
    significance_analysis_id = Column(
        GUID(), ForeignKey("ab_statistical_significance.id"), nullable=False, index=True
    )
    variant_a_id = Column(
        GUID(), ForeignKey("ab_variants.id"), nullable=False, index=True
    )
    variant_b_id = Column(
        GUID(), ForeignKey("ab_variants.id"), nullable=False, index=True
    )
    metric_type = Column(Enum(MetricType), nullable=False, index=True)

    # Comparison results
    variant_a_mean = Column(Float, nullable=False)
    variant_b_mean = Column(Float, nullable=False)
    variant_a_std = Column(Float, nullable=False)
    variant_b_std = Column(Float, nullable=False)
    variant_a_n = Column(Integer, nullable=False)
    variant_b_n = Column(Integer, nullable=False)

    # Statistical test results
    test_statistic = Column(Float, nullable=False)
    p_value = Column(Float, nullable=False)
    is_significant = Column(Boolean, nullable=False, index=True)

    # Effect size
    absolute_difference = Column(Float, nullable=False)
    relative_difference = Column(Float, nullable=False)  # Percentage change
    effect_size = Column(Float, nullable=False)
    effect_size_interpretation = Column(String(50), nullable=False)

    # Confidence interval
    ci_lower = Column(Float, nullable=False)
    ci_upper = Column(Float, nullable=False)

    # Practical significance
    is_practically_significant = Column(Boolean, nullable=False)
    business_impact = Column(Text, nullable=True)

    # Relationships
    significance_analysis = relationship(
        "StatisticalSignificance", back_populates="variant_comparisons"
    )
    variant_a = relationship("Variant", foreign_keys=[variant_a_id])
    variant_b = relationship("Variant", foreign_keys=[variant_b_id])

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "variant_a_n > 0 AND variant_b_n > 0", name="valid_comparison_sample_sizes"
        ),
        CheckConstraint(
            "p_value >= 0 AND p_value <= 1", name="valid_comparison_p_value"
        ),
        UniqueConstraint(
            "significance_analysis_id",
            "variant_a_id",
            "variant_b_id",
            "metric_type",
            name="unique_variant_comparison",
        ),
        Index(
            "idx_variant_comparison_analysis_variants",
            "significance_analysis_id",
            "variant_a_id",
            "variant_b_id",
        ),
    )

    def __repr__(self):
        return f"<VariantComparison(variant_a={self.variant_a_id}, variant_b={self.variant_b_id}, p_value={self.p_value:.4f})>"


class AggregatedMetric(BaseModel):
    """
    Pre-aggregated metrics for real-time dashboard performance
    """

    __tablename__ = "ab_aggregated_metrics"

    # Aggregation dimensions
    experiment_id = Column(
        GUID(), ForeignKey("ab_experiments.id"), nullable=False, index=True
    )
    variant_id = Column(
        GUID(), ForeignKey("ab_variants.id"), nullable=False, index=True
    )
    metric_type = Column(Enum(MetricType), nullable=False, index=True)
    aggregation_type = Column(Enum(AggregationType), nullable=False, index=True)

    # Time dimensions
    time_bucket = Column(Enum(TimeBucket), nullable=False, index=True)
    time_bucket_start = Column(DateTime(timezone=True), nullable=False, index=True)
    time_bucket_end = Column(DateTime(timezone=True), nullable=False)

    # Aggregated values
    metric_value = Column(Float, nullable=False, index=True)
    sample_size = Column(Integer, nullable=False, index=True)
    standard_error = Column(Float, nullable=True)

    # Statistical measures
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    median_value = Column(Float, nullable=True)
    percentile_25 = Column(Float, nullable=True)
    percentile_75 = Column(Float, nullable=True)
    percentile_90 = Column(Float, nullable=True)
    percentile_95 = Column(Float, nullable=True)
    percentile_99 = Column(Float, nullable=True)

    # Additional metrics
    variance = Column(Float, nullable=True)
    coefficient_of_variation = Column(Float, nullable=True)

    # Metadata
    computed_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
    computation_version = Column(String(50), nullable=False, default="1.0")

    # Relationships
    experiment = relationship("Experiment")
    variant = relationship("Variant")

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "experiment_id",
            "variant_id",
            "metric_type",
            "aggregation_type",
            "time_bucket",
            "time_bucket_start",
            name="unique_aggregated_metric",
        ),
        CheckConstraint("sample_size >= 0", name="valid_aggregated_sample_size"),
        Index(
            "idx_aggregated_metrics_experiment_time",
            "experiment_id",
            "time_bucket_start",
        ),
        Index("idx_aggregated_metrics_variant_time", "variant_id", "time_bucket_start"),
        Index("idx_aggregated_metrics_metric_time", "metric_type", "time_bucket_start"),
        Index("idx_aggregated_metrics_computed", "computed_at"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Calculate coefficient of variation if variance and mean are available
        if self.variance is not None and self.metric_value != 0:
            self.coefficient_of_variation = math.sqrt(self.variance) / abs(
                self.metric_value
            )

    def __repr__(self):
        return f"<AggregatedMetric(experiment={self.experiment_id}, variant={self.variant_id}, metric={self.metric_type.value}, time={self.time_bucket_start})>"

    def calculate_growth_rate(self, previous_value: Optional[float]) -> Optional[float]:
        """Calculate growth rate compared to previous period"""
        if previous_value is None or previous_value == 0:
            return None
        return ((self.metric_value - previous_value) / previous_value) * 100

    def get_z_score(self, baseline_mean: float, baseline_std: float) -> Optional[float]:
        """Calculate Z-score against baseline"""
        if baseline_std == 0:
            return None
        return (self.metric_value - baseline_mean) / baseline_std

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        data = super().to_dict()

        # Convert enums
        for field in ["metric_type", "aggregation_type", "time_bucket"]:
            if hasattr(self, field) and getattr(self, field):
                data[field] = getattr(self, field).value

        # Add computed statistics
        data["confidence_interval_95"] = (
            {
                "lower": self.metric_value - 1.96 * (self.standard_error or 0),
                "upper": self.metric_value + 1.96 * (self.standard_error or 0),
            }
            if self.standard_error
            else None
        )

        return data


class FunnelAnalysis(BaseModel):
    """
    Conversion funnel analysis for experiments
    """

    __tablename__ = "ab_funnel_analysis"

    # Funnel information
    experiment_id = Column(
        GUID(), ForeignKey("ab_experiments.id"), nullable=False, index=True
    )
    variant_id = Column(
        GUID(), ForeignKey("ab_variants.id"), nullable=False, index=True
    )
    funnel_name = Column(String(255), nullable=False, index=True)

    # Funnel stage
    stage_name = Column(String(255), nullable=False, index=True)
    stage_order = Column(Integer, nullable=False)
    stage_description = Column(Text, nullable=True)

    # Metrics for this stage
    users_entered = Column(Integer, nullable=False, index=True)
    users_completed = Column(Integer, nullable=False)
    conversion_rate = Column(Float, nullable=False, index=True)
    average_time_to_complete = Column(Float, nullable=True)  # In seconds

    # Comparison with control/baseline
    baseline_conversion_rate = Column(Float, nullable=True)
    conversion_rate_lift = Column(Float, nullable=True)
    statistical_significance = Column(Float, nullable=True)
    is_significant = Column(Boolean, nullable=False, index=True)

    # Time dimensions
    analysis_period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    analysis_period_end = Column(DateTime(timezone=True), nullable=False)

    # Metadata
    computed_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    experiment = relationship("Experiment")
    variant = relationship("Variant")

    # Constraints
    __table_args__ = (
        CheckConstraint("users_entered >= 0", name="valid_funnel_entered"),
        CheckConstraint("users_completed >= 0", name="valid_funnel_completed"),
        CheckConstraint(
            "conversion_rate >= 0 AND conversion_rate <= 1",
            name="valid_conversion_rate",
        ),
        UniqueConstraint(
            "experiment_id",
            "variant_id",
            "funnel_name",
            "stage_name",
            "analysis_period_start",
            name="unique_funnel_stage",
        ),
        Index("idx_funnel_experiment_variant", "experiment_id", "variant_id"),
        Index("idx_funnel_conversion_rate", "conversion_rate"),
        Index(
            "idx_funnel_analysis_period", "analysis_period_start", "analysis_period_end"
        ),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Calculate conversion rate if not provided
        if self.users_entered > 0 and self.users_completed is not None:
            self.conversion_rate = self.users_completed / self.users_entered

    def calculate_drop_off_rate(self) -> float:
        """Calculate drop-off rate for this stage"""
        return 1.0 - self.conversion_rate

    def calculate_stage_efficiency(self, previous_stage_rate: float) -> float:
        """Calculate efficiency compared to previous stage"""
        if previous_stage_rate == 0:
            return 0.0
        return self.conversion_rate / previous_stage_rate

    def __repr__(self):
        return f"<FunnelAnalysis(experiment={self.experiment_id}, stage={self.stage_name}, rate={self.conversion_rate:.2%})>"


class CohortAnalysis(BaseModel):
    """
    Cohort-based analysis for long-term experiment effects
    """

    __tablename__ = "ab_cohort_analysis"

    # Cohort information
    experiment_id = Column(
        GUID(), ForeignKey("ab_experiments.id"), nullable=False, index=True
    )
    variant_id = Column(
        GUID(), ForeignKey("ab_variants.id"), nullable=False, index=True
    )
    cohort_name = Column(String(255), nullable=False, index=True)

    # Cohort definition
    cohort_definition = Column(JSONB, nullable=False)  # Rules defining the cohort
    cohort_size = Column(Integer, nullable=False, index=True)

    # Time period analysis
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False)
    period_number = Column(Integer, nullable=False)  # Day 0, Day 1, Week 1, etc.

    # Metrics for this period
    active_users = Column(Integer, nullable=False)
    retention_rate = Column(Float, nullable=False, index=True)
    engagement_metric = Column(Float, nullable=True)
    conversion_metric = Column(Float, nullable=True)
    revenue_per_user = Column(Float, nullable=True)

    # Comparative metrics
    baseline_retention = Column(Float, nullable=True)
    retention_lift = Column(Float, nullable=True)
    cumulative_value = Column(Float, nullable=True)

    # Metadata
    computed_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    experiment = relationship("Experiment")
    variant = relationship("Variant")

    # Constraints
    __table_args__ = (
        CheckConstraint("cohort_size > 0", name="valid_cohort_size"),
        CheckConstraint(
            "retention_rate >= 0 AND retention_rate <= 1", name="valid_retention_rate"
        ),
        UniqueConstraint(
            "experiment_id",
            "variant_id",
            "cohort_name",
            "period_number",
            "period_start",
            name="unique_cohort_period",
        ),
        Index("idx_cohort_experiment_variant", "experiment_id", "variant_id"),
        Index("idx_cohort_retention", "retention_rate"),
        Index("idx_cohort_period", "period_number", "period_start"),
    )

    def calculate_lifetime_value(self) -> float:
        """Calculate projected lifetime value based on current data"""
        if self.cumulative_value and self.retention_rate > 0:
            # Simple LTV calculation: current value / retention rate
            return self.cumulative_value / self.retention_rate
        return 0.0

    def __repr__(self):
        return f"<CohortAnalysis(experiment={self.experiment_id}, cohort={self.cohort_name}, period={self.period_number}, retention={self.retention_rate:.2%})>"


class ExperimentDashboard(BaseModel):
    """
    Pre-computed dashboard data for experiment visualization
    """

    __tablename__ = "ab_experiment_dashboards"

    # Dashboard information
    experiment_id = Column(
        GUID(), ForeignKey("ab_experiments.id"), nullable=False, index=True, unique=True
    )
    dashboard_type = Column(
        String(100), nullable=False, index=True
    )  # overview, detailed, summary

    # Key metrics snapshot
    total_participants = Column(Integer, nullable=False)
    total_queries = Column(Integer, nullable=False)
    current_leader = Column(
        GUID(), ForeignKey("ab_variants.id"), nullable=True, index=True
    )
    confidence_level = Column(Float, nullable=False)
    statistical_power = Column(Float, nullable=False)

    # Performance metrics
    best_conversion_rate = Column(Float, nullable=True)
    worst_conversion_rate = Column(Float, nullable=True)
    conversion_rate_improvement = Column(Float, nullable=True)
    best_response_time = Column(Float, nullable=True)
    worst_response_time = Column(Float, nullable=True)
    response_time_improvement = Column(Float, nullable=True)

    # Risk metrics
    probability_of_harm = Column(
        Float, nullable=False
    )  # Probability variant is worse than control
    expected_loss = Column(Float, nullable=False)
    potential_upside = Column(Float, nullable=False)

    # Business impact
    estimated_revenue_impact = Column(Float, nullable=True)
    estimated_cost_savings = Column(Float, nullable=True)
    business_confidence_score = Column(Float, nullable=False, index=True)

    # Visualization data (JSON)
    chart_data = Column(JSONB, nullable=True)  # Pre-computed chart configurations
    summary_insights = Column(JSONB, nullable=True)  # Key insights and recommendations

    # Metadata
    last_updated = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
    update_frequency_minutes = Column(Integer, default=15, nullable=False)

    # Relationships
    experiment = relationship("Experiment")
    leading_variant = relationship("Variant", foreign_keys=[current_leader])

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "confidence_level > 0 AND confidence_level < 1",
            name="valid_dashboard_confidence",
        ),
        CheckConstraint(
            "statistical_power >= 0 AND statistical_power <= 1",
            name="valid_dashboard_power",
        ),
        CheckConstraint(
            "probability_of_harm >= 0 AND probability_of_harm <= 1",
            name="valid_harm_probability",
        ),
        CheckConstraint(
            "business_confidence_score >= 0 AND business_confidence_score <= 100",
            name="valid_business_confidence",
        ),
        Index("idx_dashboard_last_updated", "last_updated"),
        Index("idx_dashboard_business_confidence", "business_confidence_score"),
    )

    def should_update(self) -> bool:
        """Check if dashboard needs updating based on frequency"""
        time_since_update = datetime.utcnow() - self.last_updated
        return time_since_update.total_seconds() >= (self.update_frequency_minutes * 60)

    def get_risk_assessment(self) -> str:
        """Get risk assessment based on probability of harm"""
        if self.probability_of_harm < 0.05:
            return "very_low"
        elif self.probability_of_harm < 0.15:
            return "low"
        elif self.probability_of_harm < 0.30:
            return "moderate"
        elif self.probability_of_harm < 0.50:
            return "high"
        else:
            return "very_high"

    def get_business_recommendation(self) -> str:
        """Get business recommendation based on metrics"""
        if self.business_confidence_score >= 80:
            return "implement_immediately"
        elif self.business_confidence_score >= 60:
            return "implement_with_monitoring"
        elif self.business_confidence_score >= 40:
            return "consider_implementation"
        elif self.business_confidence_score >= 20:
            return "needs_more_data"
        else:
            return "do_not_implement"

    def __repr__(self):
        return f"<ExperimentDashboard(experiment={self.experiment_id}, confidence={self.confidence_level:.2f}, business_score={self.business_confidence_score})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        data = super().to_dict()

        # Add computed fields
        data["risk_assessment"] = self.get_risk_assessment()
        data["business_recommendation"] = self.get_business_recommendation()
        data["needs_update"] = self.should_update()

        # Add performance improvements
        data["performance_improvements"] = {
            "conversion_rate": self.conversion_rate_improvement,
            "response_time": self.response_time_improvement,
            "overall_business_score": self.business_confidence_score,
        }

        return data
