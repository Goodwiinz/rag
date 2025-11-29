-- Rollback Migration 001: Remove A/B Testing Schema
-- This migration removes all A/B testing tables and related objects
-- WARNING: This will delete all A/B testing data permanently

BEGIN;

-- Disable row level security if it exists
ALTER TABLE ab_user_assignments DISABLE ROW LEVEL SECURITY;
ALTER TABLE ab_query_events DISABLE ROW LEVEL SECURITY;
ALTER TABLE ab_quality_metrics DISABLE ROW LEVEL SECURITY;

-- Drop views
DROP VIEW IF EXISTS v_active_experiments;
DROP VIEW IF EXISTS v_experiment_performance_summary;

-- Drop functions
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS validate_experiment_constraints() CASCADE;
DROP FUNCTION IF EXISTS calculate_experiment_significance(UUID, VARCHAR, DECIMAL) CASCADE;
DROP FUNCTION IF EXISTS create_monthly_partition_user_assignments() CASCADE;
DROP FUNCTION IF EXISTS create_daily_partition_query_events() CASCADE;
DROP FUNCTION IF EXISTS monitor_ab_testing_performance() CASCADE;

-- Drop tables in order of dependencies (child tables first)
DROP TABLE IF EXISTS ab_statistical_analyses CASCADE;
DROP TABLE IF EXISTS ab_quality_metrics CASCADE;
DROP TABLE IF EXISTS ab_query_events CASCADE;
DROP TABLE IF EXISTS ab_user_assignments CASCADE;
DROP TABLE IF EXISTS ab_experiment_targeting CASCADE;
DROP TABLE IF EXISTS ab_variants CASCADE;
DROP TABLE IF EXISTS ab_user_segments CASCADE;
DROP TABLE IF EXISTS ab_experiments CASCADE;

-- Drop roles if they were created
DROP ROLE IF EXISTS ab_testing_admin;
DROP ROLE IF EXISTS ab_testing_user;

-- Remove migration record
DELETE FROM schema_migrations WHERE version = '001';

COMMIT;

-- Verify rollback
DO $$
DECLARE
    remaining_tables integer;
BEGIN
    SELECT COUNT(*) INTO remaining_tables
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name LIKE 'ab_%';

    IF remaining_tables > 0 THEN
        RAISE WARNING 'Rollback completed with % remaining A/B testing tables', remaining_tables;
    ELSE
        RAISE NOTICE 'A/B testing schema rollback completed successfully';
    END IF;
END $$;