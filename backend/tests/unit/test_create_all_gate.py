"""Truth table for the startup create_all gate (should_run_create_all).

create_all may only bootstrap a genuinely local dev database. Managed DBs are
owned by the Alembic init container — create_all against them races migrations
and permanently drifts the schema (the project_threads uq_project_thread
incident). The gate requires ENVIRONMENT=="development" AND no SUPABASE_DB_URL
AND (local host OR sqlite OR explicit RUN_CREATE_ALL force). The host condition
closes the residual gap where ENVIRONMENT defaults to "development" and a
managed non-Supabase DATABASE_URL is configured.
"""

import pytest

pytestmark = pytest.mark.unit

from src.core.database import LOCAL_DB_HOSTS, should_run_create_all


@pytest.mark.parametrize("host", sorted(LOCAL_DB_HOSTS))
def test_local_hosts_allowed_in_development(host):
    assert should_run_create_all("development", "", host, False, False) is True


def test_sqlite_allowed_without_host():
    assert should_run_create_all("development", "", None, True, False) is True


@pytest.mark.parametrize(
    "host",
    [
        "db.nyglefacyosdqoxcrxle.supabase.co",
        "rag-do-pg.b.db.ondigitalocean.com",
        "prod.cluster-abc.us-east-1.rds.amazonaws.com",
        None,
    ],
)
def test_managed_or_unknown_host_refused_even_in_development(host):
    # THE M1 gap: ENVIRONMENT unset -> "development", no SUPABASE_DB_URL, but a
    # managed DATABASE_URL. Must NOT run create_all.
    assert should_run_create_all("development", "", host, False, False) is False


def test_supabase_db_url_always_refuses():
    assert (
        should_run_create_all(
            "development", "postgresql://supabase", "localhost", False, False
        )
        is False
    )


@pytest.mark.parametrize("env", ["dev", "staging", "production", "testing", ""])
def test_non_development_environment_always_refuses(env):
    assert should_run_create_all(env, "", "localhost", False, True) is False


def test_force_overrides_host_check_but_not_environment_or_supabase():
    # force lets an unusual-but-local setup (custom container hostname) opt in
    assert should_run_create_all("development", "", "my-pg-box", False, True) is True
    # but never against a Supabase-configured pod, and never outside development
    assert (
        should_run_create_all("development", "postgresql://x", "my-pg-box", False, True)
        is False
    )
    assert should_run_create_all("production", "", "my-pg-box", False, True) is False
