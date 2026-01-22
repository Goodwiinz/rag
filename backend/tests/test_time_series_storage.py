"""
Tests for time-series storage system
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.storage.time_series_store import (
    TimeSeriesPoint, TimeSeriesQuery, TimeSeriesBackend,
    PostgreSQLTimeSeriesStore, InfluxDBTimeSeriesStore, HybridTimeSeriesStore,
    TimeSeriesStoreManager, MetricType
)
from src.storage.data_retention import (
    DataRetentionManager, RetentionPolicy, RetentionAction,
    get_retention_manager, scheduled_retention_cleanup
)
from src.models.analytics_event import AnalyticsEvent
from src.models.performance_log import PerformanceLog
from src.models.user_session import UserSession


class TestTimeSeriesPoint:
    """Test time-series point data structure"""

    def test_time_series_point_creation(self):
        """Test creating a time-series point"""
        point = TimeSeriesPoint(
            measurement="cpu_usage",
            timestamp=datetime.utcnow(),
            value=75.5,
            tags={"host": "server1", "environment": "production"},
            fields={"unit": "percent", "component": "api"}
        )

        assert point.measurement == "cpu_usage"
        assert isinstance(point.value, float)
        assert point.tags["host"] == "server1"
        assert point.fields["unit"] == "percent"

    def test_time_series_point_to_dict(self):
        """Test converting time-series point to dictionary"""
        point = TimeSeriesPoint(
            measurement="response_time",
            timestamp=datetime(2024, 1, 15, 10, 30),
            value=150,
            tags={"endpoint": "/api/v1/search"},
            fields={"unit": "ms", "method": "GET"}
        )

        point_dict = point.to_dict()

        assert "measurement" in point_dict
        assert "timestamp" in point_dict
        assert "value" in point_dict
        assert "tags" in point_dict
        assert "fields" in point_dict


class TestTimeSeriesQuery:
    """Test time-series query specification"""

    def test_time_series_query_creation(self):
        """Test creating a time-series query"""
        start_time = datetime.utcnow() - timedelta(days=7)
        end_time = datetime.utcnow()

        query = TimeSeriesQuery(
            measurement="api_metrics",
            start_time=start_time,
            end_time=end_time,
            tags={"component": "api"},
            fields=["response_time", "throughput"],
            aggregation="hour",
            limit=1000
        )

        assert query.measurement == "api_metrics"
        assert query.tags["component"] == "api"
        assert "response_time" in query.fields
        assert query.aggregation == "hour"
        assert query.limit == 1000

    def test_time_series_query_defaults(self):
        """Test time-series query with default values"""
        query = TimeSeriesQuery(
            measurement="test_metrics",
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow()
        )

        assert query.measurement == "test_metrics"
        assert query.tags is None
        assert query.fields is None
        assert query.aggregation is None
        assert query.limit is None


class TestPostgreSQLTimeSeriesStore:
    """Test PostgreSQL time-series store"""

    @pytest.fixture
    def mock_config(self):
        """Mock analytics configuration"""
        config = Mock()
        config.time_series_backend = TimeSeriesBackend.POSTGRESQL
        return config

    @pytest.fixture
    def store(self, mock_config):
        """Create PostgreSQL store instance"""
        with patch('src.storage.time_series_store.get_analytics_config', return_value=mock_config):
            return PostgreSQLTimeSeriesStore()

    @pytest.mark.asyncio
    async def test_initialize_tables(self, store):
        """Test table initialization"""
        with patch('src.storage.time_series_store.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=None)
            mock_db.execute = Mock()
            mock_db.commit = Mock()

            await store.initialize()

            # Verify that execute was called multiple times (for tables and indexes)
            assert mock_db.execute.call_count > 0
            assert mock_db.commit.call_count > 0

    @pytest.mark.asyncio
    async def test_write_analytics_event_point(self, store):
        """Test writing analytics event point"""
        point = TimeSeriesPoint(
            measurement="search_query",
            timestamp=datetime.utcnow(),
            value=1,
            tags={
                "organization_id": "org123",
                "event_type": "search"
            },
            fields={
                "event_id": "event456",
                "query": "test query"
            }
        )

        with patch('src.storage.time_series_store.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=None)
            mock_db.execute = Mock()
            mock_db.commit = Mock()

            result = await store.write_point(point)

            assert result is True
            mock_db.execute.assert_called()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_analytics_events(self, store):
        """Test querying analytics events"""
        start_time = datetime.utcnow() - timedelta(days=1)
        end_time = datetime.utcnow()

        query = TimeSeriesQuery(
            measurement="analytics_events",
            start_time=start_time,
            end_time=end_time,
            tags={"organization_id": "org123"},
            aggregation="hour"
        )

        # Mock database response
        mock_rows = [
            Mock(
                timestamp=datetime.utcnow(),
                event_type="search",
                event_name="document_search",
                value=1.0,
                tags='{"organization_id": "org123"}',
                fields='{"query": "test"}',
                count=10
            )
        ]

        with patch('src.storage.time_series_store.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=None)
            mock_result = Mock()
            mock_result.fetchall.return_value = mock_rows
            mock_db.execute = Mock(return_value=mock_result)

            result = await store.query(query)

            assert len(result) == 1
            assert result[0]["event_type"] == "search"
            assert result[0]["count"] == 10

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, store):
        """Test cleaning up old data"""
        with patch('src.storage.time_series_store.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=None)
            mock_result = Mock()
            mock_result.rowcount = 100  # 100 rows deleted
            mock_db.execute = Mock(return_value=mock_result)
            mock_db.commit = Mock()

            deleted_count = await store.cleanup_old_data(retention_days=30)

            assert deleted_count >= 0
            mock_db.execute.assert_called()
            mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_get_storage_stats(self, store):
        """Test getting storage statistics"""
        # Mock database response
        mock_stats = [
            Mock(count=1000, size="100MB", size_bytes=104857600),
            Mock(count=500, size="50MB", size_bytes=52428800)
        ]

        with patch('src.storage.time_series_store.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=None)
            mock_db.execute = Mock()
            # Mock different results for different queries
            mock_db.execute.side_effect = [
                Mock(first=Mock(count=1000)),  # Count query
                Mock(first=Mock(size="100MB", size_bytes=104857600)),  # Size query
                Mock(first=Mock(count=500)),   # Count query for second table
                Mock(first=Mock(size="50MB", size_bytes=52428800))   # Size query for second table
            ]

            stats = await store.get_storage_stats()

            assert len(stats) >= 2
            assert "analytics_events_ts" in stats
            assert "performance_metrics_ts" in stats


class TestInfluxDBTimeSeriesStore:
    """Test InfluxDB time-series store"""

    @pytest.mark.asyncio
    @patch('src.storage.time_series_store.INFLUXDB_AVAILABLE', True)
    async def test_influxdb_initialization(self):
        """Test InfluxDB initialization"""
        with patch('src.storage.time_series_store.InfluxDBClient') as mock_client_class:
            mock_client = Mock()
            mock_health = Mock()
            mock_health.status = "pass"
            mock_client.health.return_value = mock_health
            mock_client_class.return_value = mock_client

            with patch('src.storage.time_series_store.get_analytics_config') as mock_config:
                mock_config.return_value.time_series_db_url = "http://localhost:8086"

                store = InfluxDBTimeSeriesStore()
                await store.initialize()

                assert store._connected is True
                mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.storage.time_series_store.INFLUXDB_AVAILABLE', False)
    async def test_influxdb_not_available(self):
        """Test handling when InfluxDB is not available"""
        store = InfluxDBTimeSeriesStore()

        with pytest.raises(Exception):
            await store.initialize()

        assert store._connected is False

    @pytest.mark.asyncio
    @patch('src.storage.time_series_store.INFLUXDB_AVAILABLE', True)
    async def test_write_point_to_influxdb(self):
        """Test writing point to InfluxDB"""
        with patch('src.storage.time_series_store.InfluxDBClient') as mock_client_class:
            mock_client = Mock()
            mock_health = Mock()
            mock_health.status = "pass"
            mock_client.health.return_value = mock_health
            mock_client_class.return_value = mock_client

            mock_write_api = Mock()
            mock_client.write_api.return_value = mock_write_api

            store = InfluxDBTimeSeriesStore()
            store._connected = True
            store.client = mock_client

            point = TimeSeriesPoint(
                measurement="cpu_usage",
                timestamp=datetime.utcnow(),
                value=75.5,
                tags={"host": "server1"},
                fields={"unit": "percent"}
            )

            result = await store.write_point(point)

            assert result is True
            mock_write_api.write.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.storage.time_series_store.INFLUXDB_AVAILABLE', True)
    async def test_query_influxdb(self):
        """Test querying InfluxDB"""
        with patch('src.storage.time_series_store.InfluxDBClient') as mock_client_class:
            mock_client = Mock()
            mock_health = Mock()
            mock_health.status = "pass"
            mock_client.health.return_value = mock_health
            mock_client_class.return_value = mock_client

            mock_query_api = Mock()
            mock_record = Mock()
            mock_record.get_time.return_value = datetime.utcnow()
            mock_record.get_measurement.return_value = "cpu_usage"
            mock_record.get_field.return_value = "value"
            mock_record.get_value.return_value = 75.5
            mock_record.values = {"host": "server1"}

            mock_table = Mock()
            mock_table.records = [mock_record]

            mock_result = Mock()
            mock_result.__iter__ = Mock(return_value=iter([mock_table]))
            mock_query_api.query.return_value = mock_result
            mock_client.query_api.return_value = mock_query_api

            store = InfluxDBTimeSeriesStore()
            store._connected = True
            store.client = mock_client

            query = TimeSeriesQuery(
                measurement="cpu_usage",
                start_time=datetime.utcnow() - timedelta(hours=1),
                end_time=datetime.utcnow()
            )

            result = await store.query(query)

            assert len(result) == 1
            assert result[0]["measurement"] == "cpu_usage"
            assert result[0]["value"] == 75.5


class TestHybridTimeSeriesStore:
    """Test hybrid time-series store"""

    @pytest.mark.asyncio
    async def test_hybrid_initialization(self):
        """Test hybrid store initialization"""
        with patch('src.storage.time_series_store.PostgreSQLTimeSeriesStore') as mock_pg:
            mock_pg_store = Mock()
            mock_pg.initialize = AsyncMock()
            mock_pg.return_value = mock_pg

            with patch('src.storage.time_series_store.InfluxDBTimeSeriesStore') as mock_influx:
                mock_influx_store = Mock()
                mock_influx.initialize = AsyncMock(side_effect=Exception("InfluxDB not available"))
                mock_influx.return_value = mock_influx_store
                mock_influx_store._connected = False

                store = HybridTimeSeriesStore()
                await store.initialize()

                mock_pg_store.initialize.assert_called_once()
                mock_influx_store.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_write_with_influxdb_fallback(self):
        """Test hybrid store writing with InfluxDB fallback to PostgreSQL"""
        with patch('src.storage.time_series_store.PostgreSQLTimeSeriesStore') as mock_pg:
            mock_pg_store = Mock()
            mock_pg_store.write_point = AsyncMock(return_value=True)
            mock_pg.return_value = mock_pg_store

            with patch('src.storage.time_series_store.InfluxDBTimeSeriesStore') as mock_influx:
                mock_influx_store = Mock()
                mock_influx_store.write_point = AsyncMock(return_value=False)  # InfluxDB fails
                mock_influx_store._connected = False
                mock_influx.return_value = mock_influx_store

                store = HybridTimeSeriesStore()
                store.postgres_store = mock_pg_store
                store.influxdb_store = mock_influx_store

                point = TimeSeriesPoint(
                    measurement="test_metric",
                    timestamp=datetime.utcnow(),
                    value=100,
                    tags={},
                    fields={}
                )

                result = await store.write_point(point)

                # Should fallback to PostgreSQL
                assert result is True
                mock_influx_store.write_point.assert_called_once()
                mock_pg_store.write_point.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_query_with_influxdb_preferred(self):
        """Test hybrid store querying with InfluxDB preferred"""
        mock_data = [{"timestamp": "2024-01-15T10:30:00Z", "value": 75.5}]

        with patch('src.storage.time_series_store.PostgreSQLTimeSeriesStore') as mock_pg:
            mock_pg_store = Mock()
            mock_pg_store.query = AsyncMock(return_value=mock_data)
            mock_pg.return_value = mock_pg_store

            with patch('src.storage.time_series_store.InfluxDBTimeSeriesStore') as mock_influx:
                mock_influx_store = Mock()
                mock_influx_store.query = AsyncMock(return_value=mock_data)
                mock_influx_store._connected = True
                mock_influx.return_value = mock_influx_store

                store = HybridTimeSeriesStore()
                store.postgres_store = mock_pg_store
                store.influxdb_store = mock_influx_store

                query = TimeSeriesQuery(
                    measurement="test_metric",
                    start_time=datetime.utcnow() - timedelta(hours=1),
                    end_time=datetime.utcnow()
                )

                result = await store.query(query)

                # Should use InfluxDB when available
                assert result == mock_data
                mock_influx_store.query.assert_called_once()
                mock_pg_store.query.assert_not_called()


class TestTimeSeriesStoreManager:
    """Test time-series store manager"""

    @pytest.fixture
    def mock_config(self):
        """Mock analytics configuration"""
        config = Mock()
        config.time_series_backend = TimeSeriesBackend.POSTGRESQL
        return config

    @pytest.fixture
    def manager(self, mock_config):
        """Create time-series store manager"""
        with patch('src.storage.time_series_store.get_analytics_config', return_value=mock_config):
            return TimeSeriesStoreManager()

    @pytest.mark.asyncio
    async def test_manager_initialization(self, manager):
        """Test manager initialization"""
        with patch('src.storage.time_series_store.PostgreSQLTimeSeriesStore') as mock_store_class:
            mock_store = Mock()
            mock_store.initialize = AsyncMock()
            mock_store_class.return_value = mock_store

            await manager.initialize()

            assert manager._initialized is True
            assert isinstance(manager.store, type(mock_store))

    @pytest.mark.asyncio
    async def test_write_analytics_event(self, manager):
        """Test writing analytics event through manager"""
        event = Mock()
        event.id = "event123"
        event.event_name = "search_query"
        event.timestamp = datetime.utcnow()
        event.created_at = datetime.utcnow()
        event.organization_id = "org123"
        event.event_type = "search"
        event.source = "api"
        event.event_data = {"query": "test"}
        event.severity = Mock()
        event.severity.value = "low"

        with patch.object(manager, 'store') as mock_store:
            mock_store.write_point = AsyncMock(return_value=True)

            result = await manager.write_analytics_event(event)

            assert result is True
            mock_store.write_point.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_performance_metric(self, manager):
        """Test writing performance metric through manager"""
        metric = Mock()
        metric.id = "metric123"
        metric.metric_name = "response_time"
        metric.timestamp = datetime.utcnow()
        metric.created_at = datetime.utcnow()
        metric.value = 150.5
        metric.organization_id = "org123"
        metric.component = "api"
        metric.host = "server1"
        metric.environment = "production"
        metric.unit = "ms"
        metric.metric_type = Mock()
        metric.metric_type.value = "timer"
        metric.performance_level = Mock()
        metric.performance_level.value = "good"
        metric.threshold = {"warning": 200, "critical": 500}
        metric.tags = ["endpoint:/api/search"]
        metric.event_metadata = {"method": "GET"}

        with patch.object(manager, 'store') as mock_store:
            mock_store.write_point = AsyncMock(return_value=True)

            result = await manager.write_performance_metric(metric)

            assert result is True
            mock_store.write_point.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_user_session_summary(self, manager):
        """Test writing user session summary through manager"""
        session = Mock()
        session.id = "session123"
        session.session_end = datetime.utcnow()
        session.created_at = datetime.utcnow()
        session.engagement_score = 75.5
        session.organization_id = "org123"
        session.user_id = "user123"
        session.device_type = "desktop"
        session.browser = "Chrome"
        session.duration_seconds = 3600
        session.page_views = 25
        session.total_searches = 8
        session.total_downloads = 3
        session.bounce_type = "none"

        with patch.object(manager, 'store') as mock_store:
            mock_store.write_point = AsyncMock(return_value=True)

            result = await manager.write_user_session_summary(session)

            assert result is True
            mock_store.write_point.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_analytics_events(self, manager):
        """Test querying analytics events through manager"""
        mock_data = [
            {
                "timestamp": "2024-01-15T10:30:00Z",
                "event_type": "search",
                "event_name": "document_search",
                "count": 10
            }
        ]

        with patch.object(manager, 'store') as mock_store:
            mock_store.query = AsyncMock(return_value=mock_data)

            result = await manager.query_analytics_events(
                organization_id="org123",
                start_time=datetime.utcnow() - timedelta(days=1),
                end_time=datetime.utcnow(),
                event_type="search"
            )

            assert result == mock_data
            mock_store.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_storage_stats(self, manager):
        """Test getting storage statistics through manager"""
        mock_stats = {
            "analytics_events_ts": {"row_count": 1000, "size_bytes": 104857600},
            "performance_metrics_ts": {"row_count": 500, "size_bytes": 52428800}
        }

        with patch.object(manager, 'store') as mock_store:
            mock_store.get_storage_stats = AsyncMock(return_value=mock_stats)

            result = await manager.get_storage_stats()

            assert result == mock_stats
            mock_store.get_storage_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, manager):
        """Test cleaning up old data through manager"""
        with patch.object(manager, 'store') as mock_store:
            mock_store.cleanup_old_data = AsyncMock(return_value=100)

            result = await manager.cleanup_old_data(retention_days=30)

            assert result == 100
            mock_store.cleanup_old_data.assert_called_once_with(30)


class TestDataRetentionManager:
    """Test data retention manager"""

    @pytest.fixture
    def manager(self):
        """Create data retention manager"""
        with patch('src.storage.data_retention.get_analytics_config') as mock_config:
            mock_config.retention.analytics_events_retention_days = 365
            mock_config.retention.user_sessions_retention_days = 180
            mock_config.retention.performance_logs_retention_days = 90
            mock_config.retention.quality_metrics_retention_days = 730
            mock_config.retention.anonymize_after_days = 90
            mock_config.privacy.enable_data_anonymization = True

            with patch('src.storage.data_retention.get_time_series_manager') as mock_ts_manager:
                mock_ts_manager.return_value.cleanup_old_data = AsyncMock(return_value=50)

                with patch('src.storage.data_retention.DataAnonymizer') as mock_anonymizer:
                    mock_anonymizer.return_value.anonymize_ip = Mock(return_value="192.168.1.0")
                    mock_anonymizer.return_value.anonymize_user_agent = Mock(return_value="Mozilla/5.0 (anonymized)")

                    return DataRetentionManager()

    def test_load_retention_policies(self, manager):
        """Test loading retention policies"""
        policies = manager.policies

        assert len(policies) > 0

        # Check that we have policies for different data types
        policy_types = [p.data_type for p in policies]
        assert "analytics_events" in policy_types
        assert "user_sessions" in policy_types
        assert "performance_logs" in policy_types
        assert "quality_metrics" in policy_types

        # Check policy structure
        for policy in policies:
            assert hasattr(policy, 'data_type')
            assert hasattr(policy, 'table_name')
            assert hasattr(policy, 'retention_days')
            assert hasattr(policy, 'action')
            assert policy.retention_days > 0

    @pytest.mark.asyncio
    async def test_run_retention_cleanup_dry_run(self, manager):
        """Test running retention cleanup in dry run mode"""
        with patch('src.storage.data_retention.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=None)
            mock_db.execute = Mock()
            # Mock count query results
            mock_db.execute.side_effect = [
                Mock(scalar=Mock(return_value=100)),  # Count query
                Mock(),  # Delete query (won't execute in dry run)
                Mock(scalar=Mock(return_value=50)),   # Count query for second policy
                Mock()   # Delete query for second policy (won't execute in dry run)
            ]
            mock_db.commit = Mock()

            reports = await manager.run_retention_cleanup(dry_run=True)

            assert len(reports) > 0
            # In dry run, records should be processed but not deleted
            total_processed = sum(r.records_processed for r in reports)
            total_deleted = sum(r.records_deleted for r in reports)
            assert total_processed > 0
            assert total_deleted == 0  # No actual deletions in dry run

    @pytest.mark.asyncio
    async def test_run_retention_cleanup_actual(self, manager):
        """Test running actual retention cleanup"""
        with patch('src.storage.data_retention.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=None)
            mock_db.execute = Mock()
            # Mock count and delete query results
            mock_db.execute.side_effect = [
                Mock(scalar=Mock(return_value=100)),  # Count query
                Mock(),  # Delete query
                Mock(scalar=Mock(return_value=50)),   # Count query for second policy
                Mock()   # Delete query for second policy
            ]
            mock_db.commit = Mock()

            reports = await manager.run_retention_cleanup(dry_run=False)

            assert len(reports) > 0
            # In actual run, records should be both processed and deleted
            total_processed = sum(r.records_processed for r in reports)
            total_deleted = sum(r.records_deleted for r in reports)
            assert total_processed > 0
            assert total_deleted > 0

    @pytest.mark.asyncio
    async def test_get_retention_status(self, manager):
        """Test getting retention status"""
        with patch('src.storage.data_retention.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=None)

            # Mock database query results
            mock_db.execute.return_value.fetchall.return_value = [
                Mock(
                    oldest_date=datetime.utcnow() - timedelta(days=30),
                    total_count=1000,
                    expired_count=100
                )
            ]

            with patch.object(manager.time_series_manager, 'get_storage_stats') as mock_stats:
                mock_stats.return_value = {"analytics_events_ts": {"row_count": 1000}}

                status = await manager.get_retention_status()

                assert "policies" in status
                assert "storage_stats" in status
                assert len(status["policies"]) > 0

                # Check policy structure
                policy = status["policies"][0]
                assert "data_type" in policy
                assert "retention_days" in policy
                assert "total_records" in policy
                assert "expired_records" in policy

    @pytest.mark.asyncio
    async def test_get_compliance_report(self, manager):
        """Test generating compliance report"""
        with patch('src.storage.data_retention.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=None)

            # Mock violation check results
            mock_db.execute.return_value.fetchone.return_value = Mock(
                violation_count=50,
                oldest_violation=datetime.utcnow() - timedelta(days=400)
            )

            report = await manager.get_compliance_report()

            assert "generated_at" in report
            assert "compliance_summary" in report
            assert "policy_violations" in report
            assert "overall_compliance" in report

            # Should have violations since we mocked old data
            assert len(report["policy_violations"]) > 0
            assert report["total_violations"] > 0
            assert report["overall_compliance"] is False

    @pytest.mark.asyncio
    async def test_cleanup_expired_data(self, manager):
        """Test force cleanup of expired data"""
        with patch('src.storage.data_retention.get_db') as mock_get_db:
            mock_db = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_get_db.return_value.__exit__ = Mock(return_value=None)
            mock_db.execute = Mock()
            mock_db.commit = Mock()

            result = await manager.cleanup_expired_data(force=True)

            assert "start_time" in result
            assert "policies_executed" in result
            assert "total_records_processed" in result
            assert "total_records_deleted" in result


class TestRetentionHealthCheck:
    """Test retention system health checks"""

    @pytest.mark.asyncio
    async def test_retention_health_check(self):
        """Test retention system health check"""
        with patch('src.storage.data_retention._retention_manager') as mock_manager:
            mock_manager.policies = [Mock(), Mock(), Mock()]
            mock_manager.get_retention_status = AsyncMock(return_value={
                "policies": [{"cleanup_needed": False}, {"cleanup_needed": True}]
            })
            mock_manager.get_compliance_report = AsyncMock(return_value={
                "total_violations": 0,
                "policy_violations": []
            })

            from src.storage.data_retention import retention_health_check
            health = await retention_health_check()

            assert "status" in health
            assert "timestamp" in health
            assert "policies_loaded" in health
            assert "enabled_policies" in health
            assert "violations" in health
            assert health["policies_loaded"] == 3
            assert health["violations"] == 0

    @pytest.mark.asyncio
    async def test_scheduled_retention_cleanup(self):
        """Test scheduled retention cleanup task"""
        with patch('src.storage.data_retention._retention_manager') as mock_manager:
            mock_manager.run_retention_cleanup = AsyncMock(return_value=[
                Mock(records_deleted=100, records_archived=0, records_anonymized=0)
            ])

            from src.storage.data_retention import scheduled_retention_cleanup

            # Should not raise any exceptions
            await scheduled_retention_cleanup()

            mock_manager.run_retention_cleanup.assert_called_once_with(dry_run=False)


if __name__ == "__main__":
    pytest.main([__file__])