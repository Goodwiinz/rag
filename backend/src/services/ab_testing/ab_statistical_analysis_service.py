"""
A/B Testing Statistical Analysis and Reporting Service
Provides comprehensive statistical analysis, significance testing, and reporting
"""

import asyncio
import json
import logging
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import get_db
from src.models.ab_testing import (
    Experiment,
    ExperimentAssignment,
    ExperimentMetric,
    ExperimentStatus,
    MetricType,
    StatisticalTest,
    SuccessCriterion,
    Variant,
)
from src.services.cache.analytics_cache import analytics_cache

logger = logging.getLogger(__name__)


class SignificanceLevel(Enum):
    """Statistical significance levels"""

    VERY_HIGH = 0.001
    HIGH = 0.01
    MEDIUM = 0.05
    LOW = 0.1


@dataclass
class StatisticalResult:
    """Result of statistical test"""

    test_name: str
    statistic: float
    p_value: float
    significance_level: float
    is_significant: bool
    confidence_interval: Tuple[float, float]
    effect_size: float
    power: float
    sample_size: int
    interpretation: str


@dataclass
class VariantComparison:
    """Comparison between two variants"""

    control_variant: str
    treatment_variant: str
    metric_name: str
    control_mean: float
    treatment_mean: float
    absolute_difference: float
    relative_difference: float
    statistical_result: StatisticalResult
    recommendation: str


@dataclass
class ExperimentReport:
    """Comprehensive experiment analysis report"""

    experiment_id: str
    experiment_name: str
    analysis_date: datetime
    total_participants: int
    total_variants: int
    duration_days: float
    primary_metric: str
    comparisons: List[VariantComparison]
    overall_recommendation: str
    confidence_level: float
    statistical_power: float
    business_impact: Dict[str, Any]
    data_quality_metrics: Dict[str, Any]


