"""
Search Quality Evaluation Service for measuring RAG and search performance metrics
"""

import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.document import Document, ProcessingStatus
from src.models.search_schemas import (
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchType,
)

from .fulltext_search_service import fulltext_search_service
from .hybrid_search_service import hybrid_search_service
from .vector_search_service import vector_search_service

logger = logging.getLogger(__name__)


class QualityMetricType(Enum):
    """Types of quality metrics"""

    RELEVANCY = "relevancy"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    RESPONSE_TIME = "response_time"
    RESULT_DIVERSITY = "result_diversity"
    FACTUAL_ACCURACY = "factual_accuracy"
    CONTEXTUAL_PRECISION = "contextual_precision"
    USER_SATISFACTION = "user_satisfaction"


@dataclass
class QualityMetric:
    """Individual quality metric measurement"""

    metric_type: QualityMetricType
    value: float
    timestamp: datetime
    query: str
    search_type: SearchType
    result_count: int
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class SearchEvaluation:
    """Complete search evaluation results"""

    query_id: str
    query: str
    search_type: SearchType
    results: List[SearchResult]
    metrics: Dict[QualityMetricType, float]
    overall_score: float
    evaluation_time_ms: float
    timestamp: datetime
    recommendations: List[str]


class SearchQualityService:
    """Service for evaluating search quality and calculating metrics"""

    def __init__(self):
        self.metric_thresholds = {
            QualityMetricType.RELEVANCY: 0.7,
            QualityMetricType.PRECISION: 0.6,
            QualityMetricType.RECALL: 0.5,
            QualityMetricType.F1_SCORE: 0.6,
            QualityMetricType.RESPONSE_TIME: 2.0,  # seconds
            QualityMetricType.RESULT_DIVERSITY: 0.5,
            QualityMetricType.FACTUAL_ACCURACY: 0.8,
            QualityMetricType.CONTEXTUAL_PRECISION: 0.7,
            QualityMetricType.USER_SATISFACTION: 0.7,
        }

    def evaluate_search(
        self,
        search_query: SearchQuery,
        search_response: SearchResponse,
        user_id: str = None,
        organization_id: str = None,
        ground_truth_docs: List[str] = None,
    ) -> SearchEvaluation:
        """
        Evaluate search response quality using multiple metrics

        Args:
            search_query: Original search query
            search_response: Search response to evaluate
            user_id: User ID for tracking
            organization_id: Organization ID for tracking
            ground_truth_docs: Optional list of relevant document IDs

        Returns:
            SearchEvaluation with all metrics and recommendations
        """
        start_time = time.time()

        # Calculate individual metrics
        metrics = {}

        # Response time metric
        metrics[QualityMetricType.RESPONSE_TIME] = (
            search_response.search_time_ms / 1000.0
        )

        # Result diversity metric
        metrics[QualityMetricType.RESULT_DIVERSITY] = self._calculate_result_diversity(
            search_response.results
        )

        # Relevancy metric (simplified - uses position and scoring)
        metrics[QualityMetricType.RELEVANCY] = self._calculate_relevancy_score(
            search_response
        )

        # Precision@K metric
        metrics[QualityMetricType.PRECISION] = self._calculate_precision(
            search_response
        )

        # Recall metric (requires ground truth)
        if ground_truth_docs:
            metrics[QualityMetricType.RECALL] = self._calculate_recall(
                search_response, ground_truth_docs
            )
            metrics[QualityMetricType.F1_SCORE] = self._calculate_f1_score(
                metrics[QualityMetricType.PRECISION], metrics[QualityMetricType.RECALL]
            )

        # Contextual precision
        metrics[
            QualityMetricType.CONTEXTUAL_PRECISION
        ] = self._calculate_contextual_precision(search_query, search_response.results)

        # Calculate overall score
        overall_score = self._calculate_overall_score(metrics)

        # Generate recommendations
        recommendations = self._generate_recommendations(metrics)

        evaluation_time_ms = (time.time() - start_time) * 1000

        return SearchEvaluation(
            query_id=f"eval_{int(time.time())}",
            query=search_query.query,
            search_type=search_query.search_type,
            results=search_response.results,
            metrics=metrics,
            overall_score=overall_score,
            evaluation_time_ms=evaluation_time_ms,
            timestamp=datetime.utcnow(),
            recommendations=recommendations,
        )

    def _calculate_result_diversity(self, results: List[SearchResult]) -> float:
        """Calculate result diversity based on document types and content similarity"""
        if not results or len(results) < 2:
            return 0.0

        # Type diversity
        doc_types = [result.document_type.value for result in results]
        type_diversity = len(set(doc_types)) / len(doc_types)

        # Content diversity (simplified - uses title similarity)
        titles = [result.title.lower() for result in results if result.title]
        if len(titles) < 2:
            return type_diversity

        # Calculate word overlap between titles
        unique_words = set()
        for title in titles:
            words = set(title.split())
            unique_words.update(words)

        total_unique_words = len(unique_words)
        total_words = sum(len(title.split()) for title in titles)

        if total_words == 0:
            return type_diversity

        content_diversity = total_unique_words / total_words

        # Combine type and content diversity
        return (type_diversity + content_diversity) / 2.0

    def _calculate_relevancy_score(self, search_response: SearchResponse) -> float:
        """Calculate relevancy score based on result positions and scores"""
        if not search_response.results:
            return 0.0

        # Use position-based discounting
        total_score = 0.0
        for i, result in enumerate(search_response.results[:10]):  # Top 10 results
            position_discount = 1.0 / (i + 1)  # Discount factor based on position
            normalized_score = min(
                result.relevance_score / 50.0, 1.0
            )  # Normalize to 0-1
            total_score += normalized_score * position_discount

        # Normalize by number of results
        max_possible_score = sum(
            1.0 / (i + 1) for i in range(min(len(search_response.results), 10))
        )
        return total_score / max_possible_score if max_possible_score > 0 else 0.0

    def _calculate_precision(self, search_response: SearchResponse) -> float:
        """Calculate precision@K using result scores as relevance indicators"""
        if not search_response.results:
            return 0.0

        # Consider results with score above threshold as relevant
        relevant_count = 0
        threshold = 0.3  # Relevance threshold

        for result in search_response.results:
            if result.relevance_score >= threshold:
                relevant_count += 1

        return relevant_count / len(search_response.results)

    def _calculate_recall(
        self, search_response: SearchResponse, ground_truth_docs: List[str]
    ) -> float:
        """Calculate recall using ground truth documents"""
        if not ground_truth_docs:
            return 0.0

        found_relevant = 0
        result_ids = [result.document_id for result in search_response.results]

        for doc_id in ground_truth_docs:
            if doc_id in result_ids:
                found_relevant += 1

        return found_relevant / len(ground_truth_docs)

    def _calculate_f1_score(self, precision: float, recall: float) -> float:
        """Calculate F1 score from precision and recall"""
        if precision + recall == 0:
            return 0.0
        return 2 * (precision * recall) / (precision + recall)

    def _calculate_contextual_precision(
        self, search_query: SearchQuery, results: List[SearchResult]
    ) -> float:
        """Calculate contextual precision - how well results match query context"""
        if not results:
            return 0.0

        query_terms = set(search_query.query.lower().split())
        total_matches = 0
        total_checks = 0

        for result in results[:5]:  # Check top 5 results
            if result.title or result.content_preview:
                # Check term overlap with title and content
                text_to_check = (
                    f"{result.title or ''} {result.content_preview or ''}".lower()
                )
                text_terms = set(text_to_check.split())

                # Calculate overlap
                overlap = query_terms.intersection(text_terms)
                if len(query_terms) > 0:
                    match_ratio = len(overlap) / len(query_terms)
                    total_matches += match_ratio
                    total_checks += 1

        return total_matches / total_checks if total_checks > 0 else 0.0

    def _calculate_overall_score(
        self, metrics: Dict[QualityMetricType, float]
    ) -> float:
        """Calculate overall quality score from individual metrics"""
        weights = {
            QualityMetricType.RELEVANCY: 0.3,
            QualityMetricType.PRECISION: 0.2,
            QualityMetricType.RECALL: 0.15,
            QualityMetricType.F1_SCORE: 0.1,
            QualityMetricType.RESPONSE_TIME: 0.1,
            QualityMetricType.RESULT_DIVERSITY: 0.1,
            QualityMetricType.CONTEXTUAL_PRECISION: 0.05,
        }

        weighted_sum = 0.0
        total_weight = 0.0

        for metric_type, weight in weights.items():
            if metric_type in metrics:
                # Normalize response time (lower is better)
                if metric_type == QualityMetricType.RESPONSE_TIME:
                    normalized_value = max(
                        0,
                        1
                        - (metrics[metric_type] / self.metric_thresholds[metric_type]),
                    )
                else:
                    normalized_value = min(
                        metrics[metric_type] / self.metric_thresholds[metric_type], 1.0
                    )

                weighted_sum += normalized_value * weight
                total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _generate_recommendations(
        self, metrics: Dict[QualityMetricType, float]
    ) -> List[str]:
        """Generate improvement recommendations based on metrics"""
        recommendations = []

        for metric_type, value in metrics.items():
            threshold = self.metric_thresholds.get(metric_type, 0.5)

            if metric_type == QualityMetricType.RESPONSE_TIME and value > threshold:
                recommendations.append(
                    f"Response time ({value:.2f}s) exceeds threshold ({threshold:.2f}s). Consider optimizing search queries or adding caching."
                )

            elif metric_type != QualityMetricType.RESPONSE_TIME and value < threshold:
                metric_name = metric_type.value.replace("_", " ").title()
                recommendations.append(
                    f"{metric_name} ({value:.3f}) below threshold ({threshold:.3f}). Consider improving search algorithms or result ranking."
                )

        # Add general recommendations based on overall performance
        if len(recommendations) == 0:
            recommendations.append(
                "Search quality is meeting all thresholds. Continue monitoring for sustained performance."
            )
        elif len(recommendations) > 3:
            recommendations.append(
                "Multiple quality metrics are below thresholds. Consider comprehensive search system optimization."
            )

        return recommendations

    def record_user_feedback(
        self,
        query_id: str,
        user_id: str,
        rating: int,  # 1-5 scale
        feedback_text: str = None,
        document_id: str = None,
    ) -> QualityMetric:
        """Record user feedback as a quality metric"""
        # Convert rating to 0-1 scale
        normalized_rating = (rating - 1) / 4.0

        metric = QualityMetric(
            metric_type=QualityMetricType.USER_SATISFACTION,
            value=normalized_rating,
            timestamp=datetime.utcnow(),
            query=query_id,
            search_type=SearchType.HYBRID,  # Default to hybrid
            result_count=1,
            user_id=user_id,
            metadata={
                "rating": rating,
                "feedback_text": feedback_text,
                "document_id": document_id,
            },
        )

        # Store metric in database
        self._store_metric(metric)
        return metric

    def get_quality_analytics(
        self, organization_id: str, days: int = 30, search_type: SearchType = None
    ) -> Dict[str, Any]:
        """Get quality analytics for a specific organization"""
        try:
            with next(get_db()) as db:
                # This would query a quality_metrics table
                # For now, return mock analytics

                analytics = {
                    "period_days": days,
                    "organization_id": organization_id,
                    "search_type": search_type.value if search_type else "all",
                    "total_evaluations": 0,
                    "average_metrics": {},
                    "trends": {},
                    "threshold_violations": [],
                    "top_improvements": [],
                }

                # Mock data for demonstration
                if search_type is None or search_type == SearchType.HYBRID:
                    analytics["total_evaluations"] = 150
                    analytics["average_metrics"] = {
                        "relevancy": 0.82,
                        "precision": 0.75,
                        "recall": 0.68,
                        "f1_score": 0.71,
                        "response_time": 1.45,
                        "result_diversity": 0.73,
                        "contextual_precision": 0.78,
                        "user_satisfaction": 0.85,
                    }
                    analytics["threshold_violations"] = [
                        {"metric": "recall", "current_value": 0.68, "threshold": 0.7}
                    ]
                    analytics["top_improvements"] = [
                        "Improve recall by expanding document indexing",
                        "Optimize query understanding for complex questions",
                        "Enhance result ranking for better relevance",
                    ]

                return analytics

        except Exception as e:
            logger.error(f"Error getting quality analytics: {e}")
            return {"error": str(e)}

    def _store_metric(self, metric: QualityMetric):
        """Store quality metric in database"""
        try:
            # This would insert into a quality_metrics table
            # For now, just log the metric
            logger.info(
                f"Storing quality metric: {metric.metric_type.value} = {metric.value:.3f}"
            )
        except Exception as e:
            logger.error(f"Error storing quality metric: {e}")

    def run_quality_benchmark(
        self,
        test_queries: List[str],
        search_types: List[SearchType] = None,
        organization_id: str = None,
    ) -> Dict[str, Dict[str, SearchEvaluation]]:
        """Run comprehensive quality benchmark on test queries"""
        if search_types is None:
            search_types = [SearchType.FULLTEXT, SearchType.VECTOR, SearchType.HYBRID]

        benchmark_results = {}

        for query in test_queries:
            query_results = {}

            for search_type in search_types:
                # Create search query
                search_query = SearchQuery(
                    query=query, search_type=search_type, limit=10
                )

                # Execute search
                start_time = time.time()
                try:
                    if search_type == SearchType.HYBRID:
                        search_response = hybrid_search_service.search(
                            search_request=search_query,
                            user_id="benchmark_user",
                            organization_id=organization_id,
                        )
                    elif search_type == SearchType.FULLTEXT:
                        search_response = fulltext_search_service.search(
                            search_request=search_query,
                            user_id="benchmark_user",
                            organization_id=organization_id,
                        )
                    elif search_type == SearchType.VECTOR:
                        search_response = vector_search_service.search(
                            search_request=search_query,
                            user_id="benchmark_user",
                            organization_id=organization_id,
                        )
                    else:
                        continue

                    # Evaluate search quality
                    evaluation = self.evaluate_search(
                        search_query=search_query,
                        search_response=search_response,
                        user_id="benchmark_user",
                        organization_id=organization_id,
                    )

                    query_results[search_type.value] = evaluation

                except Exception as e:
                    logger.error(
                        f"Error benchmarking query '{query}' with {search_type.value}: {e}"
                    )
                    continue

            benchmark_results[query] = query_results

        return benchmark_results


# Global search quality service instance
search_quality_service = SearchQualityService()
