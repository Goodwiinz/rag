"""
Time-series database integration for RAG Analytics
Provides optimized storage and querying for time-series analytics data
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import influxdb_client
    from influxdb_client import InfluxDBClient, Point
    from influxdb_client.client.write_api import SYNCHRONOUS

    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False
    influxdb_client = None
    Point = None

try:
    import psycopg2
    from psycopg2.extras import execute_values

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from src.config.analytics_config import get_analytics_config
from src.core.database import get_db
from src.exceptions.analytics_exceptions import AnalyticsServiceException
from src.models.analytics_event import AnalyticsEvent
from src.models.performance_log import PerformanceLog
from src.models.user_session import UserSession

logger = logging.getLogger(__name__)


class TimeSeriesBackend(str, Enum):
    """Supported time-series database backends"""

    INFLUXDB = "influxdb"
    POSTGRESQL = "postgresql"
    HYBRID = "hybrid"


class MetricType(str, Enum):
    """Time-series metric types"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class TimeSeriesPoint:
    """Individual time-series data point"""

    measurement: str
    timestamp: datetime
    value: Union[float, int, str, bool]
    tags: Dict[str, str]
    fields: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class TimeSeriesQuery:
    """Time-series query specification"""

    measurement: str
    start_time: datetime
    end_time: datetime
    tags: Optional[Dict[str, str]] = None
    fields: Optional[List[str]] = None
    aggregation: Optional[str] = None
    group_by: Optional[List[str]] = None
    limit: Optional[int] = None
    order_by: Optional[str] = "time"


