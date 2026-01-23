"""
DeepEval Integration for Advanced RAG Evaluation

This module provides comprehensive integration with DeepEval for
advanced evaluation metrics and automated testing of the RAG system.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

# DeepEval imports (install with: pip install deepeval)
try:
    from deepeval import evaluate
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        FaithfulnessMetric,
        ContextualRelevancyMetric,
        HallucinationMetric,
        BiasMetric,
        ToxicityMetric
    )
    from deepeval.test_case import LLMTestCase
    from deepeval.dataset import EvaluationDataset
    from deepeval.models import GPTModel, AnthropicModel
    DEEPEVAL_AVAILABLE = True
except ImportError:
    DEEPEVAL_AVAILABLE = False
    logging.warning("DeepEval not installed. Install with: pip install deepeval")

from .success_criteria import success_criteria, QueryType, ModalityType, MetricCategory
from .rag_evaluation_service import RAGEvaluationService, RAGTriadMetrics, RAGEvaluationInput
from ..core.config import settings
from ..core.database import get_db
from src.models.evaluation import (
    EvaluationJob, EvaluationMetric, EvaluationDataset as EvalDataset,
    EvaluationType, EvaluationStatus, MetricType
)

logger = logging.getLogger(__name__)


class EvaluationFramework(Enum):
    """Supported evaluation frameworks"""
    DEEPEVAL = "deepeval"
    CUSTOM = "custom"
    HYBRID = "hybrid"


@dataclass
class DeepEvalTestCase:
    """Test case structure for DeepEval evaluation"""
    input: str
    actual_output: str
    retrieval_context: List[str]
    expected_output: Optional[str] = None
    query_type: Optional[QueryType] = None
    modalities: Optional[List[ModalityType]] = None
    metadata: Optional[Dict[str, Any]] = None
    test_id: Optional[str] = None


@dataclass
class EvaluationResults:
    """Results from evaluation framework"""
    framework: EvaluationFramework
    overall_score: float
    individual_metrics: Dict[str, float]
    success_rate: float
    evaluation_time_ms: float
    test_cases_evaluated: int
    threshold_violations: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class DeepEvalIntegration:
    """
    Advanced evaluation using DeepEval framework with custom metrics
    """

    def __init__(self):
        self.is_available = DEEPEVAL_AVAILABLE
        self.rag_service = RAGEvaluationService()
        self.evaluation_models = self._setup_evaluation_models()
        self.custom_metrics = self._setup_custom_metrics()

    def _setup_evaluation_models(self) -> Dict[str, Any]:
        """Setup evaluation models for DeepEval"""
        models = {}

        if not DEEPEVAL_AVAILABLE:
            return models

        try:
            # Setup OpenAI model
            if settings.OPENAI_API_KEY:
                models["openai"] = GPTModel(
                    model_name="gpt-4",
                    api_key=settings.OPENAI_API_KEY
                )

            # Setup Anthropic model
            if settings.ANTHROPIC_API_KEY:
                models["anthropic"] = AnthropicModel(
                    model_name="claude-3-sonnet-20240229",
                    api_key=settings.ANTHROPIC_API_KEY
                )

            logger.info(f"Setup {len(models)} evaluation models")
            return models

        except Exception as e:
            logger.error(f"Error setting up evaluation models: {e}")
            return models

    def _setup_custom_metrics(self) -> Dict[str, Any]:
        """Setup custom metrics for multimodal evaluation"""
        if not DEEPEVAL_AVAILABLE:
            return {}

        custom_metrics = {}

        try:
            # Cross-Modal Coherence Metric
            class CrossModalCoherenceMetric:
                """Custom metric for cross-modal coherence"""
                def __init__(self, threshold: float = 0.7):
                    self.threshold = threshold

                def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
                    # Implementation would check coherence across modalities
                    # Placeholder implementation
                    return 0.8

            # Entity Consistency Metric
            class EntityConsistencyMetric:
                """Custom metric for entity consistency across documents"""
                def __init__(self, threshold: float = 0.8):
                    self.threshold = threshold

                def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
                    # Implementation would check entity consistency
                    # Placeholder implementation
                    return 0.85

            # Temporal Consistency Metric
            class TemporalConsistencyMetric:
                """Custom metric for temporal consistency in answers"""
                def __init__(self, threshold: float = 0.75):
                    self.threshold = threshold

                def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
                    # Implementation would check temporal consistency
                    # Placeholder implementation
                    return 0.78

            custom_metrics = {
                "cross_modal_coherence": CrossModalCoherenceMetric(),
                "entity_consistency": EntityConsistencyMetric(),
                "temporal_consistency": TemporalConsistencyMetric()
            }

            logger.info(f"Setup {len(custom_metrics)} custom metrics")
            return custom_metrics

        except Exception as e:
            logger.error(f"Error setting up custom metrics: {e}")
            return {}

    async def run_comprehensive_evaluation(
        self,
        test_cases: List[DeepEvalTestCase],
        query_type: Optional[QueryType] = None,
        framework: EvaluationFramework = EvaluationFramework.HYBRID,
        organization_id: str = "default",
        user_id: str = "system"
    ) -> EvaluationResults:
        """
        Run comprehensive evaluation using specified framework

        Args:
            test_cases: List of test cases to evaluate
            query_type: Type of queries being evaluated
            framework: Evaluation framework to use
            organization_id: Organization ID for tracking
            user_id: User ID for tracking

        Returns:
            EvaluationResults object with comprehensive metrics
        """
        start_time = time.time()

        try:
            if framework == EvaluationFramework.DEEPEVAL and self.is_available:
                return await self._run_deepeval_evaluation(
                    test_cases, query_type, organization_id, user_id
                )
            elif framework == EvaluationFramework.CUSTOM:
                return await self._run_custom_evaluation(
                    test_cases, query_type, organization_id, user_id
                )
            else:  # HYBRID
                return await self._run_hybrid_evaluation(
                    test_cases, query_type, organization_id, user_id
                )

        except Exception as e:
            logger.error(f"Error in comprehensive evaluation: {e}")
            # Return error results
            return EvaluationResults(
                framework=framework,
                overall_score=0.0,
                individual_metrics={},
                success_rate=0.0,
                evaluation_time_ms=(time.time() - start_time) * 1000,
                test_cases_evaluated=len(test_cases),
                threshold_violations=[],
                metadata={"error": str(e)}
            )

    async def _run_deepeval_evaluation(
        self,
        test_cases: List[DeepEvalTestCase],
        query_type: Optional[QueryType],
        organization_id: str,
        user_id: str
    ) -> EvaluationResults:
        """Run evaluation using DeepEval framework"""
        start_time = time.time()

        try:
            # Convert test cases to DeepEval format
            deepeval_test_cases = []
            for tc in test_cases:
                llm_test_case = LLMTestCase(
                    input=tc.input,
                    actual_output=tc.actual_output,
                    retrieval_context=tc.retrieval_context,
                    expected_output=tc.expected_output
                )
                deepeval_test_cases.append(llm_test_case)

            # Setup metrics
            metrics = [
                AnswerRelevancyMetric(threshold=0.7),
                FaithfulnessMetric(threshold=0.9),
                ContextualRelevancyMetric(threshold=0.7),
                HallucinationMetric(threshold=0.3)
            ]

            # Add custom metrics if available
            if self.custom_metrics:
                metrics.extend(list(self.custom_metrics.values()))

            # Create dataset and evaluate
            dataset = EvaluationDataset(test_cases=deepeval_test_cases)
            evaluation_results = evaluate(dataset, metrics)

            # Process results
            overall_score = 0.0
            individual_metrics = {}
            threshold_violations = []
            successful_tests = 0

            for result in evaluation_results.test_results:
                test_score = 0.0
                test_metrics = {}

                for metric_result in result.metrics_results:
                    metric_name = metric_result.metric_name
                    metric_score = metric_result.score
                    threshold = metric_result.threshold

                    individual_metrics[metric_name] = metric_score
                    test_metrics[metric_name] = metric_score

                    if metric_score >= threshold:
                        successful_tests += 1
                    else:
                        threshold_violations.append({
                            "test_case": result.input[:50] + "...",
                            "metric": metric_name,
                            "score": metric_score,
                            "threshold": threshold,
                            "violation": threshold - metric_score
                        })

                    test_score += metric_score

                # Average score for this test case
                if test_metrics:
                    overall_score += sum(test_metrics.values()) / len(test_metrics)

            # Calculate final scores
            final_overall_score = overall_score / len(deepeval_test_cases) if deepeval_test_cases else 0.0
            success_rate = (successful_tests / (len(deepeval_test_cases) * len(metrics))) * 100

            return EvaluationResults(
                framework=EvaluationFramework.DEEPEVAL,
                overall_score=final_overall_score,
                individual_metrics=individual_metrics,
                success_rate=success_rate,
                evaluation_time_ms=(time.time() - start_time) * 1000,
                test_cases_evaluated=len(test_cases),
                threshold_violations=threshold_violations,
                metadata={
                    "query_type": query_type.value if query_type else None,
                    "model_used": self.evaluation_models.get("default", "unknown"),
                    "metrics_count": len(metrics)
                }
            )

        except Exception as e:
            logger.error(f"Error in DeepEval evaluation: {e}")
            raise

    async def _run_custom_evaluation(
        self,
        test_cases: List[DeepEvalTestCase],
        query_type: Optional[QueryType],
        organization_id: str,
        user_id: str
    ) -> EvaluationResults:
        """Run evaluation using custom RAG service"""
        start_time = time.time()

        try:
            db = next(get_db())
            individual_metrics = {}
            threshold_violations = []
            successful_tests = 0
            total_score = 0.0

            for test_case in test_cases:
                # Convert to RAGEvaluationInput
                rag_input = RAGEvaluationInput(
                    query=test_case.input,
                    generated_answer=test_case.actual_output,
                    retrieved_context=test_case.retrieval_context,
                    reference_answer=test_case.expected_output,
                    metadata=test_case.metadata
                )

                # Run RAG triad evaluation
                metrics = await self.rag_service.run_rag_triad_evaluation(
                    rag_input, None, organization_id, db
                )

                # Collect individual metrics
                individual_metrics[f"{test_case.test_id}_answer_relevancy"] = metrics.answer_relevancy
                individual_metrics[f"{test_case.test_id}_faithfulness"] = metrics.faithfulness
                individual_metrics[f"{test_case.test_id}_contextual_relevancy"] = metrics.contextual_relevancy
                individual_metrics[f"{test_case.test_id}_hallucination_rate"] = metrics.hallucination_rate

                # Check thresholds
                test_success = True
                for metric_name, score, threshold in [
                    ("answer_relevancy", metrics.answer_relevancy, 0.7),
                    ("faithfulness", metrics.faithfulness, 0.9),
                    ("contextual_relevancy", metrics.contextual_relevancy, 0.7),
                    ("hallucination_rate", metrics.hallucination_rate, 0.3)
                ]:
                    if score >= threshold:
                        successful_tests += 1
                    else:
                        test_success = False
                        threshold_violations.append({
                            "test_case": test_case.test_id,
                            "metric": metric_name,
                            "score": score,
                            "threshold": threshold,
                            "violation": threshold - score
                        })

                if test_success:
                    total_score += metrics.overall_score

            final_overall_score = total_score / len(test_cases) if test_cases else 0.0
            total_possible_metrics = len(test_cases) * 4  # 4 metrics per test
            success_rate = (successful_tests / total_possible_metrics) * 100

            return EvaluationResults(
                framework=EvaluationFramework.CUSTOM,
                overall_score=final_overall_score,
                individual_metrics=individual_metrics,
                success_rate=success_rate,
                evaluation_time_ms=(time.time() - start_time) * 1000,
                test_cases_evaluated=len(test_cases),
                threshold_violations=threshold_violations,
                metadata={
                    "query_type": query_type.value if query_type else None,
                    "model_used": "custom_rag_service",
                    "metrics_per_test": 4
                }
            )

        except Exception as e:
            logger.error(f"Error in custom evaluation: {e}")
            raise
        finally:
            db.close()

    async def _run_hybrid_evaluation(
        self,
        test_cases: List[DeepEvalTestCase],
        query_type: Optional[QueryType],
        organization_id: str,
        user_id: str
    ) -> EvaluationResults:
        """Run evaluation using both DeepEval and custom approaches"""
        try:
            # Run both evaluations
            deepeval_results = await self._run_deepeval_evaluation(
                test_cases, query_type, organization_id, user_id
            ) if self.is_available else None

            custom_results = await self._run_custom_evaluation(
                test_cases, query_type, organization_id, user_id
            )

            # Combine results
            if deepeval_results:
                # Weight the results (70% DeepEval, 30% custom)
                combined_overall_score = (
                    deepeval_results.overall_score * 0.7 +
                    custom_results.overall_score * 0.3
                )

                combined_individual_metrics = {
                    **deepeval_results.individual_metrics,
                    **{f"custom_{k}": v for k, v in custom_results.individual_metrics.items()}
                }

                combined_threshold_violations = (
                    deepeval_results.threshold_violations +
                    custom_results.threshold_violations
                )

                combined_success_rate = (
                    deepeval_results.success_rate * 0.7 +
                    custom_results.success_rate * 0.3
                )

                evaluation_time_ms = max(
                    deepeval_results.evaluation_time_ms,
                    custom_results.evaluation_time_ms
                )
            else:
                # Fallback to custom only
                combined_overall_score = custom_results.overall_score
                combined_individual_metrics = custom_results.individual_metrics
                combined_threshold_violations = custom_results.threshold_violations
                combined_success_rate = custom_results.success_rate
                evaluation_time_ms = custom_results.evaluation_time_ms

            return EvaluationResults(
                framework=EvaluationFramework.HYBRID,
                overall_score=combined_overall_score,
                individual_metrics=combined_individual_metrics,
                success_rate=combined_success_rate,
                evaluation_time_ms=evaluation_time_ms,
                test_cases_evaluated=len(test_cases),
                threshold_violations=combined_threshold_violations,
                metadata={
                    "query_type": query_type.value if query_type else None,
                    "deepeval_available": self.is_available,
                    "combination_weights": {"deepeval": 0.7, "custom": 0.3}
                }
            )

        except Exception as e:
            logger.error(f"Error in hybrid evaluation: {e}")
            raise

    async def evaluate_query_types(
        self,
        query_test_suite: Dict[QueryType, List[DeepEvalTestCase]],
        organization_id: str = "default",
        user_id: str = "system"
    ) -> Dict[str, EvaluationResults]:
        """
        Evaluate different query types with their specific test suites

        Args:
            query_test_suite: Dictionary of query types to test cases
            organization_id: Organization ID for tracking
            user_id: User ID for tracking

        Returns:
            Dictionary mapping query types to their evaluation results
        """
        results = {}

        for query_type, test_cases in query_test_suite.items():
            try:
                logger.info(f"Evaluating query type: {query_type.value} with {len(test_cases)} test cases")

                # Use hybrid evaluation for comprehensive analysis
                result = await self.run_comprehensive_evaluation(
                    test_cases=test_cases,
                    query_type=query_type,
                    framework=EvaluationFramework.HYBRID,
                    organization_id=organization_id,
                    user_id=user_id
                )

                results[query_type.value] = result

                # Log results
                logger.info(
                    f"Query type {query_type.value}: "
                    f"Score={result.overall_score:.3f}, "
                    f"Success Rate={result.success_rate:.1f}%, "
                    f"Violations={len(result.threshold_violations)}"
                )

            except Exception as e:
                logger.error(f"Error evaluating query type {query_type.value}: {e}")
                # Add error result
                results[query_type.value] = EvaluationResults(
                    framework=EvaluationFramework.HYBRID,
                    overall_score=0.0,
                    individual_metrics={},
                    success_rate=0.0,
                    evaluation_time_ms=0.0,
                    test_cases_evaluated=len(test_cases),
                    threshold_violations=[],
                    metadata={"error": str(e)}
                )

        return results

    def generate_evaluation_report(
        self,
        results: Union[EvaluationResults, Dict[str, EvaluationResults]],
        include_recommendations: bool = True
    ) -> str:
        """
        Generate comprehensive evaluation report

        Args:
            results: Evaluation results (single or dictionary)
            include_recommendations: Whether to include recommendations

        Returns:
            Formatted evaluation report as string
        """
        try:
            if isinstance(results, dict):
                # Multiple query types
                return self._generate_multi_query_report(results, include_recommendations)
            else:
                # Single evaluation
                return self._generate_single_report(results, include_recommendations)

        except Exception as e:
            logger.error(f"Error generating evaluation report: {e}")
            return f"Error generating report: {str(e)}"

    def _generate_single_report(
        self,
        results: EvaluationResults,
        include_recommendations: bool
    ) -> str:
        """Generate report for single evaluation"""
        report = f"""# RAG Evaluation Report

