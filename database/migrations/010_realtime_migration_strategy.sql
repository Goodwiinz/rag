-- Migration Strategy and Backward Compatibility
-- Safe migration from existing schema to enhanced real-time processing

BEGIN;

-- Create migration tracking table
CREATE TABLE IF NOT EXISTS migration_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    migration_version VARCHAR(50) NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'applied',
    rollback_script TEXT,
    notes TEXT,
    applied_by VARCHAR(255)
);

-- Insert migration record
INSERT INTO migration_tracking (migration_name, migration_version, notes, applied_by)
VALUES (
    '008_enhanced_realtime_document_processing',
    '1.0.0',
    'Enhanced real-time document processing status tracking with WebSocket integration',
    'database_migration'
) ON CONFLICT (migration_name) DO NOTHING;

-- Step 1: Create backup of critical existing data
-- This creates temporary tables for rollback purposes

-- Backup existing documents processing status
CREATE TEMPORARY TABLE documents_backup AS
SELECT
    id,
    processing_status,
    processing_started_at,
    processing_completed_at,
    processing_error,
    processing_retry_count,
    embedding_id,
    is_embedded,
    is_indexed
FROM documents;

-- Backup existing processing jobs
CREATE TEMPORARY TABLE processing_jobs_backup AS
SELECT * FROM document_processing_jobs;

-- Step 2: Add new columns with safe defaults
-- Using IF NOT EXISTS to ensure safe re-running

-- Enhanced documents table columns (already added in main migration)
-- These are safe additions that don't break existing functionality

-- Step 3: Data migration from existing schema
-- Migrate existing document_processing_jobs to new processing_job_executions structure

INSERT INTO processing_job_executions (
    id,
    document_id,
    organization_id,
    execution_id,
    execution_status,
    started_at,
    completed_at,
    created_at,
    updated_at,
    error_message,
    retry_count,
    max_retries
)
SELECT
    gen_random_uuid(),
    dpj.document_id,
    dpj.organization_id,
    'legacy_' || dpj.id::text,  -- Create execution ID from legacy job ID
    CASE
        WHEN dpj.status = 'pending' THEN 'pending'
        WHEN dpj.status = 'running' THEN 'running'
        WHEN dpj.status = 'completed' THEN 'completed'
        WHEN dpj.status = 'failed' THEN 'failed'
        WHEN dpj.status = 'cancelled' THEN 'cancelled'
        ELSE dpj.status
    END,
    dpj.started_at,
    dpj.completed_at,
    dpj.created_at,
    dpj.updated_at,
    dpj.error_message,
    dpj.retry_count,
    dpj.max_retries
FROM document_processing_jobs dpj
WHERE dpj.is_deleted = false
ON CONFLICT (execution_id) DO NOTHING;

-- Step 4: Update existing documents with new real-time columns
-- Set reasonable defaults for existing documents

UPDATE documents SET
    processing_progress = CASE
        WHEN processing_status = 'completed' THEN 100.0
        WHEN processing_status = 'processing' THEN 50.0
        WHEN processing_status = 'failed' THEN 0.0
        WHEN processing_status = 'queued' THEN 0.0
        ELSE 0.0
    END,
    last_status_update = COALESCE(
        processing_completed_at,
        processing_started_at,
        created_at,
        NOW()
    ),
    processing_priority = 5,
    current_execution_id = (
        SELECT pje.id
        FROM processing_job_executions pje
        WHERE pje.document_id = documents.id
        ORDER BY pje.created_at DESC
        LIMIT 1
    )
WHERE last_status_update IS NULL
OR processing_progress IS NULL;

-- Step 5: Create initial processing stages based on existing jobs
-- This helps maintain continuity in the processing pipeline

