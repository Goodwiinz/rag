"""secure backend-only agent runtime and project-skill tables

The affected tables were added after the Supabase blanket RLS migrations.
New public-schema tables can inherit PostgREST privileges for ``anon`` and
``authenticated`` unless that access is explicitly removed.

These are internal backend tables. The application accesses them over the
direct postgres connection (or with ``service_role``), never from the browser.
Enable RLS without client policies and revoke the two PostgREST roles, matching
the existing ``20260620120000_secure_agent_infra_tables_rls.sql`` boundary.

Revision ID: h8i9j0k1l2m3
Revises: e6f7a8b9c0d1
Create Date: 2026-08-03
"""

from alembic import op  # type: ignore[attr-defined]

revision = "h8i9j0k1l2m3"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None

_TABLES = (
    "agent_outbox",
    "agent_run_events",
    "agent_runs",
    "agent_runtime_snapshots",
    "project_skill_change_requests",
    "project_skill_version_scans",
    "project_skill_versions",
    "project_skills",
)

_POSTGREST_ROLES = ("anon", "authenticated")


def upgrade() -> None:
    for table in _TABLES:
        # Every table is created earlier in this revision chain. Fail loudly on
        # unexpected schema drift instead of recording a successful security
        # migration while leaving a missing/recreated table unprotected.
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        for role in _POSTGREST_ROLES:
            # Local/CI PostgreSQL does not define Supabase's PostgREST roles.
            # Use dynamic SQL so the REVOKE is only parsed when the role exists.
            op.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                        EXECUTE 'REVOKE ALL ON TABLE public."{table}" FROM {role}';
                    END IF;
                END
                $$
                """)


def downgrade() -> None:
    # Intentionally preserve the security boundary on downgrade. Regranting
    # PostgREST access or disabling RLS would recreate the data exposure.
    pass
