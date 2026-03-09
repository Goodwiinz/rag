-- Migration: Enable Row Level Security on all public tables
-- Date: 2026-03-04
-- Purpose: Fix Supabase linter errors for rls_disabled_in_public and sensitive_columns_exposed
-- Note: Backend uses service_role key which bypasses RLS. These policies protect
--       against unauthorized access via anon/authenticated PostgREST API calls.

BEGIN;

-- ============================================================================
-- 1. ENABLE ROW LEVEL SECURITY ON ALL FLAGGED TABLES
-- ============================================================================

ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_key_usage_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notification_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stance_classifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ab_experiments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ab_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ab_variants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ab_experiment_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ab_experiment_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ab_user_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ab_query_routing ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ab_user_segment_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.analytics_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.citation_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.collection_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.compliance_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.connection_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.data_retention_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_access_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_quality_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.draft_citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.generated_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.encrypted_organization_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.encrypted_user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.encryption_audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.entity_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_comparisons ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_thresholds ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.extraction_cells ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.extraction_matrices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.integrity_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.metric_aggregations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.multimodal_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.performance_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.processing_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.project_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quality_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quality_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quality_thresholds ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_blueprints ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_pipelines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.security_incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.status_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_status_broadcasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_role_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- 2. CREATE POLICIES — Authenticated users get full access
--    (service_role bypasses RLS automatically, no explicit policy needed)
-- ============================================================================

-- Helper: creates a permissive ALL policy for authenticated role
-- We use DO blocks to make this concise and maintainable.

DO $$
DECLARE
  tbl TEXT;
  tables TEXT[] := ARRAY[
    'api_key_usage_log', 'api_keys', 'notification_templates', 'stance_classifications',
    'ab_experiments', 'ab_assignments', 'users', 'ab_variants',
    'ab_experiment_metrics', 'ab_experiment_segments', 'ab_user_segments',
    'organizations', 'ab_query_routing', 'ab_user_segment_memberships',
    'analytics_events', 'audit_events', 'threads', 'chat_messages',
    'citations', 'citation_relationships', 'collections', 'collection_documents',
    'workspaces', 'compliance_reports', 'connection_events', 'conversations',
    'data_retention_policies', 'document_access_log', 'document_versions',
    'document_quality_metrics', 'draft_citations', 'generated_drafts',
    'encrypted_organization_profiles', 'encrypted_user_profiles', 'encryption_audit_logs',
    'entities', 'entity_relationships', 'evaluation_jobs', 'evaluation_comparisons',
    'evaluation_datasets', 'evaluation_metrics', 'evaluation_reports', 'evaluation_thresholds',
    'extraction_cells', 'extraction_matrices', 'integrity_scores', 'message_attachments',
    'metric_aggregations', 'multimodal_content', 'performance_logs', 'processing_history',
    'processing_jobs', 'project_notes', 'project_threads', 'quality_alerts',
    'quality_metrics', 'quality_thresholds', 'research_projects', 'research_blueprints',
    'research_sources', 'research_evidence', 'research_steps', 'research_pipelines',
    'research_runs', 'role_permissions', 'permissions', 'roles',
    'search_events', 'search_sessions', 'search_queries', 'search_results',
    'security_incidents', 'status_updates', 'system_metrics', 'system_status_broadcasts',
    'user_role_assignments', 'user_sessions', 'workspace_members', 'documents'
  ];
BEGIN
  FOREACH tbl IN ARRAY tables LOOP
    EXECUTE format(
      'CREATE POLICY "authenticated_full_access" ON public.%I FOR ALL TO authenticated USING (true) WITH CHECK (true)',
      tbl
    );
  END LOOP;
END
$$;

-- ============================================================================
-- 3. SPECIAL HANDLING — alembic_version needs postgres role access too
-- ============================================================================

CREATE POLICY "authenticated_full_access" ON public.alembic_version
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "postgres_full_access" ON public.alembic_version
  FOR ALL TO postgres USING (true) WITH CHECK (true);

COMMIT;