class PostgreSQLTimeSeriesStore:
    """PostgreSQL-based time-series storage using optimized tables"""

    def __init__(self):
        self.config = get_analytics_config()
        self._partition_created = False

    async def initialize(self):
        """Initialize time-series tables and partitions"""
        try:
            await self._create_time_series_tables()
            await self._create_indexes()
            await self._setup_partitioning()
            logger.info("PostgreSQL time-series store initialized")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL time-series store: {e}")
            raise

    async def _create_time_series_tables(self):
        """Create optimized time-series tables"""
        db = next(get_db())

        # Analytics events time-series table
        analytics_events_ts_sql = """
        CREATE TABLE IF NOT EXISTS analytics_events_ts (
            id UUID DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL,
            event_type VARCHAR(100) NOT NULL,
            event_name VARCHAR(200) NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            value DOUBLE PRECISION,
            tags JSONB,
            fields JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            PRIMARY KEY (id, timestamp)
        ) PARTITION BY RANGE (timestamp);
        """

        # Performance metrics time-series table
        performance_metrics_ts_sql = """
        CREATE TABLE IF NOT EXISTS performance_metrics_ts (
            id UUID DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL,
            metric_name VARCHAR(200) NOT NULL,
            metric_type VARCHAR(50) NOT NULL,
            component VARCHAR(100) NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            value DOUBLE PRECISION NOT NULL,
            unit VARCHAR(50),
            tags JSONB,
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            PRIMARY KEY (id, timestamp)
        ) PARTITION BY RANGE (timestamp);
        """

        # User sessions summary table
        user_sessions_ts_sql = """
        CREATE TABLE IF NOT EXISTS user_sessions_ts (
            id UUID DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL,
            user_id UUID,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            session_duration INTEGER,
            engagement_score DOUBLE PRECISION,
            page_views INTEGER,
            searches INTEGER,
            downloads INTEGER,
            tags JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            PRIMARY KEY (id, timestamp)
        ) PARTITION BY RANGE (timestamp);
        """

        try:
            db.execute(text(analytics_events_ts_sql))
            db.execute(text(performance_metrics_ts_sql))
            db.execute(text(user_sessions_ts_sql))
            db.commit()
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    async def _create_indexes(self):
        """Create optimized indexes for time-series queries"""
        db = next(get_db())

        indexes = [
            # Analytics events indexes
            "CREATE INDEX IF NOT EXISTS idx_analytics_events_ts_org_time ON analytics_events_ts (organization_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_analytics_events_ts_type_time ON analytics_events_ts (event_type, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_analytics_events_ts_tags ON analytics_events_ts USING GIN (tags)",
            # Performance metrics indexes
            "CREATE INDEX IF NOT EXISTS idx_performance_metrics_ts_org_time ON performance_metrics_ts (organization_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_performance_metrics_ts_comp_time ON performance_metrics_ts (component, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_performance_metrics_ts_metric_time ON performance_metrics_ts (metric_name, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_performance_metrics_ts_tags ON performance_metrics_ts USING GIN (tags)",
            # User sessions indexes
            "CREATE INDEX IF NOT EXISTS idx_user_sessions_ts_org_time ON user_sessions_ts (organization_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_user_sessions_ts_user_time ON user_sessions_ts (user_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_user_sessions_ts_engagement ON user_sessions_ts (engagement_score, timestamp DESC)",
        ]

        try:
            for index_sql in indexes:
                db.execute(text(index_sql))
            db.commit()
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    async def _setup_partitioning(self):
        """Create time-based partitions"""
        db = next(get_db())

        # Create partitions for the current month and next 2 months
        current_date = datetime.utcnow()

        for i in range(3):
            partition_date = current_date.replace(day=1) + timedelta(days=32 * i)
            partition_date = partition_date.replace(day=1)
            partition_name = partition_date.strftime("%Y_%m")
            start_date = partition_date
            end_date = partition_date + timedelta(days=32)
            end_date = end_date.replace(day=1)

            # Create partitions for each table
            partition_tables = [
                f"analytics_events_ts_{partition_name}",
                f"performance_metrics_ts_{partition_name}",
                f"user_sessions_ts_{partition_name}",
            ]

            base_tables = [
                "analytics_events_ts",
                "performance_metrics_ts",
                "user_sessions_ts",
            ]

            # Validate base table names
            allowed_base_tables = ['analytics_events_ts', 'performance_metrics_ts', 'user_sessions_ts']
            
            for base_table, partition_table in zip(base_tables, partition_tables):
                if base_table not in allowed_base_tables:
                    logger.warning(f"Skipping invalid base table: {base_table}")
                    continue
                    
                partition_sql = """
                CREATE TABLE IF NOT EXISTS {} 
                PARTITION OF {}
                FOR VALUES FROM (%s) TO (%s);
                """.format(partition_table, base_table)

                try:
                    db.execute(text(partition_sql), (start_date.isoformat(), end_date.isoformat()))
                except Exception as e:
                    logger.warning(f"Failed to create partition {partition_table}: {e}")

        db.commit()
        db.close()

    async def write_point(self, point: TimeSeriesPoint) -> bool:
        """Write a single time-series point"""
        try:
            db = next(get_db())

            if point.measurement == "analytics_events":
                await self._write_analytics_event(db, point)
            elif point.measurement == "performance_metrics":
                await self._write_performance_metric(db, point)
            elif point.measurement == "user_sessions":
                await self._write_user_session(db, point)
            else:
                raise ValueError(f"Unknown measurement: {point.measurement}")

            db.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to write time-series point: {e}")
            if "db" in locals():
                db.rollback()
                db.close()
            return False

    async def _write_analytics_event(self, db: Session, point: TimeSeriesPoint):
        """Write analytics event to time-series table"""
        sql = """
        INSERT INTO analytics_events_ts (
            organization_id, event_type, event_name, timestamp, value, tags, fields
        ) VALUES (:org_id, :event_type, :event_name, :timestamp, :value, :tags, :fields)
        """

        db.execute(
            text(sql),
            {
                "org_id": point.tags.get("organization_id"),
                "event_type": point.tags.get("event_type"),
                "event_name": point.measurement,
                "timestamp": point.timestamp,
                "value": float(point.value)
                if isinstance(point.value, (int, float))
                else None,
                "tags": json.dumps(point.tags),
                "fields": json.dumps(point.fields),
            },
        )

    async def _write_performance_metric(self, db: Session, point: TimeSeriesPoint):
        """Write performance metric to time-series table"""
        sql = """
        INSERT INTO performance_metrics_ts (
            organization_id, metric_name, metric_type, component, timestamp, value, unit, tags, metadata
        ) VALUES (:org_id, :metric_name, :metric_type, :component, :timestamp, :value, :unit, :tags, :metadata)
        """

        db.execute(
            text(sql),
            {
                "org_id": point.tags.get("organization_id"),
                "metric_name": point.measurement,
                "metric_type": point.tags.get("metric_type", "gauge"),
                "component": point.tags.get("component", "unknown"),
                "timestamp": point.timestamp,
                "value": float(point.value),
                "unit": point.tags.get("unit"),
                "tags": json.dumps(point.tags),
                "metadata": json.dumps(point.fields),
            },
        )

    async def _write_user_session(self, db: Session, point: TimeSeriesPoint):
        """Write user session data to time-series table"""
        sql = """
        INSERT INTO user_sessions_ts (
            organization_id, user_id, timestamp, session_duration, engagement_score,
            page_views, searches, downloads, tags
        ) VALUES (:org_id, :user_id, :timestamp, :duration, :engagement, :page_views, :searches, :downloads, :tags)
        """

        db.execute(
            text(sql),
            {
                "org_id": point.tags.get("organization_id"),
                "user_id": point.tags.get("user_id"),
                "timestamp": point.timestamp,
                "duration": point.fields.get("session_duration"),
                "engagement": point.value,
                "page_views": point.fields.get("page_views", 0),
                "searches": point.fields.get("searches", 0),
                "downloads": point.fields.get("downloads", 0),
                "tags": json.dumps(point.tags),
            },
        )

    async def write_points(self, points: List[TimeSeriesPoint]) -> int:
        """Write multiple time-series points"""
        success_count = 0

        for point in points:
            if await self.write_point(point):
                success_count += 1

        return success_count

    async def query(self, query_spec: TimeSeriesQuery) -> List[Dict[str, Any]]:
        """Query time-series data"""
        try:
            db = next(get_db())

            if query_spec.measurement == "analytics_events":
                return await self._query_analytics_events(db, query_spec)
            elif query_spec.measurement == "performance_metrics":
                return await self._query_performance_metrics(db, query_spec)
            elif query_spec.measurement == "user_sessions":
                return await self._query_user_sessions(db, query_spec)
            else:
                raise ValueError(f"Unknown measurement: {query_spec.measurement}")

        except Exception as e:
            logger.error(f"Failed to query time-series data: {e}")
            return []
        finally:
            if "db" in locals():
                db.close()

    async def _query_analytics_events(
        self, db: Session, query: TimeSeriesQuery
    ) -> List[Dict[str, Any]]:
        """Query analytics events from time-series table"""
        sql = """
        SELECT
            timestamp,
            event_type,
            event_name,
            value,
            tags,
            fields,
            COUNT(*) as count
        FROM analytics_events_ts
        WHERE organization_id = :org_id
            AND timestamp BETWEEN :start_time AND :end_time
        """

        params = {
            "org_id": query.tags.get("organization_id") if query.tags else None,
            "start_time": query.start_time,
            "end_time": query.end_time,
        }

        # Add tag filters
        if query.tags:
            tag_conditions = []
            for i, (key, value) in enumerate(query.tags.items()):
                if key != "organization_id":
                    param_name = f"tag_{i}"
                    tag_conditions.append(f"tags::text LIKE :{param_name}")
                    params[param_name] = f'%"{key}": "{value}"%'

            if tag_conditions:
                sql += " AND " + " AND ".join(tag_conditions)

        # Add grouping
        if query.aggregation:
            if query.aggregation == "hour":
                sql += " GROUP BY date_trunc('hour', timestamp), event_type, event_name"
            elif query.aggregation == "day":
                sql += " GROUP BY date_trunc('day', timestamp), event_type, event_name"
            elif query.aggregation == "week":
                sql += " GROUP BY date_trunc('week', timestamp), event_type, event_name"
        else:
            sql += " GROUP BY timestamp, event_type, event_name, value, tags, fields"

        # Add ordering
        sql += " ORDER BY timestamp DESC"

        # Add limit
        if query.limit:
            sql += " LIMIT :limit"
            params["limit"] = int(query.limit)

        result = db.execute(text(sql), params)
        rows = result.fetchall()

        return [
            {
                "timestamp": row.timestamp.isoformat(),
                "event_type": row.event_type,
                "event_name": row.event_name,
                "value": row.value,
                "tags": json.loads(row.tags) if row.tags else {},
                "fields": json.loads(row.fields) if row.fields else {},
                "count": row.count,
            }
            for row in rows
        ]

    async def _query_performance_metrics(
        self, db: Session, query: TimeSeriesQuery
    ) -> List[Dict[str, Any]]:
        """Query performance metrics from time-series table"""
        sql = """
        SELECT
            timestamp,
            metric_name,
            metric_type,
            component,
            value,
            unit,
            tags,
            metadata,
            AVG(value) as avg_value,
            MIN(value) as min_value,
            MAX(value) as max_value,
            COUNT(*) as count
        FROM performance_metrics_ts
        WHERE organization_id = :org_id
            AND timestamp BETWEEN :start_time AND :end_time
        """

        params = {
            "org_id": query.tags.get("organization_id") if query.tags else None,
            "start_time": query.start_time,
            "end_time": query.end_time,
        }

        # Add tag filters
        if query.tags:
            tag_conditions = []
            for i, (key, value) in enumerate(query.tags.items()):
                if key != "organization_id":
                    param_name = f"tag_{i}"
                    tag_conditions.append(f"tags::text LIKE :{param_name}")
                    params[param_name] = f'%"{key}": "{value}"%'

            if tag_conditions:
                sql += " AND " + " AND ".join(tag_conditions)

        # Add grouping
        if query.aggregation:
            if query.aggregation == "hour":
                sql += " GROUP BY date_trunc('hour', timestamp), metric_name, component"
            elif query.aggregation == "day":
                sql += " GROUP BY date_trunc('day', timestamp), metric_name, component"
            elif query.aggregation == "week":
                sql += " GROUP BY date_trunc('week', timestamp), metric_name, component"
        else:
            sql += " GROUP BY timestamp, metric_name, metric_type, component, value, unit, tags, metadata"

        # Add ordering
        sql += " ORDER BY timestamp DESC"

        # Add limit
        if query.limit:
            sql += " LIMIT :limit"
            params["limit"] = int(query.limit)

        result = db.execute(text(sql), params)
        rows = result.fetchall()

        return [
            {
                "timestamp": row.timestamp.isoformat(),
                "metric_name": row.metric_name,
                "metric_type": row.metric_type,
                "component": row.component,
                "value": row.value,
                "unit": row.unit,
                "tags": json.loads(row.tags) if row.tags else {},
                "metadata": json.loads(row.metadata) if row.metadata else {},
                "avg_value": float(row.avg_value) if row.avg_value else None,
                "min_value": float(row.min_value) if row.min_value else None,
                "max_value": float(row.max_value) if row.max_value else None,
                "count": row.count,
            }
            for row in rows
        ]

    async def _query_user_sessions(
        self, db: Session, query: TimeSeriesQuery
    ) -> List[Dict[str, Any]]:
        """Query user sessions from time-series table"""
        sql = """
        SELECT
            timestamp,
            user_id,
            session_duration,
            engagement_score,
            page_views,
            searches,
            downloads,
            tags,
            AVG(engagement_score) as avg_engagement,
            COUNT(*) as session_count
        FROM user_sessions_ts
        WHERE organization_id = :org_id
            AND timestamp BETWEEN :start_time AND :end_time
        """

        params = {
            "org_id": query.tags.get("organization_id") if query.tags else None,
            "start_time": query.start_time,
            "end_time": query.end_time,
        }

        # Add tag filters
        if query.tags:
            tag_conditions = []
            for i, (key, value) in enumerate(query.tags.items()):
                if key != "organization_id":
                    param_name = f"tag_{i}"
                    tag_conditions.append(f"tags::text LIKE :{param_name}")
                    params[param_name] = f'%"{key}": "{value}"%'

            if tag_conditions:
                sql += " AND " + " AND ".join(tag_conditions)

        # Add grouping
        if query.aggregation:
            if query.aggregation == "hour":
                sql += " GROUP BY date_trunc('hour', timestamp), user_id"
            elif query.aggregation == "day":
                sql += " GROUP BY date_trunc('day', timestamp), user_id"
            elif query.aggregation == "week":
                sql += " GROUP BY date_trunc('week', timestamp), user_id"
        else:
            sql += " GROUP BY timestamp, user_id, session_duration, engagement_score, page_views, searches, downloads, tags"

        # Add ordering
        sql += " ORDER BY timestamp DESC"

        # Add limit
        if query.limit:
            sql += " LIMIT :limit"
            params["limit"] = int(query.limit)

        result = db.execute(text(sql), params)
        rows = result.fetchall()

        return [
            {
                "timestamp": row.timestamp.isoformat(),
                "user_id": row.user_id,
                "session_duration": row.session_duration,
                "engagement_score": row.engagement_score,
                "page_views": row.page_views,
                "searches": row.searches,
                "downloads": row.downloads,
                "tags": json.loads(row.tags) if row.tags else {},
                "avg_engagement": float(row.avg_engagement)
                if row.avg_engagement
                else None,
                "session_count": row.session_count,
            }
            for row in rows
        ]

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get time-series storage statistics"""
        try:
            db = next(get_db())

            # Get table sizes
            tables = [
                "analytics_events_ts",
                "performance_metrics_ts",
                "user_sessions_ts",
            ]
            stats = {}

            for table in tables:
                # Validate table name
                if table not in ["analytics_events_ts", "performance_metrics_ts", "user_sessions_ts"]:
                    continue

                # Get row count
                count_sql = "SELECT COUNT(*) as count FROM {}".format(table)  # nosec: B608 - table validated against whitelist
                count_result = db.execute(text(count_sql)).first()

                # Get table size (approximate) - use parameterized query
                size_sql = """
                SELECT
                    pg_size_pretty(pg_total_relation_size(:table_name)) as size,
                    pg_total_relation_size(:table_name) as size_bytes
                """
                size_result = db.execute(text(size_sql), {'table_name': table}).first()

                stats[table] = {
                    "row_count": count_result.count,
                    "size_pretty": size_result.size,
                    "size_bytes": size_result.size_bytes,
                }

            db.close()
            return stats

        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}

    async def cleanup_old_data(self, retention_days: int = 365) -> int:
        """Clean up old time-series data based on retention policy"""
        try:
            db = next(get_db())
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            deleted_count = 0
            tables = [
                "analytics_events_ts",
                "performance_metrics_ts",
                "user_sessions_ts",
            ]

            for table in tables:
                # Validate table name
                if table not in ["analytics_events_ts", "performance_metrics_ts", "user_sessions_ts"]:
                    continue

                delete_sql = "DELETE FROM {} WHERE timestamp < :cutoff_date".format(table)  # nosec: B608 - table validated against whitelist
                result = db.execute(text(delete_sql), {"cutoff_date": cutoff_date})
                deleted_count += result.rowcount

            db.commit()
            db.close()

            logger.info(f"Cleaned up {deleted_count} old time-series records")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            if "db" in locals():
                db.rollback()
                db.close()
            return 0


class InfluxDBTimeSeriesStore:
    """InfluxDB-based time-series storage"""

    def __init__(self):
        self.config = get_analytics_config()
        self.client: Optional[InfluxDBClient] = None
        self._connected = False

    async def initialize(self):
        """Initialize InfluxDB connection"""
        if not INFLUXDB_AVAILABLE:
            raise AnalyticsServiceException(
                "influxdb",
                "InfluxDB client not available",
                "Install influxdb-client package",
            )

        if not self.config.time_series_db_url:
            raise AnalyticsServiceException(
                "influxdb",
                "InfluxDB URL not configured",
                "Set TIME_SERIES_DB_URL in configuration",
            )

        if not self.config.time_series_db_token:
            raise AnalyticsServiceException(
                "influxdb",
                "InfluxDB token not configured",
                "Set TIME_SERIES_DB_TOKEN in configuration",
            )

        if not self.config.time_series_db_org:
            raise AnalyticsServiceException(
                "influxdb",
                "InfluxDB organization not configured",
                "Set TIME_SERIES_DB_ORG in configuration",
            )

        try:
            self.client = InfluxDBClient(
                url=self.config.time_series_db_url,
                token=self.config.time_series_db_token,
                org=self.config.time_series_db_org,
            )

            # Test connection
            health = self.client.health()
            if health.status == "pass":
                self._connected = True
                logger.info("InfluxDB time-series store initialized")
            else:
                raise Exception(f"InfluxDB health check failed: {health.message}")

        except Exception as e:
            logger.error(f"Failed to initialize InfluxDB: {e}")
            self._connected = False
            raise

    async def write_point(self, point: TimeSeriesPoint) -> bool:
        """Write a single time-series point to InfluxDB"""
        if not self._connected:
            return False

        try:
            write_api = self.client.write_api(write_options=SYNCHRONOUS)

            influx_point = Point(point.measurement)
            influx_point.time(point.timestamp)

            # Add tags
            for key, value in point.tags.items():
                influx_point.tag(key, str(value))

            # Add fields
            for key, value in point.fields.items():
                influx_point.field(key, value)

            # Add value as default field if not in fields
            if "value" not in point.fields:
                influx_point.field("value", point.value)

            write_api.write(bucket="analytics", record=influx_point)
            return True

        except Exception as e:
            logger.error(f"Failed to write point to InfluxDB: {e}")
            return False

    async def write_points(self, points: List[TimeSeriesPoint]) -> int:
        """Write multiple time-series points to InfluxDB"""
        if not self._connected:
            return 0

        try:
            write_api = self.client.write_api(write_options=SYNCHRONOUS)
            influx_points = []

            for point in points:
                influx_point = Point(point.measurement)
                influx_point.time(point.timestamp)

                # Add tags
                for key, value in point.tags.items():
                    influx_point.tag(key, str(value))

                # Add fields
                for key, value in point.fields.items():
                    influx_point.field(key, value)

                # Add value as default field if not in fields
                if "value" not in point.fields:
                    influx_point.field("value", point.value)

                influx_points.append(influx_point)

            write_api.write(bucket="analytics", record=influx_points)
            return len(points)

        except Exception as e:
            logger.error(f"Failed to write points to InfluxDB: {e}")
            return 0

    async def query(self, query_spec: TimeSeriesQuery) -> List[Dict[str, Any]]:
        """Query time-series data from InfluxDB"""
        if not self._connected:
            return []

        try:
            query_api = self.client.query_api()

            # Build Flux query
            flux_query = f"""
            from(bucket: "analytics")
                |> range(start: {query_spec.start_time.isoformat()}, stop: {query_spec.end_time.isoformat()})
                |> filter(fn: (r) => r._measurement == "{query_spec.measurement}")
            """

            # Add tag filters
            if query_spec.tags:
                for key, value in query_spec.tags.items():
                    flux_query += f'|> filter(fn: (r) => r.{key} == "{value}")\n'

            # Add field filters
            if query_spec.fields:
                fields_filter = " or ".join(
                    [f'r._field == "{field}"' for field in query_spec.fields]
                )
                flux_query += f"|> filter(fn: (r) => {fields_filter})\n"

            # Add aggregation
            if query_spec.aggregation:
                if query_spec.aggregation == "hour":
                    flux_query += (
                        "|> aggregateWindow(every: 1h, fn: mean, createEmpty: false)\n"
                    )
                elif query_spec.aggregation == "day":
                    flux_query += (
                        "|> aggregateWindow(every: 1d, fn: mean, createEmpty: false)\n"
                    )
                elif query_spec.aggregation == "week":
                    flux_query += (
                        "|> aggregateWindow(every: 1w, fn: mean, createEmpty: false)\n"
                    )

            # Add limit
            if query_spec.limit:
                flux_query += f"|> limit(n: {query_spec.limit})\n"

            # Execute query
            result = query_api.query(flux_query)

            # Convert to dictionary format
            data = []
            for table in result:
                for record in table.records:
                    data.append(
                        {
                            "timestamp": record.get_time().isoformat(),
                            "measurement": record.get_measurement(),
                            "field": record.get_field(),
                            "value": record.get_value(),
                            "tags": record.values,
                        }
                    )

            return data

        except Exception as e:
            logger.error(f"Failed to query InfluxDB: {e}")
            return []


class HybridTimeSeriesStore:
    """Hybrid time-series store using both PostgreSQL and InfluxDB"""

    def __init__(self):
        self.postgres_store = PostgreSQLTimeSeriesStore()
        self.influxdb_store = InfluxDBTimeSeriesStore()
        self._initialized = False

    async def initialize(self):
        """Initialize both stores"""
        try:
            # Initialize PostgreSQL (always available)
            await self.postgres_store.initialize()

            # Try to initialize InfluxDB (optional)
            try:
                await self.influxdb_store.initialize()
                logger.info(
                    "Hybrid store initialized with both PostgreSQL and InfluxDB"
                )
            except Exception as e:
                logger.warning(f"InfluxDB not available, using PostgreSQL only: {e}")

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize hybrid store: {e}")
            raise

    async def write_point(self, point: TimeSeriesPoint) -> bool:
        """Write point to available stores"""
        success = False

        # Try InfluxDB first (better for time-series)
        if self.influxdb_store._connected:
            success = await self.influxdb_store.write_point(point)

        # Fallback to PostgreSQL
        if not success:
            success = await self.postgres_store.write_point(point)

        return success

    async def write_points(self, points: List[TimeSeriesPoint]) -> int:
        """Write points to available stores"""
        # Try InfluxDB first
        if self.influxdb_store._connected:
            return await self.influxdb_store.write_points(points)
        else:
            return await self.postgres_store.write_points(points)

    async def query(self, query_spec: TimeSeriesQuery) -> List[Dict[str, Any]]:
        """Query from available stores"""
        # Try InfluxDB first
        if self.influxdb_store._connected:
            return await self.influxdb_store.query(query_spec)
        else:
            return await self.postgres_store.query(query_spec)


class TimeSeriesStoreManager:
    """Manager for time-series storage operations"""

    def __init__(self):
        self.config = get_analytics_config()
        self.store: Union[
            PostgreSQLTimeSeriesStore, InfluxDBTimeSeriesStore, HybridTimeSeriesStore
        ] = None
        self._initialized = False

    async def initialize(self):
        """Initialize the appropriate time-series store"""
        if self._initialized:
            return

        backend = getattr(
            self.config, "time_series_backend", TimeSeriesBackend.POSTGRESQL
        )

        try:
            if backend == TimeSeriesBackend.INFLUXDB:
                self.store = InfluxDBTimeSeriesStore()
            elif backend == TimeSeriesBackend.POSTGRESQL:
                self.store = PostgreSQLTimeSeriesStore()
            elif backend == TimeSeriesBackend.HYBRID:
                self.store = HybridTimeSeriesStore()
            else:
                logger.warning(
                    f"Unknown time-series backend: {backend}, using PostgreSQL"
                )
                self.store = PostgreSQLTimeSeriesStore()

            await self.store.initialize()
            self._initialized = True
            logger.info(f"Time-series store initialized with backend: {backend}")

        except Exception as e:
            logger.error(f"Failed to initialize time-series store: {e}")
            # Fallback to PostgreSQL
            self.store = PostgreSQLTimeSeriesStore()
            await self.store.initialize()
            self._initialized = True
            logger.info("Fallback to PostgreSQL time-series store completed")

    async def write_analytics_event(self, event: AnalyticsEvent) -> bool:
        """Write analytics event to time-series store"""
        if not self._initialized:
            await self.initialize()

        point = TimeSeriesPoint(
            measurement=event.event_name,
            timestamp=event.timestamp or event.created_at,
            value=1,  # Event count
            tags={
                "organization_id": str(event.organization_id),
                "event_type": event.event_type,
                "source": event.source or "api",
            },
            fields={
                "event_id": str(event.id),
                "event_data": event.event_data or {},
                "severity": event.severity.value if event.severity else "low",
            },
        )

        return await self.store.write_point(point)

    async def write_performance_metric(self, metric: PerformanceLog) -> bool:
        """Write performance metric to time-series store"""
        if not self._initialized:
            await self.initialize()

        point = TimeSeriesPoint(
            measurement=metric.metric_name,
            timestamp=metric.timestamp or metric.created_at,
            value=metric.value,
            tags={
                "organization_id": str(metric.organization_id),
                "component": metric.component,
                "host": metric.host,
                "environment": metric.environment,
            },
            fields={
                "metric_id": str(metric.id),
                "unit": metric.unit,
                "metric_type": metric.metric_type.value,
                "performance_level": metric.performance_level.value,
                "threshold": metric.threshold or {},
                "tags": metric.tags or [],
                "metadata": metric.event_metadata or {},
            },
        )

        return await self.store.write_point(point)

    async def write_user_session_summary(self, session: UserSession) -> bool:
        """Write user session summary to time-series store"""
        if not self._initialized:
            await self.initialize()

        point = TimeSeriesPoint(
            measurement="user_session_summary",
            timestamp=session.session_end or session.created_at,
            value=session.engagement_score or 0,
            tags={
                "organization_id": str(session.organization_id),
                "user_id": str(session.user_id),
                "device_type": session.device_type,
                "browser": session.browser,
            },
            fields={
                "session_id": str(session.id),
                "session_duration": session.duration_seconds,
                "page_views": session.page_views,
                "searches": session.total_searches,
                "downloads": session.total_downloads,
                "bounce_type": session.bounce_type,
                "engagement_score": session.engagement_score,
            },
        )

        return await self.store.write_point(point)

    async def query_analytics_events(
        self,
        organization_id: str,
        start_time: datetime,
        end_time: datetime,
        event_type: Optional[str] = None,
        aggregation: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query analytics events from time-series store"""
        if not self._initialized:
            await self.initialize()

        tags = {"organization_id": organization_id}
        if event_type:
            tags["event_type"] = event_type

        query_spec = TimeSeriesQuery(
            measurement="analytics_events",
            start_time=start_time,
            end_time=end_time,
            tags=tags,
            aggregation=aggregation,
            limit=limit,
        )

        return await self.store.query(query_spec)

    async def query_performance_metrics(
        self,
        organization_id: str,
        start_time: datetime,
        end_time: datetime,
        component: Optional[str] = None,
        aggregation: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query performance metrics from time-series store"""
        if not self._initialized:
            await self.initialize()

        tags = {"organization_id": organization_id}
        if component:
            tags["component"] = component

        query_spec = TimeSeriesQuery(
            measurement="performance_metrics",
            start_time=start_time,
            end_time=end_time,
            tags=tags,
            aggregation=aggregation,
            limit=limit,
        )

        return await self.store.query(query_spec)

    async def query_user_sessions(
        self,
        organization_id: str,
        start_time: datetime,
        end_time: datetime,
        aggregation: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query user sessions from time-series store"""
        if not self._initialized:
            await self.initialize()

        query_spec = TimeSeriesQuery(
            measurement="user_sessions",
            start_time=start_time,
            end_time=end_time,
            tags={"organization_id": organization_id},
            aggregation=aggregation,
            limit=limit,
        )

        return await self.store.query(query_spec)

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        if not self._initialized:
            await self.initialize()

        if hasattr(self.store, "get_storage_stats"):
            return await self.store.get_storage_stats()
        else:
            return {"message": "Storage stats not available for this backend"}

    async def cleanup_old_data(self, retention_days: Optional[int] = None) -> int:
        """Clean up old data based on retention policy"""
        if not self._initialized:
            await self.initialize()

        retention_days = (
            retention_days or self.config.retention.analytics_events_retention_days
        )

        if hasattr(self.store, "cleanup_old_data"):
            return await self.store.cleanup_old_data(retention_days)
        else:
            logger.warning("Data cleanup not available for this backend")
            return 0


# Global time-series store manager
_time_series_manager = TimeSeriesStoreManager()


def get_time_series_manager() -> TimeSeriesStoreManager:
    """Get the global time-series store manager"""
    return _time_series_manager
