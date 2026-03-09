-- Migration: Add covering indexes for unindexed foreign keys + drop duplicate indexes
-- Date: 2026-03-05
-- Purpose: Fix Supabase linter warnings for unindexed_foreign_keys and duplicate_index

BEGIN;

-- ============================================================================
-- 1. DROP duplicate indexes (keep idx_* versions, drop ix_* duplicates)
-- ============================================================================
DROP INDEX IF EXISTS public.ix_analytics_events_batch_id;
DROP INDEX IF EXISTS public.ix_analytics_events_date_day;
DROP INDEX IF EXISTS public.ix_analytics_events_date_hour;
DROP INDEX IF EXISTS public.ix_analytics_events_processed;
DROP INDEX IF EXISTS public.ix_performance_logs_date_day;
DROP INDEX IF EXISTS public.ix_performance_logs_date_hour;

-- ============================================================================
-- 2. CREATE covering indexes for all unindexed foreign keys
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_fk_ab_experiments_winning_variant_id ON public.ab_experiments (winning_variant_id);
CREATE INDEX IF NOT EXISTS idx_fk_ab_user_segments_created_by ON public.ab_user_segments (created_by);
CREATE INDEX IF NOT EXISTS idx_fk_chat_messages_user_id ON public.chat_messages (user_id);
CREATE INDEX IF NOT EXISTS idx_fk_compliance_reports_generated_by ON public.compliance_reports (generated_by);
CREATE INDEX IF NOT EXISTS idx_fk_connection_events_connection_id ON public.connection_events (connection_id);
CREATE INDEX IF NOT EXISTS idx_fk_conversations_created_by_id ON public.conversations (created_by_id);
CREATE INDEX IF NOT EXISTS idx_fk_document_access_log_document_version_id ON public.document_access_log (document_version_id);
CREATE INDEX IF NOT EXISTS idx_fk_document_access_log_organization_id ON public.document_access_log (organization_id);
CREATE INDEX IF NOT EXISTS idx_fk_document_access_log_user_id ON public.document_access_log (user_id);
CREATE INDEX IF NOT EXISTS idx_fk_document_quality_metrics_assessed_by_user_id ON public.document_quality_metrics (assessed_by_user_id);
CREATE INDEX IF NOT EXISTS idx_fk_document_quality_metrics_organization_id ON public.document_quality_metrics (organization_id);
CREATE INDEX IF NOT EXISTS idx_fk_document_versions_created_by_user_id ON public.document_versions (created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_fk_document_versions_organization_id ON public.document_versions (organization_id);
CREATE INDEX IF NOT EXISTS idx_fk_document_versions_parent_version_id ON public.document_versions (parent_version_id);
CREATE INDEX IF NOT EXISTS idx_fk_documents_organization_id ON public.documents (organization_id);
CREATE INDEX IF NOT EXISTS idx_fk_documents_uploaded_by_user_id ON public.documents (uploaded_by_user_id);
CREATE INDEX IF NOT EXISTS idx_fk_draft_citations_citation_id ON public.draft_citations (citation_id);
CREATE INDEX IF NOT EXISTS idx_fk_encryption_audit_logs_organization_id ON public.encryption_audit_logs (organization_id);
CREATE INDEX IF NOT EXISTS idx_fk_encryption_audit_logs_performed_by ON public.encryption_audit_logs (performed_by);
CREATE INDEX IF NOT EXISTS idx_fk_entities_document_id ON public.entities (document_id);
CREATE INDEX IF NOT EXISTS idx_fk_entities_organization_id ON public.entities (organization_id);
CREATE INDEX IF NOT EXISTS idx_fk_entity_relationships_target_entity_id ON public.entity_relationships (target_entity_id);
CREATE INDEX IF NOT EXISTS idx_fk_evaluation_comparisons_baseline_job_id ON public.evaluation_comparisons (baseline_job_id);
CREATE INDEX IF NOT EXISTS idx_fk_evaluation_comparisons_comparison_job_id ON public.evaluation_comparisons (comparison_job_id);
CREATE INDEX IF NOT EXISTS idx_fk_multimodal_content_document_version_id ON public.multimodal_content (document_version_id);
CREATE INDEX IF NOT EXISTS idx_fk_multimodal_content_organization_id ON public.multimodal_content (organization_id);
CREATE INDEX IF NOT EXISTS idx_fk_processing_history_organization_id ON public.processing_history (organization_id);
CREATE INDEX IF NOT EXISTS idx_fk_processing_jobs_created_by_user_id ON public.processing_jobs (created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_fk_processing_jobs_document_id ON public.processing_jobs (document_id);
CREATE INDEX IF NOT EXISTS idx_fk_project_threads_linked_by_id ON public.project_threads (linked_by_id);
CREATE INDEX IF NOT EXISTS idx_fk_quality_alerts_acknowledged_by ON public.quality_alerts (acknowledged_by);
CREATE INDEX IF NOT EXISTS idx_fk_quality_alerts_metric_id ON public.quality_alerts (metric_id);
CREATE INDEX IF NOT EXISTS idx_fk_quality_alerts_resolved_by ON public.quality_alerts (resolved_by);
CREATE INDEX IF NOT EXISTS idx_fk_quality_metrics_created_by_user_id ON public.quality_metrics (created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_fk_quality_metrics_organization_id ON public.quality_metrics (organization_id);
CREATE INDEX IF NOT EXISTS idx_fk_quality_thresholds_created_by ON public.quality_thresholds (created_by);
CREATE INDEX IF NOT EXISTS idx_fk_research_blueprints_project_id ON public.research_blueprints (project_id);
CREATE INDEX IF NOT EXISTS idx_fk_research_evidence_source_id ON public.research_evidence (source_id);
CREATE INDEX IF NOT EXISTS idx_fk_research_evidence_step_id ON public.research_evidence (step_id);
CREATE INDEX IF NOT EXISTS idx_fk_research_projects_owner_id ON public.research_projects (owner_id);
CREATE INDEX IF NOT EXISTS idx_fk_research_runs_blueprint_id ON public.research_runs (blueprint_id);
CREATE INDEX IF NOT EXISTS idx_fk_research_sources_run_id ON public.research_sources (run_id);
CREATE INDEX IF NOT EXISTS idx_fk_research_steps_run_id ON public.research_steps (run_id);
CREATE INDEX IF NOT EXISTS idx_fk_role_permissions_granted_by ON public.role_permissions (granted_by);
CREATE INDEX IF NOT EXISTS idx_fk_role_permissions_permission_id ON public.role_permissions (permission_id);
CREATE INDEX IF NOT EXISTS idx_fk_search_queries_organization_id ON public.search_queries (organization_id);
CREATE INDEX IF NOT EXISTS idx_fk_search_queries_user_id ON public.search_queries (user_id);
CREATE INDEX IF NOT EXISTS idx_fk_search_results_document_id ON public.search_results (document_id);
CREATE INDEX IF NOT EXISTS idx_fk_search_results_search_query_id ON public.search_results (search_query_id);
CREATE INDEX IF NOT EXISTS idx_fk_search_sessions_user_id ON public.search_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_fk_security_incidents_assigned_to ON public.security_incidents (assigned_to);
CREATE INDEX IF NOT EXISTS idx_fk_system_status_broadcasts_created_by ON public.system_status_broadcasts (created_by);
CREATE INDEX IF NOT EXISTS idx_fk_threads_created_by_id ON public.threads (created_by_id);
CREATE INDEX IF NOT EXISTS idx_fk_user_role_assignments_assigned_by ON public.user_role_assignments (assigned_by);
CREATE INDEX IF NOT EXISTS idx_fk_users_organization_id ON public.users (organization_id);
CREATE INDEX IF NOT EXISTS idx_fk_workspace_members_invited_by_id ON public.workspace_members (invited_by_id);

-- ============================================================================
-- 3. ADD recommended index from query advisor
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_processing_jobs_organization_id ON public.processing_jobs (organization_id);

COMMIT;