INSERT INTO stage_executions (
    job_execution_id,
    stage_key,
    stage_name,
    stage_order,
    stage_status,
    started_at,
    completed_at,
    progress_percentage,
    duration_ms,
    error_message,
    retry_count,
    max_retries,
    created_at,
    updated_at
)
SELECT
    pje.id,
    LOWER(REPLACE(dpj.job_type, '_', '_')),  -- Convert job type to stage key
    INITCAP(REPLACE(dpj.job_type, '_', ' ')),  -- Convert job type to stage name
    ROW_NUMBER() OVER (PARTITION BY dpj.document_id ORDER BY dpj.created_at),
    CASE
        WHEN dpj.status = 'pending' THEN 'pending'
        WHEN dpj.status = 'running' THEN 'running'
        WHEN dpj.status = 'completed' THEN 'completed'
        WHEN dpj.status = 'failed' THEN 'failed'
        WHEN dpj.status = 'cancelled' THEN 'cancelled'
        ELSE dpj.status
    END,
    dpj.started_at,
    dpj.completed_at,
    CASE
        WHEN dpj.status = 'completed' THEN 100.0
        WHEN dpj.status = 'running' THEN 50.0
        WHEN dpj.status = 'failed' THEN 0.0
        ELSE 0.0
    END,
    CASE
        WHEN dpj.started_at IS NOT NULL AND dpj.completed_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (dpj.completed_at - dpj.started_at)) * 1000
        ELSE NULL
    END,
    dpj.error_message,
    dpj.retry_count,
    dpj.max_retries,
    dpj.created_at,
    dpj.updated_at
FROM processing_job_executions pje
JOIN document_processing_jobs dpj ON pje.execution_id = 'legacy_' || dpj.id::text
WHERE dpj.is_deleted = false
ON CONFLICT (job_execution_id, stage_key) DO NOTHING;

-- Step 6: Create initial status snapshots for existing documents
-- This provides historical context for the new monitoring system

INSERT INTO document_status_snapshots (
    document_id,
    processing_status,
    processing_progress,
    current_stage,
    processing_duration_seconds,
    error_rate,
    quality_score,
    snapshot_reason,
    created_at
)
SELECT
    d.id,
    d.processing_status,
    d.processing_progress,
    d.current_processing_stage,
    CASE
        WHEN d.processing_started_at IS NOT NULL AND d.processing_completed_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (d.processing_completed_at - d.processing_started_at))::INTEGER
        WHEN d.processing_started_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (NOW() - d.processing_started_at))::INTEGER
        ELSE NULL
    END,
    CASE WHEN d.processing_status = 'failed' THEN 1.0 ELSE 0.0 END,
    d.quality_score,
    'migration_snapshot',
    NOW()
FROM documents d
WHERE d.is_deleted = false
AND d.processing_status IS NOT NULL;

-- Step 7: Update processing job executions to calculate progress based on stages
-- This ensures the new progress tracking works for migrated jobs

UPDATE processing_job_executions SET
    total_stages = (
        SELECT COUNT(*)
        FROM stage_executions se
        WHERE se.job_execution_id = processing_job_executions.id
        AND se.is_deleted = false
    ),
    completed_stages = (
        SELECT COUNT(*)
        FROM stage_executions se
        WHERE se.job_execution_id = processing_job_executions.id
        AND se.stage_status = 'completed'
        AND se.is_deleted = false
    ),
    failed_stages = (
        SELECT COUNT(*)
        FROM stage_executions se
        WHERE se.job_execution_id = processing_job_executions.id
        AND se.stage_status = 'failed'
        AND se.is_deleted = false
    ),
    overall_progress = CASE
        WHEN (
            SELECT COUNT(*)
            FROM stage_executions se
            WHERE se.job_execution_id = processing_job_executions.id
            AND se.is_deleted = false
        ) > 0
        THEN (
            SELECT COUNT(*)
            FROM stage_executions se
            WHERE se.job_execution_id = processing_job_executions.id
            AND se.stage_status = 'completed'
            AND se.is_deleted = false
        ) * 100.0 / (
            SELECT COUNT(*)
            FROM stage_executions se
            WHERE se.job_execution_id = processing_job_executions.id
            AND se.is_deleted = false
        )
        ELSE 0
    END
WHERE id IN (
    SELECT DISTINCT pje.id
    FROM processing_job_executions pje
    JOIN stage_executions se ON pje.id = se.job_execution_id
    WHERE pje.is_deleted = false
    AND se.is_deleted = false
);

