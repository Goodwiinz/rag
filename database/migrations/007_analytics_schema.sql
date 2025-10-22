-- Analytics Schema Migration
-- Migration for Knowledge Graph Analytics Dashboard

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_analytics_dashboards_owner_id ON analytics_dashboards(owner_id);
CREATE INDEX IF NOT EXISTS idx_analytics_dashboards_organization_id ON analytics_dashboards(organization_id);
CREATE INDEX IF NOT EXISTS idx_analytics_dashboards_is_public ON analytics_dashboards(is_public);
CREATE INDEX IF NOT EXISTS idx_analytics_dashboards_category ON analytics_dashboards(category);
CREATE INDEX IF NOT EXISTS idx_analytics_dashboards_created_at ON analytics_dashboards(created_at);

CREATE INDEX IF NOT EXISTS idx_analytics_dashboard_widgets_dashboard_id ON analytics_dashboard_widgets(dashboard_id);
CREATE INDEX IF NOT EXISTS idx_analytics_dashboard_widgets_widget_type ON analytics_dashboard_widgets(widget_type);
CREATE INDEX IF NOT EXISTS idx_analytics_dashboard_widgets_is_active ON analytics_dashboard_widgets(is_active);
CREATE INDEX IF NOT EXISTS idx_analytics_dashboard_widgets_cache_key ON analytics_dashboard_widgets(cache_key);

CREATE INDEX IF NOT EXISTS idx_analytics_dashboard_permissions_dashboard_id ON analytics_dashboard_permissions(dashboard_id);
CREATE INDEX IF NOT EXISTS idx_analytics_dashboard_permissions_user_id ON analytics_dashboard_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_analytics_dashboard_permissions_role_id ON analytics_dashboard_permissions(role_id);

