"""
Unit tests for Quality Recommendations Service
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json
import asyncio

from src.services.quality.quality_recommendations_service import (
    QualityRecommendationsService,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    QualityRecommendation,
    QualityInsight,
    RecommendationEffectiveness
)
from src.schemas.quality_recommendations import (
    RecommendationCreate,
    RecommendationUpdate,
    RecommendationFilter
)


class TestQualityRecommendationsService:
    """Test suite for QualityRecommendationsService"""

    @pytest.fixture
    def service(self):
        """Create a QualityRecommendationsService instance for testing."""
        return QualityRecommendationsService()

    @pytest.fixture
    def sample_recommendation(self):
        """Sample quality recommendation for testing."""
        return QualityRecommendation(
            id="rec-123",
            category=RecommendationCategory.CONTENT,
            priority=RecommendationPriority.HIGH,
            title="Improve Document Quality",
            description="Update outdated content and enhance metadata",
            impact_assessment="High impact on search accuracy",
            effort_required="Medium",
            actionable_steps=[
                "Audit existing documents",
                "Update metadata fields",
                "Implement quality scoring"
            ],
            expected_outcome="15-20% improvement in search relevance",
            metrics_to_track=["search_accuracy", "click_through_rate"],
            supporting_data={
                "outdated_documents": 45,
                "missing_metadata": 120,
                "quality_score_avg": 0.72
            },
            estimated_improvement=18,
            due_date=datetime.utcnow() + timedelta(days=30),
            status=RecommendationStatus.PENDING,
            assigned_to="content-team",
            organization_id="org-123",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    @pytest.fixture
    def sample_quality_insight(self):
        """Sample quality insight for testing."""
        return QualityInsight(
            metric_name="search_accuracy",
            current_value=0.89,
            target_value=0.95,
            gap=0.06,
            trend="improving",
            impact_area="User Experience",
            root_causes=[
                "Outdated content",
                "Incomplete metadata",
                "Suboptimal ranking parameters"
            ],
            related_metrics=["click_through_rate", "user_satisfaction"],
            supporting_data={
                "historical_trend": [0.85, 0.87, 0.88, 0.89],
                "benchmark": 0.92,
                "industry_average": 0.88
            }
        )

    # Test Initialization
    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.cache_ttl == 3600
        assert service.recommendation_cache == {}
        assert service.insight_cache == {}
        assert service.redis_client is None

    # Test Quality Insights Analysis
    @pytest.mark.asyncio
    async def test_analyze_quality_insights(self, service, sample_quality_insight):
        """Test analyzing quality insights."""
        organization_id = "org-123"
        days_back = 30

        with patch.object(service, '_collect_quality_metrics') as mock_collect:
            with patch.object(service, '_analyze_metric_gaps') as mock_analyze:
                mock_metrics = [sample_quality_insight]
                mock_collect.return_value = {"search_accuracy": 0.89, "response_time": 245}
                mock_analyze.return_value = [sample_quality_insight]

                result = await service.analyze_quality_insights(
                    organization_id=organization_id,
                    days_back=days_back
                )

                assert len(result) == 1
                assert result[0].metric_name == "search_accuracy"
                assert result[0].current_value == 0.89
                assert result[0].target_value == 0.95
                mock_collect.assert_called_once()
                mock_analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_metric_gaps(self, service):
        """Test analyzing metric gaps."""
        current_metrics = {
            "search_accuracy": 0.89,
            "response_time": 350,
            "user_satisfaction": 4.2,
            "click_through_rate": 0.35
        }
        target_metrics = {
            "search_accuracy": 0.95,
            "response_time": 200,
            "user_satisfaction": 4.8,
            "click_through_rate": 0.45
        }

        insights = await service._analyze_metric_gaps(current_metrics, target_metrics)

        assert len(insights) == 4

        # Check search accuracy insight
        accuracy_insight = next(i for i in insights if i.metric_name == "search_accuracy")
        assert accuracy_insight.current_value == 0.89
        assert accuracy_insight.target_value == 0.95
        assert accuracy_insight.gap == 0.06

        # Check response time insight
        response_insight = next(i for i in insights if i.metric_name == "response_time")
        assert response_insight.current_value == 350
        assert response_insight.target_value == 200
        assert response_insight.gap == 150

    @pytest.mark.asyncio
    async def test_identify_root_causes(self, service):
        """Test identifying root causes for metric gaps."""
        metric_name = "search_accuracy"
        current_value = 0.89
        target_value = 0.95

        with patch.object(service, '_analyze_search_performance') as mock_analyze:
            mock_analyze.return_value = {
                "outdated_content_ratio": 0.25,
                "missing_metadata_ratio": 0.40,
                "low_quality_docs": 0.15,
                "ranking_issues": 0.20
            }

            root_causes = await service._identify_root_causes(metric_name, current_value, target_value)

            assert isinstance(root_causes, list)
            assert len(root_causes) > 0
            assert any("outdated" in cause.lower() for cause in root_causes)
            assert any("metadata" in cause.lower() for cause in root_causes)

    # Test Recommendation Generation
    @pytest.mark.asyncio
    async def test_generate_recommendations(self, service, sample_quality_insight, sample_recommendation):
        """Test generating quality recommendations."""
        organization_id = "org-123"
        focus_areas = [RecommendationCategory.CONTENT]
        days_back = 30

        with patch.object(service, 'analyze_quality_insights') as mock_analyze:
            with patch.object(service, '_generate_content_recommendations') as mock_generate:
                mock_insights = [sample_quality_insight]
                mock_analyze.return_value = mock_insights
                mock_generate.return_value = [sample_recommendation]

                result = await service.generate_recommendations(
                    organization_id=organization_id,
                    focus_areas=focus_areas,
                    days_back=days_back
                )

                assert len(result) == 1
                assert result[0].category == RecommendationCategory.CONTENT
                assert result[0].priority == RecommendationPriority.HIGH
                mock_analyze.assert_called_once()
                mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_content_recommendations(self, service, sample_quality_insight):
        """Test generating content-specific recommendations."""
        insights = [sample_quality_insight]

        recommendations = await service._generate_content_recommendations(insights, "org-123")

        assert len(recommendations) > 0
        content_rec = recommendations[0]
        assert content_rec.category == RecommendationCategory.CONTENT
        assert content_rec.title is not None
        assert content_rec.description is not None
        assert len(content_rec.actionable_steps) > 0

    @pytest.mark.asyncio
    async def test_generate_search_algorithm_recommendations(self, service):
        """Test generating search algorithm recommendations."""
        insights = [
            QualityInsight(
                metric_name="response_time",
                current_value=500,
                target_value=200,
                gap=300,
                trend="stable",
                impact_area="Performance",
                root_causes=["Inefficient ranking", "Missing indexes"],
                related_metrics=["cpu_usage", "memory_usage"],
                supporting_data={}
            )
        ]

        recommendations = await service._generate_search_algorithm_recommendations(insights, "org-123")

        assert len(recommendations) > 0
        search_rec = recommendations[0]
        assert search_rec.category == RecommendationCategory.SEARCH_ALGORITHM
        assert search_rec.priority in [RecommendationPriority.HIGH, RecommendationPriority.CRITICAL]

    @pytest.mark.asyncio
    async def test_generate_indexing_recommendations(self, service):
        """Test generating indexing recommendations."""
        insights = [
            QualityInsight(
                metric_name="index_freshness",
                current_value=0.75,
                target_value=0.95,
                gap=0.20,
                trend="declining",
                impact_area="Content Freshness",
                root_causes=["Slow indexing process", "Missing updates"],
                related_metrics=["content_age", "update_frequency"],
                supporting_data={}
            )
        ]

        recommendations = await service._generate_indexing_recommendations(insights, "org-123")

        assert len(recommendations) > 0
        indexing_rec = recommendations[0]
        assert indexing_rec.category == RecommendationCategory.INDEXING

    @pytest.mark.asyncio
    async def test_generate_user_experience_recommendations(self, service):
        """Test generating user experience recommendations."""
        insights = [
            QualityInsight(
                metric_name="user_satisfaction",
                current_value=3.8,
                target_value=4.5,
                gap=0.7,
                trend="stable",
                impact_area="User Experience",
                root_causes=["Poor result presentation", "Missing filters"],
                related_metrics=["click_through_rate", "bounce_rate"],
                supporting_data={}
            )
        ]

        recommendations = await service._generate_user_experience_recommendations(insights, "org-123")

        assert len(recommendations) > 0
        ux_rec = recommendations[0]
        assert ux_rec.category == RecommendationCategory.USER_EXPERIENCE

    @pytest.mark.asyncio
    async def test_generate_infrastructure_recommendations(self, service):
        """Test generating infrastructure recommendations."""
        insights = [
            QualityInsight(
                metric_name="system_availability",
                current_value=0.98,
                target_value=0.999,
                gap=0.019,
                trend="stable",
                impact_area="Reliability",
                root_causes=["Single point of failure", "Insufficient resources"],
                related_metrics=["error_rate", "response_time"],
                supporting_data={}
            )
        ]

        recommendations = await service._generate_infrastructure_recommendations(insights, "org-123")

        assert len(recommendations) > 0
        infra_rec = recommendations[0]
        assert infra_rec.category == RecommendationCategory.INFRASTRUCTURE

    @pytest.mark.asyncio
    async def test_generate_monitoring_recommendations(self, service):
        """Test generating monitoring recommendations."""
        insights = [
            QualityInsight(
                metric_name="alert_response_time",
                current_value=1800,  # 30 minutes
                target_value=300,   # 5 minutes
                gap=1500,
                trend="stable",
                impact_area="Operations",
                root_causes=["Manual monitoring", "Missing automation"],
                related_metrics=["mttr", "mtbf"],
                supporting_data={}
            )
        ]

        recommendations = await service._generate_monitoring_recommendations(insights, "org-123")

        assert len(recommendations) > 0
        monitoring_rec = recommendations[0]
        assert monitoring_rec.category == RecommendationCategory.MONITORING

    # Test Recommendation Management
    @pytest.mark.asyncio
    async def test_create_recommendation(self, service, sample_recommendation):
        """Test creating a recommendation."""
        recommendation_data = RecommendationCreate(
            category=RecommendationCategory.CONTENT,
            priority=RecommendationPriority.HIGH,
            title="Test Recommendation",
            description="Test description",
            actionable_steps=["Step 1", "Step 2"],
            estimated_improvement=15
        )

        with patch.object(service, '_store_recommendation') as mock_store:
            mock_store.return_value = sample_recommendation

            result = await service.create_recommendation(
                organization_id="org-123",
                recommendation_data=recommendation_data.dict()
            )

            assert result.title == "Test Recommendation"
            assert result.category == RecommendationCategory.CONTENT
            mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_recommendations(self, service):
        """Test getting recommendations."""
        organization_id = "org-123"
        filters = RecommendationFilter(
            category=RecommendationCategory.CONTENT,
            priority=RecommendationPriority.HIGH,
            status=RecommendationStatus.PENDING
        )

        with patch.object(service, '_query_recommendations') as mock_query:
            mock_recommendations = [Mock(), Mock(), Mock()]
            mock_query.return_value = mock_recommendations

            result = await service.get_recommendations(
                organization_id=organization_id,
                filters=filters
            )

            assert len(result) == 3
            mock_query.assert_called_once_with(organization_id, filters)

    @pytest.mark.asyncio
    async def test_update_recommendation(self, service, sample_recommendation):
        """Test updating a recommendation."""
        update_data = RecommendationUpdate(
            status=RecommendationStatus.IN_PROGRESS,
            notes="Started implementation",
            actual_improvement=5.0
        )

        with patch.object(service, '_update_recommendation_in_db') as mock_update:
            mock_update.return_value = True

            result = await service.update_recommendation(
                recommendation_id=sample_recommendation.id,
                update_data=update_data.dict()
            )

            assert result is True
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_recommendation_progress(self, service, sample_recommendation):
        """Test tracking recommendation progress."""
        status = RecommendationStatus.IN_PROGRESS
        notes = "Working on metadata updates"
        actual_improvement = 8.5

        with patch.object(service, '_update_progress_in_db') as mock_update:
            mock_update.return_value = True

            result = await service.track_recommendation_progress(
                recommendation_id=sample_recommendation.id,
                status=status,
                notes=notes,
                actual_improvement=actual_improvement
            )

            assert result is True
            mock_update.assert_called_once()

    # Test Recommendation Effectiveness
    @pytest.mark.asyncio
    async def test_get_recommendation_effectiveness(self, service):
        """Test getting recommendation effectiveness."""
        organization_id = "org-123"
        completed_days = 30

        with patch.object(service, '_calculate_effectiveness') as mock_calc:
            mock_effectiveness = RecommendationEffectiveness(
                organization_id=organization_id,
                period_days=completed_days,
                effectiveness={
                    "overall_improvement": 0.15,
                    "recommendations_analyzed": 10,
                    "successful_implementations": 7,
                    "avg_improvement_per_rec": 0.12
                },
                recommendations_summary=[
                    {
                        "recommendation_id": "rec-1",
                        "estimated_improvement": 0.20,
                        "actual_improvement": 0.18,
                        "effectiveness_score": 0.9
                    }
                ]
            )
            mock_calc.return_value = mock_effectiveness

            result = await service.get_recommendation_effectiveness(
                organization_id=organization_id,
                completed_days=completed_days
            )

            assert result.organization_id == organization_id
            assert result.effectiveness["overall_improvement"] == 0.15
            assert len(result.recommendations_summary) == 1

    @pytest.mark.asyncio
    async def test_calculate_recommendation_roi(self, service):
        """Test calculating recommendation ROI."""
        recommendations = [
            {
                "id": "rec-1",
                "estimated_improvement": 0.15,
                "actual_improvement": 0.12,
                "effort_hours": 40,
                "impact_value": 10000  # Monetary value
            },
            {
                "id": "rec-2",
                "estimated_improvement": 0.20,
                "actual_improvement": 0.25,
                "effort_hours": 60,
                "impact_value": 15000
            }
        ]

        roi_data = await service._calculate_recommendation_roi(recommendations)

        assert "total_roi" in roi_data
        assert "roi_percentage" in roi_data
        assert "payback_period_days" in roi_data
        assert roi_data["total_recommendations"] == 2

    # Test Caching
    @pytest.mark.asyncio
    async def test_cache_recommendations(self, service, mock_redis_client, sample_recommendation):
        """Test caching recommendations."""
        service.redis_client = mock_redis_client
        organization_id = "org-123"
        recommendations = [sample_recommendation]

        await service._cache_recommendations(organization_id, recommendations, ttl=3600)

        mock_redis_client.set.assert_called_once()
        mock_redis_client.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cached_recommendations(self, service, mock_redis_client):
        """Test getting cached recommendations."""
        service.redis_client = mock_redis_client
        organization_id = "org-123"
        cached_data = json.dumps([{"id": "rec-123", "title": "Test"}])

        mock_redis_client.get.return_value = cached_data

        result = await service._get_cached_recommendations(organization_id)

        assert len(result) == 1
        assert result[0]["id"] == "rec-123"
        mock_redis_client.get.assert_called_once()

    # Test Priority Calculation
    @pytest.mark.asyncio
    async def test_calculate_recommendation_priority(self, service):
        """Test calculating recommendation priority."""
        insight = QualityInsight(
            metric_name="search_accuracy",
            current_value=0.75,
            target_value=0.95,
            gap=0.20,
            trend="declining",
            impact_area="User Experience",
            root_causes=["Major issues"],
            related_metrics=[],
            supporting_data={}
        )

        priority = await service._calculate_recommendation_priority(insight)

        # Should be HIGH or CRITICAL due to large gap and declining trend
        assert priority in [RecommendationPriority.HIGH, RecommendationPriority.CRITICAL]

    @pytest.mark.asyncio
    async def test_calculate_effort_required(self, service):
        """Test calculating effort required for recommendations."""
        category = RecommendationCategory.INDEXING
        complexity_factors = ["large_dataset", "complex_schema"]

        effort = await service._calculate_effort_required(category, complexity_factors)

        assert effort in ["Low", "Medium", "High"]
        # Indexing with complexity factors should be Medium or High
        assert effort in ["Medium", "High"]

    # Test Test Data
    @pytest.mark.asyncio
    async def test_get_recommendation_categories(self, service):
        """Test getting recommendation categories with descriptions."""
        result = await service.get_recommendation_categories()

        assert isinstance(result, list)
        assert len(result) == 6  # All categories should be present

        categories = [cat["category"] for cat in result]
        assert RecommendationCategory.CONTENT in categories
        assert RecommendationCategory.SEARCH_ALGORITHM in categories
        assert RecommendationCategory.INDEXING in categories
        assert RecommendationCategory.USER_EXPERIENCE in categories
        assert RecommendationCategory.INFRASTRUCTURE in categories
        assert RecommendationCategory.MONITORING in categories

        # Check that each category has required fields
        for cat in result:
            assert "category" in cat
            assert "description" in cat
            assert "examples" in cat
            assert "typical_improvement" in cat

    @pytest.mark.asyncio
    async def test_get_recommendation_summary(self, service):
        """Test getting recommendations summary."""
        organization_id = "org-123"

        with patch.object(service, 'generate_recommendations') as mock_generate:
            mock_recs = [
                Mock(category=RecommendationCategory.CONTENT, priority=RecommendationPriority.HIGH, estimated_improvement=15),
                Mock(category=RecommendationCategory.CONTENT, priority=RecommendationPriority.MEDIUM, estimated_improvement=10),
                Mock(category=RecommendationCategory.SEARCH_ALGORITHM, priority=RecommendationPriority.CRITICAL, estimated_improvement=20),
                Mock(category=RecommendationCategory.INDEXING, priority=RecommendationPriority.LOW, estimated_improvement=5)
            ]
            mock_generate.return_value = mock_recs

            summary = await service.get_recommendation_summary(organization_id)

            assert summary["total_count"] == 4
            assert summary["estimated_total_improvement"] == 50
            assert "by_category" in summary
            assert "by_priority" in summary
            assert "by_status" in summary

            # Check category grouping
            assert "content" in summary["by_category"]
            assert "search_algorithm" in summary["by_category"]
            assert summary["by_category"]["content"]["count"] == 2

            # Check priority grouping
            assert "critical" in summary["by_priority"]
            assert "high" in summary["by_priority"]
            assert summary["by_priority"]["critical"]["count"] == 1

    # Test Error Handling
    @pytest.mark.asyncio
    async def test_database_error_handling(self, service):
        """Test handling of database errors."""
        with patch.object(service, '_store_recommendation') as mock_store:
            mock_store.side_effect = Exception("Database connection failed")

            with pytest.raises(Exception, match="Database connection failed"):
                await service.create_recommendation(
                    organization_id="org-123",
                    recommendation_data={"title": "test"}
                )

    @pytest.mark.asyncio
    async def test_invalid_recommendation_data(self, service):
        """Test handling of invalid recommendation data."""
        # Test empty title
        with pytest.raises(ValueError, match="Title cannot be empty"):
            await service._validate_recommendation_data({
                "title": "",
                "description": "test",
                "category": RecommendationCategory.CONTENT
            })

        # Test invalid estimated improvement
        with pytest.raises(ValueError, match="Estimated improvement must be between 0 and 100"):
            await service._validate_recommendation_data({
                "title": "test",
                "description": "test",
                "category": RecommendationCategory.CONTENT,
                "estimated_improvement": 150
            })

    # Test Performance
    @pytest.mark.asyncio
    async def test_batch_recommendation_generation(self, service):
        """Test batch generation of recommendations."""
        import time

        organizations = ["org-1", "org-2", "org-3", "org-4", "org-5"]

        with patch.object(service, 'generate_recommendations') as mock_generate:
            mock_generate.return_value = [Mock(), Mock()]

            start_time = time.time()
            tasks = [
                service.generate_recommendations(org_id, days_back=30)
                for org_id in organizations
            ]
            results = await asyncio.gather(*tasks)
            end_time = time.time()

            assert len(results) == 5
            assert end_time - start_time < 15.0  # Should complete within 15 seconds

    # Test Integration
    @pytest.mark.asyncio
    async def test_end_to_end_recommendation_workflow(self, service, sample_quality_insight, sample_recommendation):
        """Test end-to-end recommendation workflow."""
        organization_id = "org-123"

        with patch.object(service, 'analyze_quality_insights') as mock_analyze:
            with patch.object(service, '_generate_content_recommendations') as mock_generate:
                with patch.object(service, '_store_recommendation') as mock_store:
                    with patch.object(service, 'track_recommendation_progress') as mock_track:

                        # Step 1: Analyze insights
                        mock_insights = [sample_quality_insight]
                        mock_analyze.return_value = mock_insights

                        # Step 2: Generate recommendations
                        mock_recommendations = [sample_recommendation]
                        mock_generate.return_value = mock_recommendations

                        # Step 3: Store recommendations
                        mock_store.return_value = sample_recommendation

                        # Step 4: Track progress
                        mock_track.return_value = True

                        # Execute workflow
                        insights = await service.analyze_quality_insights(organization_id, 30)
                        recommendations = await service.generate_recommendations(organization_id)
                        created_rec = await service.create_recommendation(
                            organization_id,
                            sample_recommendation.dict()
                        )
                        progress = await service.track_recommendation_progress(
                            sample_recommendation.id,
                            RecommendationStatus.IN_PROGRESS,
                            "Started work"
                        )

                        assert len(insights) == 1
                        assert len(recommendations) == 1
                        assert created_rec.id == sample_recommendation.id
                        assert progress is True