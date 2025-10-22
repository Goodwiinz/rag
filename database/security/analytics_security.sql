-- Knowledge Graph Analytics Dashboard Security Configuration
-- Comprehensive security policies, roles, and access controls

-- ============================================================================
-- SECURITY ROLES AND PRIVILEGES
-- ============================================================================

-- Create analytics-specific roles
DO $$
BEGIN
    -- Create analytics admin role
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analytics_admin') THEN
        CREATE ROLE analytics_admin;
    END IF;

    -- Create analytics viewer role
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analytics_viewer') THEN
        CREATE ROLE analytics_viewer;
    END IF;

    -- Create analytics editor role
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analytics_editor') THEN
        CREATE ROLE analytics_editor;
    END IF;

    -- Create analytics reporter role
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analytics_reporter') THEN
        CREATE ROLE analytics_reporter;
    END IF;
END $$;

-- Grant role hierarchy
GRANT analytics_viewer TO analytics_editor;
GRANT analytics_editor TO analytics_admin;
GRANT analytics_reporter TO analytics_editor;

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================

-- Enable RLS on all analytics tables
ALTER TABLE entity_analytics_optimized ENABLE ROW LEVEL SECURITY;
ALTER TABLE relationship_analytics_optimized ENABLE ROW LEVEL SECURITY;
ALTER TABLE graph_metrics_analytics_optimized ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_analytics_optimized ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_interaction_analytics_optimized ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboard_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE custom_analytics_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboard_aggregations ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_alert_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_change_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_log ENABLE ROW LEVEL SECURITY;

-- Entity Analytics RLS Policies
CREATE POLICY entity_analytics_org_policy ON entity_analytics_optimized
    FOR ALL TO analytics_viewer
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY entity_analytics_admin_policy ON entity_analytics_optimized
    FOR ALL TO analytics_admin
    USING (true);

CREATE POLICY entity_analytics_editor_policy ON entity_analytics_optimized
    FOR ALL TO analytics_editor
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Relationship Analytics RLS Policies
CREATE POLICY relationship_analytics_org_policy ON relationship_analytics_optimized
    FOR ALL TO analytics_viewer
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY relationship_analytics_admin_policy ON relationship_analytics_optimized
    FOR ALL TO analytics_admin
    USING (true);

-- Graph Metrics Analytics RLS Policies
CREATE POLICY graph_metrics_analytics_org_policy ON graph_metrics_analytics_optimized
    FOR SELECT TO analytics_viewer
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY graph_metrics_analytics_editor_policy ON graph_metrics_analytics_optimized
    FOR ALL TO analytics_editor
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY graph_metrics_analytics_admin_policy ON graph_metrics_analytics_optimized
    FOR ALL TO analytics_admin
    USING (true);

-- Document Analytics RLS Policies
CREATE POLICY document_analytics_org_policy ON document_analytics_optimized
    FOR ALL TO analytics_viewer
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY document_analytics_admin_policy ON document_analytics_optimized
    FOR ALL TO analytics_admin
    USING (true);

-- User Interaction Analytics RLS Policies (more restrictive for privacy)
CREATE POLICY user_interaction_analytics_org_policy ON user_interaction_analytics_optimized
    FOR SELECT TO analytics_viewer
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY user_interaction_analytics_editor_policy ON user_interaction_analytics_optimized
    FOR ALL TO analytics_editor
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY user_interaction_analytics_admin_policy ON user_interaction_analytics_optimized
    FOR ALL TO analytics_admin
    USING (true);

-- Dashboard Configurations RLS Policies
CREATE POLICY dashboard_configurations_user_policy ON dashboard_configurations
    FOR SELECT TO analytics_viewer
    USING (
        organization_id = current_setting('app.current_organization_id', true)::UUID
        AND (user_id = current_setting('app.current_user_id', true)::UUID OR is_default = true)
    );

CREATE POLICY dashboard_configurations_editor_policy ON dashboard_configurations
    FOR ALL TO analytics_editor
    USING (
        organization_id = current_setting('app.current_organization_id', true)::UUID
        AND (user_id = current_setting('app.current_user_id', true)::UUID OR is_default = true)
    );

CREATE POLICY dashboard_configurations_admin_policy ON dashboard_configurations
    FOR ALL TO analytics_admin
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Custom Analytics Reports RLS Policies
CREATE POLICY custom_analytics_reports_org_policy ON custom_analytics_reports
    FOR SELECT TO analytics_viewer
    USING (
        organization_id = current_setting('app.current_organization_id', true)::UUID
        AND (is_public = TRUE OR created_by_user_id = current_setting('app.current_user_id', true)::UUID)
    );