class StatisticalAnalysisService:
    """
    Comprehensive statistical analysis service for A/B testing
    """

    def __init__(self):
        self._cache_ttl = 3600  # 1 hour
        self._minimum_sample_size = 100
        self._outlier_threshold = 3.0  # Standard deviations

    async def analyze_experiment(
        self,
        experiment_id: str,
        confidence_level: float = 0.95,
        include_secondary_metrics: bool = True,
    ) -> ExperimentReport:
        """
        Perform comprehensive statistical analysis of an experiment
        """
        try:
            db = next(get_db())

            # Get experiment data
            experiment = (
                db.query(Experiment).filter(Experiment.id == experiment_id).first()
            )
            if not experiment:
                raise ValueError(f"Experiment {experiment_id} not found")

            # Check if experiment has sufficient data
            if not await self._has_sufficient_data(experiment, db):
                raise ValueError("Insufficient data for statistical analysis")

            # Get metrics data
            metrics_data = await self._collect_metrics_data(experiment, db)

            # Perform primary metric analysis
            primary_comparison = await self._analyze_primary_metric(
                experiment, metrics_data, confidence_level, db
            )

            # Perform secondary metrics analysis if requested
            secondary_comparisons = []
            if include_secondary_metrics:
                secondary_comparisons = await self._analyze_secondary_metrics(
                    experiment, metrics_data, confidence_level, db
                )

            # Generate overall report
            report = await self._generate_experiment_report(
                experiment,
                primary_comparison,
                secondary_comparisons,
                metrics_data,
                confidence_level,
                db,
            )

            # Cache the results
            cache_key = f"ab_analysis:{experiment_id}:{confidence_level}"
            await self._cache_analysis_results(cache_key, report)

            db.close()
            return report

        except Exception as e:
            logger.error(f"Error analyzing experiment {experiment_id}: {e}")
            raise

    async def calculate_statistical_significance(
        self,
        control_data: List[float],
        treatment_data: List[float],
        test_type: StatisticalTest,
        confidence_level: float = 0.95,
        alternative: str = "two-sided",
    ) -> StatisticalResult:
        """
        Calculate statistical significance between two groups
        """
        try:
            if (
                len(control_data) < self._minimum_sample_size
                or len(treatment_data) < self._minimum_sample_size
            ):
                raise ValueError("Insufficient sample size for statistical test")

            # Remove outliers
            control_clean = self._remove_outliers(control_data)
            treatment_clean = self._remove_outliers(treatment_data)

            # Calculate basic statistics
            control_mean = statistics.mean(control_clean)
            control_std = (
                statistics.stdev(control_clean) if len(control_clean) > 1 else 0
            )
            treatment_mean = statistics.mean(treatment_clean)
            treatment_std = (
                statistics.stdev(treatment_clean) if len(treatment_clean) > 1 else 0
            )

            # Perform statistical test based on type
            if test_type == StatisticalTest.Z_TEST:
                result = await self._perform_z_test(
                    control_clean, treatment_clean, confidence_level, alternative
                )
            elif test_type == StatisticalTest.T_TEST:
                result = await self._perform_t_test(
                    control_clean, treatment_clean, confidence_level, alternative
                )
            elif test_type == StatisticalTest.WELCH_T_TEST:
                result = await self._perform_welch_t_test(
                    control_clean, treatment_clean, confidence_level, alternative
                )
            elif test_type == StatisticalTest.MANN_WHITNEY:
                result = await self._perform_mann_whitney_test(
                    control_clean, treatment_clean, confidence_level, alternative
                )
            elif test_type == StatisticalTest.CHI_SQUARE:
                result = await self._perform_chi_square_test(
                    control_clean, treatment_clean, confidence_level
                )
            else:
                raise ValueError(f"Unsupported test type: {test_type}")

            # Calculate effect size
            effect_size = self._calculate_effect_size(control_clean, treatment_clean)

            # Calculate statistical power
            power = self._calculate_statistical_power(
                effect_size, len(control_clean), len(treatment_clean), confidence_level
            )

            # Generate interpretation
            interpretation = self._interpret_results(result, effect_size, power)

            return StatisticalResult(
                test_name=test_type.value,
                statistic=result["statistic"],
                p_value=result["p_value"],
                significance_level=1 - confidence_level,
                is_significant=result["p_value"] < (1 - confidence_level),
                confidence_interval=result["confidence_interval"],
                effect_size=effect_size,
                power=power,
                sample_size=len(control_clean) + len(treatment_clean),
                interpretation=interpretation,
            )

        except Exception as e:
            logger.error(f"Error calculating statistical significance: {e}")
            raise

    async def _perform_z_test(
        self,
        control: List[float],
        treatment: List[float],
        confidence_level: float,
        alternative: str,
    ) -> Dict[str, Any]:
        """Perform Z-test for large samples"""
        try:
            control_mean = statistics.mean(control)
            control_std = statistics.stdev(control)
            treatment_mean = statistics.mean(treatment)
            treatment_std = statistics.stdev(treatment)

            n1, n2 = len(control), len(treatment)
            pooled_std = math.sqrt(
                ((n1 - 1) * control_std**2 + (n2 - 1) * treatment_std**2)
                / (n1 + n2 - 2)
            )
            standard_error = pooled_std * math.sqrt(1 / n1 + 1 / n2)

            z_statistic = (treatment_mean - control_mean) / standard_error

            # Calculate p-value based on alternative hypothesis
            if alternative == "two-sided":
                p_value = 2 * (1 - stats.norm.cdf(abs(z_statistic)))
            elif alternative == "greater":
                p_value = 1 - stats.norm.cdf(z_statistic)
            else:  # 'less'
                p_value = stats.norm.cdf(z_statistic)

            # Calculate confidence interval
            alpha = 1 - confidence_level
            z_critical = stats.norm.ppf(1 - alpha / 2)
            margin_of_error = z_critical * standard_error
            confidence_interval = (
                treatment_mean - control_mean - margin_of_error,
                treatment_mean - control_mean + margin_of_error,
            )

            return {
                "statistic": z_statistic,
                "p_value": p_value,
                "confidence_interval": confidence_interval,
            }

        except Exception as e:
            logger.error(f"Error performing Z-test: {e}")
            raise

    async def _perform_t_test(
        self,
        control: List[float],
        treatment: List[float],
        confidence_level: float,
        alternative: str,
    ) -> Dict[str, Any]:
        """Perform Student's t-test"""
        try:
            if alternative == "two-sided":
                t_statistic, p_value = stats.ttest_ind(treatment, control)
            elif alternative == "greater":
                t_statistic, p_value = stats.ttest_ind(
                    treatment, control, alternative="greater"
                )
            else:  # 'less'
                t_statistic, p_value = stats.ttest_ind(
                    treatment, control, alternative="less"
                )

            # Calculate confidence interval for difference in means
            control_mean = statistics.mean(control)
            treatment_mean = statistics.mean(treatment)
            diff = treatment_mean - control_mean

            n1, n2 = len(control), len(treatment)
            df = n1 + n2 - 2
            pooled_std = math.sqrt(
                (
                    (n1 - 1) * statistics.stdev(control) ** 2
                    + (n2 - 1) * statistics.stdev(treatment) ** 2
                )
                / df
            )
            standard_error = pooled_std * math.sqrt(1 / n1 + 1 / n2)

            alpha = 1 - confidence_level
            t_critical = stats.t.ppf(1 - alpha / 2, df)
            margin_of_error = t_critical * standard_error
            confidence_interval = (diff - margin_of_error, diff + margin_of_error)

            return {
                "statistic": t_statistic,
                "p_value": p_value,
                "confidence_interval": confidence_interval,
            }

        except Exception as e:
            logger.error(f"Error performing t-test: {e}")
            raise

    async def _perform_welch_t_test(
        self,
        control: List[float],
        treatment: List[float],
        confidence_level: float,
        alternative: str,
    ) -> Dict[str, Any]:
        """Perform Welch's t-test for unequal variances"""
        try:
            if alternative == "two-sided":
                t_statistic, p_value = stats.ttest_ind(
                    treatment, control, equal_var=False
                )
            elif alternative == "greater":
                t_statistic, p_value = stats.ttest_ind(
                    treatment, control, equal_var=False, alternative="greater"
                )
            else:  # 'less'
                t_statistic, p_value = stats.ttest_ind(
                    treatment, control, equal_var=False, alternative="less"
                )

            # Calculate degrees of freedom for Welch's test
            n1, n2 = len(control), len(treatment)
            s1, s2 = statistics.stdev(control), statistics.stdev(treatment)
            df_numerator = (s1**2 / n1 + s2**2 / n2) ** 2
            df_denominator = (s1**4 / (n1**2 * (n1 - 1))) + (
                s2**4 / (n2**2 * (n2 - 1))
            )
            df = df_numerator / df_denominator

            # Calculate confidence interval
            control_mean = statistics.mean(control)
            treatment_mean = statistics.mean(treatment)
            diff = treatment_mean - control_mean
            standard_error = math.sqrt(s1**2 / n1 + s2**2 / n2)

            alpha = 1 - confidence_level
            t_critical = stats.t.ppf(1 - alpha / 2, df)
            margin_of_error = t_critical * standard_error
            confidence_interval = (diff - margin_of_error, diff + margin_of_error)

            return {
                "statistic": t_statistic,
                "p_value": p_value,
                "confidence_interval": confidence_interval,
            }

        except Exception as e:
            logger.error(f"Error performing Welch's t-test: {e}")
            raise

    async def _perform_mann_whitney_test(
        self,
        control: List[float],
        treatment: List[float],
        confidence_level: float,
        alternative: str,
    ) -> Dict[str, Any]:
        """Perform Mann-Whitney U test (non-parametric)"""
        try:
            if alternative == "two-sided":
                u_statistic, p_value = stats.mannwhitneyu(
                    treatment, control, alternative="two-sided"
                )
            elif alternative == "greater":
                u_statistic, p_value = stats.mannwhitneyu(
                    treatment, control, alternative="greater"
                )
            else:  # 'less'
                u_statistic, p_value = stats.mannwhitneyu(
                    treatment, control, alternative="less"
                )

            # For non-parametric test, we'll use the difference in medians
            control_median = statistics.median(control)
            treatment_median = statistics.median(treatment)
            diff = treatment_median - control_median

            # Approximate confidence interval using bootstrap
            confidence_interval = await self._bootstrap_confidence_interval(
                control, treatment, confidence_level
            )

            return {
                "statistic": u_statistic,
                "p_value": p_value,
                "confidence_interval": confidence_interval,
            }

        except Exception as e:
            logger.error(f"Error performing Mann-Whitney test: {e}")
            raise

    async def _perform_chi_square_test(
        self, control: List[float], treatment: List[float], confidence_level: float
    ) -> Dict[str, Any]:
        """Perform Chi-square test for categorical data"""
        try:
            # For simplicity, convert continuous data to binary (above/below median)
            combined = control + treatment
            overall_median = statistics.median(combined)

            control_binary = [1 if x > overall_median else 0 for x in control]
            treatment_binary = [1 if x > overall_median else 0 for x in treatment]

            # Create contingency table
            contingency_table = [
                [sum(control_binary), len(control_binary) - sum(control_binary)],
                [sum(treatment_binary), len(treatment_binary) - sum(treatment_binary)],
            ]

            chi2_statistic, p_value, dof, expected = stats.chi2_contingency(
                contingency_table
            )

            # Calculate confidence interval for difference in proportions
            control_prop = sum(control_binary) / len(control_binary)
            treatment_prop = sum(treatment_binary) / len(treatment_binary)
            diff = treatment_prop - control_prop

            standard_error = math.sqrt(
                (control_prop * (1 - control_prop) / len(control_binary))
                + (treatment_prop * (1 - treatment_prop) / len(treatment_binary))
            )

            alpha = 1 - confidence_level
            z_critical = stats.norm.ppf(1 - alpha / 2)
            margin_of_error = z_critical * standard_error
            confidence_interval = (diff - margin_of_error, diff + margin_of_error)

            return {
                "statistic": chi2_statistic,
                "p_value": p_value,
                "confidence_interval": confidence_interval,
            }

        except Exception as e:
            logger.error(f"Error performing Chi-square test: {e}")
            raise

    async def _bootstrap_confidence_interval(
        self,
        control: List[float],
        treatment: List[float],
        confidence_level: float,
        n_bootstrap: int = 1000,
    ) -> Tuple[float, float]:
        """Calculate confidence interval using bootstrap method"""
        try:
            bootstrap_diffs = []
            n_control, n_treatment = len(control), len(treatment)

            for _ in range(n_bootstrap):
                # Bootstrap samples
                control_sample = np.random.choice(control, size=n_control, replace=True)
                treatment_sample = np.random.choice(
                    treatment, size=n_treatment, replace=True
                )

                # Calculate difference in means
                diff = np.mean(treatment_sample) - np.mean(control_sample)
                bootstrap_diffs.append(diff)

            # Calculate confidence interval
            alpha = 1 - confidence_level
            lower_percentile = (alpha / 2) * 100
            upper_percentile = (1 - alpha / 2) * 100

            confidence_interval = (
                np.percentile(bootstrap_diffs, lower_percentile),
                np.percentile(bootstrap_diffs, upper_percentile),
            )

            return confidence_interval

        except Exception as e:
            logger.error(f"Error calculating bootstrap confidence interval: {e}")
            return (0.0, 0.0)

    def _remove_outliers(self, data: List[float]) -> List[float]:
        """Remove outliers using IQR method"""
        try:
            if len(data) < 4:
                return data

            q1 = np.percentile(data, 25)
            q3 = np.percentile(data, 75)
            iqr = q3 - q1

            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            return [x for x in data if lower_bound <= x <= upper_bound]

        except Exception as e:
            logger.error(f"Error removing outliers: {e}")
            return data

    def _calculate_effect_size(
        self, control: List[float], treatment: List[float]
    ) -> float:
        """Calculate Cohen's d effect size"""
        try:
            control_mean = statistics.mean(control)
            treatment_mean = statistics.mean(treatment)
            control_std = statistics.stdev(control) if len(control) > 1 else 0
            treatment_std = statistics.stdev(treatment) if len(treatment) > 1 else 0

            # Pooled standard deviation
            n1, n2 = len(control), len(treatment)
            pooled_std = math.sqrt(
                ((n1 - 1) * control_std**2 + (n2 - 1) * treatment_std**2)
                / (n1 + n2 - 2)
            )

            if pooled_std == 0:
                return 0.0

            cohens_d = (treatment_mean - control_mean) / pooled_std
            return cohens_d

        except Exception as e:
            logger.error(f"Error calculating effect size: {e}")
            return 0.0

    def _calculate_statistical_power(
        self, effect_size: float, n1: int, n2: int, confidence_level: float
    ) -> float:
        """Calculate statistical power of the test"""
        try:
            # Simplified power calculation
            # In practice, use power analysis libraries like statsmodels

            alpha = 1 - confidence_level
            n_avg = (n1 + n2) / 2

            # Approximate power calculation
            z_alpha = stats.norm.ppf(1 - alpha / 2)
            ncp = effect_size * math.sqrt(n_avg / 2)  # Non-centrality parameter

            # Power calculation (simplified)
            power = 1 - stats.norm.cdf(z_alpha - ncp)

            return max(0.0, min(1.0, power))

        except Exception as e:
            logger.error(f"Error calculating statistical power: {e}")
            return 0.0

    def _interpret_results(
        self, result: Dict[str, Any], effect_size: float, power: float
    ) -> str:
        """Generate interpretation of statistical results"""
        try:
            if result["p_value"] < 0.001:
                significance = "very highly significant"
            elif result["p_value"] < 0.01:
                significance = "highly significant"
            elif result["p_value"] < 0.05:
                significance = "significant"
            elif result["p_value"] < 0.1:
                significance = "marginally significant"
            else:
                significance = "not significant"

            # Effect size interpretation
            if abs(effect_size) < 0.2:
                magnitude = "negligible"
            elif abs(effect_size) < 0.5:
                magnitude = "small"
            elif abs(effect_size) < 0.8:
                magnitude = "medium"
            else:
                magnitude = "large"

            # Power interpretation
            if power < 0.8:
                power_desc = "low statistical power"
            elif power < 0.9:
                power_desc = "adequate statistical power"
            else:
                power_desc = "high statistical power"

            interpretation = (
                f"The result is {significance} (p={result['p_value']:.4f}) "
            )
            interpretation += (
                f"with a {magnitude} effect size (Cohen's d={effect_size:.3f}). "
            )
            interpretation += f"The test has {power_desc} ({power:.2f})."

            return interpretation

        except Exception as e:
            logger.error(f"Error interpreting results: {e}")
            return "Unable to interpret results due to error."

    async def _has_sufficient_data(self, experiment: Experiment, db: Session) -> bool:
        """Check if experiment has sufficient data for analysis"""
        try:
            total_participants = (
                db.query(ExperimentAssignment)
                .filter(ExperimentAssignment.experiment_id == experiment.id)
                .count()
            )

            return total_participants >= experiment.minimum_sample_size

        except Exception as e:
            logger.error(f"Error checking data sufficiency: {e}")
            return False

    async def _collect_metrics_data(
        self, experiment: Experiment, db: Session
    ) -> Dict[str, Any]:
        """Collect metrics data for all variants"""
        try:
            metrics_data = {}

            for variant in experiment.variants:
                variant_metrics = (
                    db.query(ExperimentMetric)
                    .filter(
                        and_(
                            ExperimentMetric.experiment_id == experiment.id,
                            ExperimentMetric.variant_id == variant.id,
                        )
                    )
                    .all()
                )

                # Group metrics by type
                metrics_by_type = defaultdict(list)
                for metric in variant_metrics:
                    metrics_by_type[metric.metric_type.value].append(
                        metric.metric_value
                    )

                metrics_data[variant.id] = {
                    "variant_name": variant.name,
                    "is_control": variant.is_control,
                    "metrics": dict(metrics_by_type),
                    "participant_count": variant.participant_count,
                    "query_count": variant.query_count,
                }

            return metrics_data

        except Exception as e:
            logger.error(f"Error collecting metrics data: {e}")
            return {}

    async def _analyze_primary_metric(
        self,
        experiment: Experiment,
        metrics_data: Dict[str, Any],
        confidence_level: float,
        db: Session,
    ) -> List[VariantComparison]:
        """Analyze primary metric across variants"""
        try:
            comparisons = []

            # Find control variant
            control_variant_id = None
            control_data = None

            for variant_id, data in metrics_data.items():
                if data["is_control"]:
                    control_variant_id = variant_id
                    control_data = data
                    break

            if not control_variant_id:
                logger.warning("No control variant found for primary metric analysis")
                return comparisons

            # Compare each treatment variant against control
            for variant_id, data in metrics_data.items():
                if variant_id == control_variant_id or not data["is_control"]:
                    continue

                # Get primary metric data
                primary_metric_name = experiment.primary_metric.value
                control_values = control_data["metrics"].get(primary_metric_name, [])
                treatment_values = data["metrics"].get(primary_metric_name, [])

                if not control_values or not treatment_values:
                    continue

                # Perform statistical test
                statistical_result = await self.calculate_statistical_significance(
                    control_values,
                    treatment_values,
                    experiment.statistical_test,
                    confidence_level,
                )

                # Calculate differences
                control_mean = statistics.mean(control_values)
                treatment_mean = statistics.mean(treatment_values)
                absolute_diff = treatment_mean - control_mean
                relative_diff = (
                    (absolute_diff / control_mean) * 100 if control_mean != 0 else 0
                )

                # Generate recommendation
                recommendation = self._generate_recommendation(
                    statistical_result, experiment.success_criteria
                )

                comparison = VariantComparison(
                    control_variant=control_variant_id,
                    treatment_variant=variant_id,
                    metric_name=primary_metric_name,
                    control_mean=control_mean,
                    treatment_mean=treatment_mean,
                    absolute_difference=absolute_diff,
                    relative_difference=relative_diff,
                    statistical_result=statistical_result,
                    recommendation=recommendation,
                )

                comparisons.append(comparison)

            return comparisons

        except Exception as e:
            logger.error(f"Error analyzing primary metric: {e}")
            return []

    async def _analyze_secondary_metrics(
        self,
        experiment: Experiment,
        metrics_data: Dict[str, Any],
        confidence_level: float,
        db: Session,
    ) -> List[VariantComparison]:
        """Analyze secondary metrics across variants"""
        # Implementation similar to primary metric analysis
        # but for all secondary metrics
        return []

    async def _generate_experiment_report(
        self,
        experiment: Experiment,
        primary_comparisons: List[VariantComparison],
        secondary_comparisons: List[VariantComparison],
        metrics_data: Dict[str, Any],
        confidence_level: float,
        db: Session,
    ) -> ExperimentReport:
        """Generate comprehensive experiment report"""
        try:
            # Calculate totals
            total_participants = sum(
                data["participant_count"] for data in metrics_data.values()
            )
            total_variants = len(metrics_data)
            duration_days = (
                (experiment.end_time - experiment.start_time).days
                if experiment.end_time
                else 0
            )

            # Generate overall recommendation
            overall_recommendation = self._generate_overall_recommendation(
                primary_comparisons
            )

            # Calculate business impact
            business_impact = await self._calculate_business_impact(
                experiment, primary_comparisons, metrics_data
            )

            # Calculate data quality metrics
            data_quality = await self._calculate_data_quality_metrics(
                experiment, metrics_data, db
            )

            return ExperimentReport(
                experiment_id=str(experiment.id),
                experiment_name=experiment.name,
                analysis_date=datetime.utcnow(),
                total_participants=total_participants,
                total_variants=total_variants,
                duration_days=duration_days,
                primary_metric=experiment.primary_metric.value,
                comparisons=primary_comparisons + secondary_comparisons,
                overall_recommendation=overall_recommendation,
                confidence_level=confidence_level,
                statistical_power=experiment.calculate_statistical_power(),
                business_impact=business_impact,
                data_quality_metrics=data_quality,
            )

        except Exception as e:
            logger.error(f"Error generating experiment report: {e}")
            raise

    def _generate_recommendation(
        self, statistical_result: StatisticalResult, success_criteria: SuccessCriterion
    ) -> str:
        """Generate recommendation based on statistical results"""
        try:
            if not statistical_result.is_significant:
                return "No statistically significant difference detected. Continue experiment or consider inconclusive results."

            if success_criteria == SuccessCriterion.HIGHER_IS_BETTER:
                if statistical_result.effect_size > 0:
                    return "Treatment variant shows statistically significant improvement. Consider implementing."
                else:
                    return "Control variant performs significantly better. Maintain current implementation."
            elif success_criteria == SuccessCriterion.LOWER_IS_BETTER:
                if statistical_result.effect_size < 0:
                    return "Treatment variant shows statistically significant improvement. Consider implementing."
                else:
                    return "Control variant performs significantly better. Maintain current implementation."
            else:
                return "Statistically significant difference detected. Evaluate based on business context."

        except Exception as e:
            logger.error(f"Error generating recommendation: {e}")
            return "Unable to generate recommendation due to error."

    def _generate_overall_recommendation(
        self, comparisons: List[VariantComparison]
    ) -> str:
        """Generate overall experiment recommendation"""
        try:
            if not comparisons:
                return "Insufficient data for recommendation."

            significant_results = [
                c for c in comparisons if c.statistical_result.is_significant
            ]

            if not significant_results:
                return "No statistically significant results detected. Experiment may need more time or different approach."

            # Find best performing variant
            best_comparison = max(
                significant_results,
                key=lambda c: c.relative_difference
                if c.statistical_result.effect_size > 0
                else -abs(c.relative_difference),
            )

            if best_comparison.statistical_result.effect_size > 0:
                return f"Recommend implementing variant {best_comparison.treatment_variant} which shows {best_comparison.relative_difference:.1f}% improvement in {best_comparison.metric_name}."
            else:
                return f"Recommend maintaining control variant as it outperforms all treatment variants."

        except Exception as e:
            logger.error(f"Error generating overall recommendation: {e}")
            return "Unable to generate overall recommendation due to error."

    async def _calculate_business_impact(
        self,
        experiment: Experiment,
        comparisons: List[VariantComparison],
        metrics_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate business impact metrics"""
        try:
            impact = {
                "estimated_annual_impact": 0.0,
                "confidence_in_estimate": "medium",
                "key_drivers": [],
                "risk_factors": [],
            }

            # Simplified business impact calculation
            # In practice, this would use actual business metrics and conversion rates
            for comparison in comparisons:
                if comparison.statistical_result.is_significant:
                    annual_impact = (
                        comparison.relative_difference * 10000
                    )  # Placeholder calculation
                    impact["estimated_annual_impact"] += annual_impact
                    impact["key_drivers"].append(
                        {
                            "metric": comparison.metric_name,
                            "impact": annual_impact,
                            "confidence": comparison.statistical_result.confidence_level,
                        }
                    )

            return impact

        except Exception as e:
            logger.error(f"Error calculating business impact: {e}")
            return {}

    async def _calculate_data_quality_metrics(
        self, experiment: Experiment, metrics_data: Dict[str, Any], db: Session
    ) -> Dict[str, Any]:
        """Calculate data quality metrics"""
        try:
            quality = {
                "completeness": 0.0,
                "consistency": 0.0,
                "sample_size_adequacy": False,
                "outlier_percentage": 0.0,
                "data_freshness_days": 0.0,
            }

            # Calculate sample size adequacy
            total_participants = sum(
                data["participant_count"] for data in metrics_data.values()
            )
            quality["sample_size_adequacy"] = (
                total_participants >= experiment.minimum_sample_size
            )

            # Calculate data freshness
            latest_metric = (
                db.query(func.max(ExperimentMetric.timestamp))
                .filter(ExperimentMetric.experiment_id == experiment.id)
                .scalar()
            )

            if latest_metric:
                quality["data_freshness_days"] = (
                    datetime.utcnow() - latest_metric
                ).days

            return quality

        except Exception as e:
            logger.error(f"Error calculating data quality metrics: {e}")
            return {}

    async def _cache_analysis_results(self, cache_key: str, report: ExperimentReport):
        """Cache analysis results"""
        try:
            cache_data = {
                "report": {
                    "experiment_id": report.experiment_id,
                    "experiment_name": report.experiment_name,
                    "analysis_date": report.analysis_date.isoformat(),
                    "total_participants": report.total_participants,
                    "total_variants": report.total_variants,
                    "duration_days": report.duration_days,
                    "primary_metric": report.primary_metric,
                    "overall_recommendation": report.overall_recommendation,
                    "confidence_level": report.confidence_level,
                    "statistical_power": report.statistical_power,
                    "business_impact": report.business_impact,
                    "data_quality_metrics": report.data_quality_metrics,
                },
                "comparisons": [
                    {
                        "control_variant": comp.control_variant,
                        "treatment_variant": comp.treatment_variant,
                        "metric_name": comp.metric_name,
                        "control_mean": comp.control_mean,
                        "treatment_mean": comp.treatment_mean,
                        "absolute_difference": comp.absolute_difference,
                        "relative_difference": comp.relative_difference,
                        "recommendation": comp.recommendation,
                        "statistical_result": {
                            "test_name": comp.statistical_result.test_name,
                            "statistic": comp.statistical_result.statistic,
                            "p_value": comp.statistical_result.p_value,
                            "is_significant": comp.statistical_result.is_significant,
                            "effect_size": comp.statistical_result.effect_size,
                            "power": comp.statistical_result.power,
                            "interpretation": comp.statistical_result.interpretation,
                        },
                    }
                    for comp in report.comparisons
                ],
            }

            await analytics_cache.set(cache_key, cache_data, ttl=self._cache_ttl)

        except Exception as e:
            logger.error(f"Error caching analysis results: {e}")


# Global service instance
statistical_analysis_service = StatisticalAnalysisService()
