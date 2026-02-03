"""
RAG Evaluation Service for calculating RAG Triad metrics and evaluation workflows
"""

import asyncio
import json
import logging
import statistics
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import get_db
from src.models.document import Document
from src.models.evaluation import (
    EvaluationComparison,
    EvaluationDataset,
    EvaluationJob,
    EvaluationMetric,
    EvaluationReport,
    EvaluationStatus,
    EvaluationThreshold,
    EvaluationType,
    MetricType,
)
from src.models.search_schemas import (
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchType,
)
from src.services.knowledge_graph import knowledge_graph_service
from src.services.quality.quality_metrics_service import quality_metrics_service
from src.services.search.hybrid_search_service import hybrid_search_service
from src.services.search.vector_search_service import vector_search_service

logger = logging.getLogger(__name__)


@dataclass
class RAGEvaluationInput:
    """Input data for RAG evaluation"""

    query: str
    generated_answer: str
    retrieved_context: List[str]
    reference_answer: Optional[str] = None
    document_ids: Optional[List[str]] = None
    search_type: str = "hybrid"
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RAGTriadMetrics:
    """RAG Triad metrics calculation results"""

    answer_relevancy: float
    faithfulness: float
    contextual_relevancy: float
    overall_score: float
    hallucination_rate: float = 0.0
    response_time_ms: float = 0.0
    metadata: Dict[str, Any] = None


@dataclass
class EvaluationRequest:
    """Request for evaluation job"""

    name: str
    evaluation_type: EvaluationType
    dataset: List[RAGEvaluationInput]
    parameters: Dict[str, Any]
    user_id: str
    organization_id: str
    description: Optional[str] = None


