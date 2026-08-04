-- Secure backend-only agent runtime and project-skill tables that were added
-- after the blanket public-schema RLS migrations.
--
-- The frontend uses Supabase for Auth only. These tables are accessed by the
-- backend over its direct postgres connection (or by service_role), so neither
-- anon nor authenticated needs PostgREST table privileges or an RLS policy.

BEGIN;

DO $$
DECLARE
  tbl text;
  tables text[] := ARRAY[
    'agent_outbox',
    'agent_run_events',
    'agent_runs',
    'agent_runtime_snapshots',
    'project_skill_change_requests',
    'project_skill_version_scans',
    'project_skill_versions',
    'project_skills'
  ];
BEGIN
  FOREACH tbl IN ARRAY tables LOOP
    -- Supabase migrations and Alembic coexist in this repository. Keep this
    -- migration safe on a fresh Supabase-only reset where the Alembic-managed
    -- table may not have been created yet; the paired Alembic revision applies
    -- the same boundary after those tables exist.
    IF to_regclass(format('public.%I', tbl)) IS NOT NULL THEN
      EXECUTE format(
        'ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',
        tbl
      );
      EXECUTE format(
        'REVOKE ALL ON TABLE public.%I FROM anon, authenticated',
        tbl
      );
    END IF;
  END LOOP;
END
$$;

COMMIT;
