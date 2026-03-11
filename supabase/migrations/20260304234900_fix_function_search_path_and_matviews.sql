-- Migration: Fix function search_path and materialized view API exposure
-- Date: 2026-03-04
-- Purpose: Fix Supabase linter warnings for function_search_path_mutable
--          and materialized_view_in_api
-- 
-- Addresses:
--   - 5 functions with mutable search_path (WARN: function_search_path_mutable)
--   - 2 materialized views accessible via API (WARN: materialized_view_in_api)

BEGIN;

-- ============================================================================
-- 1. SET search_path ON ALL FLAGGED FUNCTIONS
--    Prevents search_path manipulation attacks by pinning to 'public'
-- ============================================================================

ALTER FUNCTION public.get_user_websocket_connections(uuid)
  SET search_path = public;

ALTER FUNCTION public.refresh_realtime_views()
  SET search_path = public;

ALTER FUNCTION public.update_document_realtime_status(uuid, character varying, numeric, character varying, character varying, text, boolean)
  SET search_path = public;

ALTER FUNCTION public.update_last_status_update()
  SET search_path = public;

ALTER FUNCTION public.update_updated_at_column()
  SET search_path = public;

-- ============================================================================
-- 2. REVOKE API ACCESS ON MATERIALIZED VIEWS
--    These should only be accessed via service_role (backend), not directly
--    via the PostgREST API by anon/authenticated users
-- ============================================================================

REVOKE SELECT ON public.realtime_document_dashboard FROM anon, authenticated;
REVOKE SELECT ON public.realtime_system_status FROM anon, authenticated;

COMMIT;