CREATE INDEX IF NOT EXISTS idx_analytics_events_event_type ON analytics_events(event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_events_event_name ON analytics_events(event_name);
CREATE INDEX IF NOT EXISTS idx_analytics_events_user_id ON analytics_events(user_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_session_id ON analytics_events(session_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_processed ON analytics_events(processed);
CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at ON analytics_events(created_at);

CREATE INDEX IF NOT EXISTS idx_analytics_metrics_name ON analytics_metrics(name);
CREATE INDEX IF NOT EXISTS idx_analytics_metrics_metric_type ON analytics_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_analytics_metrics_is_active ON analytics_metrics(is_active);
CREATE INDEX IF NOT EXISTS idx_analytics_metrics_is_public ON analytics_metrics(is_public);

CREATE INDEX IF NOT EXISTS idx_analytics_kpis_metric_id ON analytics_kpis(metric_id);
CREATE INDEX IF NOT EXISTS idx_analytics_kpis_is_active ON analytics_kpis(is_active);
CREATE INDEX IF NOT EXISTS idx_analytics_kpis_is_critical ON analytics_kpis(is_critical);

CREATE INDEX IF NOT EXISTS idx_analytics_metric_aggregations_metric_id ON analytics_metric_aggregations(metric_id);
CREATE INDEX IF NOT EXISTS idx_analytics_metric_aggregations_aggregation_type ON analytics_metric_aggregations(aggregation_type);
CREATE INDEX IF NOT EXISTS idx_analytics_metric_aggregations_time_window ON analytics_metric_aggregations(time_window);
CREATE INDEX IF NOT EXISTS idx_analytics_metric_aggregations_timestamp ON analytics_metric_aggregations(timestamp);
CREATE INDEX IF NOT EXISTS idx_analytics_metric_aggregations_dimensions_hash ON analytics_metric_aggregations(dimensions_hash);

CREATE INDEX IF NOT EXISTS idx_analytics_reports_owner_id ON analytics_reports(owner_id);
CREATE INDEX IF NOT EXISTS idx_analytics_reports_organization_id ON analytics_reports(organization_id);
CREATE INDEX IF NOT EXISTS idx_analytics_reports_is_active ON analytics_reports(is_active);
CREATE INDEX IF NOT EXISTS idx_analytics_reports_last_run_at ON analytics_reports(last_run_at);

CREATE INDEX IF NOT EXISTS idx_graph_analytics_results_analysis_type ON graph_analytics_results(analysis_type);
CREATE INDEX IF NOT EXISTS idx_graph_analytics_results_status ON graph_analytics_results(status);
CREATE INDEX IF NOT EXISTS idx_graph_analytics_results_created_at ON graph_analytics_results(created_at);

CREATE INDEX IF NOT EXISTS idx_graph_node_metrics_analytics_result_id ON graph_node_metrics(analytics_result_id);
CREATE INDEX IF NOT EXISTS idx_graph_node_metrics_node_id ON graph_node_metrics(node_id);
CREATE INDEX IF NOT EXISTS idx_graph_node_metrics_community_id ON graph_node_metrics(community_id);

CREATE INDEX IF NOT EXISTS idx_graph_edge_metrics_analytics_result_id ON graph_edge_metrics(analytics_result_id);
CREATE INDEX IF NOT EXISTS idx_graph_edge_metrics_source_node_id ON graph_edge_metrics(source_node_id);
CREATE INDEX IF NOT EXISTS idx_graph_edge_metrics_target_node_id ON graph_edge_metrics(target_node_id);

CREATE INDEX IF NOT EXISTS idx_graph_community_metrics_analytics_result_id ON graph_community_metrics(analytics_result_id);
CREATE INDEX IF NOT EXISTS idx_graph_community_metrics_community_id ON graph_community_metrics(community_id);

CREATE INDEX IF NOT EXISTS idx_graph_path_analytics_source_node_id ON graph_path_analytics(source_node_id);
CREATE INDEX IF NOT EXISTS idx_graph_path_analytics_target_node_id ON graph_path_analytics(target_node_id);
CREATE INDEX IF NOT EXISTS idx_graph_path_analytics_status ON graph_path_analytics(status);

CREATE INDEX IF NOT EXISTS idx_realtime_subscriptions_user_id ON realtime_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_realtime_subscriptions_websocket_id ON realtime_subscriptions(websocket_id);
CREATE INDEX IF NOT EXISTS idx_realtime_subscriptions_subscription_type ON realtime_subscriptions(subscription_type);
CREATE INDEX IF NOT EXISTS idx_realtime_subscriptions_channel ON realtime_subscriptions(channel);
CREATE INDEX IF NOT EXISTS idx_realtime_subscriptions_is_active ON realtime_subscriptions(is_active);

CREATE INDEX IF NOT EXISTS idx_live_metrics_metric_id ON live_metrics(metric_id);
CREATE INDEX IF NOT EXISTS idx_live_metrics_channel ON live_metrics(channel);
CREATE INDEX IF NOT EXISTS idx_live_metrics_timestamp ON live_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_live_metrics_time_window ON live_metrics(time_window);

CREATE INDEX IF NOT EXISTS idx_event_streams_event_type ON event_streams(event_type);
CREATE INDEX IF NOT EXISTS idx_event_streams_user_id ON event_streams(user_id);
CREATE INDEX IF NOT EXISTS idx_event_streams_session_id ON event_streams(session_id);
CREATE INDEX IF NOT EXISTS idx_event_streams_processed_at ON event_streams(processed_at);

CREATE INDEX IF NOT EXISTS idx_websocket_connections_user_id ON websocket_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_websocket_connections_session_id ON websocket_connections(session_id);
CREATE INDEX IF NOT EXISTS idx_websocket_connections_is_connected ON websocket_connections(is_connected);
CREATE INDEX IF NOT EXISTS idx_websocket_connections_connected_at ON websocket_connections(connected_at);

-- Create composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_analytics_events_user_type ON analytics_events(user_id, event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_events_session_time ON analytics_events(session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_analytics_metric_aggregations_metric_time ON analytics_metric_aggregations(metric_id, time_window, timestamp);
CREATE INDEX IF NOT EXISTS idx_analytics_metric_aggregations_time_window_agg ON analytics_metric_aggregations(time_window, aggregation_type, timestamp);

-- Add triggers for automatic timestamp updates if needed
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for tables that need updated_at auto-update
CREATE TRIGGER update_analytics_dashboards_updated_at
    BEFORE UPDATE ON analytics_dashboards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analytics_dashboard_widgets_updated_at
    BEFORE UPDATE ON analytics_dashboard_widgets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analytics_metrics_updated_at
    BEFORE UPDATE ON analytics_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analytics_kpis_updated_at
    BEFORE UPDATE ON analytics_kpis
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add partitioning for large tables if needed (optional)
-- This is for high-volume tables that might benefit from partitioning

-- Example: Partition analytics_events by date
/*
CREATE TABLE analytics_events_y2024m01 PARTITION OF analytics_events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE analytics_events_y2024m02 PARTITION OF analytics_events
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- Add similar partitions for other months
*/

-- Add check constraints for data integrity
ALTER TABLE analytics_dashboards
    ADD CONSTRAINT chk_analytics_dashboards_refresh_interval
    CHECK (refresh_interval > 0 AND refresh_interval <= 3600);

ALTER TABLE analytics_dashboard_widgets
    ADD CONSTRAINT chk_analytics_dashboard_widgets_dimensions
    CHECK (width > 0 AND height > 0 AND width <= 24 AND height <= 24);

ALTER TABLE analytics_kpis
    ADD CONSTRAINT chk_analytics_kpis_time_window
    CHECK (time_window >= 60 AND time_window <= 86400);

ALTER TABLE realtime_subscriptions
    ADD CONSTRAINT chk_realtime_subscriptions_batch_size
    CHECK (batch_size > 0 AND batch_size <= 1000);

ALTER TABLE realtime_subscriptions
    ADD CONSTRAINT chk_realtime_subscriptions_update_interval
    CHECK (update_interval >= 100 AND update_interval <= 300000);

ALTER TABLE websocket_connections
    ADD CONSTRAINT chk_websocket_connections_max_subscriptions
    CHECK (max_subscriptions >= 0 AND max_subscriptions <= 1000);

-- Create views for commonly accessed data
CREATE OR REPLACE VIEW analytics_dashboards_with_widget_count AS
SELECT
    d.*,
    COUNT(w.id) as widget_count,
    MAX(w.updated_at) as last_widget_update
FROM analytics_dashboards d
LEFT JOIN analytics_dashboard_widgets w ON d.id = w.dashboard_id AND w.is_active = true
WHERE d.is_deleted = false
GROUP BY d.id;

CREATE OR REPLACE VIEW analytics_metrics_with_kpis AS
SELECT
    m.*,
    COUNT(k.id) as kpi_count
FROM analytics_metrics m
LEFT JOIN analytics_kpis k ON m.id = k.metric_id AND k.is_active = true
WHERE m.is_deleted = false
GROUP BY m.id;

CREATE OR REPLACE VIEW analytics_active_subscriptions AS
SELECT
    rs.*,
    u.email as user_email,
    u.username as user_name
FROM realtime_subscriptions rs
JOIN users u ON rs.user_id = u.id
WHERE rs.is_active = true
    AND rs.expires_at > CURRENT_TIMESTAMP
    OR rs.expires_at IS NULL;

-- Create functions for common operations
CREATE OR REPLACE FUNCTION analytics_get_metric_value(
    p_metric_name TEXT,
    p_time_range TEXT DEFAULT '1h',
    p_aggregation TEXT DEFAULT 'avg'
) RETURNS NUMERIC AS $$
DECLARE
    v_value NUMERIC;
BEGIN
    SELECT ma.value INTO v_value
    FROM analytics_metrics m
    JOIN analytics_metric_aggregations ma ON m.id = ma.metric_id
    WHERE m.name = p_metric_name
        AND ma.aggregation_type = p_aggregation
        AND ma.time_window = p_time_range
        AND ma.timestamp >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
    ORDER BY ma.timestamp DESC
    LIMIT 1;

    RETURN COALESCE(v_value, 0);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION analytics_get_kpi_status(
    p_kpi_id UUID
) RETURNS TEXT AS $$
DECLARE
    v_current_value NUMERIC;
    v_target_value NUMERIC;
    v_warning_threshold NUMERIC;
    v_critical_threshold NUMERIC;
    v_status TEXT := 'normal';
BEGIN
    -- Get KPI details
    SELECT k.target_value, k.warning_threshold, k.critical_threshold
    INTO v_target_value, v_warning_threshold, v_critical_threshold
    FROM analytics_kpis k
    WHERE k.id = p_kpi_id;

    -- Get current value (simplified)
    SELECT analytics_get_metric_value(m.name)
    INTO v_current_value
    FROM analytics_kpis k
    JOIN analytics_metrics m ON k.metric_id = m.id
    WHERE k.id = p_kpi_id;

    -- Determine status
    IF v_current_value IS NOT NULL THEN
        IF v_critical_threshold IS NOT NULL AND v_current_value <= v_critical_threshold THEN
            v_status := 'critical';
        ELSIF v_warning_threshold IS NOT NULL AND v_current_value <= v_warning_threshold THEN
            v_status := 'warning';
        ELSIF v_target_value IS NOT NULL AND v_current_value >= v_target_value THEN
            v_status := 'good';
        END IF;
    ELSE
        v_status := 'unknown';
    END IF;

    RETURN v_status;
END;
$$ LANGUAGE plpgsql;

-- Create materialized views for performance (optional)
/*
CREATE MATERIALIZED VIEW analytics_daily_metrics AS
SELECT
    DATE_TRUNC('day', created_at) as metric_date,
    COUNT(*) as total_events,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT session_id) as unique_sessions
FROM analytics_events
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY metric_date DESC;

-- Create unique index for materialized view
CREATE UNIQUE INDEX idx_analytics_daily_metrics_date ON analytics_daily_metrics(metric_date);

-- Create function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_analytics_daily_metrics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY analytics_daily_metrics;
END;
$$ LANGUAGE plpgsql;
*/

-- Add row-level security policies if needed (optional)
/*
ALTER TABLE analytics_dashboards ENABLE ROW LEVEL SECURITY;

-- Policy: Users can see their own dashboards and public dashboards
CREATE POLICY analytics_dashboards_select_policy ON analytics_dashboards
    FOR SELECT USING (
        owner_id = current_setting('app.current_user_id')::UUID
        OR is_public = true
    );

-- Policy: Users can only modify their own dashboards
CREATE POLICY analytics_dashboards_modify_policy ON analytics_dashboards
    FOR ALL USING (
        owner_id = current_setting('app.current_user_id')::UUID
    );
*/

-- Create functions for data cleanup
CREATE OR REPLACE FUNCTION analytics_cleanup_old_data(
    days_to_keep INTEGER DEFAULT 90
) RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER := 0;
BEGIN
    -- Clean up old analytics events
    DELETE FROM analytics_events
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '1 day' * days_to_keep;

    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;

    -- Clean up old metric aggregations (keep longer for higher time windows)
    DELETE FROM analytics_metric_aggregations
    WHERE time_window IN ('1m', '5m', '15m')
        AND timestamp < CURRENT_TIMESTAMP - INTERVAL '7 days';

    DELETE FROM analytics_metric_aggregations
    WHERE time_window = '1h'
        AND timestamp < CURRENT_TIMESTAMP - INTERVAL '30 days';

    DELETE FROM analytics_metric_aggregations
    WHERE time_window IN ('6h', '1d')
        AND timestamp < CURRENT_TIMESTAMP - INTERVAL '90 days';

    -- Clean up old live metrics
    DELETE FROM live_metrics
    WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '24 hours';

    -- Clean up old event streams
    DELETE FROM event_streams
    WHERE processed_at < CURRENT_TIMESTAMP - INTERVAL '7 days';

    -- Clean up disconnected WebSocket connections
    DELETE FROM websocket_connections
    WHERE is_connected = false
        AND disconnected_at < CURRENT_TIMESTAMP - INTERVAL '1 day';

    -- Clean up expired subscriptions
    DELETE FROM realtime_subscriptions
    WHERE expires_at < CURRENT_TIMESTAMP
        AND auto_renew = false;

    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create scheduled job for cleanup (requires pg_cron extension)
/*
SELECT cron.schedule('analytics-cleanup', '0 2 * * *', 'SELECT analytics_cleanup_old_data(90);');
*/

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON analytics_dashboards TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON analytics_dashboard_widgets TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON analytics_dashboard_permissions TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON analytics_events TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON analytics_metrics TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON analytics_kpis TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON analytics_metric_aggregations TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON analytics_reports TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON graph_analytics_results TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON graph_node_metrics TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON graph_edge_metrics TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON graph_community_metrics TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON graph_path_analytics TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON realtime_subscriptions TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON live_metrics TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON event_streams TO your_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON websocket_connections TO your_app_user;

-- Grant usage of sequences
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO your_app_user;

-- Grant access to views
GRANT SELECT ON analytics_dashboards_with_widget_count TO your_app_user;
GRANT SELECT ON analytics_metrics_with_kpis TO your_app_user;
GRANT SELECT ON analytics_active_subscriptions TO your_app_user;

-- Grant execute permissions for functions
GRANT EXECUTE ON FUNCTION analytics_get_metric_value(TEXT, TEXT, TEXT) TO your_app_user;
GRANT EXECUTE ON FUNCTION analytics_get_kpi_status(UUID) TO your_app_user;
GRANT EXECUTE ON FUNCTION analytics_cleanup_old_data(INTEGER) TO your_app_user;

-- Add comments for documentation
COMMENT ON TABLE analytics_dashboards IS 'Analytics dashboards configuration and metadata';
COMMENT ON TABLE analytics_dashboard_widgets IS 'Individual widgets within analytics dashboards';
COMMENT ON TABLE analytics_dashboard_permissions IS 'Access permissions for analytics dashboards';
COMMENT ON TABLE analytics_events IS 'Raw analytics events for tracking user interactions';
COMMENT ON TABLE analytics_metrics IS 'Definition of analytics metrics and KPIs';
COMMENT ON TABLE analytics_kpis IS 'Key Performance Indicators based on metrics';
COMMENT ON TABLE analytics_metric_aggregations IS 'Pre-aggregated metric data for performance';
COMMENT ON TABLE analytics_reports IS 'Report generation and scheduling configuration';
COMMENT ON TABLE graph_analytics_results IS 'Results from graph analysis algorithms';
COMMENT ON TABLE graph_node_metrics IS 'Node-level metrics from graph analysis';
COMMENT ON TABLE graph_edge_metrics IS 'Edge-level metrics from graph analysis';
COMMENT ON TABLE graph_community_metrics IS 'Community-level metrics from graph analysis';
COMMENT ON TABLE graph_path_analytics IS 'Path analysis results';
COMMENT ON TABLE realtime_subscriptions IS 'Real-time analytics subscriptions';
COMMENT ON TABLE live_metrics IS 'Live metric data for real-time updates';
COMMENT ON TABLE event_streams IS 'Event streaming data for real-time processing';
COMMENT ON TABLE websocket_connections IS 'WebSocket connection tracking';

-- Migration complete
SELECT 'Analytics schema migration completed successfully' as migration_status;