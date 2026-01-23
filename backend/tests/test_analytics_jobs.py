"""
Tests for analytics background job processing system
Validates job creation, processing, and aggregation functionality
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from src.tasks.analytics_processor import (
    AnalyticsJobProcessor, AnalyticsJobType, AnalyticsJobConfig,
    AnalyticsDataAggregator
)
from src.tasks.data_aggregator import (
    AnalyticsDataAggregator, AggregationConfig, AggregationGranularity,
    MetricType
)
from src.tasks.recommendation_generator import (
    AnalyticsRecommendationGenerator, RecommendationType,
    RecommendationPriority
)
from src.models.processing import ProcessingJob, JobStatus, JobPriority


class TestAnalyticsJobConfig:
    """Test analytics job configuration"""

    def test_job_config_creation(self):
        """Test creating analytics job configuration"""
        config = AnalyticsJobConfig(
            job_type=AnalyticsJobType.DAILY_SUMMARY,
            organization_id="test-org-id",
            parameters={"target_date": "2025-10-10"},
            priority=JobPriority.HIGH
        )

        assert config.job_type == AnalyticsJobType.DAILY_SUMMARY
        assert config.organization_id == "test-org-id"
        assert config.parameters["target_date"] == "2025-10-10"
        assert config.priority == JobPriority.HIGH
        assert config.max_retries == 3
        assert config.timeout_seconds == 3600

    def test_job_config_defaults(self):
        """Test analytics job configuration defaults"""
        config = AnalyticsJobConfig(
            job_type=AnalyticsJobType.DATA_AGGREGATION
        )

        assert config.organization_id is None
        assert config.parameters is None
        assert config.priority == JobPriority.NORMAL
        assert config.max_retries == 3
        assert config.timeout_seconds == 3600


class TestAnalyticsDataAggregator:
    """Test analytics data aggregation"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def aggregator(self, mock_db):
        """Create analytics data aggregator"""
        return AnalyticsDataAggregator(mock_db)

    def test_aggregator_initialization(self, aggregator, mock_db):
        """Test aggregator initialization"""
        assert aggregator.db == mock_db

    @pytest.mark.asyncio
    async def test_time_buckets_generation(self, aggregator):
        """Test time bucket generation"""
        start_date = datetime(2025, 10, 1, 0, 0, 0)
        end_date = datetime(2025, 10, 1, 3, 0, 0)

        buckets = aggregator.get_time_buckets(
            AggregationGranularity.HOUR,
            start_date,
            end_date
        )

        assert len(buckets) == 3
        assert buckets[0] == (start_date, start_date + timedelta(hours=1))
        assert buckets[1] == (start_date + timedelta(hours=1), start_date + timedelta(hours=2))
        assert buckets[2] == (start_date + timedelta(hours=2), end_date)

    @pytest.mark.asyncio
    async def test_minute_granularity_buckets(self, aggregator):
        """Test minute granularity time buckets"""
        start_date = datetime(2025, 10, 1, 12, 0, 0)
        end_date = datetime(2025, 10, 1, 12, 5, 0)

        buckets = aggregator.get_time_buckets(
            AggregationGranularity.MINUTE,
            start_date,
            end_date
        )

        assert len(buckets) == 5
        assert all((end - start).total_seconds() == 60 for start, end in buckets)

    @pytest.mark.asyncio
    async def test_day_granularity_buckets(self, aggregator):
        """Test day granularity time buckets"""
        start_date = datetime(2025, 10, 1, 0, 0, 0)
        end_date = datetime(2025, 10, 4, 0, 0, 0)

        buckets = aggregator.get_time_buckets(
            AggregationGranularity.DAY,
            start_date,
            end_date
        )

        assert len(buckets) == 3
        assert all((end - start).days == 1 for start, end in buckets)

    @pytest.mark.asyncio
    async def test_aggregate_events_count(self, aggregator):
        """Test event count aggregation"""
        # Mock query and results
        mock_query = Mock()
        mock_query.count.return_value = 100
        aggregator.db.query.return_value = mock_query

        config = AggregationConfig(
            metric_type=MetricType.COUNT,
            granularity=AggregationGranularity.DAY,
            organization_id="test-org"
        )

        result = await aggregator.aggregate_events(config)

        assert result["metric_type"] == "count"
        assert result["granularity"] == "day"
        assert result["count"] == 100
        assert len(result["results"]) == 1
        assert result["results"][0]["count"] == 100

    @pytest.mark.asyncio
    async def test_aggregate_events_with_filters(self, aggregator):
        """Test event aggregation with filters"""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 50
        aggregator.db.query.return_value = mock_query

        config = AggregationConfig(
            metric_type=MetricType.COUNT,
            granularity=AggregationGranularity.HOUR,
            filters={"event_type": "search"},
            organization_id="test-org"
        )

        result = await aggregator.aggregate_events(config)

        # Verify filters were applied
        assert mock_query.filter.call_count >= 2  # organization_id + event_type
        assert result["count"] == 50

    @pytest.mark.asyncio
    async def test_aggregate_events_grouped(self, aggregator):
        """Test grouped event aggregation"""
        # Mock query with group by
        mock_query = Mock()
        mock_result = Mock()
        mock_result.event_type = "search"
        mock_result.count = 25
        mock_query.with_entities.return_value.group_by.return_value.all.return_value = [mock_result]
        aggregator.db.query.return_value = mock_query

        config = AggregationConfig(
            metric_type=MetricType.COUNT,
            granularity=AggregationGranularity.DAY,
            group_by=["event_type"],
            organization_id="test-org"
        )

        result = await aggregator.aggregate_events(config)

        assert result["metric_type"] == "count"
        assert result["group_by"] == ["event_type"]
        assert len(result["results"]) == 1
        assert result["results"][0]["event_type"] == "search"
        assert result["results"][0]["count"] == 25

    @pytest.mark.asyncio
    async def test_aggregate_time_series(self, aggregator):
        """Test time series aggregation"""
        # Mock the aggregate_events method
        with patch.object(aggregator, 'aggregate_events') as mock_aggregate:
            mock_aggregate.return_value = {
                "metric_type": "count",
                "results": [{"count": 10}]
            }

            config = AggregationConfig(
                metric_type=MetricType.COUNT,
                granularity=AggregationGranularity.HOUR,
                organization_id="test-org",
                time_range=(
                    datetime(2025, 10, 1, 0, 0, 0),
                    datetime(2025, 10, 1, 2, 0, 0)
                )
            )

            result = await aggregator.aggregate_time_series(config, "events")

            assert result["metric_type"] == "count"
            assert result["granularity"] == "hour"
            assert result["data_source"] == "events"
            assert len(result["data_points"]) == 2  # 2 hours
            assert all("timestamp" in point and "value" in point for point in result["data_points"])

    def test_aggregation_config_validation(self):
        """Test aggregation configuration validation"""
        # Valid config
        config = AggregationConfig(
            metric_type=MetricType.AVERAGE,
            granularity=AggregationGranularity.DAY,
            field_name="response_time",
            organization_id="test-org"
        )
        assert config.metric_type == MetricType.AVERAGE
        assert config.field_name == "response_time"

        # Test time range tuple
        start_date = datetime(2025, 10, 1)
        end_date = datetime(2025, 10, 2)
        config.time_range = (start_date, end_date)
        assert config.time_range == (start_date, end_date)


