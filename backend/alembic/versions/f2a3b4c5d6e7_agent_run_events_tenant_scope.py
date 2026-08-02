"""agent_run_events: tenant scope + one-terminal-event invariant

P0-B (run-event ledger). Expand-only — no drops, no data rewrites, safe to
run against a live database:

- ``organization_id`` (nullable uuid) so ledger reads can be tenant-scoped
  like every other user-facing query. Deliberately NOT backfilled: the table
  has no producers yet (``run_event_store`` is the first one, this PR), so
  every existing row is either absent or org-less by construction.
- ``idx_agent_run_events_org_run`` for the tenant-scoped replay read.
- ``uq_agent_run_events_one_terminal``: a partial unique index making "one
  terminal event per run, ever" a database invariant rather than a service
  convention. Creation cannot fail on live data — the table has no writers
  yet, so no run can already carry two terminal events.

``organization_id`` is intentionally NOT part of ``uq_agent_run_events_run_seq``:
NULLs are distinct in a PostgreSQL unique constraint, so an org in the key
would let org-less rows repeat a ``seq`` for the same run — exactly the
ordering guarantee the ledger exists to provide. It is also intentionally NOT
a foreign key, mirroring the sibling ``agent_runs.organization_id`` /
``agent_hitl_audit.organization_id`` columns.

No ``chat_messages`` column is added here (decision D2); the message ↔ run
correlation already lives on ``agent_runs``.

Revision ID: f2a3b4c5d6e7
Revises: d5e6f7a8b9c0
Create Date: 2026-08-02
"""

from alembic import op  # type: ignore[attr-defined]

revision = "f2a3b4c5d6e7"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None

# Kept byte-identical to ``_TERMINAL_EVENT_PREDICATE`` in
# src/models/agent_run_event.py (a test asserts both match the
# TERMINAL_RUN_EVENTS vocabulary).
_TERMINAL_PREDICATE = "event_type IN ('run.completed', 'run.failed', 'run.cancelled')"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agent_run_events ADD COLUMN IF NOT EXISTS organization_id uuid"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_run_events_org_run "
        "ON agent_run_events (organization_id, run_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_run_events_one_terminal "
        f"ON agent_run_events (run_id) WHERE {_TERMINAL_PREDICATE}"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_agent_run_events_one_terminal")
    op.execute("DROP INDEX IF EXISTS idx_agent_run_events_org_run")
    op.execute("ALTER TABLE agent_run_events DROP COLUMN IF EXISTS organization_id")