CREATE POLICY custom_analytics_reports_editor_policy ON custom_analytics_reports
    FOR ALL TO analytics_editor
    USING (
        organization_id = current_setting('app.current_organization_id', true)::UUID
        AND (created_by_user_id = current_setting('app.current_user_id', true)::UUID OR is_public = TRUE)
    );

CREATE POLICY custom_analytics_reports_admin_policy ON custom_analytics_reports
    FOR ALL TO analytics_admin
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Report Executions RLS Policies
CREATE POLICY report_executions_user_policy ON report_executions
    FOR SELECT TO analytics_viewer
    USING (
        organization_id = current_setting('app.current_organization_id', true)::UUID
        AND executed_by_user_id = current_setting('app.current_user_id', true)::UUID
    );

CREATE POLICY report_executions_editor_policy ON report_executions
    FOR ALL TO analytics_editor
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY report_executions_admin_policy ON report_executions
    FOR ALL TO analytics_admin
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Analytics Cache RLS Policies
CREATE POLICY analytics_cache_org_policy ON analytics_cache
    FOR ALL TO analytics_viewer
    USING (
        organization_id = current_setting('app.current_organization_id', true)::UUID
        OR organization_id IS NULL -- System-wide cache entries
    );

CREATE POLICY analytics_cache_admin_policy ON analytics_cache
    FOR ALL TO analytics_admin
    USING (true);

-- Analytics Alerts RLS Policies
CREATE POLICY analytics_alerts_org_policy ON analytics_alerts
    FOR SELECT TO analytics_viewer
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY analytics_alerts_editor_policy ON analytics_alerts
    FOR ALL TO analytics_editor
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY analytics_alerts_admin_policy ON analytics_alerts
    FOR ALL TO analytics_admin
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Analytics Change Log RLS Policies (audit trail - restricted access)
CREATE POLICY analytics_change_log_editor_policy ON analytics_change_log
    FOR SELECT TO analytics_editor
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY analytics_change_log_admin_policy ON analytics_change_log
    FOR ALL TO analytics_admin
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Performance Log RLS Policies (restricted for security)
CREATE POLICY performance_log_admin_policy ON performance_log
    FOR ALL TO analytics_admin
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- ============================================================================
-- COLUMN-LEVEL SECURITY FOR SENSITIVE DATA
-- ============================================================================

-- Create views with restricted column access for different user roles

-- Public analytics view (hides sensitive information)
CREATE OR REPLACE VIEW public_analytics_summary AS
SELECT
    organization_id,
    time_bucket,
    bucket_type,
    total_entities,
    total_relationships,
    total_documents,
    processing_success_rate,
    system_health_score,
    -- Aggregated metrics only, no sensitive details
    jsonb_build_object(
        'entity_types', jsonb_object_keys(entity_type_counts),
        'relationship_types', jsonb_object_keys(relationship_type_counts),
        'document_modalities', jsonb_object_keys(modality_counts)
    ) as summary_metadata
FROM entity_analytics_optimized eao
JOIN relationship_analytics_optimized rao ON eao.organization_id = rao.organization_id
                                      AND eao.time_bucket = rao.time_bucket
                                      AND eao.bucket_type = rao.bucket_type
JOIN document_analytics_optimized dao ON eao.organization_id = dao.organization_id
                                     AND eao.time_bucket = dao.time_bucket
                                     AND eao.bucket_type = dao.bucket_type
WHERE eao.organization_id = current_setting('app.current_organization_id', true)::UUID;

GRANT SELECT ON public_analytics_summary TO analytics_viewer;

-- User analytics view (privacy-preserving)
CREATE OR REPLACE VIEW user_analytics_privacy_preserving AS
SELECT
    organization_id,
    time_bucket,
    bucket_type,
    total_sessions,
    avg_session_duration_seconds,
    total_searches,
    search_success_rate,
    avg_response_time_ms,
    -- Aggregate satisfaction metrics, no individual ratings
    CASE
        WHEN avg_user_satisfaction_score >= 4.5 THEN 'excellent'
        WHEN avg_user_satisfaction_score >= 3.5 THEN 'good'
        WHEN avg_user_satisfaction_score >= 2.5 THEN 'average'
        ELSE 'needs_improvement'
    END as satisfaction_category,
    -- Remove personally identifiable information
    jsonb_build_object(
        'query_complexity_distribution', query_complexity_distribution,
        'feature_usage', feature_usage,
        'device_distribution', user_device_distribution
    ) as usage_patterns
