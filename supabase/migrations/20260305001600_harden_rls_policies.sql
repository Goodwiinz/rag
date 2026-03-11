-- Migration: Harden RLS policies — replace permissive ALL policies
-- Date: 2026-03-05
-- Purpose: Fix Supabase linter warnings (rls_policy_always_true) for 68 tables.
--
-- Context:
--   - Backend uses SQLAlchemy with direct DB connection (bypasses RLS).
--   - Backend Supabase client uses service_role key (bypasses RLS).
--   - Frontend only uses supabase.auth.* — no PostgREST data queries.
--   - Therefore: deny all writes via PostgREST, allow reads for Realtime compat.
--
-- The linter intentionally excludes SELECT policies with USING(true),
-- so read-only access does NOT trigger a warning.

BEGIN;

-- ============================================================================
-- 1. DROP existing permissive ALL policies from all 68 tables
-- ============================================================================

DO $$
DECLARE
  tbl TEXT;
  tables TEXT[] := ARRAY[
    'ab_assignments', 'ab_experiment_metrics', 'ab_experiment_segments',
    'ab_experiments', 'ab_query_routing', 'ab_user_segment_memberships',
    'ab_user_segments', 'ab_variants', 'alembic_version',
    'analytics_events', 'api_key_usage_log', 'api_keys',
    'audit_events', 'chat_messages', 'citation_relationships',
    'citations', 'collection_documents', 'collections',
    'compliance_reports', 'connection_events', 'conversations',
    'data_retention_policies', 'document_access_log', 'document_quality_metrics',
    'document_versions', 'documents', 'draft_citations',
    'encrypted_organization_profiles', 'encrypted_user_profiles', 'encryption_audit_logs',
    'entities', 'entity_relationships', 'evaluation_comparisons',
    'evaluation_datasets', 'evaluation_jobs', 'evaluation_metrics',
    'evaluation_reports', 'evaluation_thresholds', 'extraction_cells',
    'extraction_matrices', 'generated_drafts', 'integrity_scores',
    'message_attachments', 'metric_aggregations', 'multimodal_content',
    'notification_templates', 'organizations', 'performance_logs',
    'permissions', 'processing_history', 'processing_jobs',
    'project_notes', 'project_threads', 'quality_alerts',
    'quality_metrics', 'quality_thresholds', 'research_blueprints',
    'research_evidence', 'research_pipelines', 'research_projects',
    'research_runs', 'research_sources', 'research_steps',
    'role_permissions', 'roles', 'search_events',
    'search_queries', 'search_results', 'search_sessions',
    'security_incidents', 'stance_classifications', 'status_updates',
    'system_metrics', 'system_status_broadcasts', 'threads',
    'user_role_assignments', 'user_sessions', 'users',
    'workspace_members', 'workspaces'
  ];
BEGIN
  FOREACH tbl IN ARRAY tables LOOP
    -- Drop the old permissive ALL policy
    EXECUTE format(
      'DROP POLICY IF EXISTS "authenticated_full_access" ON public.%I',
      tbl
    );

    -- SELECT: allow reads (intentionally excluded from linter check)
    EXECUTE format(
      'CREATE POLICY "authenticated_read_only" ON public.%I FOR SELECT TO authenticated USING (true)',
      tbl
    );

    -- INSERT: deny all writes via PostgREST
    EXECUTE format(
      'CREATE POLICY "deny_postgrest_insert" ON public.%I FOR INSERT TO authenticated WITH CHECK (false)',
      tbl
    );

    -- UPDATE: deny all writes via PostgREST
    EXECUTE format(
      'CREATE POLICY "deny_postgrest_update" ON public.%I FOR UPDATE TO authenticated USING (false) WITH CHECK (false)',
      tbl
    );

    -- DELETE: deny all writes via PostgREST
    EXECUTE format(
      'CREATE POLICY "deny_postgrest_delete" ON public.%I FOR DELETE TO authenticated USING (false)',
      tbl
    );
  END LOOP;
END
$$;

-- ============================================================================
-- 2. ADD policies to tables that have RLS enabled but no policies
-- ============================================================================

DO $$
DECLARE
  tbl TEXT;
  tables TEXT[] := ARRAY[
    'document_processing_stages',
    'realtime_performance_metrics',
    'realtime_status_updates',
    'user_realtime_subscriptions',
    'websocket_connections'
  ];
BEGIN
  FOREACH tbl IN ARRAY tables LOOP
    EXECUTE format('CREATE POLICY "authenticated_read_only" ON public.%I FOR SELECT TO authenticated USING (true)', tbl);
    EXECUTE format('CREATE POLICY "deny_postgrest_insert" ON public.%I FOR INSERT TO authenticated WITH CHECK (false)', tbl);
    EXECUTE format('CREATE POLICY "deny_postgrest_update" ON public.%I FOR UPDATE TO authenticated USING (false) WITH CHECK (false)', tbl);
    EXECUTE format('CREATE POLICY "deny_postgrest_delete" ON public.%I FOR DELETE TO authenticated USING (false)', tbl);
  END LOOP;
END
$$;

-- ============================================================================
-- 3. Keep postgres_full_access on alembic_version (unchanged, needed for migrations)
-- ============================================================================
-- The postgres_full_access policy from the previous migration remains in place.
-- No changes needed here.

COMMIT;
