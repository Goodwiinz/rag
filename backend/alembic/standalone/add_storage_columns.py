#!/usr/bin/env python3
"""
Database migration: Add Supabase Storage columns to documents table.

Adds:
  - storage_path (VARCHAR 2000, nullable) — Supabase Storage key
  - storage_backend (VARCHAR 20, NOT NULL, default 'local') — 'local' or 'supabase'

Existing rows default to storage_backend='local', storage_path=NULL.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.core.database import engine


def run_migration():
    """Run the storage columns migration."""
    print("Starting storage columns migration...")

    try:
        with engine.connect() as conn:
            trans = conn.begin()

            try:
                # Add storage_path column
                print("Adding storage_path column...")
                conn.execute(
                    text("""
                    ALTER TABLE documents
                    ADD COLUMN IF NOT EXISTS storage_path VARCHAR(2000) DEFAULT NULL
                """)
                )

                # Add storage_backend column with default 'local'
                print("Adding storage_backend column...")
                conn.execute(
                    text("""
                    ALTER TABLE documents
                    ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(20) NOT NULL DEFAULT 'local'
                """)
                )

                # Add index on storage_backend for efficient filtering
                print("Adding index on storage_backend...")
                conn.execute(
                    text("""
                    CREATE INDEX IF NOT EXISTS idx_document_storage_backend
                    ON documents (storage_backend)
                """)
                )

                trans.commit()
                print("Storage columns migration completed successfully.")

            except Exception as e:
                trans.rollback()
                print(f"Migration failed, rolled back: {e}")
                raise

    except Exception as e:
        print(f"Migration error: {e}")
        sys.exit(1)


def rollback_migration():
    """Rollback the storage columns migration."""
    print("Rolling back storage columns migration...")

    try:
        with engine.connect() as conn:
            trans = conn.begin()

            try:
                conn.execute(
                    text("DROP INDEX IF EXISTS idx_document_storage_backend")
                )
                conn.execute(
                    text("ALTER TABLE documents DROP COLUMN IF EXISTS storage_backend")
                )
                conn.execute(
                    text("ALTER TABLE documents DROP COLUMN IF EXISTS storage_path")
                )

                trans.commit()
                print("Rollback completed successfully.")

            except Exception as e:
                trans.rollback()
                print(f"Rollback failed: {e}")
                raise

    except Exception as e:
        print(f"Rollback error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Storage columns migration")
    parser.add_argument(
        "--rollback", action="store_true", help="Rollback the migration"
    )
    args = parser.parse_args()

    if args.rollback:
        rollback_migration()
    else:
        run_migration()
