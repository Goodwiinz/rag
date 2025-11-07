"""
Migration 006: Create comprehensive monitoring and observability tables

This migration extends the existing monitoring schema with advanced observability features:
- Enhanced metrics collection with definitions and aggregations
- Distributed tracing with spans and events
- Structured logging with pattern detection
- Advanced alerting with rules and channels
- Comprehensive health checking
- Monitoring session correlation
"""

import uuid
from datetime import datetime
from sqlalchemy import text
from ..core.database import engine, get_db


def upgrade():
    """Create comprehensive monitoring tables"""

    # Create monitoring-specific tables that extend the existing schema

    # Metric definitions table
    create_metric_definitions_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_metric_definitions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) UNIQUE NOT NULL,
        description TEXT,
        metric_type VARCHAR(50) NOT NULL,
        unit VARCHAR(50) NOT NULL,
        tags JSONB DEFAULT '{}',
        labels_schema JSONB DEFAULT '{}',
        aggregation_rules JSONB DEFAULT '{}',
        retention_days INTEGER DEFAULT 30,
        is_active BOOLEAN DEFAULT TRUE,
        category VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Metrics table with enhanced indexing
    create_metrics_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_metrics (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        definition_id UUID NOT NULL REFERENCES monitoring_metric_definitions(id) ON DELETE CASCADE,
        value DECIMAL(15,6) NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL,
        labels JSONB DEFAULT '{}',
        source VARCHAR(100),
        instance VARCHAR(255),
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    ) PARTITION BY RANGE (timestamp);
    """

    # Create initial partitions for metrics
    create_metrics_partitions_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_metrics_y2024m11
        PARTITION OF monitoring_metrics
        FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');

    CREATE TABLE IF NOT EXISTS monitoring_metrics_y2024m12
        PARTITION OF monitoring_metrics
        FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');
    """

    # Metric aggregations table
    create_metric_aggregations_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_metric_aggregations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        definition_id UUID NOT NULL REFERENCES monitoring_metric_definitions(id) ON DELETE CASCADE,
        aggregation_type VARCHAR(50) NOT NULL,
        time_bucket TIMESTAMPTZ NOT NULL,
        bucket_size_minutes INTEGER NOT NULL,
        value DECIMAL(15,6) NOT NULL,
        sample_count INTEGER DEFAULT 0,
        labels JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    ) PARTITION BY RANGE (time_bucket);
    """

    # Time series data table
    create_time_series_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_time_series (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        metric_name VARCHAR(255) NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL,
        value DECIMAL(15,6) NOT NULL,
        labels JSONB DEFAULT '{}',
        source VARCHAR(100),
        quality VARCHAR(20) DEFAULT 'good',
        annotations JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    ) PARTITION BY RANGE (timestamp);
    """

    # Traces table
    create_traces_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_traces (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        trace_id VARCHAR(128) UNIQUE NOT NULL,
        root_span_id VARCHAR(128) NOT NULL,
        service_name VARCHAR(255) NOT NULL,
        operation_name VARCHAR(255) NOT NULL,
        start_time TIMESTAMPTZ NOT NULL,
        end_time TIMESTAMPTZ,
        duration_ms DECIMAL(15,6),
        span_count INTEGER DEFAULT 0,
        error_count INTEGER DEFAULT 0,
        status VARCHAR(50) DEFAULT 'ok',
        tags JSONB DEFAULT '{}',
        resource_attributes JSONB DEFAULT '{}',
        sampled BOOLEAN DEFAULT TRUE,
        processing_status VARCHAR(50) DEFAULT 'pending',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Spans table
    create_spans_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_spans (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        trace_id VARCHAR(128) NOT NULL REFERENCES monitoring_traces(trace_id),
        span_id VARCHAR(128) UNIQUE NOT NULL,
        parent_span_id VARCHAR(128),
        operation_name VARCHAR(255) NOT NULL,
        kind VARCHAR(50) DEFAULT 'internal',
        start_time TIMESTAMPTZ NOT NULL,
        end_time TIMESTAMPTZ,
        duration_ms DECIMAL(15,6),
        status VARCHAR(50) DEFAULT 'ok',
        status_message TEXT,
        attributes JSONB DEFAULT '{}',
        tags JSONB DEFAULT '{}',
        resource_attributes JSONB DEFAULT '{}',
        service_name VARCHAR(255) NOT NULL,
        component VARCHAR(255),
        library VARCHAR(255),
        sampled BOOLEAN DEFAULT TRUE,
        processing_status VARCHAR(50) DEFAULT 'pending',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Span events table
    create_span_events_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_span_events (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        span_id VARCHAR(128) NOT NULL REFERENCES monitoring_spans(span_id),
        name VARCHAR(255) NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL,
        attributes JSONB DEFAULT '{}',
        dropped_attributes_count INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Span links table
    create_span_links_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_span_links (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        span_id VARCHAR(128) NOT NULL REFERENCES monitoring_spans(span_id),
        linked_trace_id VARCHAR(128) NOT NULL,
        linked_span_id VARCHAR(128) NOT NULL,
        attributes JSONB DEFAULT '{}',
        dropped_attributes_count INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Trace errors table
    create_trace_errors_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_trace_errors (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        trace_id VARCHAR(128) NOT NULL REFERENCES monitoring_traces(trace_id),
        span_id VARCHAR(128) NOT NULL,
        error_type VARCHAR(255) NOT NULL,
        message TEXT NOT NULL,
        stack_trace TEXT,
        timestamp TIMESTAMPTZ NOT NULL,
        severity VARCHAR(50) DEFAULT 'error',
        category VARCHAR(100),
        attributes JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Enhanced log entries table
    create_log_entries_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        timestamp TIMESTAMPTZ NOT NULL,
        level VARCHAR(10) NOT NULL,
        message TEXT NOT NULL,
        logger_name VARCHAR(255),
        thread_name VARCHAR(255),
        service_name VARCHAR(255) NOT NULL,
        host_name VARCHAR(255),
        process_id INTEGER,
        thread_id VARCHAR(50),
        correlation_id VARCHAR(128),
        trace_id VARCHAR(128),
        span_id VARCHAR(128),
        user_id VARCHAR(255),
        session_id VARCHAR(255),
        request_id VARCHAR(255),
        file_name VARCHAR(255),
        line_number INTEGER,
        function_name VARCHAR(255),
        class_name VARCHAR(255),
        module VARCHAR(255),
        exception_class VARCHAR(255),
        exception_message TEXT,
        stack_trace TEXT,
        fields JSONB DEFAULT '{}',
        tags JSONB DEFAULT '[]',
        labels JSONB DEFAULT '{}',
        processed BOOLEAN DEFAULT FALSE,
        indexed BOOLEAN DEFAULT FALSE,
        archived BOOLEAN DEFAULT FALSE,
        quality_score INTEGER DEFAULT 100,
        is_sensitive BOOLEAN DEFAULT FALSE,
        retention_days INTEGER DEFAULT 30,
        created_at TIMESTAMPTZ DEFAULT NOW()
    ) PARTITION BY RANGE (timestamp);
    """

    # Log patterns table
    create_log_patterns_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_log_patterns (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) NOT NULL,
        pattern_type VARCHAR(50) NOT NULL,
        pattern_regex TEXT NOT NULL,
        description TEXT,
        severity VARCHAR(20) DEFAULT 'info',
        category VARCHAR(100),
        tags JSONB DEFAULT '[]',
        is_active BOOLEAN DEFAULT TRUE,
        match_count INTEGER DEFAULT 0,
        first_seen TIMESTAMPTZ,
        last_seen TIMESTAMPTZ,
        frequency_per_hour DECIMAL(10,2) DEFAULT 0.0,
        sample_rate DECIMAL(3,2) DEFAULT 1.0,
        alert_on_match BOOLEAN DEFAULT FALSE,
        auto_tag JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Log pattern matches association table
    create_log_pattern_matches_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_log_pattern_matches (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        log_id UUID NOT NULL REFERENCES monitoring_logs(id),
        pattern_id UUID NOT NULL REFERENCES monitoring_log_patterns(id),
        match_timestamp TIMESTAMPTZ DEFAULT NOW(),
        confidence DECIMAL(3,2) DEFAULT 1.0,
        match_details JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Log aggregations table
    create_log_aggregations_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_log_aggregations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        time_bucket TIMESTAMPTZ NOT NULL,
        bucket_size_minutes INTEGER NOT NULL,
        service_name VARCHAR(255),
        level VARCHAR(10),
        logger_name VARCHAR(255),
        pattern_id UUID REFERENCES monitoring_log_patterns(id),
        count INTEGER DEFAULT 0,
        unique_messages INTEGER DEFAULT 0,
        unique_users INTEGER DEFAULT 0,
        error_rate DECIMAL(5,4) DEFAULT 0.0,
        avg_response_time DECIMAL(10,2),
        max_response_time DECIMAL(10,2),
        min_response_time DECIMAL(10,2),
        top_messages JSONB DEFAULT '[]',
        top_exceptions JSONB DEFAULT '[]',
        top_users JSONB DEFAULT '[]',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Alert rules table
    create_alert_rules_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_alert_rules (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) UNIQUE NOT NULL,
        description TEXT,
        rule_type VARCHAR(50) NOT NULL,
        severity VARCHAR(20) NOT NULL DEFAULT 'medium',
        category VARCHAR(100),
        conditions JSONB NOT NULL,
        evaluation_window_minutes INTEGER DEFAULT 5,
        evaluation_interval_seconds INTEGER DEFAULT 60,
        consecutive_evaluations INTEGER DEFAULT 1,
        metric_name VARCHAR(255),
        log_pattern VARCHAR(500),
        trace_conditions JSONB DEFAULT '{}',
        channels JSONB DEFAULT '[]',
        notification_cooldown_minutes INTEGER DEFAULT 5,
        max_notifications_per_hour INTEGER DEFAULT 10,
        is_active BOOLEAN DEFAULT TRUE,
        current_state VARCHAR(50) DEFAULT 'normal',
        last_evaluation TIMESTAMPTZ,
        last_triggered TIMESTAMPTZ,
        trigger_count INTEGER DEFAULT 0,
        tags JSONB DEFAULT '[]',
        metadata JSONB DEFAULT '{}',
        created_by VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Alerts table
    create_alerts_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_alerts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        alert_id VARCHAR(128) UNIQUE NOT NULL,
        rule_id UUID NOT NULL REFERENCES monitoring_alert_rules(id),
        title VARCHAR(500) NOT NULL,
        description TEXT NOT NULL,
        severity VARCHAR(20) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'open',
        alert_type VARCHAR(50) NOT NULL,
        triggered_at TIMESTAMPTZ NOT NULL,
        acknowledged_at TIMESTAMPTZ,
        resolved_at TIMESTAMPTZ,
        closed_at TIMESTAMPTZ,
        duration_minutes DECIMAL(10,2),
        source_data JSONB DEFAULT '{}',
        context JSONB DEFAULT '{}',
        metrics JSONB DEFAULT '{}',
        labels JSONB DEFAULT '{}',
        assigned_to VARCHAR(255),
        acknowledged_by VARCHAR(255),
        resolved_by VARCHAR(255),
        notifications_sent JSONB DEFAULT '[]',
        notification_errors JSONB DEFAULT '[]',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Alert history table
    create_alert_history_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_alert_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        alert_id UUID NOT NULL REFERENCES monitoring_alerts(id),
        rule_id UUID NOT NULL REFERENCES monitoring_alert_rules(id),
        event_type VARCHAR(50) NOT NULL,
        old_status VARCHAR(50),
        new_status VARCHAR(50),
        old_severity VARCHAR(50),
        new_severity VARCHAR(50),
        message TEXT,
        details JSONB DEFAULT '{}',
        actor VARCHAR(255),
        source VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Alert channels table
    create_alert_channels_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_alert_channels (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) UNIQUE NOT NULL,
        channel_type VARCHAR(50) NOT NULL,
        description TEXT,
        configuration JSONB NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        test_mode BOOLEAN DEFAULT FALSE,
        max_notifications_per_minute INTEGER DEFAULT 10,
        max_notifications_per_hour INTEGER DEFAULT 100,
        last_success TIMESTAMPTZ,
        last_failure TIMESTAMPTZ,
        failure_count INTEGER DEFAULT 0,
        is_healthy BOOLEAN DEFAULT TRUE,
        tags JSONB DEFAULT '[]',
        created_by VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Alert subscriptions table
    create_alert_subscriptions_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_alert_subscriptions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        rule_id UUID NOT NULL REFERENCES monitoring_alert_rules(id),
        channel_id UUID NOT NULL REFERENCES monitoring_alert_channels(id),
        is_active BOOLEAN DEFAULT TRUE,
        min_severity VARCHAR(50),
        filters JSONB DEFAULT '{}',
        created_by VARCHAR(255),
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Health checks table
    create_health_checks_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_health_checks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(255) UNIQUE NOT NULL,
        description TEXT,
        check_type VARCHAR(50) NOT NULL,
        component_name VARCHAR(255) NOT NULL,
        endpoint_url VARCHAR(500),
        timeout_seconds INTEGER DEFAULT 10,
        check_interval_seconds INTEGER DEFAULT 30,
        retry_count INTEGER DEFAULT 3,
        retry_delay_seconds INTEGER DEFAULT 5,
        expected_status_code INTEGER DEFAULT 200,
        expected_response_time_ms INTEGER DEFAULT 1000,
        expected_content TEXT,
        validation_script TEXT,
        response_time_warning_ms INTEGER DEFAULT 500,
        response_time_critical_ms INTEGER DEFAULT 2000,
        success_rate_warning_percent DECIMAL(5,2) DEFAULT 95.0,
        success_rate_critical_percent DECIMAL(5,2) DEFAULT 90.0,
        is_active BOOLEAN DEFAULT TRUE,
        is_critical BOOLEAN DEFAULT FALSE,
        dependencies JSONB DEFAULT '[]',
        tags JSONB DEFAULT '[]',
        metadata JSONB DEFAULT '{}',
        created_by VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Health check results table
    create_health_check_results_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_health_check_results (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        check_id UUID NOT NULL REFERENCES monitoring_health_checks(id),
        check_timestamp TIMESTAMPTZ NOT NULL,
        status VARCHAR(50) NOT NULL,
        response_time_ms DECIMAL(10,2),
        status_code INTEGER,
        success BOOLEAN NOT NULL,
        error_message TEXT,
        error_details JSONB DEFAULT '{}',
        response_body TEXT,
        response_headers JSONB DEFAULT '{}',
        dns_lookup_time_ms DECIMAL(10,2),
        connection_time_ms DECIMAL(10,2),
        ssl_handshake_time_ms DECIMAL(10,2),
        first_byte_time_ms DECIMAL(10,2),
        cpu_usage_percent DECIMAL(5,2),
        memory_usage_percent DECIMAL(5,2),
        disk_usage_percent DECIMAL(5,2),
        check_version VARCHAR(50),
        check_metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Health check history table
    create_health_check_history_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_health_check_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        check_id UUID NOT NULL REFERENCES monitoring_health_checks(id),
        time_bucket TIMESTAMPTZ NOT NULL,
        bucket_size_minutes INTEGER NOT NULL,
        total_checks INTEGER DEFAULT 0,
        successful_checks INTEGER DEFAULT 0,
        failed_checks INTEGER DEFAULT 0,
        success_rate_percent DECIMAL(5,2) DEFAULT 0.0,
        availability_percent DECIMAL(5,2) DEFAULT 0.0,
        avg_response_time_ms DECIMAL(10,2),
        min_response_time_ms DECIMAL(10,2),
        max_response_time_ms DECIMAL(10,2),
        p95_response_time_ms DECIMAL(10,2),
        p99_response_time_ms DECIMAL(10,2),
        healthy_count INTEGER DEFAULT 0,
        degraded_count INTEGER DEFAULT 0,
        unhealthy_count INTEGER DEFAULT 0,
        unknown_count INTEGER DEFAULT 0,
        top_errors JSONB DEFAULT '[]',
        error_patterns JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Component health table
    create_component_health_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_component_health (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        component_name VARCHAR(255) NOT NULL,
        component_type VARCHAR(100) NOT NULL,
        health_check_id UUID NOT NULL REFERENCES monitoring_health_checks(id),
        status VARCHAR(50) NOT NULL,
        status_message TEXT,
        last_check_timestamp TIMESTAMPTZ NOT NULL,
        status_duration_minutes DECIMAL(10,2),
        uptime_percentage DECIMAL(5,2) DEFAULT 100.0,
        mttr_minutes DECIMAL(10,2) DEFAULT 0.0,
        incident_count_24h INTEGER DEFAULT 0,
        incident_count_7d INTEGER DEFAULT 0,
        dependencies JSONB DEFAULT '[]',
        dependents JSONB DEFAULT '[]',
        sli_current DECIMAL(5,4),
        slo_target DECIMAL(5,4),
        slo_compliance_percent DECIMAL(5,2),
        version VARCHAR(100),
        environment VARCHAR(100),
        owner VARCHAR(255),
        tags JSONB DEFAULT '[]',
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(component_name, component_type)
    );
    """

    # Monitoring sessions table
    create_monitoring_sessions_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_sessions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id VARCHAR(128) UNIQUE NOT NULL,
        parent_session_id VARCHAR(128),
        session_type VARCHAR(50) NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'active',
        start_time TIMESTAMPTZ NOT NULL,
        end_time TIMESTAMPTZ,
        duration_seconds DECIMAL(15,6),
        timeout_seconds INTEGER,
        user_id VARCHAR(255),
        organization_id VARCHAR(255),
        request_id VARCHAR(255),
        correlation_id VARCHAR(128),
        operation_name VARCHAR(255) NOT NULL,
        operation_type VARCHAR(100),
        component VARCHAR(255),
        service_name VARCHAR(255),
        client_info JSONB DEFAULT '{}',
        request_details JSONB DEFAULT '{}',
        environment JSONB DEFAULT '{}',
        total_requests INTEGER DEFAULT 0,
        successful_requests INTEGER DEFAULT 0,
        failed_requests INTEGER DEFAULT 0,
        total_data_processed_bytes INTEGER DEFAULT 0,
        avg_response_time_ms DECIMAL(10,2),
        min_response_time_ms DECIMAL(10,2),
        max_response_time_ms DECIMAL(10,2),
        p95_response_time_ms DECIMAL(10,2),
        p99_response_time_ms DECIMAL(10,2),
        peak_memory_usage_mb DECIMAL(10,2),
        peak_cpu_usage_percent DECIMAL(5,2),
        total_database_queries INTEGER DEFAULT 0,
        total_cache_hits INTEGER DEFAULT 0,
        total_cache_misses INTEGER DEFAULT 0,
        error_count INTEGER DEFAULT 0,
        error_rate_percent DECIMAL(5,4) DEFAULT 0.0,
        critical_errors JSONB DEFAULT '[]',
        tags JSONB DEFAULT '[]',
        labels JSONB DEFAULT '{}',
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Session metrics table
    create_session_metrics_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_session_metrics (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id VARCHAR(128) NOT NULL REFERENCES monitoring_sessions(session_id),
        timestamp TIMESTAMPTZ NOT NULL,
        metric_name VARCHAR(255) NOT NULL,
        metric_value DECIMAL(15,6) NOT NULL,
        metric_unit VARCHAR(50),
        metric_type VARCHAR(50),
        component VARCHAR(255),
        labels JSONB DEFAULT '{}',
        tags JSONB DEFAULT '[]',
        source VARCHAR(255),
        quality VARCHAR(20) DEFAULT 'good',
        annotations JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Session traces table
    create_session_traces_sql = """
    CREATE TABLE IF NOT EXISTS monitoring_session_traces (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id VARCHAR(128) NOT NULL REFERENCES monitoring_sessions(session_id),
        trace_id VARCHAR(128) NOT NULL,
        span_id VARCHAR(128) NOT NULL,
        parent_span_id VARCHAR(128),
        operation_name VARCHAR(255) NOT NULL,
        component VARCHAR(255),
        service_name VARCHAR(255),
        start_time TIMESTAMPTZ NOT NULL,
        end_time TIMESTAMPTZ,
        duration_ms DECIMAL(15,6),
        status VARCHAR(50),
        trace_type VARCHAR(100),
        critical_path BOOLEAN DEFAULT FALSE,
        error_occurred BOOLEAN DEFAULT FALSE,
        attributes JSONB DEFAULT '{}',
        tags JSONB DEFAULT '[]',
        links JSONB DEFAULT '[]',
        self_time_ms DECIMAL(15,6),
        child_count INTEGER DEFAULT 0,
        depth INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """

    # Execute all table creation statements
    with engine.connect() as conn:
        tables_to_create = [
            create_metric_definitions_sql,
            create_metrics_sql,
            create_metrics_partitions_sql,
            create_metric_aggregations_sql,
            create_time_series_sql,
            create_traces_sql,
            create_spans_sql,
            create_span_events_sql,
            create_span_links_sql,
            create_trace_errors_sql,
            create_log_entries_sql,
            create_log_patterns_sql,
            create_log_pattern_matches_sql,
            create_log_aggregations_sql,
            create_alert_rules_sql,
            create_alerts_sql,
            create_alert_history_sql,
            create_alert_channels_sql,
            create_alert_subscriptions_sql,
            create_health_checks_sql,
            create_health_check_results_sql,
            create_health_check_history_sql,
            create_component_health_sql,
            create_monitoring_sessions_sql,
            create_session_metrics_sql,
            create_session_traces_sql,
        ]

        for sql in tables_to_create:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ Created monitoring table successfully")
            except Exception as e:
                print(f"❌ Error creating table: {e}")
                conn.rollback()

    # Create comprehensive indexes
    create_indexes_sql = [
        # Metrics indexes
        "CREATE INDEX IF NOT EXISTS idx_metrics_definition_timestamp ON monitoring_metrics(definition_id, timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_metrics_source_timestamp ON monitoring_metrics(source, timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_metrics_labels ON monitoring_metrics USING gin(labels);",

        # Metric aggregations indexes
        "CREATE INDEX IF NOT EXISTS idx_aggregations_definition_bucket ON monitoring_metric_aggregations(definition_id, time_bucket, aggregation_type);",
        "CREATE INDEX IF NOT EXISTS idx_aggregations_bucket_type ON monitoring_metric_aggregations(time_bucket, aggregation_type);",

        # Time series indexes
        "CREATE INDEX IF NOT EXISTS idx_timeseries_metric_timestamp ON monitoring_time_series(metric_name, timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_timeseries_source_timestamp ON monitoring_time_series(source, timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_timeseries_labels ON monitoring_time_series USING gin(labels);",

        # Traces indexes
        "CREATE INDEX IF NOT EXISTS idx_traces_service_time ON monitoring_traces(service_name, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_traces_operation_time ON monitoring_traces(operation_name, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_traces_status_time ON monitoring_traces(status, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_traces_duration ON monitoring_traces(duration_ms DESC);",

        # Spans indexes
        "CREATE INDEX IF NOT EXISTS idx_spans_trace_operation ON monitoring_spans(trace_id, operation_name);",
        "CREATE INDEX IF NOT EXISTS idx_spans_service_time ON monitoring_spans(service_name, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_spans_parent ON monitoring_spans(parent_span_id);",
        "CREATE INDEX IF NOT EXISTS idx_spans_attributes ON monitoring_spans USING gin(attributes);",

        # Span events indexes
        "CREATE INDEX IF NOT EXISTS idx_span_events_span_time ON monitoring_span_events(span_id, timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_span_events_name_time ON monitoring_span_events(name, timestamp DESC);",

        # Span links indexes
        "CREATE INDEX IF NOT EXISTS idx_span_links_span_linked ON monitoring_span_links(span_id, linked_span_id);",
        "CREATE INDEX IF NOT EXISTS idx_span_links_trace ON monitoring_span_links(linked_trace_id);",

        # Trace errors indexes
        "CREATE INDEX IF NOT EXISTS idx_trace_errors_type_time ON monitoring_trace_errors(error_type, timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_trace_errors_severity_time ON monitoring_trace_errors(severity, timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_trace_errors_span ON monitoring_trace_errors(span_id);",

        # Log entries indexes
        "CREATE INDEX IF NOT EXISTS idx_logs_timestamp_level ON monitoring_logs(timestamp DESC, level);",
        "CREATE INDEX IF NOT EXISTS idx_logs_service_timestamp ON monitoring_logs(service_name, timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_logs_correlation ON monitoring_logs(correlation_id);",
        "CREATE INDEX IF NOT EXISTS idx_logs_trace_span ON monitoring_logs(trace_id, span_id);",
        "CREATE INDEX IF NOT EXISTS idx_logs_user_session ON monitoring_logs(user_id, session_id);",
        "CREATE INDEX IF NOT EXISTS idx_logs_exception ON monitoring_logs(exception_class);",
        "CREATE INDEX IF NOT EXISTS idx_logs_fields ON monitoring_logs USING gin(fields);",
        "CREATE INDEX IF NOT EXISTS idx_logs_tags ON monitoring_logs USING gin(tags);",

        # Log patterns indexes
        "CREATE INDEX IF NOT EXISTS idx_log_patterns_type_active ON monitoring_log_patterns(pattern_type, is_active);",
        "CREATE INDEX IF NOT EXISTS idx_log_patterns_frequency ON monitoring_log_patterns(frequency_per_hour DESC);",

        # Log pattern matches indexes
        "CREATE INDEX IF NOT EXISTS idx_log_pattern_matches_log ON monitoring_log_pattern_matches(log_id);",
        "CREATE INDEX IF NOT EXISTS idx_log_pattern_matches_pattern ON monitoring_log_pattern_matches(pattern_id);",
        "CREATE INDEX IF NOT EXISTS idx_log_pattern_matches_timestamp ON monitoring_log_pattern_matches(match_timestamp DESC);",

        # Log aggregations indexes
        "CREATE INDEX IF NOT EXISTS idx_log_aggregations_time_service ON monitoring_log_aggregations(time_bucket DESC, service_name);",
        "CREATE INDEX IF NOT EXISTS idx_log_aggregations_time_level ON monitoring_log_aggregations(time_bucket DESC, level);",
        "CREATE INDEX IF NOT EXISTS idx_log_aggregations_pattern_time ON monitoring_log_aggregations(pattern_id, time_bucket DESC);",

        # Alert rules indexes
        "CREATE INDEX IF NOT EXISTS idx_alert_rules_active_type ON monitoring_alert_rules(is_active, rule_type);",
        "CREATE INDEX IF NOT EXISTS idx_alert_rules_severity ON monitoring_alert_rules(severity);",
        "CREATE INDEX IF NOT EXISTS idx_alert_rules_metric ON monitoring_alert_rules(metric_name);",

        # Alerts indexes
        "CREATE INDEX IF NOT EXISTS idx_alerts_status_severity ON monitoring_alerts(status, severity);",
        "CREATE INDEX IF NOT EXISTS idx_alerts_triggered_time ON monitoring_alerts(triggered_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_alerts_type_time ON monitoring_alerts(alert_type, triggered_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_alerts_assigned ON monitoring_alerts(assigned_to);",

        # Alert history indexes
        "CREATE INDEX IF NOT EXISTS idx_alert_history_alert_time ON monitoring_alert_history(alert_id, created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_alert_history_event_type ON monitoring_alert_history(event_type);",
        "CREATE INDEX IF NOT EXISTS idx_alert_history_rule_time ON monitoring_alert_history(rule_id, created_at DESC);",

        # Alert channels indexes
        "CREATE INDEX IF NOT EXISTS idx_alert_channels_type_active ON monitoring_alert_channels(channel_type, is_active);",
        "CREATE INDEX IF NOT EXISTS idx_alert_channels_healthy ON monitoring_alert_channels(is_healthy);",

        # Alert subscriptions indexes
        "CREATE INDEX IF NOT EXISTS idx_alert_subscriptions_rule_channel ON monitoring_alert_subscriptions(rule_id, channel_id);",
        "CREATE INDEX IF NOT EXISTS idx_alert_subscriptions_active ON monitoring_alert_subscriptions(is_active);",

        # Health check indexes
        "CREATE INDEX IF NOT EXISTS idx_health_checks_type_active ON monitoring_health_checks(check_type, is_active);",
        "CREATE INDEX IF NOT EXISTS idx_health_checks_component ON monitoring_health_checks(component_name);",
        "CREATE INDEX IF NOT EXISTS idx_health_checks_critical ON monitoring_health_checks(is_critical);",

        # Health check results indexes
        "CREATE INDEX IF NOT EXISTS idx_health_results_check_time ON monitoring_health_check_results(check_id, check_timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_health_results_status_time ON monitoring_health_check_results(status, check_timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_health_results_success_time ON monitoring_health_check_results(success, check_timestamp DESC);",

        # Health check history indexes
        "CREATE INDEX IF NOT EXISTS idx_health_history_check_time ON monitoring_health_check_history(check_id, time_bucket DESC);",
        "CREATE INDEX IF NOT EXISTS idx_health_history_success_rate ON monitoring_health_check_history(success_rate_percent DESC);",
        "CREATE INDEX IF NOT EXISTS idx_health_history_availability ON monitoring_health_check_history(availability_percent DESC);",

        # Component health indexes
        "CREATE INDEX IF NOT EXISTS idx_component_health_name_type ON monitoring_component_health(component_name, component_type);",
        "CREATE INDEX IF NOT EXISTS idx_component_health_status_time ON monitoring_component_health(status, last_check_timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_component_health_slo ON monitoring_component_health(slo_compliance_percent DESC);",

        # Monitoring sessions indexes
        "CREATE INDEX IF NOT EXISTS idx_sessions_user_time ON monitoring_sessions(user_id, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_sessions_operation_time ON monitoring_sessions(operation_name, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_sessions_service_time ON monitoring_sessions(service_name, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_sessions_status_time ON monitoring_sessions(status, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_sessions_correlation ON monitoring_sessions(correlation_id);",
        "CREATE INDEX IF NOT EXISTS idx_sessions_parent ON monitoring_sessions(parent_session_id);",

        # Session metrics indexes
        "CREATE INDEX IF NOT EXISTS idx_session_metrics_session_time ON monitoring_session_metrics(session_id, timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_session_metrics_name_time ON monitoring_session_metrics(metric_name, timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_session_metrics_labels ON monitoring_session_metrics USING gin(labels);",

        # Session traces indexes
        "CREATE INDEX IF NOT EXISTS idx_session_traces_session_time ON monitoring_session_traces(session_id, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_session_traces_trace_span ON monitoring_session_traces(trace_id, span_id);",
        "CREATE INDEX IF NOT EXISTS idx_session_traces_operation_time ON monitoring_session_traces(operation_name, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_session_traces_status_time ON monitoring_session_traces(status, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_session_traces_critical ON monitoring_session_traces(critical_path);",
    ]

    with engine.connect() as conn:
        for index_sql in create_indexes_sql:
            try:
                conn.execute(text(index_sql))
                conn.commit()
            except Exception as e:
                print(f"❌ Error creating index: {e}")
                conn.rollback()

    print("✅ Comprehensive monitoring tables and indexes created successfully")


def downgrade():
    """Drop comprehensive monitoring tables"""

    drop_tables_sql = [
        "DROP TABLE IF EXISTS monitoring_session_traces CASCADE;",
        "DROP TABLE IF EXISTS monitoring_session_metrics CASCADE;",
        "DROP TABLE IF EXISTS monitoring_sessions CASCADE;",
        "DROP TABLE IF EXISTS monitoring_component_health CASCADE;",
        "DROP TABLE IF EXISTS monitoring_health_check_history CASCADE;",
        "DROP TABLE IF EXISTS monitoring_health_check_results CASCADE;",
        "DROP TABLE IF EXISTS monitoring_health_checks CASCADE;",
        "DROP TABLE IF EXISTS monitoring_alert_subscriptions CASCADE;",
        "DROP TABLE IF EXISTS monitoring_alert_channels CASCADE;",
        "DROP TABLE IF EXISTS monitoring_alert_history CASCADE;",
        "DROP TABLE IF EXISTS monitoring_alerts CASCADE;",
        "DROP TABLE IF EXISTS monitoring_alert_rules CASCADE;",
        "DROP TABLE IF EXISTS monitoring_log_aggregations CASCADE;",
        "DROP TABLE IF EXISTS monitoring_log_pattern_matches CASCADE;",
        "DROP TABLE IF EXISTS monitoring_log_patterns CASCADE;",
        "DROP TABLE IF EXISTS monitoring_logs CASCADE;",
        "DROP TABLE IF EXISTS monitoring_trace_errors CASCADE;",
        "DROP TABLE IF EXISTS monitoring_span_links CASCADE;",
        "DROP TABLE IF EXISTS monitoring_span_events CASCADE;",
        "DROP TABLE IF EXISTS monitoring_spans CASCADE;",
        "DROP TABLE IF EXISTS monitoring_traces CASCADE;",
        "DROP TABLE IF EXISTS monitoring_time_series CASCADE;",
        "DROP TABLE IF EXISTS monitoring_metric_aggregations CASCADE;",
        "DROP TABLE IF EXISTS monitoring_metrics CASCADE;",
        "DROP TABLE IF EXISTS monitoring_metric_definitions CASCADE;",
    ]

    with engine.connect() as conn:
        for drop_sql in drop_tables_sql:
            try:
                conn.execute(text(drop_sql))
                conn.commit()
                print(f"✅ Dropped monitoring table successfully")
            except Exception as e:
                print(f"❌ Error dropping table: {e}")
                conn.rollback()

    print("✅ Comprehensive monitoring tables dropped successfully")


if __name__ == "__main__":
    upgrade()