class TestAnalyticsJobProcessor:
    """Test analytics job processor"""

    @pytest.fixture
    def processor(self):
        """Create analytics job processor"""
        return AnalyticsJobProcessor()

    def test_processor_initialization(self, processor):
        """Test processor initialization"""
        assert processor.aggregator is None
        assert processor.config is not None

    @patch('src.tasks.analytics_processor.get_db')
    def test_create_job(self, mock_get_db, processor):
        """Test job creation"""
        # Mock database session
        mock_db = Mock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_db.return_value.__exit__.return_value = None

        # Mock job creation
        mock_job = Mock()
        mock_job.id = "test-job-id"
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        with patch('src.tasks.analytics_processor.ProcessingJob') as mock_job_class:
            mock_job_class.return_value = mock_job

            config = AnalyticsJobConfig(
                job_type=AnalyticsJobType.DAILY_SUMMARY,
                organization_id="test-org"
            )

            job_id = processor.create_job(config)

            assert job_id == "test-job-id"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.tasks.analytics_processor.get_db')
    async def test_process_job_not_found(self, mock_get_db, processor):
        """Test processing a job that doesn't exist"""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_db.return_value.__exit__.return_value = None

        with pytest.raises(ValueError, match="Job test-job-id not found"):
            await processor.process_job("test-job-id")

    @pytest.mark.asyncio
    @patch('src.tasks.analytics_processor.get_db')
    async def test_process_data_aggregation_job(self, mock_get_db, processor):
        """Test processing data aggregation job"""
        # Mock database and job
        mock_db = Mock()
        mock_job = Mock()
        mock_job.id = "test-job-id"
        mock_job.job_type.value = "batch_processing"  # Maps to data aggregation
        mock_job.parameters = {
            "organization_id": "test-org",
            "date_range": {
                "start": "2025-10-01T00:00:00",
                "end": "2025-10-03T00:00:00"
            }
        }
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_db.return_value.__exit__.return_value = None

        # Mock aggregator
        mock_aggregator = Mock()
        mock_aggregator.aggregate_daily_metrics.return_value = {
            "date": "2025-10-01",
            "user_metrics": {"active_sessions": 10}
        }
        processor.aggregator = mock_aggregator

        result = await processor.process_job("test-job-id")

        assert result["job_type"] == "data_aggregation"
        assert result["organization_id"] == "test-org"
        assert "results" in result

        # Verify job status updates
        assert mock_job.status == JobStatus.COMPLETED
        assert mock_job.progress_percentage == 100

    @pytest.mark.asyncio
    @patch('src.tasks.analytics_processor.get_db')
    async def test_process_daily_summary_job(self, mock_get_db, processor):
        """Test processing daily summary job"""
        # Mock database and job
        mock_db = Mock()
        mock_job = Mock()
        mock_job.id = "test-job-id"
        mock_job.job_type.value = "batch_processing"  # Maps to daily summary
        mock_job.parameters = {
            "organization_id": "test-org",
            "target_date": "2025-10-01"
        }
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_db.return_value.__exit__.return_value = None

        # Mock aggregator
        mock_aggregator = Mock()
        mock_aggregator.aggregate_daily_metrics.return_value = {
            "date": "2025-10-01",
            "user_metrics": {"active_sessions": 25}
        }
        processor.aggregator = mock_aggregator

        result = await processor.process_job("test-job-id")

        assert result["job_type"] == "daily_summary"
        assert result["target_date"] == "2025-10-01"
        assert "summary" in result

    @pytest.mark.asyncio
    @patch('src.tasks.analytics_processor.get_db')
    async def test_process_job_failure(self, mock_get_db, processor):
        """Test job processing failure"""
        # Mock database and job
        mock_db = Mock()
        mock_job = Mock()
        mock_job.id = "test-job-id"
        mock_job.job_type.value = "batch_processing"
        mock_job.parameters = {"invalid": "data"}
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_db.return_value.__exit__.return_value = None

        # Mock aggregator to raise an exception
        mock_aggregator = Mock()
        mock_aggregator.aggregate_daily_metrics.side_effect = Exception("Database error")
        processor.aggregator = mock_aggregator

        with pytest.raises(Exception, match="Database error"):
            await processor.process_job("test-job-id")

        # Verify job status updated to failed
        assert mock_job.status == JobStatus.FAILED
        assert "Database error" in mock_job.error_message

    @patch('src.tasks.analytics_processor.get_db')
    def test_schedule_recurring_jobs(self, mock_get_db, processor):
        """Test scheduling recurring jobs"""
        # Mock database and organizations
        mock_db = Mock()
        mock_org = Mock()
        mock_org.id = "test-org-id"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_org]
        mock_get_db.return_value.__enter__.return_value = mock_db
        mock_get_db.return_value.__exit__.return_value = None

        # Mock job creation
        with patch.object(processor, 'create_job') as mock_create:
            mock_create.return_value = "job-id"

            processor.schedule_recurring_jobs()

            # Should create daily summary for each organization
            assert mock_create.call_count >= 1


