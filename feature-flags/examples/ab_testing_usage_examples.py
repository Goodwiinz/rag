"""
A/B Testing System Usage Examples

This file demonstrates how to use the A/B testing system for the Multimodal Enterprise RAG.
Examples include experiment setup, query routing, metrics collection, and analysis.
"""

import asyncio
import math
import random
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import uuid

# Example imports (adjust based on your actual import paths)
from src.models.ab_testing import (
    Experiment, Variant, ExperimentAssignment, ExperimentMetric,
    ExperimentType, TrafficSplitType, MetricType, StatisticalTest
)
from src.models.ab_testing_analytics import (
    StatisticalSignificance, AggregatedMetric, ExperimentDashboard
)
from src.config.ab_testing_config import get_config, get_high_volume_config
from src.models.ab_testing_optimization import (
    ABTestingCacheManager, ExperimentAssignmentOptimizer,
    MetricsAggregationOptimizer, DashboardOptimizer
)


# ==============================================================================
# Example 1: Creating a Search Algorithm A/B Test
# ==============================================================================

def create_search_algorithm_experiment():
    """
    Example: Create an A/B test to compare different search algorithms
    """
    print("🔬 Creating Search Algorithm A/B Test")
    print("=" * 50)

    # Create experiment
    experiment = Experiment(
        name="Hybrid Search vs Vector Search",
        description="Compare hybrid search performance against pure vector search",
        hypothesis="Hybrid search combining vector and keyword search will improve relevance scores by 15% compared to vector-only search",
        experiment_type=ExperimentType.SEARCH_ALGORITHM,
        traffic_split_type=TrafficSplitType.UNIFORM,
        traffic_percentage=50.0,  # Start with 50% traffic
        confidence_level=0.95,
        minimum_sample_size=2000,
        statistical_test=StatisticalTest.T_TEST,
        expected_effect_size=0.15,  # 15% improvement
        primary_metric=MetricType.RELEVANCE_SCORE,
        success_criteria="higher_is_better",
        target_improvement=15.0,  # 15% target improvement
        minimum_duration_days=7,
        organization_id=uuid.uuid4(),  # Your organization ID
        created_by=uuid.uuid4()       # User creating the experiment
    )

    # Add control variant (existing vector search)
    control_variant = Variant(
        name="Vector Search (Control)",
        description="Existing pure vector search implementation",
        is_control=True,
        weight=1.0,
        config={
            "algorithm": "vector_search",
            "parameters": {
                "embedding_model": "text-embedding-3-large",
                "similarity_threshold": 0.7,
                "max_results": 10,
                "reranking": False
            }
        }
    )

    # Add treatment variant (hybrid search)
    treatment_variant = Variant(
        name="Hybrid Search",
        description="New hybrid search combining vector and keyword search",
        is_control=False,
        weight=1.0,
        config={
            "algorithm": "hybrid_search",
            "parameters": {
                "vector_weight": 0.6,
                "keyword_weight": 0.4,
                "embedding_model": "text-embedding-3-large",
                "similarity_threshold": 0.7,
                "max_results": 10,
                "reranking": True,
                "reranking_model": "cross-encoder-ms-marco-MiniLM-L-6-v2"
            }
        }
    )

    experiment.variants = [control_variant, treatment_variant]

    print(f"✅ Created experiment: {experiment.name}")
    print(f"   📊 Hypothesis: {experiment.hypothesis}")
    print(f"   🎯 Primary Metric: {experiment.primary_metric.value}")
    print(f"   📈 Target Improvement: {experiment.target_improvement}%")
    print(f"   ⏱️  Minimum Duration: {experiment.minimum_duration_days} days")
    print(f"   📋 Variants: {[v.name for v in experiment.variants]}")

    return experiment


# ==============================================================================
# Example 2: User Assignment and Query Routing
# ==============================================================================