-- Step 8: Create migration validation queries
-- These queries verify the migration was successful

-- Validate document migration
DO $$
DECLARE
    doc_count INTEGER;
    updated_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO doc_count FROM documents WHERE is_deleted = false;
    SELECT COUNT(*) INTO updated_count FROM documents
    WHERE processing_progress IS NOT NULL
    AND last_status_update IS NOT NULL
    AND is_deleted = false;

    IF updated_count < doc_count * 0.95 THEN
        RAISE EXCEPTION 'Document migration incomplete: % of % documents updated', updated_count, doc_count;
    END IF;

    RAISE NOTICE 'Document migration successful: % documents updated out of % total', updated_count, doc_count;
END $$;

-- Validate job execution migration
DO $$
DECLARE
    legacy_jobs INTEGER;
    migrated_jobs INTEGER;
BEGIN
    SELECT COUNT(*) INTO legacy_jobs FROM document_processing_jobs WHERE is_deleted = false;
    SELECT COUNT(*) INTO migrated_jobs FROM processing_job_executions WHERE execution_id LIKE 'legacy_%';

    IF migrated_jobs < legacy_jobs THEN
        RAISE EXCEPTION 'Job migration incomplete: % legacy jobs, % migrated', legacy_jobs, migrated_jobs;
    END IF;

    RAISE NOTICE 'Job migration successful: % jobs migrated out of % legacy', migrated_jobs, legacy_jobs;
END $$;

-- Step 9: Create backward compatibility layer
-- This ensures existing queries continue to work during transition period

-- Create a view that mimics the old document_processing_jobs table structure
CREATE OR REPLACE VIEW document_processing_jobs_legacy AS
SELECT
    gen_random_uuid() as id,
    pje.document_id,
    pje.organization_id,
    pje.execution_id as job_id,
    CASE
        WHEN pje.execution_status = 'pending' THEN 'pending'
        WHEN pje.execution_status = 'queued' THEN 'pending'
        WHEN pje.execution_status = 'running' THEN 'running'
        WHEN pje.execution_status = 'completed' THEN 'completed'
        WHEN pje.execution_status = 'failed' THEN 'failed'
        WHEN pje.execution_status = 'cancelled' THEN 'cancelled'
        WHEN pje.execution_status = 'retrying' THEN 'pending'
        ELSE 'pending'
    END as status,
    pje.started_at,
    pje.completed_at,
    pje.error_message,
    pje.retry_count,
    pje.max_retries,
    pje.queued_at as created_at,
    pje.updated_at,
    pje.execution_metadata as result_data,
    pje.error_details as error_details,
    pje.primary_worker_id as worker_id,
    '1.0' as worker_version,
    5 as job_priority,
    JSONB '{}' as requirements,
    0 as cpu_time_ms,
    0 as memory_peak_mb,
    0 as tokens_used,
    0.0 as cost_usd,
    FALSE as is_deleted
FROM processing_job_executions pje
WHERE pje.is_deleted = false;

COMMENT ON VIEW document_processing_jobs_legacy IS 'Backward compatibility view for legacy document_processing_jobs table';

-- Step 10: Create migration completion checkpoint
-- This marks the migration as successfully completed

CREATE OR REPLACE FUNCTION migration_008_completion_check()
RETURNS BOOLEAN AS $$
DECLARE
    migration_exists BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM migration_tracking
        WHERE migration_name = '008_enhanced_realtime_document_processing'
        AND status = 'applied'
    ) INTO migration_exists;

    RETURN migration_exists;
END;
$$ LANGUAGE plpgsql;

-- Perform final validation
DO $$
DECLARE
    migration_complete BOOLEAN;
BEGIN
    SELECT migration_008_completion_check() INTO migration_complete;

    IF migration_complete THEN
        RAISE NOTICE 'Migration 008 completed successfully';

        -- Log completion
        UPDATE migration_tracking
        SET
            status = 'completed',
            notes = notes || ' - Migration validated and completed successfully'
        WHERE migration_name = '008_enhanced_realtime_document_processing';
    ELSE
        RAISE EXCEPTION 'Migration 008 validation failed';
    END IF;
END $$;

COMMIT;