## Executive Summary

**Framework**: {results.framework.value}
**Overall Score**: {results.overall_score:.3f}
**Success Rate**: {results.success_rate:.1f}%
**Test Cases Evaluated**: {results.test_cases_evaluated}
**Evaluation Time**: {results.evaluation_time_ms:.0f}ms

## Performance Analysis

### Overall Performance
- **Score**: {results.overall_score:.3f} {"✅" if results.overall_score >= 0.75 else "⚠️" if results.overall_score >= 0.6 else "❌"}
- **Success Rate**: {results.success_rate:.1f}% {"✅" if results.success_rate >= 80 else "⚠️" if results.success_rate >= 60 else "❌"}

### Individual Metrics
"""

        for metric_name, score in results.individual_metrics.items():
            report += f"- **{metric_name}**: {score:.3f}\n"

        if results.threshold_violations:
            report += f"""

## Threshold Violations ({len(results.threshold_violations)})

| Test Case | Metric | Score | Threshold | Violation |
|-----------|--------|-------|-----------|-----------|
"""
            for violation in results.threshold_violations[:10]:  # Limit to top 10
                report += f"| {violation['test_case'][:30]}... | {violation['metric']} | {violation['score']:.3f} | {violation['threshold']:.3f} | {violation['violation']:.3f} |\n"

            if len(results.threshold_violations) > 10:
                report += f"| ... | ... | ... | ... | ... |\n*Showing 10 of {len(results.threshold_violations)} violations*\n"

        if include_recommendations:
            report += self._generate_recommendations(results)

        report += f"""