class QueryRouter:
    """
    Example implementation of query routing with A/B testing
    """

    def __init__(self):
        self.config = get_high_volume_config()
        # In a real implementation, you would inject these dependencies
        # self.cache_manager = ABTestingCacheManager(redis_client, self.config)
        # self.assignment_optimizer = ExperimentAssignmentOptimizer(cache_manager, db_session_factory)

    def route_query(self, user_id: str, query_text: str, organization_id: str) -> Dict[str, Any]:
        """
        Route a user query through the appropriate A/B test variant
        """
        print(f"🔀 Routing query for user {user_id[:8]}...")
        print(f"   Query: {query_text[:50]}...")

        # Step 1: Check if user is already assigned to active experiments
        user_assignments = self._get_user_assignments(user_id, organization_id)

        routing_results = []

        for assignment in user_assignments:
            variant = assignment.variant
            experiment = assignment.experiment

            # Step 2: Apply variant configuration to query
            search_config = variant.config
            search_results = self._execute_search(query_text, search_config)

            # Step 3: Record routing decision
            self._record_routing(user_id, experiment.id, variant.id, query_text)

            routing_results.append({
                "experiment_id": str(experiment.id),
                "experiment_name": experiment.name,
                "variant_name": variant.name,
                "is_control": variant.is_control,
                "search_config": search_config,
                "results": search_results
            })

            print(f"   ✅ Routed to experiment: {experiment.name}")
            print(f"   🎛️  Variant: {variant.name} {'(Control)' if variant.is_control else '(Treatment)'}")
            print(f"   📊 Found {len(search_results)} results")

        return routing_results

    def _get_user_assignments(self, user_id: str, organization_id: str) -> List[ExperimentAssignment]:
        """
        Get user's active experiment assignments
        In a real implementation, this would query the database with caching
        """
        # Mock implementation - would use optimized database query
        return []

    def _execute_search(self, query: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute search using the variant-specific configuration
        """
        # Mock search implementation
        start_time = time.time()

        # Simulate search based on algorithm type
        if config.get("algorithm") == "vector_search":
            # Simulate vector search results
            results = [
                {"id": f"doc_{i}", "score": 0.8 - (i * 0.05), "content": f"Document {i} content"}
                for i in range(5)
            ]
        elif config.get("algorithm") == "hybrid_search":
            # Simulate hybrid search with better relevance
            results = [
                {"id": f"doc_{i}", "score": 0.9 - (i * 0.03), "content": f"Document {i} content"}
                for i in range(8)
            ]
        else:
            results = []

        search_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        # Add search metadata
        for result in results:
            result["search_time_ms"] = search_time
            result["algorithm"] = config.get("algorithm")

        return results

    def _record_routing(self, user_id: str, experiment_id: str, variant_id: str, query: str):
        """
        Record the routing decision for analytics
        """
        # In a real implementation, this would be batched for performance
        routing_record = {
            "user_id": user_id,
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "query_text": query,
            "routing_timestamp": datetime.utcnow(),
            "processing_overhead_ms": 5  # Simulated routing overhead
        }

        # Would batch insert to database
        print(f"   📝 Recorded routing decision (overhead: {routing_record['processing_overhead_ms']}ms)")


# ==============================================================================
# Example 3: Metrics Collection and Real-time Analysis
# ==============================================================================

class MetricsCollector:
    """
    Example implementation of high-performance metrics collection
    """

    def __init__(self):
        self.metrics_buffer = []
        self.buffer_size = 1000

    def record_query_metrics(self, user_id: str, session_id: str, experiment_id: str,
                           variant_id: str, query_id: str, search_results: List[Dict]):
        """
        Record comprehensive metrics for a single query
        """
        base_metrics = {
            "user_id": user_id,
            "session_id": session_id,
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "query_id": query_id,
            "timestamp": datetime.utcnow()
        }

        # Extract different types of metrics
        metrics_to_record = []

        # Response time metric
        if search_results:
            response_time = search_results[0].get("search_time_ms", 0)
            metrics_to_record.append({
                **base_metrics,
                "metric_type": MetricType.RESPONSE_TIME,
                "metric_value": response_time,
                "metadata": {"algorithm": search_results[0].get("algorithm")}
            })

        # Relevance score metric (average of top 5 results)
        if len(search_results) >= 5:
            avg_relevance = sum(r.get("score", 0) for r in search_results[:5]) / 5
            metrics_to_record.append({
                **base_metrics,
                "metric_type": MetricType.RELEVANCE_SCORE,
                "metric_value": avg_relevance,
                "metadata": {"result_count": len(search_results)}
            })

        # Result count metric
        metrics_to_record.append({
            **base_metrics,
            "metric_type": MetricType.RESULT_COUNT,
            "metric_value": len(search_results),
            "metadata": {"algorithm": search_results[0].get("algorithm") if search_results else None}
        })

        # Add to buffer for batch processing
        self.metrics_buffer.extend(metrics_to_record)

        # Flush buffer if full (in production, this would be async)
        if len(self.metrics_buffer) >= self.buffer_size:
            self.flush_metrics()

        print(f"📊 Recorded {len(metrics_to_record)} metrics for query {query_id[:8]}")
        for metric in metrics_to_record:
            print(f"   {metric['metric_type'].value}: {metric['metric_value']:.3f}")

    def flush_metrics(self):
        """
        Flush metrics buffer to database
        """
        if not self.metrics_buffer:
            return

        print(f"💾 Flushing {len(self.metrics_buffer)} metrics to database...")

        # In a real implementation, this would use batch INSERT
        # and async processing for high performance
        for metric in self.metrics_buffer:
            # Would create ExperimentMetric objects and bulk insert
            pass

        self.metrics_buffer.clear()
        print("✅ Metrics flushed successfully")

    def record_user_feedback(self, user_id: str, experiment_id: str, variant_id: str,
                           satisfaction_rating: int, feedback_text: str = None):
        """
        Record user satisfaction feedback
        """
        feedback_metric = {
            "user_id": user_id,
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "metric_type": MetricType.USER_SATISFACTION,
            "metric_value": satisfaction_rating,
            "timestamp": datetime.utcnow(),
            "metadata": {"feedback_text": feedback_text} if feedback_text else {}
        }

        self.metrics_buffer.append(feedback_metric)
        print(f"👤 Recorded user feedback: {satisfaction_rating}/5 stars")

    def record_click_event(self, user_id: str, experiment_id: str, variant_id: str,
                         result_position: int, document_id: str):
        """
        Record user click on search result
        """
        click_metric = {
            "user_id": user_id,
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "metric_type": MetricType.CLICK_THROUGH_RATE,
            "metric_value": 1.0,  # Binary click event
            "timestamp": datetime.utcnow(),
            "metadata": {
                "result_position": result_position,
                "document_id": document_id
            }
        }

        self.metrics_buffer.append(click_metric)
        print(f"🖱️  Recorded click on result position {result_position}")


# ==============================================================================
# Example 4: Statistical Analysis and Reporting
# ==============================================================================

class ExperimentAnalyzer:
    """
    Example implementation of statistical analysis for A/B tests
    """

    def analyze_experiment_results(self, experiment_id: str) -> Dict[str, Any]:
        """
        Perform comprehensive statistical analysis of experiment results
        """
        print(f"📈 Analyzing experiment {experiment_id[:8]}...")
        print("=" * 50)

        # Step 1: Collect variant performance data
        variant_performance = self._collect_variant_data(experiment_id)

        print("📊 Variant Performance Summary:")
        for variant_id, data in variant_performance.items():
            print(f"   Variant {variant_id[:8]}:")
            print(f"     Sample Size: {data['sample_size']}")
            print(f"     Mean Relevance: {data['mean_relevance']:.3f}")
            print(f"     Mean Response Time: {data['mean_response_time']:.1f}ms")
            print(f"     Click Rate: {data['click_rate']:.2%}")

        # Step 2: Perform statistical significance test
        significance_results = self._calculate_statistical_significance(variant_performance)

        print(f"\n🧮 Statistical Significance Results:")
        print(f"   Test Type: {significance_results['test_type']}")
        print(f"   P-value: {significance_results['p_value']:.6f}")
        print(f"   Is Significant: {significance_results['is_significant']}")
        print(f"   Effect Size: {significance_results['effect_size']:.3f}")
        print(f"   Confidence Interval: [{significance_results['ci_lower']:.3f}, {significance_results['ci_upper']:.3f}]")

        # Step 3: Calculate business impact
        business_impact = self._calculate_business_impact(variant_performance, significance_results)

        print(f"\n💰 Business Impact Analysis:")
        print(f"   Estimated Revenue Impact: {business_impact['revenue_impact']:+.1%}")
        print(f"   User Satisfaction Impact: {business_impact['satisfaction_improvement']:+.1%}")
        print(f"   Recommendation: {business_impact['recommendation']}")

        # Step 4: Generate visualization data
        chart_data = self._prepare_visualization_data(variant_performance)

        return {
            "experiment_id": experiment_id,
            "variant_performance": variant_performance,
            "statistical_significance": significance_results,
            "business_impact": business_impact,
            "visualization_data": chart_data,
            "analysis_timestamp": datetime.utcnow()
        }

    def _collect_variant_data(self, experiment_id: str) -> Dict[str, Dict]:
        """
        Collect performance data for each variant
        """
        # Mock data collection - in reality, this would query the database
        mock_data = {
            "variant_1": {  # Control
                "sample_size": 2500,
                "mean_relevance": 0.723,
                "std_relevance": 0.156,
                "mean_response_time": 145.2,
                "std_response_time": 45.8,
                "click_rate": 0.34,
                "satisfaction_score": 3.8,
                "is_control": True
            },
            "variant_2": {  # Treatment
                "sample_size": 2480,
                "mean_relevance": 0.812,
                "std_relevance": 0.142,
                "mean_response_time": 167.3,
                "std_response_time": 52.1,
                "click_rate": 0.41,
                "satisfaction_score": 4.2,
                "is_control": False
            }
        }
        return mock_data

    def _calculate_statistical_significance(self, variant_data: Dict) -> Dict[str, Any]:
        """
        Calculate statistical significance between variants
        """
        variants = list(variant_data.keys())
        control = variant_data[variants[0]]
        treatment = variant_data[variants[1]]

        # Calculate two-sample t-test for relevance scores
        n1, n2 = control["sample_size"], treatment["sample_size"]
        mean1, mean2 = control["mean_relevance"], treatment["mean_relevance"]
        std1, std2 = control["std_relevance"], treatment["std_relevance"]

        # Pooled standard error
        pooled_se = math.sqrt((std1**2 / n1) + (std2**2 / n2))

        # T-statistic
        t_stat = (mean2 - mean1) / pooled_se

        # Approximate p-value (simplified)
        p_value = 0.001 if abs(t_stat) > 3.3 else 0.01 if abs(t_stat) > 2.6 else 0.05

        # Effect size (Cohen's d)
        pooled_std = math.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
        effect_size = (mean2 - mean1) / pooled_std if pooled_std > 0 else 0

        # Confidence interval
        margin_error = 1.96 * pooled_se
        ci_lower = (mean2 - mean1) - margin_error
        ci_upper = (mean2 - mean1) + margin_error

        return {
            "test_type": "two_sample_t_test",
            "t_statistic": t_stat,
            "p_value": p_value,
            "is_significant": p_value < 0.05,
            "effect_size": effect_size,
            "confidence_interval": (ci_lower, ci_upper),
            "ci_lower": ci_lower,
            "ci_upper": ci_upper
        }

    def _calculate_business_impact(self, variant_data: Dict, significance: Dict) -> Dict[str, Any]:
        """
        Calculate business impact metrics
        """
        variants = list(variant_data.keys())
        control = variant_data[variants[0]]
        treatment = variant_data[variants[1]]

        # Calculate relative improvements
        relevance_improvement = (treatment["mean_relevance"] - control["mean_relevance"]) / control["mean_relevance"]
        click_improvement = (treatment["click_rate"] - control["click_rate"]) / control["click_rate"]
        satisfaction_improvement = (treatment["satisfaction_score"] - control["satisfaction_score"]) / control["satisfaction_score"]

        # Estimated revenue impact (simplified model)
        revenue_impact = click_improvement * 0.8 + relevance_improvement * 0.2  # Weighted impact

        # Generate recommendation
        if significance["is_significant"] and revenue_impact > 0.05:  # 5% improvement threshold
            recommendation = "implement_immediately"
        elif significance["is_significant"] and revenue_impact > 0:
            recommendation = "consider_implementation"
        else:
            recommendation = "continue_testing"

        return {
            "relevance_improvement": relevance_improvement,
            "click_improvement": click_improvement,
            "satisfaction_improvement": satisfaction_improvement,
            "revenue_impact": revenue_impact,
            "recommendation": recommendation,
            "confidence_level": 0.95 if significance["is_significant"] else 0.5
        }

    def _prepare_visualization_data(self, variant_data: Dict) -> Dict[str, Any]:
        """
        Prepare data for dashboard visualizations
        """
        return {
            "comparison_chart": {
                "type": "bar_chart_with_error_bars",
                "data": [
                    {
                        "variant": "Control",
                        "relevance": variant_data["variant_1"]["mean_relevance"],
                        "response_time": variant_data["variant_1"]["mean_response_time"],
                        "click_rate": variant_data["variant_1"]["click_rate"]
                    },
                    {
                        "variant": "Treatment",
                        "relevance": variant_data["variant_2"]["mean_relevance"],
                        "response_time": variant_data["variant_2"]["mean_response_time"],
                        "click_rate": variant_data["variant_2"]["click_rate"]
                    }
                ]
            },
            "time_series": {
                "type": "line_chart",
                "data": "time_series_data_placeholder"  # Would contain actual time series data
            },
            "funnel_chart": {
                "type": "funnel_chart",
                "data": "funnel_data_placeholder"  # Would contain conversion funnel data
            }
        }


# ==============================================================================
# Example 5: Complete End-to-End Usage
# ==============================================================================

def run_complete_ab_test_example():
    """
    Example of complete A/B testing workflow
    """
    print("🚀 Starting Complete A/B Testing Example")
    print("=" * 60)

    # Step 1: Create experiment
    experiment = create_search_algorithm_experiment()

    # Step 2: Initialize components
    router = QueryRouter()
    metrics_collector = MetricsCollector()
    analyzer = ExperimentAnalyzer()

    # Step 3: Simulate user queries
    print("\n🔍 Simulating User Queries...")
    print("-" * 40)

    # Simulate multiple users and queries
    users = [f"user_{i}" for i in range(10)]
    queries = [
        "machine learning algorithms",
        "natural language processing",
        "vector databases",
        "semantic search techniques",
        "information retrieval systems"
    ]

    for user_id in users:
        for query in queries:
            # Route query through A/B testing system
            routing_results = router.route_query(user_id, query, experiment.organization_id)

            # Record metrics for each routing result
            for result in routing_results:
                if result["results"]:
                    metrics_collector.record_query_metrics(
                        user_id=user_id,
                        session_id=f"session_{user_id}",
                        experiment_id=result["experiment_id"],
                        variant_id=result["variant_id"],
                        query_id=f"query_{uuid.uuid4().hex[:8]}",
                        search_results=result["results"]
                    )

            # Simulate user feedback (randomly)
            if random.random() < 0.3:  # 30% of users provide feedback
                satisfaction = random.randint(3, 5)  # 3-5 stars
                metrics_collector.record_user_feedback(
                    user_id=user_id,
                    experiment_id=experiment.id,
                    variant_id=random.choice([v.id for v in experiment.variants]),
                    satisfaction_rating=satisfaction
                )

    # Step 4: Flush remaining metrics
    metrics_collector.flush_metrics()

    # Step 5: Analyze results
    print("\n📊 Analyzing Experiment Results...")
    print("-" * 40)

    analysis_results = analyzer.analyze_experiment_results(str(experiment.id))

    # Step 6: Display summary
    print("\n🎯 Experiment Summary")
    print("=" * 40)
    print(f"Experiment: {experiment.name}")
    print(f"Hypothesis: {experiment.hypothesis}")
    print(f"Total Queries Simulated: {len(users) * len(queries)}")
    print(f"Statistical Significance: {'✅ Significant' if analysis_results['statistical_significance']['is_significant'] else '❌ Not Significant'}")
    print(f"Business Impact: {analysis_results['business_impact']['recommendation']}")
    print(f"Revenue Impact: {analysis_results['business_impact']['revenue_impact']:+.1%}")

    print("\n🎉 A/B Testing Example Complete!")


if __name__ == "__main__":
    # Run the complete example
    run_complete_ab_test_example()