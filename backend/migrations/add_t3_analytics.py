"""
Add T3 analytics tables (without conflicting existing tables)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.core.database import engine
import logging

logger = logging.getLogger(__name__)


def run_migration():
    """Run the T3 analytics migration"""
    logger.info("Starting T3 analytics migration...")

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Create quality_alerts table
            logger.info("Creating quality_alerts table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS quality_alerts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    metric_id UUID,
                    metric_type VARCHAR(50),
                    severity VARCHAR(20) NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    message TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'active' NOT NULL,
                    acknowledged_at TIMESTAMP WITH TIME ZONE,
                    acknowledged_by UUID REFERENCES users(id),
                    resolved_at TIMESTAMP WITH TIME ZONE,
                    resolved_by UUID REFERENCES users(id),
                    organization_id UUID REFERENCES organizations(id) NOT NULL,
                    query TEXT,
                    current_value FLOAT,
                    threshold_value FLOAT,
                    violation_type VARCHAR(10),
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """))

            # Create indexes for quality_alerts
            logger.info("Creating indexes for quality_alerts...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_quality_alerts_org_status
                ON quality_alerts (organization_id, status)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_quality_alerts_severity
                ON quality_alerts (severity, created_at)
            """))

            # Create metric_aggregations table
            logger.info("Creating metric_aggregations table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS metric_aggregations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    metric_type VARCHAR(50) NOT NULL,
                    aggregation_type VARCHAR(20) NOT NULL,
                    aggregation_period_start TIMESTAMP WITH TIME ZONE NOT NULL,
                    aggregation_period_end TIMESTAMP WITH TIME ZONE NOT NULL,
                    avg_value FLOAT NOT NULL,
                    min_value FLOAT NOT NULL,
                    max_value FLOAT NOT NULL,
                    count_values INTEGER NOT NULL,
                    sum_values FLOAT NOT NULL,
                    std_deviation FLOAT,
                    percentiles JSONB,
                    organization_id UUID REFERENCES organizations(id) NOT NULL,
                    search_type VARCHAR(20),
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """))

            # Create indexes for metric_aggregations
            logger.info("Creating indexes for metric_aggregations...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_metric_agg_org_type_period
                ON metric_aggregations (organization_id, metric_type, aggregation_type)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_metric_agg_period_start
                ON metric_aggregations (aggregation_period_start)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_metric_agg_search_type
                ON metric_aggregations (search_type)
            """))

            # Create search_sessions table
            logger.info("Creating search_sessions table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS search_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id VARCHAR(100) NOT NULL UNIQUE,
                    user_id UUID REFERENCES users(id),
                    organization_id UUID REFERENCES organizations(id) NOT NULL,
                    start_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    end_time TIMESTAMP WITH TIME ZONE,
                    search_count INTEGER DEFAULT 0 NOT NULL,
                    total_response_time FLOAT DEFAULT 0.0 NOT NULL,
                    user_agent TEXT,
                    ip_address VARCHAR(45),
                    referrer TEXT,
                    avg_response_time FLOAT,
                    session_duration FLOAT,
                    bounce_rate BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """))

            # Create indexes for search_sessions
            logger.info("Creating indexes for search_sessions...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_search_sessions_org_user
                ON search_sessions (organization_id, user_id)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_search_sessions_start_time
                ON search_sessions (start_time)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_search_sessions_session_id
                ON search_sessions (session_id)
            """))

            # Create search_events table
            logger.info("Creating search_events table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS search_events (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id UUID REFERENCES search_sessions(id) ON DELETE CASCADE,
                    search_query_id UUID,
                    query TEXT NOT NULL,
                    search_type VARCHAR(20) NOT NULL,
                    results_count INTEGER NOT NULL,
                    response_time FLOAT NOT NULL,
                    clicked_results INTEGER DEFAULT 0 NOT NULL,
                    clicked_result_ids JSONB,
                    time_to_first_click FLOAT,
                    dwell_time FLOAT,
                    user_rating INTEGER,
                    feedback_text TEXT,
                    is_bookmarked BOOLEAN DEFAULT FALSE,
                    user_id UUID REFERENCES users(id),
                    organization_id UUID REFERENCES organizations(id) NOT NULL,
                    page_number INTEGER DEFAULT 1 NOT NULL,
                    filters_applied JSONB,
                    sort_order VARCHAR(20),
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """))

            # Create indexes for search_events
            logger.info("Creating indexes for search_events...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_search_events_org_time
                ON search_events (organization_id, created_at)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_search_events_session
                ON search_events (session_id)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_search_events_query
                ON search_events USING gin(to_tsvector('english', query))
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_search_events_user
                ON search_events (user_id)
            """))

            # Create system_metrics table
            logger.info("Creating system_metrics table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    metric_name VARCHAR(100) NOT NULL,
                    metric_value FLOAT NOT NULL,
                    metric_unit VARCHAR(20),
                    component_name VARCHAR(100) NOT NULL,
                    component_instance VARCHAR(100),
                    organization_id UUID REFERENCES organizations(id),
                    metadata JSONB,
                    measured_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """))

            # Create indexes for system_metrics
            logger.info("Creating indexes for system_metrics...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_system_metrics_component_time
                ON system_metrics (component_name, measured_at)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_system_metrics_name_time
                ON system_metrics (metric_name, measured_at)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_system_metrics_org_time
                ON system_metrics (organization_id, measured_at)
            """))

            # Create quality_thresholds table
            logger.info("Creating quality_thresholds table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS quality_thresholds (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    metric_type VARCHAR(50) NOT NULL,
                    threshold_min FLOAT,
                    threshold_max FLOAT,
                    threshold_target FLOAT,
                    alert_severity VARCHAR(20) DEFAULT 'medium' NOT NULL,
                    is_enabled BOOLEAN DEFAULT TRUE NOT NULL,
                    alert_cooldown_minutes INTEGER DEFAULT 60 NOT NULL,
                    organization_id UUID REFERENCES organizations(id),
                    search_type VARCHAR(20),
                    description TEXT,
                    created_by UUID REFERENCES users(id) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """))

            # Create indexes for quality_thresholds
            logger.info("Creating indexes for quality_thresholds...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_quality_thresholds_org_type
                ON quality_thresholds (organization_id, metric_type)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_quality_thresholds_enabled
                ON quality_thresholds (is_enabled)
            """))

            # Add updated_at trigger function (if not exists)
            logger.info("Adding updated_at trigger function...")
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """))

            # Create user_sessions table
            logger.info("Creating user_sessions table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES users(id) NOT NULL,
                    organization_id UUID REFERENCES organizations(id) NOT NULL,
                    session_id VARCHAR(255) NOT NULL UNIQUE,
                    session_token VARCHAR(512),
                    status VARCHAR(20) DEFAULT 'active' NOT NULL,
                    user_agent TEXT,
                    ip_address VARCHAR(45),
                    device_type VARCHAR(50),
                    browser VARCHAR(100),
                    os VARCHAR(100),
                    location_country VARCHAR(2),
                    location_city VARCHAR(100),
                    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    last_activity TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    ended_at TIMESTAMP WITH TIME ZONE,
                    duration_seconds INTEGER,
                    total_searches INTEGER DEFAULT 0 NOT NULL,
                    total_documents_viewed INTEGER DEFAULT 0 NOT NULL,
                    total_downloads INTEGER DEFAULT 0 NOT NULL,
                    total_clicks INTEGER DEFAULT 0 NOT NULL,
                    engagement_score FLOAT DEFAULT 0.0 NOT NULL,
                    search_queries JSONB,
                    viewed_documents JSONB,
                    clicked_results JSONB,
                    navigation_path JSONB,
                    bounce_rate FLOAT DEFAULT 0.0 NOT NULL,
                    conversion_events JSONB,
                    satisfaction_rating INTEGER,
                    avg_response_time FLOAT,
                    error_count INTEGER DEFAULT 0 NOT NULL,
                    page_load_time FLOAT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    is_deleted BOOLEAN DEFAULT FALSE NOT NULL
                )
            """))

            # Create indexes for user_sessions
            logger.info("Creating indexes for user_sessions...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions (user_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_organization_id ON user_sessions (organization_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_session_id ON user_sessions (session_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_status ON user_sessions (status)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_started_at ON user_sessions (started_at)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_last_activity ON user_sessions (last_activity)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_user_org ON user_sessions (user_id, organization_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_active_sessions ON user_sessions (user_id, status, last_activity)
            """))

            # Create analytics_events table
            logger.info("Creating analytics_events table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    event_type VARCHAR(50) NOT NULL,
                    event_category VARCHAR(100),
                    severity VARCHAR(20) DEFAULT 'info' NOT NULL,
                    user_id UUID REFERENCES users(id),
                    session_id VARCHAR(255),
                    organization_id UUID REFERENCES organizations(id) NOT NULL,
                    event_name VARCHAR(255) NOT NULL,
                    description TEXT,
                    event_data JSONB,
                    user_agent TEXT,
                    ip_address VARCHAR(45),
                    referrer TEXT,
                    page_url TEXT,
                    api_endpoint VARCHAR(500),
                    response_time_ms INTEGER,
                    memory_usage_mb FLOAT,
                    cpu_usage_percent FLOAT,
                    value FLOAT,
                    unit VARCHAR(50),
                    tags JSONB,
                    event_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    date_hour VARCHAR(13) NOT NULL,
                    date_day VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    processed BOOLEAN DEFAULT FALSE NOT NULL,
                    batch_id VARCHAR(100)
                )
            """))

            # Create indexes for analytics_events
            logger.info("Creating indexes for analytics_events...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_analytics_events_type_org ON analytics_events (event_type, organization_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_analytics_events_user_time ON analytics_events (user_id, event_timestamp)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_analytics_events_org_time ON analytics_events (organization_id, event_timestamp)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_analytics_events_session ON analytics_events (session_id, event_timestamp)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_analytics_events_severity ON analytics_events (severity, event_timestamp)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_analytics_events_date_hour ON analytics_events (date_hour)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_analytics_events_date_day ON analytics_events (date_day)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_analytics_events_processed ON analytics_events (processed)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_analytics_events_batch ON analytics_events (batch_id)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_analytics_events_composite ON analytics_events (organization_id, event_type, date_day)
            """))

            # Create performance_logs table
            logger.info("Creating performance_logs table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS performance_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    metric_name VARCHAR(255) NOT NULL,
                    metric_category VARCHAR(50) NOT NULL,
                    performance_level VARCHAR(20) NOT NULL,
                    organization_id UUID REFERENCES organizations(id),
                    value FLOAT NOT NULL,
                    unit VARCHAR(50),
                    baseline_value FLOAT,
                    threshold_warning FLOAT,
                    threshold_critical FLOAT,
                    cpu_usage_percent FLOAT,
                    memory_usage_mb FLOAT,
                    memory_usage_percent FLOAT,
                    disk_usage_gb FLOAT,
                    disk_usage_percent FLOAT,
                    network_io_mb FLOAT,
                    response_time_ms INTEGER,
                    request_count INTEGER,
                    error_count INTEGER,
                    active_connections INTEGER,
                    queue_size INTEGER,
                    db_connections INTEGER,
                    db_query_time_ms INTEGER,
                    db_slow_queries INTEGER,
                    db_cache_hit_rate FLOAT,
                    search_query_time_ms INTEGER,
                    index_size_mb FLOAT,
                    search_results_count INTEGER,
                    component VARCHAR(100),
                    environment VARCHAR(50),
                    version VARCHAR(50),
                    node_id VARCHAR(100),
                    tags JSONB,
                    event_metadata JSONB,
                    alert_triggered BOOLEAN DEFAULT FALSE NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    date_hour VARCHAR(13) NOT NULL,
                    date_day VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    batch_id VARCHAR(100)
                )
            """))

            # Create indexes for performance_logs
            logger.info("Creating indexes for performance_logs...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_logs_metric_time ON performance_logs (metric_name, timestamp)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_logs_category_time ON performance_logs (metric_category, timestamp)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_logs_org_time ON performance_logs (organization_id, timestamp)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_logs_level_time ON performance_logs (performance_level, timestamp)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_logs_component_time ON performance_logs (component, timestamp)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_logs_date_hour ON performance_logs (date_hour)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_logs_date_day ON performance_logs (date_day)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_logs_alert ON performance_logs (alert_triggered, timestamp)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_logs_composite ON performance_logs (metric_category, organization_id, date_day)
            """))

            # Add triggers for updated_at columns
            logger.info("Adding updated_at triggers...")
            tables_with_updated_at = [
                'quality_alerts',
                'metric_aggregations',
                'search_sessions',
                'search_events',
                'quality_thresholds',
                'user_sessions'
            ]

            for table in tables_with_updated_at:
                conn.execute(text(f"""
                    DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};
                    CREATE TRIGGER update_{table}_updated_at
                        BEFORE UPDATE ON {table}
                        FOR EACH ROW
                        EXECUTE FUNCTION update_updated_at_column();
                """))

            # Create default quality thresholds
            logger.info("Creating default quality thresholds...")
            default_thresholds = [
                # Response time thresholds (in milliseconds)
                ('response_time', None, 5000.0, 2000.0, 'high'),
                ('response_time', 1000.0, None, 2000.0, 'medium'),

                # Result count thresholds
                ('result_count', 1.0, None, 10.0, 'medium'),
                ('result_count', None, 100.0, 50.0, 'low'),

                # Relevance score thresholds
                ('avg_relevance_score', 0.5, None, 0.7, 'medium'),
                ('avg_relevance_score', None, 2.0, 1.5, 'low'),

                # Freshness thresholds (in days)
                ('freshness', None, 365.0, 180.0, 'medium'),

                # Diversity score thresholds
                ('result_diversity', 0.3, None, 0.5, 'medium'),
            ]

            # Get an existing user for created_by
            admin_user = conn.execute(text("""
                SELECT id FROM users LIMIT 1
            """)).scalar()

            if not admin_user:
                # Skip creating default thresholds if no users exist
                logger.warning("No users found, skipping default threshold creation")
                admin_user = None

            if admin_user:
                for metric_type, min_val, max_val, target_val, severity in default_thresholds:
                    conn.execute(text("""
                        INSERT INTO quality_thresholds (
                            metric_type, threshold_min, threshold_max, threshold_target,
                            alert_severity, description, created_by
                        ) VALUES (
                            :metric_type, :min_val, :max_val, :target_val,
                            :severity, :description, :admin_user
                        ) ON CONFLICT DO NOTHING
                    """), {
                        'metric_type': metric_type,
                        'min_val': min_val,
                        'max_val': max_val,
                        'target_val': target_val,
                        'severity': severity,
                        'description': f'Default threshold for {metric_type}',
                        'admin_user': admin_user
                    })

            trans.commit()
            logger.info("T3 analytics migration completed successfully!")

        except Exception as e:
            trans.rollback()
            logger.error(f"Migration failed: {e}")
            raise


def rollback_migration():
    """Rollback the T3 analytics migration"""
    logger.info("Rolling back T3 analytics migration...")

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Drop tables in reverse order of creation
            tables = [
                'quality_thresholds',
                'system_metrics',
                'performance_logs',
                'analytics_events',
                'user_sessions',
                'search_events',
                'search_sessions',
                'metric_aggregations',
                'quality_alerts'
            ]

            for table in tables:
                logger.info(f"Dropping table {table}...")
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))

            # Keep the trigger function as it might be used by other tables
            # conn.execute(text("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE"))

            trans.commit()
            logger.info("T3 analytics migration rollback completed!")

        except Exception as e:
            trans.rollback()
            logger.error(f"Rollback failed: {e}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="T3 analytics migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback migration")

    args = parser.parse_args()

    if args.rollback:
        rollback_migration()
    else:
        run_migration()