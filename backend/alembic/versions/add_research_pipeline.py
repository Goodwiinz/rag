"""
Add research_pipelines table for step-by-step research wizard workflow.
"""

import logging
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from src.core.database import engine

logger = logging.getLogger(__name__)


def run_migration():
    """Run the research pipeline migration."""
    logger.info("Starting research pipeline migration...")

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            logger.info("Creating research_pipelines table...")
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS research_pipelines (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    project_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
                    current_step INTEGER NOT NULL DEFAULT 0,
                    completed_steps INTEGER[] NOT NULL DEFAULT '{}',
                    skipped_steps INTEGER[] NOT NULL DEFAULT '{}',
                    step_data JSONB NOT NULL DEFAULT '{}',
                    invalidated_steps INTEGER[] NOT NULL DEFAULT '{}',
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    deleted_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                    UNIQUE(project_id)
                )
            """)
            )

            conn.execute(
                text("""
                CREATE INDEX IF NOT EXISTS ix_research_pipelines_project_id
                ON research_pipelines(project_id)
            """)
            )

            trans.commit()
            logger.info("Research pipeline migration completed successfully.")
        except Exception as e:
            trans.rollback()
            logger.error("Migration failed: %s", e)
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migration()