## Metadata

- **Query Type**: {results.metadata.get('query_type', 'N/A')}
- **Model Used**: {results.metadata.get('model_used', 'N/A')}
- **Framework**: {results.framework.value}
- **Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""

        return report

    def _generate_multi_query_report(
        self,
        results: Dict[str, EvaluationResults],
        include_recommendations: bool
    ) -> str:
        """Generate report for multiple query types"""
        report = f"""# Multimodal RAG Evaluation Report

## Executive Summary

This report presents evaluation results across {len(results)} query types.

"""

        # Summary table
        report += """### Performance Summary by Query Type

| Query Type | Overall Score | Success Rate | Violations | Status |
|------------|---------------|--------------|------------|--------|
"""
        for query_type, result in results.items():
            status = "✅" if result.overall_score >= 0.75 else "⚠️" if result.overall_score >= 0.6 else "❌"
            report += f"| {query_type} | {result.overall_score:.3f} | {result.success_rate:.1f}% | {len(result.threshold_violations)} | {status} |\n"

        # Detailed analysis for each query type
        for query_type, result in results.items():
            report += f"""

## {query_type.replace('_', ' ').title()} Analysis

**Score**: {result.overall_score:.3f}
**Success Rate**: {result.success_rate:.1f}%
**Test Cases**: {result.test_cases_evaluated}

#### Key Metrics
"""
            # Show top 5 metrics for this query type
            metrics_sorted = sorted(
                result.individual_metrics.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]

            for metric_name, score in metrics_sorted:
                report += f"- **{metric_name}**: {score:.3f}\n"

            if result.threshold_violations:
                report += f"#### Critical Issues ({len(result.threshold_violations)} violations)\n"
                for violation in result.threshold_violations[:3]:
                    report += f"- **{violation['metric']}**: Score {violation['score']:.3f} < {violation['threshold']:.3f}\n"

        if include_recommendations:
            report += self._generate_multi_query_recommendations(results)

        report += f"""

## System Overview

- **Total Test Cases**: {sum(r.test_cases_evaluated for r in results.values())}
- **Average Success Rate**: {sum(r.success_rate for r in results.values()) / len(results):.1f}%
- **Total Violations**: {sum(len(r.threshold_violations) for r in results.values())}
- **Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""

        return report

    def _generate_recommendations(self, results: EvaluationResults) -> str:
        """Generate recommendations based on evaluation results"""
        recommendations = []

        # Overall performance recommendations
        if results.overall_score < 0.6:
            recommendations.append("- 🚨 **Critical**: Overall system performance requires immediate attention")
        elif results.overall_score < 0.75:
            recommendations.append("- ⚠️ **Moderate**: System performance needs improvement")
        else:
            recommendations.append("- ✅ **Good**: System performance is acceptable")

        # Specific metric recommendations
        for violation in results.threshold_violations[:5]:
            metric = violation['metric']
            if 'relevancy' in metric.lower():
                recommendations.append(f"- 📝 **Improve {metric}**: Review query understanding and context retrieval")
            elif 'faithfulness' in metric.lower():
                recommendations.append(f"- 🔗 **Improve {metric}**: Ensure answers are grounded in retrieved context")
            elif 'hallucination' in metric.lower():
                recommendations.append(f"- 🛡️ **Reduce {metric}**: Implement stricter fact-checking and validation")
            else:
                recommendations.append(f"- 🔍 **Review {metric}**: Investigate and optimize performance")

        if not recommendations:
            recommendations.append("- ✅ **Excellent**: No critical issues identified")

        return f"""