class TestAnalyticsRecommendationGenerator:
    """Test analytics recommendation generator"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def generator(self, mock_db):
        """Create recommendation generator"""
        return AnalyticsRecommendationGenerator(mock_db)

    def test_generator_initialization(self, generator, mock_db):
        """Test generator initialization"""
        assert generator.db == mock_db

    @pytest.mark.asyncio
    async def test_generate_performance_recommendations(self, generator):
        """Test performance recommendations generation"""
        # Mock slow response time
        generator.db.query.return_value.filter.return_value.scalar.return_value = 3000

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        time_range = (start_date, end_date)

        recommendations = await generator._generate_performance_recommendations("test-org", time_range)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.type == RecommendationType.PERFORMANCE_OPTIMIZATION
        assert "response time" in rec.title.lower()
        assert rec.priority == RecommendationPriority.CRITICAL
        assert rec.impact_score > 50

    @pytest.mark.asyncio
    async def test_generate_engagement_recommendations(self, generator):
        """Test engagement recommendations generation"""
        # Mock short session duration
        generator.db.query.return_value.filter.return_value.scalar.return_value = 60

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        time_range = (start_date, end_date)

        recommendations = await generator._generate_engagement_recommendations("test-org", time_range)

        assert len(recommendations) == 1
        rec = recommendations[0]
        assert rec.type == RecommendationType.USER_ENGAGEMENT
        assert "session duration" in rec.title.lower()
        assert rec.priority == RecommendationPriority.HIGH

    @pytest.mark.asyncio
    async def test_generate_recommendations_with_types(self, generator):
        """Test generating specific recommendation types"""
        # Mock database queries
        generator.db.query.return_value.filter.return_value.scalar.return_value = 3000

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        time_range = (start_date, end_date)

        recommendations = await generator.generate_recommendations(
            "test-org",
            time_range,
            [RecommendationType.PERFORMANCE_OPTIMIZATION]
        )

        assert len(recommendations) == 1
        assert recommendations[0].type == RecommendationType.PERFORMANCE_OPTIMIZATION

    @pytest.mark.asyncio
    async def test_format_recommendations(self, generator):
        """Test recommendations formatting"""
        from src.tasks.recommendation_generator import Recommendation

        rec = Recommendation(
            type=RecommendationType.PERFORMANCE_OPTIMIZATION,
            title="Test Recommendation",
            description="Test description",
            priority=RecommendationPriority.HIGH,
            impact_score=75.0,
            effort_estimate="medium",
            metrics=["response_time"],
            suggested_actions=["Action 1", "Action 2"],
            expected_outcome="Better performance",
            data_evidence={"metric": 3000},
            created_at=datetime.utcnow()
        )

        formatted = generator.format_recommendations([rec])

        assert "recommendations" in formatted
        assert "summary" in formatted
        assert len(formatted["recommendations"]) == 1
        assert formatted["recommendations"][0]["title"] == "Test Recommendation"
        assert formatted["summary"]["total_recommendations"] == 1

    @pytest.mark.asyncio
    async def test_recommendation_priority_assignment(self, generator):
        """Test recommendation priority assignment based on metrics"""
        # Test critical priority for very slow response time
        generator.db.query.return_value.filter.return_value.scalar.return_value = 6000

        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        time_range = (start_date, end_date)

        recommendations = await generator._generate_performance_recommendations("test-org", time_range)

        assert len(recommendations) == 1
        assert recommendations[0].priority == RecommendationPriority.CRITICAL

    def test_recommendation_data_evidence(self, generator):
        """Test recommendation includes data evidence"""
        from src.tasks.recommendation_generator import Recommendation

        rec = Recommendation(
            type=RecommendationType.PERFORMANCE_OPTIMIZATION,
            title="Test Recommendation",
            description="Test description",
            priority=RecommendationPriority.MEDIUM,
            impact_score=50.0,
            effort_estimate="low",
            metrics=["test_metric"],
            suggested_actions=["Test action"],
            expected_outcome="Test outcome",
            data_evidence={
                "metric_value": 1000,
                "threshold": 500,
                "period": "30 days"
            },
            created_at=datetime.utcnow()
        )

        assert rec.data_evidence["metric_value"] == 1000
        assert rec.data_evidence["threshold"] == 500
        assert rec.data_evidence["period"] == "30 days"


if __name__ == "__main__":
    pytest.main([__file__])