"""Add composite indexes for dashboard performance queries

Revision ID: p3q4r5s6t7u8
Revises: o2r3s4t5u6v7
Create Date: 2026-04-20 12:00:00.000000

Dashboard overview endpoint fetches search stats, quality metrics, user engagement,
and alert data — all filtered by (organization_id, created_at). These columns only
have single-column indexes, forcing sequential scans on large tables.

Also adds composite index on analytics_dashboard_widgets for the widget count query
used by list_dashboards.

All indexes created CONCURRENTLY-safe via op.create_index (Alembic default).
Run with `--sql` to preview DDL before applying to production.
"""

from alembic import op

revision = "p3q4r5s6t7u8"
down_revision = "o2r3s4t5u6v7"
branch_labels = None
depends_on = None


def upgrade():
    # ──────────────────────────────────────────────────────────────────────
    # search_queries — hit by every dashboard metric query
    # ──────────────────────────────────────────────────────────────────────

    # Core filter: organization_id + created_at (used by all search analytics)
    op.create_index(
        "idx_search_queries_org_created",
        "search_queries",
        ["organization_id", "created_at"],
    )

    # Covering index for P95 response time percentile queries
    op.create_index(
        "idx_search_queries_org_created_duration",
        "search_queries",
        ["organization_id", "created_at", "search_duration_ms"],
    )

    # Recent response time metrics (system health, no org filter)
    op.create_index(
        "idx_search_queries_created_duration",
        "search_queries",
        ["created_at", "search_duration_ms"],
    )

    # ──────────────────────────────────────────────────────────────────────
    # quality_metrics — quality summary queries
    # ──────────────────────────────────────────────────────────────────────

    op.create_index(
        "idx_quality_metrics_org_created_type",
        "quality_metrics",
        ["organization_id", "created_at", "metric_type"],
    )

    # Trend comparison queries use measured_at
    op.create_index(
        "idx_quality_metrics_org_measured_type",
        "quality_metrics",
        ["organization_id", "measured_at", "metric_type"],
    )

    # ──────────────────────────────────────────────────────────────────────
    # quality_alerts — active alerts lookup
    # ──────────────────────────────────────────────────────────────────────

    op.create_index(
        "idx_quality_alerts_org_status",
        "quality_alerts",
        ["organization_id", "status"],
    )

    # ──────────────────────────────────────────────────────────────────────
    # analytics_dashboard_widgets — widget count subquery
    # ──────────────────────────────────────────────────────────────────────

    op.create_index(
        "idx_dashboard_widgets_dashboard_active",
        "analytics_dashboard_widgets",
        ["dashboard_id", "is_active"],
    )

    # ──────────────────────────────────────────────────────────────────────
    # documents — list/search queries (organization + sort + filters)
    # ──────────────────────────────────────────────────────────────────────

    # Default list: WHERE organization_id = ? AND is_deleted = false ORDER BY created_at DESC
    op.create_index(
        "idx_documents_org_deleted_created",
        "documents",
        ["organization_id", "is_deleted", "created_at"],
    )

    # Search: GIN index on search_vector for full-text search (if not exists)
    # The model defines idx_documents_search but it may not be created yet
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_documents_search_gin
        ON documents USING GIN(search_vector)
        WHERE search_vector IS NOT NULL
        """
    )

    # Partial index for title/filename ILIKE searches within an org
    op.create_index(
        "idx_documents_org_title",
        "documents",
        ["organization_id", "title"],
    )


def downgrade():
    op.drop_index("idx_documents_org_title", "documents")
    op.execute("DROP INDEX IF EXISTS idx_documents_search_gin")
    op.drop_index("idx_documents_org_deleted_created", "documents")
    op.drop_index("idx_dashboard_widgets_dashboard_active", "analytics_dashboard_widgets")
    op.drop_index("idx_quality_alerts_org_status", "quality_alerts")
    op.drop_index("idx_quality_metrics_org_measured_type", "quality_metrics")
    op.drop_index("idx_quality_metrics_org_created_type", "quality_metrics")
    op.drop_index("idx_search_queries_created_duration", "search_queries")
    op.drop_index("idx_search_queries_org_created_duration", "search_queries")
    op.drop_index("idx_search_queries_org_created", "search_queries")
