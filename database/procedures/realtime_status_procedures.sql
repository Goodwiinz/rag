-- Real-Time Status Management Stored Procedures
-- High-performance stored procedures for real-time status tracking and management

-- =================================================================
-- DOCUMENT PROCESSING STATUS MANAGEMENT
-- =================================================================

-- Procedure to atomically update document processing status with comprehensive tracking
CREATE OR REPLACE PROCEDURE update_document_processing_status_comprehensive(
    p_document_id UUID,
    p_new_status VARCHAR(50),
    p_progress DECIMAL(5,2) DEFAULT NULL,
    p_stage VARCHAR(100) DEFAULT NULL,
    p_execution_id UUID DEFAULT NULL,
    p_remaining_seconds INTEGER DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_old_status VARCHAR(50);
    v_old_progress DECIMAL(5,2);
    v_organization_id UUID;
    v_job_execution_id UUID;
    v_should_snapshot BOOLEAN := FALSE;
    v_notification_data JSONB;
BEGIN
    -- Get current document state
    SELECT processing_status, processing_progress, organization_id, current_execution_id
    INTO v_old_status, v_old_progress, v_organization_id, v_job_execution_id
    FROM documents
    WHERE id = p_document_id
    FOR UPDATE; -- Lock the row

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Document not found: %', p_document_id;
    END IF;

    -- Determine if this is a significant change requiring snapshot
    v_should_snapshot := (
        v_old_status != p_new_status OR
        (p_progress IS NOT NULL AND ABS(v_old_progress - p_progress) > 10) OR
        p_error_message IS NOT NULL OR
        (p_stage IS NOT NULL AND p_execution_id IS NOT NULL)
    );

    -- Update document with new status
    UPDATE documents
    SET
        processing_status = p_new_status,
        processing_progress = COALESCE(p_progress, processing_progress),
        current_processing_stage = COALESCE(p_stage, current_processing_stage),
        current_execution_id = COALESCE(p_execution_id, current_execution_id),
        estimated_remaining_seconds = COALESCE(p_remaining_seconds, estimated_remaining_seconds),
        processing_error = COALESCE(p_error_message, processing_error),
        document_metadata = document_metadata || p_metadata,
        last_status_update = NOW()
    WHERE id = p_document_id;

    -- Create status snapshot for significant changes
    IF v_should_snapshot THEN
        INSERT INTO document_status_snapshots (
            document_id,
            job_execution_id,
            processing_status,
            processing_progress,
            current_stage,
            stage_progress,
            processing_duration_seconds,
            estimated_remaining_seconds,
            error_rate,
            snapshot_reason,
            snapshot_data
        )
        VALUES (
            p_document_id,
            p_job_execution_id,
            p_new_status,
            COALESCE(p_progress, 0),
            p_stage,
            COALESCE(p_metadata, '{}'::jsonb),
            EXTRACT(EPOCH FROM (NOW() - created_at))::INTEGER,
            p_remaining_seconds,
            CASE WHEN p_error_message IS NOT NULL THEN 1.0 ELSE 0.0 END,
            CASE
                WHEN v_old_status != p_new_status THEN 'status_change'
                WHEN p_error_message IS NOT NULL THEN 'error'
                WHEN p_progress IS NOT NULL AND ABS(v_old_progress - p_progress) > 10 THEN 'progress_milestone'
                ELSE 'periodic'
            END,
            json_build_object(
                'old_status', v_old_status,
                'new_status', p_new_status,
                'old_progress', v_old_progress,
                'new_progress', COALESCE(p_progress, v_old_progress),
                'stage', p_stage,
                'error', p_error_message IS NOT NULL
            )
        );
    END IF;

    -- Build notification data for real-time updates
    v_notification_data := json_build_object(
        'document_id', p_document_id,
        'organization_id', v_organization_id,
        'old_status', v_old_status,
        'new_status', p_new_status,
        'progress', COALESCE(p_progress, v_old_progress),
        'stage', p_stage,
        'timestamp', NOW(),
        'error_occurred', p_error_message IS NOT NULL,
        'completion', p_new_status = 'completed',
        'failure', p_new_status = 'failed'
    );

    -- Send notification for real-time dashboard updates
    PERFORM pg_notify('document_status_update', v_notification_data::text);

    -- Update related job execution if provided
    IF p_execution_id IS NOT NULL THEN
        UPDATE processing_job_executions
        SET
            execution_status = p_new_status,
            overall_progress = COALESCE(p_progress, overall_progress),
            current_stage = p_stage,
            estimated_remaining_seconds = p_remaining_seconds,
            error_message = p_error_message,
            updated_at = NOW()
        WHERE execution_id = p_execution_id::TEXT;
    END IF;

    COMMIT;
END;
$$;

-- Function to get document processing status with all related data
CREATE OR REPLACE FUNCTION get_document_processing_status_full(p_document_id UUID)
RETURNS TABLE(
    document_id UUID,
    title VARCHAR,
    filename VARCHAR,
    processing_status VARCHAR(50),
    processing_progress DECIMAL(5,2),
    current_processing_stage VARCHAR(100),
    estimated_remaining_seconds INTEGER,
    processing_error TEXT,
    last_status_update TIMESTAMPTZ,
    created_at TIMESTAMPTZ,

    -- Job execution details
    job_execution_id UUID,
    execution_status VARCHAR(50),
    overall_progress DECIMAL(5,2),
    total_stages INTEGER,
    completed_stages INTEGER,
    failed_stages INTEGER,
    started_at TIMESTAMPTZ,
    primary_worker_id VARCHAR,

    -- Current stage details
    current_stage_name VARCHAR(200),
    current_stage_progress DECIMAL(5,2),
    current_stage_started_at TIMESTAMPTZ,
    current_worker_id VARCHAR,

    -- Recent status history
    recent_snapshots JSONB,

    -- Performance metrics
    total_duration_seconds INTEGER,
    avg_stage_duration_seconds DECIMAL(10,2),
    quality_score DECIMAL(5,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH document_info AS (
        SELECT
            d.*,
            pje.id as job_exec_id,
            pje.execution_status as job_status,
            pje.overall_progress as job_progress,
            pje.total_stages,
            pje.completed_stages,
            pje.failed_stages,
            pje.started_at as job_started,
            pje.primary_worker_id,
            se.stage_name as current_stage_name,
            se.progress_percentage as current_stage_progress,
            se.started_at as current_stage_started,
            se.worker_id as current_worker_id
        FROM documents d
        LEFT JOIN processing_job_executions pje ON d.current_execution_id = pje.execution_id
        LEFT JOIN stage_executions se ON pje.id = se.job_execution_id AND se.stage_status = 'running'
        WHERE d.id = p_document_id
    ),
    status_history AS (
        SELECT json_agg(
            json_build_object(
                'status', processing_status,
                'progress', processing_progress,
                'stage', current_stage,
                'snapshot_reason', snapshot_reason,
                'created_at', created_at
            )
            ORDER BY created_at DESC
        ) as snapshots
        FROM document_status_snapshots
        WHERE document_id = p_document_id
            AND created_at >= NOW() - INTERVAL '24 hours'
        LIMIT 10
    ),
    performance_data AS (
        SELECT
            EXTRACT(EPOCH FROM (completed_at - started_at))::INTEGER as total_duration,
            AVG(se.duration_ms) / 1000.0 as avg_stage_duration,
            AVG(se.output_quality_score) as quality_score
        FROM processing_job_executions pje
        LEFT JOIN stage_executions se ON pje.id = se.job_execution_id AND se.stage_status = 'completed'
        WHERE pje.document_id = p_document_id
            AND pje.execution_status = 'completed'
        GROUP BY pje.id, pje.completed_at, pje.started_at
        ORDER BY pje.completed_at DESC
        LIMIT 1
    )
    SELECT
        di.id,
        di.title,
        di.filename,
        di.processing_status,
        di.processing_progress,
        di.current_processing_stage,
        di.estimated_remaining_seconds,
        di.processing_error,
        di.last_status_update,
        di.created_at,
        di.job_exec_id,
        di.job_status,
        di.job_progress,
        di.total_stages,
        di.completed_stages,
        di.failed_stages,
        di.job_started,
        di.primary_worker_id,
        di.current_stage_name,
        di.current_stage_progress,
        di.current_stage_started,
        di.current_worker_id,
        COALESCE(sh.snapshots, '[]'::jsonb),
        pd.total_duration,
        pd.avg_stage_duration,
        pd.quality_score
    FROM document_info di
    CROSS JOIN status_history sh
    LEFT JOIN performance_data pd ON true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =================================================================
-- BATCH PROCESSING OPERATIONS
-- =================================================================

-- Procedure to create and start batch processing operations
CREATE OR REPLACE PROCEDURE start_batch_processing(
    p_organization_id UUID,
    p_document_ids UUID[],
    p_processing_config JSONB DEFAULT '{}',
    p_priority INTEGER DEFAULT 5,
    p_batch_label VARCHAR(200) DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_batch_id VARCHAR(100);
    v_total_documents INTEGER := array_length(p_document_ids, 1);
    v_created_jobs INTEGER := 0;
    v_notification_data JSONB;
BEGIN
    -- Generate unique batch ID
    v_batch_id := COALESCE(p_batch_label, 'batch') || '_' || extract(epoch from now())::TEXT || '_' || substr(md5(random()::TEXT), 1, 8);

    -- Create job executions for all documents in batch
    INSERT INTO processing_job_executions (
        document_id,
        organization_id,
        execution_id,
        batch_id,
        execution_status,
        overall_progress,
        total_stages,
        execution_config,
        processing_priority
    )
    SELECT
        doc_id,
        p_organization_id,
        v_batch_id || '_' || row_number::TEXT,
        v_batch_id,
        'queued',
        0,
        (SELECT COUNT(*) FROM document_processing_stages WHERE is_active = true),
        json_build_object(
            'batch_id', v_batch_id,
            'priority', p_priority,
            'config', p_processing_config,
            'total_documents', v_total_documents,
            'created_at', NOW()
        ),
        p_priority
    FROM unnest(p_document_ids) WITH ORDINALITY AS t(doc_id, row_number);

    GET DIAGNOSTICS v_created_jobs = ROW_COUNT;

    -- Update documents with batch information
    UPDATE documents
    SET
        processing_batch_id = v_batch_id,
        processing_priority = p_priority,
        processing_status = CASE
            WHEN processing_status IN ('pending', 'failed') THEN 'queued'
            ELSE processing_status
        END,
        last_status_update = NOW()
    WHERE id = ANY(p_document_ids)
        AND organization_id = p_organization_id;

    -- Build notification data
    v_notification_data := json_build_object(
        'organization_id', p_organization_id,
        'batch_id', v_batch_id,
        'total_documents', v_total_documents,
        'created_jobs', v_created_jobs,
        'priority', p_priority,
        'status', 'started',
        'timestamp', NOW()
    );

    -- Send batch notification
    PERFORM pg_notify('batch_processing_started', v_notification_data::text);

    COMMIT;
END;
$$;

-- Function to get batch processing status
CREATE OR REPLACE FUNCTION get_batch_processing_status(p_batch_id VARCHAR(100))
RETURNS TABLE(
    batch_id VARCHAR(100),
    organization_id UUID,
    total_documents INTEGER,
    pending_documents INTEGER,
    processing_documents INTEGER,
    completed_documents INTEGER,
    failed_documents INTEGER,
    retrying_documents INTEGER,

    -- Progress metrics
    overall_progress DECIMAL(5,2),
    avg_processing_time_seconds DECIMAL(10,2),
    estimated_completion_seconds INTEGER,

    -- Performance metrics
    success_rate DECIMAL(5,2),
    avg_quality_score DECIMAL(5,4),
    total_cost_usd DECIMAL(10,6),

    -- Worker metrics
    active_workers INTEGER,
    total_workers INTEGER,

    -- Timing metrics
    started_at TIMESTAMPTZ,
    estimated_completion_at TIMESTAMPTZ,
    duration_seconds INTEGER,

    -- Recent errors
    recent_error_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH batch_metrics AS (
        SELECT
            pje.batch_id,
            pje.organization_id,
            COUNT(DISTINCT pje.document_id) as total_docs,
            COUNT(DISTINCT pje.document_id) FILTER (WHERE pje.execution_status = 'queued') as pending_docs,
            COUNT(DISTINCT pje.document_id) FILTER (WHERE pje.execution_status = 'running') as processing_docs,
            COUNT(DISTINCT pje.document_id) FILTER (WHERE pje.execution_status = 'completed') as completed_docs,
            COUNT(DISTINCT pje.document_id) FILTER (WHERE pje.execution_status = 'failed') as failed_docs,
            COUNT(DISTINCT pje.document_id) FILTER (WHERE pje.execution_status = 'retrying') as retrying_docs,

            -- Progress calculations
            COALESCE(AVG(pje.overall_progress), 0) as avg_progress,
            COUNT(DISTINCT pje.primary_worker_id) as active_workers,
            MIN(pje.queued_at) as started_at,

            -- Performance metrics
            COALESCE(AVG(EXTRACT(EPOCH FROM (pje.completed_at - pje.started_at))), 0) as avg_duration_seconds

        FROM processing_job_executions pje
        WHERE pje.batch_id = p_batch_id
            AND pje.is_deleted = false
        GROUP BY pje.batch_id, pje.organization_id
    ),
    error_metrics AS (
        SELECT
            COUNT(*) as recent_error_count
        FROM processing_error_logs pel
        JOIN processing_job_executions pje ON pel.job_execution_id = pje.id
        WHERE pje.batch_id = p_batch_id
            AND pel.occurred_at >= NOW() - INTERVAL '1 hour'
    ),
    quality_metrics AS (
        SELECT
            COALESCE(AVG(se.output_quality_score), 0) as avg_quality,
            COALESCE(SUM(ae.cost_usd), 0) as total_cost
        FROM processing_job_executions pje
        LEFT JOIN stage_executions se ON pje.id = se.job_execution_id AND se.stage_status = 'completed'
        LEFT JOIN agent_executions ae ON se.id = ae.stage_execution_id
        WHERE pje.batch_id = p_batch_id
            AND pje.execution_status = 'completed'
    )
    SELECT
        bm.batch_id,
        bm.organization_id,
        bm.total_docs as total_documents,
        bm.pending_docs as pending_documents,
        bm.processing_docs as processing_documents,
        bm.completed_docs as completed_documents,
        bm.failed_docs as failed_documents,
        bm.retrying_docs as retrying_documents,
        bm.avg_progress as overall_progress,
        bm.avg_duration_seconds as avg_processing_time_seconds,
        CASE
            WHEN bm.avg_progress > 0 AND bm.processing_docs > 0 THEN
                (bm.avg_duration_seconds / bm.avg_progress * 100.0)::INTEGER
            ELSE NULL
        END as estimated_completion_seconds,
        ROUND(bm.completed_docs * 100.0 / NULLIF(bm.total_docs, 0), 2) as success_rate,
        qm.avg_quality as avg_quality_score,
        qm.total_cost as total_cost_usd,
        bm.active_workers,
        bm.total_docs as total_workers,
        bm.started_at,
        CASE
            WHEN bm.avg_progress > 0 AND bm.processing_docs > 0 THEN
                bm.started_at + (bm.avg_duration_seconds / bm.avg_progress * 100.0) * INTERVAL '1 second'
            ELSE NULL
        END as estimated_completion_at,
        EXTRACT(EPOCH FROM (NOW() - bm.started_at))::INTEGER as duration_seconds,
        COALESCE(em.recent_error_count, 0) as recent_error_count
    FROM batch_metrics bm
    LEFT JOIN error_metrics em ON true
    LEFT JOIN quality_metrics qm ON true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =================================================================
-- WORKER MANAGEMENT PROCEDURES
-- =================================================================

-- Procedure to assign worker to processing job
CREATE OR REPLACE PROCEDURE assign_worker_to_job(
    p_job_execution_id UUID,
    p_worker_id VARCHAR(255),
    p_worker_capabilities JSONB DEFAULT '{}'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_organization_id UUID;
    v_notification_data JSONB;
BEGIN
    -- Update job execution with worker assignment
    UPDATE processing_job_executions
    SET
        primary_worker_id = p_worker_id,
        execution_status = 'running',
        started_at = COALESCE(started_at, NOW()),
        worker_capabilities = p_worker_capabilities,
        updated_at = NOW()
    WHERE id = p_job_execution_id
        AND execution_status IN ('queued', 'retrying')
    RETURNING organization_id INTO v_organization_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Job execution not found or not in assignable state: %', p_job_execution_id;
    END IF;

    -- Update document status
    UPDATE documents
    SET
        processing_status = 'processing',
        active_workers = jsonb_set(
            COALESCE(active_workers, '[]'::jsonb),
            array_length(COALESCE(active_workers, '[]'::jsonb), 1)::TEXT,
            json_build_object('worker_id', p_worker_id, 'assigned_at', NOW())
        ),
        last_status_update = NOW()
    WHERE current_execution_id = (
        SELECT execution_id FROM processing_job_executions WHERE id = p_job_execution_id
    );

    -- Build notification data
    v_notification_data := json_build_object(
        'organization_id', v_organization_id,
        'job_execution_id', p_job_execution_id,
        'worker_id', p_worker_id,
        'status', 'worker_assigned',
        'timestamp', NOW()
    );

    -- Send notification
    PERFORM pg_notify('worker_assigned', v_notification_data::text);

    COMMIT;
END;
$$;

-- Function to get worker current workload
CREATE OR REPLACE FUNCTION get_worker_workload(p_worker_id VARCHAR(255))
RETURNS TABLE(
    worker_id VARCHAR(255),
    active_jobs INTEGER,
    queued_jobs INTEGER,
    total_jobs INTEGER,
    avg_progress DECIMAL(5,2),
    estimated_completion_seconds INTEGER,
    current_stages JSONB,
    recent_performance JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH worker_jobs AS (
        SELECT
            pje.primary_worker_id,
            COUNT(*) FILTER (WHERE execution_status = 'running') as active,
            COUNT(*) FILTER (WHERE execution_status = 'queued') as queued,
            COUNT(*) as total,
            COALESCE(AVG(pje.overall_progress), 0) as avg_prog,
            json_agg(
                json_build_object(
                    'job_id', pje.id,
                    'document_id', pje.document_id,
                    'status', pje.execution_status,
                    'progress', pje.overall_progress,
                    'current_stage', pje.current_stage,
                    'document_title', d.title
                )
            ) FILTER (WHERE pje.execution_status IN ('running', 'queued')) as stages
        FROM processing_job_executions pje
        LEFT JOIN documents d ON pje.document_id = d.id
        WHERE pje.primary_worker_id = p_worker_id
            AND pje.is_deleted = false
            AND pje.execution_status IN ('running', 'queued', 'retrying')
        GROUP BY pje.primary_worker_id
    ),
    performance_data AS (
        SELECT
            json_build_object(
                'avg_job_duration_seconds', COALESCE(AVG(EXTRACT(EPOCH FROM (completed_at - started_at))), 0),
                'jobs_completed_last_hour', COUNT(*) FILTER (WHERE completed_at >= NOW() - INTERVAL '1 hour'),
                'avg_quality_score', COALESCE(AVG(se.output_quality_score), 0),
                'total_cost_usd', COALESCE(SUM(ae.cost_usd), 0),
                'success_rate', ROUND(COUNT(*) FILTER (WHERE execution_status = 'completed') * 100.0 / NULLIF(COUNT(*), 0), 2)
            ) as perf_data
        FROM processing_job_executions pje
        LEFT JOIN stage_executions se ON pje.id = se.job_execution_id AND se.stage_status = 'completed'
        LEFT JOIN agent_executions ae ON se.id = ae.stage_execution_id
        WHERE pje.primary_worker_id = p_worker_id
            AND pje.completed_at >= NOW() - INTERVAL '24 hours'
        GROUP BY pje.primary_worker_id
    )
    SELECT
        wj.primary_worker_id,
        wj.active,
        wj.queued,
        wj.total,
        wj.avg_prog,
        CASE
            WHEN wj.avg_prog > 0 AND wj.active > 0 THEN
                (SELECT AVG(estimated_remaining_seconds) FROM processing_job_executions
                 WHERE primary_worker_id = p_worker_id AND execution_status = 'running')::INTEGER
            ELSE NULL
        END,
        wj.stages,
        COALESCE(pd.perf_data, '{}'::jsonb)
    FROM worker_jobs wj
    LEFT JOIN performance_data pd ON true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permissions
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA public TO authenticated_users;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated_users;