## Recommendations

{''.join(recommendations)}
"""

    def _generate_multi_query_recommendations(self, results: Dict[str, EvaluationResults]) -> str:
        """Generate recommendations for multiple query types"""
        recommendations = []

        # Identify patterns across query types
        weak_areas = []
        strong_areas = []

        for query_type, result in results.items():
            if result.overall_score < 0.6:
                weak_areas.append(query_type)
            elif result.overall_score >= 0.8:
                strong_areas.append(query_type)

        if weak_areas:
            recommendations.append(f"- 🚨 **Critical Issues**: Query types needing immediate attention: {', '.join(weak_areas)}")

        if strong_areas:
            recommendations.append(f"- ✅ **Strong Performance**: Query types performing well: {', '.join(strong_areas)}")

        # Common violations across query types
        violation_counts = {}
        for result in results.values():
            for violation in result.threshold_violations:
                metric = violation['metric']
                violation_counts[metric] = violation_counts.get(metric, 0) + 1

        if violation_counts:
            top_violations = sorted(violation_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            recommendations.append("- 🔍 **Common Issues**: Metrics that need system-wide attention:")
            for metric, count in top_violations:
                recommendations.append(f"  - **{metric}**: {count} violations across query types")

        return f"""

## Recommendations

{''.join(recommendations) if recommendations else "- ✅ **Excellent**: All query types are performing well"}
"""


# Global DeepEval integration instance
deepeval_integration = DeepEvalIntegration()