FROM user_interaction_analytics_optimized
WHERE organization_id = current_setting('app.current_organization_id', true)::UUID;

GRANT SELECT ON user_analytics_privacy_preserving TO analytics_viewer;

-- ============================================================================
-- SECURITY FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to set session context for RLS
CREATE OR REPLACE FUNCTION set_analytics_session_context(
    p_organization_id UUID,
    p_user_id UUID DEFAULT NULL,
    p_user_role TEXT DEFAULT 'viewer'
) RETURNS VOID AS $$
BEGIN
    -- Set organization context
    PERFORM set_config('app.current_organization_id', p_organization_id::TEXT, true);

    -- Set user context if provided
    IF p_user_id IS NOT NULL THEN
        PERFORM set_config('app.current_user_id', p_user_id::TEXT, true);
    END IF;

    -- Set user role context
    PERFORM set_config('app.current_user_role', p_user_role, true);

    -- Log the session context setting
    INSERT INTO analytics_security_log (
        organization_id,
        user_id,
        action_type,
        action_details,
        created_at
    ) VALUES (
        p_organization_id,
        p_user_id,
        'session_context_set',
        jsonb_build_object(
            'user_role', p_user_role,
            'session_start', NOW()
        ),
        NOW()
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check analytics access permissions
CREATE OR REPLACE FUNCTION check_analytics_access(
    p_organization_id UUID,
    p_required_permission TEXT DEFAULT 'read'
) RETURNS BOOLEAN AS $$
DECLARE
    current_user_role TEXT;
    current_org_id UUID;
    has_access BOOLEAN := FALSE;
BEGIN
    -- Get current session context
    current_org_id := current_setting('app.current_organization_id', true)::UUID;
    current_user_role := current_setting('app.current_user_role', true);

    -- Check if organization context matches
    IF current_org_id IS DISTINCT FROM p_organization_id THEN
        RAISE WARNING 'Organization access denied: % vs %', current_org_id, p_organization_id;
        RETURN FALSE;
    END IF;

    -- Check role-based permissions
    CASE current_user_role
        WHEN 'admin' THEN
            has_access := TRUE;
        WHEN 'editor' THEN
            has_access := p_required_permission IN ('read', 'write', 'execute');
        WHEN 'reporter' THEN
            has_access := p_required_permission IN ('read', 'execute');
        WHEN 'viewer' THEN
            has_access := p_required_permission = 'read';
        ELSE
            has_access := FALSE;
    END CASE;

    -- Log access attempt
    INSERT INTO analytics_security_log (
        organization_id,
        user_id,
        action_type,
        action_details,
        created_at
    ) VALUES (
        p_organization_id,
        current_setting('app.current_user_id', true)::UUID,
        'access_check',
        jsonb_build_object(
            'required_permission', p_required_permission,
            'user_role', current_user_role,
            'access_granted', has_access
        ),
        NOW()
    );

    RETURN has_access;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Security audit trigger for sensitive operations
CREATE OR REPLACE FUNCTION trigger_analytics_security_audit()
RETURNS TRIGGER AS $$
DECLARE
    operation_type TEXT;
    security_level TEXT;
BEGIN
    -- Determine operation type and security level
    IF TG_OP = 'INSERT' THEN
        operation_type := 'create';
        security_level := CASE
            WHEN TG_TABLE_NAME IN ('custom_analytics_reports', 'dashboard_configurations') THEN 'high'
            WHEN TG_TABLE_NAME IN ('analytics_alerts', 'analytics_cache') THEN 'medium'
            ELSE 'low'
        END;
    ELSIF TG_OP = 'UPDATE' THEN
        operation_type := 'update';
        security_level := CASE
            WHEN TG_TABLE_NAME IN ('custom_analytics_reports', 'dashboard_configurations') THEN 'high'
            ELSE 'medium'
        END;
    ELSIF TG_OP = 'DELETE' THEN
        operation_type := 'delete';
        security_level := 'high';
    END IF;

    -- Log security-relevant operations
    INSERT INTO analytics_security_log (
        organization_id,
        user_id,
        action_type,
        table_name,
        record_id,
        security_level,
        action_details,
        created_at
    ) VALUES (
        COALESCE(NEW.organization_id, OLD.organization_id),
        current_setting('app.current_user_id', true)::UUID,
        operation_type,
        TG_TABLE_NAME,
        COALESCE(NEW.id, OLD.id),
        security_level,
        jsonb_build_object(
            'old_values', CASE WHEN TG_OP = 'DELETE' THEN row_to_json(OLD) ELSE NULL END,
            'new_values', CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN row_to_json(NEW) ELSE NULL END,
            'operation', TG_OP
        ),
        NOW()
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Apply security audit triggers to sensitive tables
CREATE TRIGGER custom_analytics_reports_security_trigger
    AFTER INSERT OR UPDATE OR DELETE ON custom_analytics_reports
    FOR EACH ROW
    EXECUTE FUNCTION trigger_analytics_security_audit();

CREATE TRIGGER dashboard_configurations_security_trigger
    AFTER INSERT OR UPDATE OR DELETE ON dashboard_configurations
    FOR EACH ROW
    EXECUTE FUNCTION trigger_analytics_security_audit();

CREATE TRIGGER analytics_alerts_security_trigger
    AFTER INSERT OR UPDATE OR DELETE ON analytics_alerts
    FOR EACH ROW
    EXECUTE FUNCTION trigger_analytics_security_audit();

-- ============================================================================
-- SECURITY LOGGING TABLES
-- ============================================================================

-- Analytics security log table
CREATE TABLE IF NOT EXISTS analytics_security_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    user_id UUID,
    action_type VARCHAR(100) NOT NULL,
    table_name VARCHAR(255),
    record_id UUID,
    security_level VARCHAR(50) DEFAULT 'medium',
    action_details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create partitions for security log
CREATE TABLE IF NOT EXISTS analytics_security_log_current PARTITION OF analytics_security_log
    FOR VALUES FROM (DATE_TRUNC('month', CURRENT_DATE)) TO (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month');

-- Indexes for security monitoring
CREATE INDEX idx_analytics_security_log_org_time ON analytics_security_log (organization_id, created_at DESC);
CREATE INDEX idx_analytics_security_log_user_time ON analytics_security_log (user_id, created_at DESC);
CREATE INDEX idx_analytics_security_log_action ON analytics_security_log (action_type, created_at DESC);
CREATE INDEX idx_analytics_security_log_security_level ON analytics_security_log (security_level, created_at DESC);

-- Enable RLS on security log
ALTER TABLE analytics_security_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY analytics_security_log_admin_policy ON analytics_security_log
    FOR ALL TO analytics_admin
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- ============================================================================
-- SECURITY MONITORING VIEWS
-- ============================================================================

-- Security monitoring view for administrators
CREATE OR REPLACE VIEW security_monitoring_dashboard AS
WITH security_events AS (
    SELECT
        organization_id,
        created_at::DATE as event_date,
        action_type,
        security_level,
        COUNT(*) as event_count,
        COUNT(DISTINCT user_id) as unique_users,
        COUNT(DISTINCT ip_address) as unique_ips
    FROM analytics_security_log
    WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY organization_id, created_at::DATE, action_type, security_level
),
high_risk_events AS (
    SELECT
        organization_id,
        created_at,
        action_type,
        table_name,
        user_id,
        action_details
    FROM analytics_security_log
    WHERE security_level = 'high'
      AND created_at >= CURRENT_DATE - INTERVAL '7 days'
),
access_denials AS (
    SELECT
        organization_id,
        created_at::DATE as denial_date,
        COUNT(*) as denial_count,
        COUNT(DISTINCT user_id) as affected_users
    FROM analytics_security_log
    WHERE action_type = 'access_check'
      AND (action_details->>'access_granted')::BOOLEAN = FALSE
      AND created_at >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY organization_id, created_at::DATE
)
SELECT
    org.id as organization_id,
    org.name as organization_name,
    se.event_date,
    se.action_type,
    se.security_level,
    se.event_count,
    se.unique_users,
    se.unique_ips,
    ad.denial_count,
    ad.affected_users,
    hre.high_risk_event_count,
    -- Security score calculation
    LEAST(100, GREATEST(0,
        100 - (COALESCE(ad.denial_count, 0) * 10) -
              (COALESCE(hre.high_risk_event_count, 0) * 5) -
              CASE WHEN se.security_level = 'high' THEN se.event_count * 2 ELSE 0 END
    )) as security_score
FROM organizations org
LEFT JOIN security_events se ON org.id = se.organization_id
LEFT JOIN (
    SELECT
        organization_id,
        COUNT(*) as high_risk_event_count
    FROM high_risk_events
    GROUP BY organization_id
) hre ON org.id = hre.organization_id
LEFT JOIN access_denials ad ON org.id = ad.organization_id AND se.event_date = ad.denial_date
WHERE org.is_active = TRUE;

GRANT SELECT ON security_monitoring_dashboard TO analytics_admin;

-- ============================================================================
-- DATA MASKING FUNCTIONS
-- ============================================================================

-- Function to mask sensitive user data in analytics
CREATE OR REPLACE FUNCTION mask_user_analytics_data(
    p_data JSONB,
    p_masking_level TEXT DEFAULT 'standard'
) RETURNS JSONB AS $$
BEGIN
    CASE p_masking_level
        WHEN 'strict' THEN
            -- Remove all potentially identifying information
            RETURN p_data - ARRAY[
                'user_id', 'email', 'ip_address', 'user_agent',
                'session_id', 'query_text'
            ];

        WHEN 'standard' THEN
            -- Hash identifying fields but keep aggregates
            RETURN jsonb_build_object(
                'user_count', (p_data->>'user_count')::INTEGER,
                'query_count', (p_data->>'query_count')::INTEGER,
                'avg_session_duration', (p_data->>'avg_session_duration')::NUMERIC,
                'anonymized_patterns', p_data - ARRAY[
                    'user_id', 'email', 'ip_address', 'user_agent',
                    'session_id', 'query_text'
                ]
            );

        WHEN 'minimal' THEN
            -- Only remove direct identifiers
            RETURN p_data - ARRAY['email', 'ip_address', 'user_agent'];

        ELSE
            RETURN p_data;
    END CASE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SECURITY CONFIGURATION FUNCTIONS
-- ============================================================================

-- Function to create analytics user with appropriate permissions
CREATE OR REPLACE FUNCTION create_analytics_user(
    p_username TEXT,
    p_password TEXT,
    p_organization_id UUID,
    p_role TEXT DEFAULT 'viewer'
) RETURNS UUID AS $$
DECLARE
    user_id UUID;
BEGIN
    -- Create the database user
    EXECUTE format('CREATE USER %I WITH PASSWORD %L', p_username, p_password);

    -- Grant appropriate role based on requested role
    CASE p_role
        WHEN 'admin' THEN
            EXECUTE format('GRANT analytics_admin TO %I', p_username);
        WHEN 'editor' THEN
            EXECUTE format('GRANT analytics_editor TO %I', p_username);
        WHEN 'reporter' THEN
            EXECUTE format('GRANT analytics_reporter TO %I', p_username);
        WHEN 'viewer' THEN
            EXECUTE format('GRANT analytics_viewer TO %I', p_username);
        ELSE
            RAISE EXCEPTION 'Invalid role: %s. Must be admin, editor, reporter, or viewer', p_role;
    END CASE;

    -- Grant basic connection permissions
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), p_username);
    EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', p_username);

    -- Grant usage on sequences for tables that allow inserts
    EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', p_username);

    -- Log user creation
    INSERT INTO analytics_security_log (
        organization_id,
        action_type,
        action_details,
        security_level,
        created_at
    ) VALUES (
        p_organization_id,
        'user_created',
        jsonb_build_object(
            'username', p_username,
            'role', p_role,
            'created_by', current_user
        ),
        'high',
        NOW()
    );

    RETURN gen_random_uuid(); -- Return a session identifier
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to revoke analytics access
CREATE OR REPLACE FUNCTION revoke_analytics_access(
    p_username TEXT,
    p_organization_id UUID
) RETURNS BOOLEAN AS $$
BEGIN
    -- Revoke all analytics roles
    EXECUTE format('REVOKE analytics_admin FROM %I', p_username);
    EXECUTE format('REVOKE analytics_editor FROM %I', p_username);
    EXECUTE format('REVOKE analytics_reporter FROM %I', p_username);
    EXECUTE format('REVOKE analytics_viewer FROM %I', p_username);

    -- Optionally drop the user (uncomment if desired)
    -- EXECUTE format('DROP USER IF EXISTS %I', p_username);

    -- Log access revocation
    INSERT INTO analytics_security_log (
        organization_id,
        action_type,
        action_details,
        security_level,
        created_at
    ) VALUES (
        p_organization_id,
        'access_revoked',
        jsonb_build_object(
            'username', p_username,
            'revoked_by', current_user
        ),
        'high',
        NOW()
    );

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;