class RAGEvaluationService:
    """
    Service for RAG evaluation including RAG Triad metrics calculation
    """

    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None
        self._initialize_llm_clients()

    def _initialize_llm_clients(self):
        """Initialize LLM clients for evaluation"""
        try:
            # Initialize OpenAI client
            if settings.OPENAI_API_KEY:
                import openai

                self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

            # Initialize Anthropic client
            if settings.ANTHROPIC_API_KEY:
                import anthropic

                self.anthropic_client = anthropic.Anthropic(
                    api_key=settings.ANTHROPIC_API_KEY
                )

        except Exception as e:
            logger.warning(f"Failed to initialize LLM clients: {e}")

    async def create_evaluation_job(
        self, request: EvaluationRequest, db: Session
    ) -> EvaluationJob:
        """
        Create a new evaluation job
        """
        try:
            # Create evaluation job
            job = EvaluationJob(
                name=request.name,
                description=request.description,
                evaluation_type=request.evaluation_type.value,
                parameters=request.parameters,
                dataset_size=len(request.dataset),
                user_id=request.user_id if request.user_id != "anonymous" else None,
                organization_id=request.organization_id,
            )

            db.add(job)
            db.commit()
            db.refresh(job)

            # Create evaluation dataset
            dataset = EvaluationDataset(
                job_id=job.id,
                name=f"Dataset for {request.name}",
                description=request.description,
                questions=[item.query for item in request.dataset],
                reference_answers=[item.reference_answer for item in request.dataset],
                contexts=[item.retrieved_context for item in request.dataset],
                dataset_type="rag_evaluation",
            )

            db.add(dataset)
            db.commit()

            logger.info(
                f"Created evaluation job {job.id} with {len(request.dataset)} items"
            )
            return job

        except Exception as e:
            logger.error(f"Error creating evaluation job: {e}")
            db.rollback()
            raise

    async def run_rag_triad_evaluation(
        self,
        evaluation_input: RAGEvaluationInput,
        job_id: str,
        organization_id: str,
        db: Session,
    ) -> RAGTriadMetrics:
        """
        Calculate RAG Triad metrics for a single evaluation
        """
        start_time = time.time()

        try:
            # Calculate each triad metric
            answer_relevancy = await self._calculate_answer_relevancy(
                evaluation_input.query, evaluation_input.generated_answer
            )

            faithfulness = await self._calculate_faithfulness(
                evaluation_input.generated_answer, evaluation_input.retrieved_context
            )

            contextual_relevancy = await self._calculate_contextual_relevancy(
                evaluation_input.query, evaluation_input.retrieved_context
            )

            # Calculate hallucination rate
            hallucination_rate = await self._calculate_hallucination_rate(
                evaluation_input.generated_answer,
                evaluation_input.retrieved_context,
                evaluation_input.reference_answer,
            )

            # Calculate overall score (weighted average)
            weights = self._get_metric_weights(organization_id, db)
            overall_score = (
                answer_relevancy * weights.get("answer_relevancy", 0.33)
                + faithfulness * weights.get("faithfulness", 0.33)
                + contextual_relevancy * weights.get("contextual_relevancy", 0.34)
            )

            # Calculate response time
            response_time_ms = (time.time() - start_time) * 1000

            # Create metrics record
            metric = EvaluationMetric(
                job_id=job_id,
                metric_type=MetricType.RAG_TRIAD_ANSWER_RELEVANCY.value,
                metric_name="Answer Relevancy",
                value=answer_relevancy,
                query=evaluation_input.query,
                generated_answer=evaluation_input.generated_answer,
                retrieved_context=json.dumps(evaluation_input.retrieved_context),
                reference_answer=evaluation_input.reference_answer,
                metadata={
                    "calculation_method": "llm_judgment",
                    "model_used": self._get_default_model(),
                    "evaluation_timestamp": datetime.utcnow().isoformat(),
                },
            )

            # Set thresholds
            threshold = self._get_threshold(
                MetricType.RAG_TRIAD_ANSWER_RELEVANCY.value, organization_id, db
            )
            if threshold:
                metric.threshold_min = threshold.threshold_min
                metric.threshold_max = threshold.threshold_max
                metric.check_threshold_violation()

            db.add(metric)

            # Create faithfulness metric
            faithfulness_metric = EvaluationMetric(
                job_id=job_id,
                metric_type=MetricType.RAG_TRIAD_FAITHFULNESS.value,
                metric_name="Faithfulness",
                value=faithfulness,
                query=evaluation_input.query,
                generated_answer=evaluation_input.generated_answer,
                retrieved_context=json.dumps(evaluation_input.retrieved_context),
                reference_answer=evaluation_input.reference_answer,
                metadata={
                    "calculation_method": "llm_judgment",
                    "model_used": self._get_default_model(),
                    "evaluation_timestamp": datetime.utcnow().isoformat(),
                },
            )

            faithfulness_threshold = self._get_threshold(
                MetricType.RAG_TRIAD_FAITHFULNESS.value, organization_id, db
            )
            if faithfulness_threshold:
                faithfulness_metric.threshold_min = faithfulness_threshold.threshold_min
                faithfulness_metric.threshold_max = faithfulness_threshold.threshold_max
                faithfulness_metric.check_threshold_violation()

            db.add(faithfulness_metric)

            # Create contextual relevancy metric
            contextual_metric = EvaluationMetric(
                job_id=job_id,
                metric_type=MetricType.RAG_TRIAD_CONTEXTUAL_RELEVANCY.value,
                metric_name="Contextual Relevancy",
                value=contextual_relevancy,
                query=evaluation_input.query,
                generated_answer=evaluation_input.generated_answer,
                retrieved_context=json.dumps(evaluation_input.retrieved_context),
                reference_answer=evaluation_input.reference_answer,
                metadata={
                    "calculation_method": "llm_judgment",
                    "model_used": self._get_default_model(),
                    "evaluation_timestamp": datetime.utcnow().isoformat(),
                },
            )

            contextual_threshold = self._get_threshold(
                MetricType.RAG_TRIAD_CONTEXTUAL_RELEVANCY.value, organization_id, db
            )
            if contextual_threshold:
                contextual_metric.threshold_min = contextual_threshold.threshold_min
                contextual_metric.threshold_max = contextual_threshold.threshold_max
                contextual_metric.check_threshold_violation()

            db.add(contextual_metric)

            # Create hallucination rate metric
            hallucination_metric = EvaluationMetric(
                job_id=job_id,
                metric_type=MetricType.HALLUCINATION_RATE.value,
                metric_name="Hallucination Rate",
                value=hallucination_rate,
                query=evaluation_input.query,
                generated_answer=evaluation_input.generated_answer,
                retrieved_context=json.dumps(evaluation_input.retrieved_context),
                reference_answer=evaluation_input.reference_answer,
                metadata={
                    "calculation_method": "llm_judgment",
                    "model_used": self._get_default_model(),
                    "evaluation_timestamp": datetime.utcnow().isoformat(),
                },
            )

            hallucination_threshold = self._get_threshold(
                MetricType.HALLUCINATION_RATE.value, organization_id, db
            )
            if hallucination_threshold:
                hallucination_metric.threshold_min = (
                    hallucination_threshold.threshold_min
                )
                hallucination_metric.threshold_max = (
                    hallucination_threshold.threshold_max
                )
                hallucination_metric.check_threshold_violation()

            db.add(hallucination_metric)

            db.commit()

            return RAGTriadMetrics(
                answer_relevancy=answer_relevancy,
                faithfulness=faithfulness,
                contextual_relevancy=contextual_relevancy,
                overall_score=overall_score,
                hallucination_rate=hallucination_rate,
                response_time_ms=response_time_ms,
                metadata=evaluation_input.metadata,
            )

        except Exception as e:
            logger.error(f"Error calculating RAG triad metrics: {e}")
            raise

    async def _calculate_answer_relevancy(self, query: str, answer: str) -> float:
        """
        Calculate answer relevancy - measures how relevant the answer is to the query
        """
        try:
            prompt = f"""
            Evaluate the relevance of the following answer to the given question.
            Rate on a scale of 0.0 to 1.0 where:
            - 0.0: Completely irrelevant
            - 0.5: Somewhat relevant
            - 1.0: Perfectly relevant

            Question: {query}
            Answer: {answer}

            Provide only a numerical score (0.0-1.0) as your response.
            """

            response = await self._call_llm(prompt)
            score = self._extract_score_from_response(response)
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.error(f"Error calculating answer relevancy: {e}")
            return 0.5  # Default to middle score on error

    async def _calculate_faithfulness(self, answer: str, context: List[str]) -> float:
        """
        Calculate faithfulness - measures if the answer is supported by the retrieved context
        """
        try:
            context_text = "\n\n".join(context) if context else ""

            prompt = f"""
            Evaluate whether the following answer is faithful to and supported by the provided context.
            Rate on a scale of 0.0 to 1.0 where:
            - 0.0: Answer is completely unsupported or contradicts the context
            - 0.5: Answer is partially supported but contains unsupported claims
            - 1.0: Answer is fully supported by the context

            Context:
            {context_text}

            Answer: {answer}

            Provide only a numerical score (0.0-1.0) as your response.
            """

            response = await self._call_llm(prompt)
            score = self._extract_score_from_response(response)
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.error(f"Error calculating faithfulness: {e}")
            return 0.5  # Default to middle score on error

    async def _calculate_contextual_relevancy(
        self, query: str, context: List[str]
    ) -> float:
        """
        Calculate contextual relevancy - measures how relevant the retrieved context is to the query
        """
        try:
            context_text = "\n\n".join(context) if context else ""

            prompt = f"""
            Evaluate how relevant the following context is to the given question.
            Rate on a scale of 0.0 to 1.0 where:
            - 0.0: Context is completely irrelevant to the question
            - 0.5: Context is somewhat relevant but doesn't fully address the question
            - 1.0: Context is highly relevant and addresses the question comprehensively

            Question: {query}

            Context:
            {context_text}

            Provide only a numerical score (0.0-1.0) as your response.
            """

            response = await self._call_llm(prompt)
            score = self._extract_score_from_response(response)
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.error(f"Error calculating contextual relevancy: {e}")
            return 0.5  # Default to middle score on error

    async def _calculate_hallucination_rate(
        self, answer: str, context: List[str], reference_answer: Optional[str] = None
    ) -> float:
        """
        Calculate hallucination rate - measures fabricated information not supported by context
        """
        try:
            context_text = "\n\n".join(context) if context else ""
            ref_text = (
                f"\nReference Answer: {reference_answer}" if reference_answer else ""
            )

            prompt = f"""
            Evaluate the following answer for hallucinations (fabricated information not supported by the context).
            Rate on a scale of 0.0 to 1.0 where:
            - 0.0: No hallucinations - answer is fully supported by context
            - 0.5: Some hallucinations - answer contains some unsupported claims
            - 1.0: Severe hallucinations - answer is mostly fabricated

            Context:
            {context_text}
            {ref_text}

            Answer: {answer}

            Provide only a numerical score (0.0-1.0) as your response.
            """

            response = await self._call_llm(prompt)
            score = self._extract_score_from_response(response)
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.error(f"Error calculating hallucination rate: {e}")
            return 0.3  # Default to low hallucination rate on error

    async def _call_llm(self, prompt: str) -> str:
        """
        Call LLM for evaluation scoring
        """
        try:
            # Try OpenAI first
            if self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=10,
                    temperature=0.0,
                )
                return response.choices[0].message.content.strip()

            # Fallback to Anthropic
            elif self.anthropic_client:
                response = self.anthropic_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=10,
                    temperature=0.0,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text.strip()

            else:
                # Fallback to simple pattern-based scoring
                return self._fallback_scoring(prompt)

        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return "0.5"  # Default fallback score

    def _extract_score_from_response(self, response: str) -> float:
        """
        Extract numerical score from LLM response
        """
        try:
            # Try to find a decimal number in the response
            import re

            matches = re.findall(r"\d*\.?\d+", response)
            if matches:
                score = float(matches[0])
                return max(0.0, min(1.0, score))

            # Fallback patterns
            response_lower = response.lower()
            if "0." in response_lower:
                try:
                    return float(response.split("0.")[1].split()[0])
                except:
                    pass

            # Default fallback
            return 0.5

        except Exception as e:
            logger.error(f"Error extracting score from response: {e}")
            return 0.5

    def _fallback_scoring(self, prompt: str) -> str:
        """
        Simple fallback scoring when LLM is not available
        """
        # Very basic heuristic scoring
        prompt_lower = prompt.lower()

        # Count keywords that might indicate quality
        positive_keywords = ["relevant", "supported", "accurate", "comprehensive"]
        negative_keywords = ["irrelevant", "unsupported", "fabricated", "hallucinated"]

        positive_count = sum(
            1 for keyword in positive_keywords if keyword in prompt_lower
        )
        negative_count = sum(
            1 for keyword in negative_keywords if keyword in prompt_lower
        )

        if positive_count > negative_count:
            return "0.8"
        elif negative_count > positive_count:
            return "0.3"
        else:
            return "0.5"

    def _get_default_model(self) -> str:
        """Get default model name for evaluation"""
        if self.openai_client:
            return "gpt-3.5-turbo"
        elif self.anthropic_client:
            return "claude-3-haiku-20240307"
        else:
            return "fallback_heuristic"

    def _get_metric_weights(
        self, organization_id: str, db: Session
    ) -> Dict[str, float]:
        """
        Get organization-specific metric weights
        """
        # Default weights - could be made configurable per organization
        return {
            "answer_relevancy": 0.33,
            "faithfulness": 0.33,
            "contextual_relevancy": 0.34,
        }

    def _get_threshold(
        self, metric_type: str, organization_id: str, db: Session
    ) -> Optional[EvaluationThreshold]:
        """
        Get threshold configuration for a metric
        """
        return (
            db.query(EvaluationThreshold)
            .filter(
                and_(
                    EvaluationThreshold.metric_type == metric_type,
                    or_(
                        EvaluationThreshold.organization_id == organization_id,
                        EvaluationThreshold.organization_id.is_(None),
                    ),
                    EvaluationThreshold.is_enabled == True,
                )
            )
            .order_by(EvaluationThreshold.organization_id.desc().nullslast())
            .first()
        )

    async def evaluate_search_pipeline(
        self,
        queries: List[str],
        organization_id: str,
        user_id: str,
        search_type: str = "hybrid",
        limit: int = 5,
    ) -> List[RAGTriadMetrics]:
        """
        Evaluate the search pipeline end-to-end with provided queries
        """
        results = []

        for query in queries:
            try:
                # Perform search
                search_request = SearchQuery(
                    query=query, search_type=SearchType(search_type), limit=limit
                )

                search_response = hybrid_search_service.search(
                    search_request=search_request,
                    user_id=user_id,
                    organization_id=organization_id,
                )

                # Generate answer (simplified - would use actual answer generation)
                generated_answer = self._generate_simple_answer(
                    query, search_response.results
                )

                # Extract context from search results
                retrieved_context = [
                    result.content_text or result.snippet or ""
                    for result in search_response.results
                ]

                # Create evaluation input
                evaluation_input = RAGEvaluationInput(
                    query=query,
                    generated_answer=generated_answer,
                    retrieved_context=retrieved_context,
                    document_ids=[
                        result.document_id for result in search_response.results
                    ],
                    search_type=search_type,
                    metadata={
                        "search_time_ms": search_response.search_time_ms,
                        "results_count": len(search_response.results),
                        "search_response": search_response.to_dict(),
                    },
                )

                # Calculate metrics
                db = next(get_db())
                try:
                    metrics = await self.run_rag_triad_evaluation(
                        evaluation_input, None, organization_id, db
                    )
                    results.append(metrics)
                finally:
                    db.close()

            except Exception as e:
                logger.error(f"Error evaluating query '{query}': {e}")
                continue

        return results

    def _generate_simple_answer(self, query: str, results: List[SearchResult]) -> str:
        """
        Generate a simple answer from search results (placeholder)
        """
        if not results:
            return f"I couldn't find relevant information about '{query}'."

        # Simple answer generation based on top result
        top_result = results[0]
        content = top_result.content_text or top_result.snippet or ""

        # Truncate to reasonable length
        if len(content) > 500:
            content = content[:500] + "..."

        return f"Based on the search results, {content}"

    async def compare_evaluations(
        self,
        baseline_job_id: str,
        comparison_job_id: str,
        name: str,
        user_id: str,
        organization_id: str,
        db: Session,
    ) -> EvaluationComparison:
        """
        Compare two evaluation jobs
        """
        try:
            # Get the jobs
            baseline_job = (
                db.query(EvaluationJob)
                .filter(EvaluationJob.id == baseline_job_id)
                .first()
            )

            comparison_job = (
                db.query(EvaluationJob)
                .filter(EvaluationJob.id == comparison_job_id)
                .first()
            )

            if not baseline_job or not comparison_job:
                raise ValueError("One or both evaluation jobs not found")

            # Get metrics for both jobs
            baseline_metrics = (
                db.query(EvaluationMetric)
                .filter(EvaluationMetric.job_id == baseline_job_id)
                .all()
            )

            comparison_metrics = (
                db.query(EvaluationMetric)
                .filter(EvaluationMetric.job_id == comparison_job_id)
                .all()
            )

            # Calculate comparison statistics
            baseline_avg = (
                statistics.mean([m.value for m in baseline_metrics])
                if baseline_metrics
                else 0.0
            )
            comparison_avg = (
                statistics.mean([m.value for m in comparison_metrics])
                if comparison_metrics
                else 0.0
            )

            improvement_percentage = (
                ((comparison_avg - baseline_avg) / baseline_avg * 100)
                if baseline_avg > 0
                else 0.0
            )

            # Statistical significance test (simplified)
            statistical_significance = self._calculate_statistical_significance(
                baseline_metrics, comparison_metrics
            )

            # Create comparison record
            comparison = EvaluationComparison(
                name=name,
                description=f"Comparison between {baseline_job.name} and {comparison_job.name}",
                baseline_job_id=baseline_job_id,
                comparison_job_id=comparison_job_id,
                baseline_score=baseline_avg,
                comparison_score=comparison_avg,
                improvement_percentage=improvement_percentage,
                statistical_significance=statistical_significance,
                metric_comparisons={
                    "baseline_metrics": len(baseline_metrics),
                    "comparison_metrics": len(comparison_metrics),
                    "baseline_avg_score": baseline_avg,
                    "comparison_avg_score": comparison_avg,
                },
                user_id=user_id,
                organization_id=organization_id,
            )

            db.add(comparison)
            db.commit()

            return comparison

        except Exception as e:
            logger.error(f"Error creating evaluation comparison: {e}")
            db.rollback()
            raise

    def _calculate_statistical_significance(
        self,
        baseline_metrics: List[EvaluationMetric],
        comparison_metrics: List[EvaluationMetric],
    ) -> float:
        """
        Calculate statistical significance using t-test (simplified)
        """
        try:
            if len(baseline_metrics) < 2 or len(comparison_metrics) < 2:
                return 1.0  # Not statistically significant

            baseline_values = [m.value for m in baseline_metrics]
            comparison_values = [m.value for m in comparison_metrics]

            # Simple t-test calculation (placeholder)
            # In practice, would use scipy.stats.ttest_ind
            import math

            baseline_mean = statistics.mean(baseline_values)
            comparison_mean = statistics.mean(comparison_values)

            baseline_std = (
                statistics.stdev(baseline_values) if len(baseline_values) > 1 else 0.0
            )
            comparison_std = (
                statistics.stdev(comparison_values)
                if len(comparison_values) > 1
                else 0.0
            )

            # Pooled standard error
            n1, n2 = len(baseline_values), len(comparison_values)
            pooled_se = math.sqrt((baseline_std**2 / n1) + (comparison_std**2 / n2))

            if pooled_se == 0:
                return 1.0

            # T-statistic
            t_statistic = (comparison_mean - baseline_mean) / pooled_se

            # Simplified p-value calculation (would normally use t-distribution)
            if abs(t_statistic) > 2.0:
                return 0.05  # Significant
            elif abs(t_statistic) > 1.5:
                return 0.10  # Marginally significant
            else:
                return 0.50  # Not significant

        except Exception as e:
            logger.error(f"Error calculating statistical significance: {e}")
            return 1.0

    def get_evaluation_summary(
        self, job_id: str, organization_id: str, db: Session
    ) -> Dict[str, Any]:
        """
        Get comprehensive summary of evaluation results
        """
        try:
            # Get job and metrics
            job = (
                db.query(EvaluationJob)
                .filter(
                    and_(
                        EvaluationJob.id == job_id,
                        EvaluationJob.organization_id == organization_id,
                    )
                )
                .first()
            )

            if not job:
                raise ValueError("Evaluation job not found")

            metrics = (
                db.query(EvaluationMetric)
                .filter(EvaluationMetric.job_id == job_id)
                .all()
            )

            # Group metrics by type
            metrics_by_type = {}
            for metric in metrics:
                metric_type = metric.metric_type
                if metric_type not in metrics_by_type:
                    metrics_by_type[metric_type] = []
                metrics_by_type[metric_type].append(metric.value)

            # Calculate statistics for each metric type
            summary_stats = {}
            for metric_type, values in metrics_by_type.items():
                if values:
                    summary_stats[metric_type] = {
                        "count": len(values),
                        "mean": statistics.mean(values),
                        "min": min(values),
                        "max": max(values),
                        "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
                    }

            # Get threshold violations
            violations = (
                db.query(EvaluationMetric)
                .filter(
                    and_(
                        EvaluationMetric.job_id == job_id,
                        EvaluationMetric.is_threshold_violation == True,
                    )
                )
                .count()
            )

            return {
                "job_info": {
                    "id": str(job.id),
                    "name": job.name,
                    "status": job.status,
                    "evaluation_type": job.evaluation_type,
                    "created_at": job.created_at.isoformat(),
                    "duration_seconds": job.duration_seconds,
                    "dataset_size": job.dataset_size,
                    "processed_count": job.processed_count,
                },
                "summary_statistics": summary_stats,
                "threshold_violations": violations,
                "total_metrics": len(metrics),
                "overall_score": job.overall_score,
                "success_rate": job.success_rate,
            }

        except Exception as e:
            logger.error(f"Error getting evaluation summary: {e}")
            raise

    def get_evaluation_metrics(
        self,
        job_id: str,
        organization_id: str,
        metric_types: List[str] = None,
        limit: int = 100,
        db: Session = None,
    ) -> List[EvaluationMetric]:
        """
        Get metrics for a specific evaluation job
        """
        try:
            if not db:
                db = next(get_db())

            query = db.query(EvaluationMetric).filter(EvaluationMetric.job_id == job_id)

            if metric_types:
                query = query.filter(EvaluationMetric.metric_type.in_(metric_types))

            return query.order_by(desc(EvaluationMetric.created_at)).limit(limit).all()

        except Exception as e:
            logger.error(f"Error getting evaluation metrics: {e}")
            return []

    def _generate_summary_report(self, summary: Dict[str, Any]) -> str:
        """
        Generate a summary report from evaluation summary
        """
        try:
            job_info = summary.get("job_info", {})
            stats = summary.get("summary_statistics", {})

            report = f"""# Evaluation Report: {job_info.get('name', 'Unknown')}

## Executive Summary

This report summarizes the results of the RAG evaluation job "{job_info.get('name', 'Unknown')}" conducted on {job_info.get('created_at', 'Unknown')[:10]}.

### Key Metrics
- **Overall Score**: {summary.get('overall_score', 'N/A'):.3f}
- **Success Rate**: {summary.get('success_rate', 'N/A'):.1f}%
- **Total Metrics**: {summary.get('total_metrics', 0)}
- **Threshold Violations**: {summary.get('threshold_violations', 0)}

### Job Information
- **Status**: {job_info.get('status', 'Unknown')}
- **Evaluation Type**: {job_info.get('evaluation_type', 'Unknown')}
- **Dataset Size**: {job_info.get('dataset_size', 0)}
- **Processed Items**: {job_info.get('processed_count', 0)}
- **Duration**: {job_info.get('duration_seconds', 0):.2f} seconds

### Detailed Metrics Breakdown
"""

            # Add detailed metrics
            for metric_type, values in stats.items():
                report += f"""
#### {metric_type.replace('_', ' ').title()}
- **Count**: {values.get('count', 0)}
- **Mean**: {values.get('mean', 0):.3f}
- **Min**: {values.get('min', 0):.3f}
- **Max**: {values.get('max', 0):.3f}
- **Std Dev**: {values.get('std_dev', 0):.3f}
"""

            # Add recommendations based on results
            overall_score = summary.get("overall_score", 0)
            violations = summary.get("threshold_violations", 0)

            report += f"""
## Recommendations

"""

            if overall_score > 0.8:
                report += "- ✅ **Excellent Performance**: The RAG system is performing well with high overall scores.\n"
            elif overall_score > 0.6:
                report += "- ⚠️ **Good Performance**: The RAG system is performing adequately but has room for improvement.\n"
            else:
                report += "- ❌ **Poor Performance**: The RAG system needs significant improvements.\n"

            if violations > 0:
                report += f"- 🔍 **Threshold Violations**: {violations} metrics violated their configured thresholds. Consider reviewing these areas.\n"

            # Add specific metric recommendations
            if "rag_triad_answer_relevancy" in stats:
                relevancy_mean = stats["rag_triad_answer_relevancy"]["mean"]
                if relevancy_mean < 0.7:
                    report += "- 📝 **Answer Relevancy**: Consider improving answer generation or retrieval quality.\n"

            if "rag_triad_faithfulness" in stats:
                faithfulness_mean = stats["rag_triad_faithfulness"]["mean"]
                if faithfulness_mean < 0.7:
                    report += "- 🔗 **Faithfulness**: Answers may contain information not supported by context. Review answer generation.\n"

            if "rag_triad_contextual_relevancy" in stats:
                contextual_mean = stats["rag_triad_contextual_relevancy"]["mean"]
                if contextual_mean < 0.7:
                    report += "- 📚 **Contextual Relevancy**: Retrieved context may not be relevant to queries. Review search strategy.\n"

            report += f"""
## Conclusion

The evaluation shows {'strong' if overall_score > 0.7 else 'moderate' if overall_score > 0.5 else 'weak'} overall performance. Continue monitoring and iterating on the RAG system to improve quality metrics.

*Report generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*
"""

            return report

        except Exception as e:
            logger.error(f"Error generating summary report: {e}")
            return f"Error generating report: {str(e)}"

    def _generate_detailed_report(self, job_id: str, db: Session) -> str:
        """
        Generate a detailed report with individual metric analysis
        """
        try:
            # Get all metrics for the job
            metrics = (
                db.query(EvaluationMetric)
                .filter(EvaluationMetric.job_id == job_id)
                .order_by(EvaluationMetric.created_at)
                .all()
            )

            if not metrics:
                return "No metrics found for this evaluation job."

            # Group metrics by type
            metrics_by_type = {}
            for metric in metrics:
                metric_type = metric.metric_type
                if metric_type not in metrics_by_type:
                    metrics_by_type[metric_type] = []
                metrics_by_type[metric_type].append(metric)

            report = f"""# Detailed Evaluation Report

## Overview

This detailed report provides a comprehensive analysis of all metrics calculated during the evaluation job.

### Summary Statistics
- **Total Metrics**: {len(metrics)}
- **Metric Types**: {len(metrics_by_type)}

"""

            # Add detailed analysis for each metric type
            for metric_type, metric_list in metrics_by_type.items():
                values = [m.value for m in metric_list]
                avg_score = sum(values) / len(values)

                report += f"""
## {metric_type.replace('_', ' ').title()}

**Average Score**: {avg_score:.3f}
**Total Evaluations**: {len(metric_list)}

### Individual Results

| Query | Score | Threshold | Violation | Model Used |
|-------|-------|-----------|-----------|------------|
"""

                for metric in metric_list[:20]:  # Limit to top 20 for readability
                    query_preview = (
                        (metric.query or "")[:50] + "..."
                        if len(metric.query or "") > 50
                        else (metric.query or "")
                    )
                    threshold_info = (
                        f"{metric.threshold_min}-{metric.threshold_max}"
                        if metric.threshold_min is not None
                        else "N/A"
                    )
                    violation = "Yes" if metric.is_threshold_violation else "No"
                    model = (
                        metric.metadata.get("model_used", "Unknown")
                        if metric.metadata
                        else "Unknown"
                    )

                    report += f"| {query_preview} | {metric.value:.3f} | {threshold_info} | {violation} | {model} |\n"

                if len(metric_list) > 20:
                    report += f"| ... | ... | ... | ... | ... |\n*Showing 20 of {len(metric_list)} results*\n"

            # Add threshold violations analysis
            violations = [m for m in metrics if m.is_threshold_violation]
            if violations:
                report += f"""

## Threshold Violations Analysis

**Total Violations**: {len(violations)} ({(len(violations)/len(metrics))*100:.1f}%)

### Violations by Metric Type
"""
                violation_counts = {}
                for violation in violations:
                    violation_counts[violation.metric_type] = (
                        violation_counts.get(violation.metric_type, 0) + 1
                    )

                for metric_type, count in violation_counts.items():
                    report += f"- **{metric_type.replace('_', ' ').title()}**: {count} violations\n"

            report += f"""

## Recommendations

Based on the detailed analysis:

"""

            # Generate specific recommendations based on patterns
            for metric_type, metric_list in metrics_by_type.items():
                values = [m.value for m in metric_list]
                avg_score = sum(values) / len(values)

                if avg_score < 0.6:
                    if "answer_relevancy" in metric_type:
                        report += "- **Improve Answer Generation**: Consider refining the prompt engineering or context utilization in answer generation.\n"
                    elif "faithfulness" in metric_type:
                        report += "- **Enhance Context Grounding**: Ensure answers are more tightly grounded in retrieved context.\n"
                    elif "contextual_relevancy" in metric_type:
                        report += "- **Optimize Retrieval Strategy**: Review search queries, indexing, and ranking mechanisms.\n"
                    elif "hallucination" in metric_type:
                        report += "- **Reduce Hallucinations**: Implement stricter fact-checking and context validation.\n"

            report += f"""
*Report generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*
"""

            return report

        except Exception as e:
            logger.error(f"Error generating detailed report: {e}")
            return f"Error generating detailed report: {str(e)}"


# Global service instance
rag_evaluation_service = RAGEvaluationService()
