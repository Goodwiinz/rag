#!/usr/bin/env python3
"""
Supabase Storage setup: Create buckets and apply RLS policies.

Creates private buckets for each document type and applies row-level security
policies so that:
  - Service role has full access (used by backend).
  - Authenticated users can read files within their organization prefix.
  - Authenticated users can insert files within their organization prefix.

Usage:
    python migrations/setup_supabase_storage.py
    python migrations/setup_supabase_storage.py --rollback
"""

import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog
from src.core.config import settings
from src.core.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)

BUCKETS = ["documents", "images", "audio", "video", "processed"]


def create_buckets():
    """Create private storage buckets."""
    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured. Check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        sys.exit(1)

    existing = {b.name for b in client.storage.list_buckets()}

    for bucket_name in BUCKETS:
        if bucket_name in existing:
            print(f"  Bucket '{bucket_name}' already exists, skipping.")
            continue

        print(f"  Creating bucket '{bucket_name}'...")
        client.storage.create_bucket(
            bucket_name,
            options={
                "public": False,
                "file_size_limit": 500 * 1024 * 1024,  # 500 MB
            },
        )
        print(f"  Bucket '{bucket_name}' created.")


def apply_rls_policies():
    """Apply RLS policies to storage buckets via Supabase Management API.

    RLS policies reference the 'authenticated' role which only exists within
    Supabase's internal PostgreSQL context (not accessible via the app's
    direct DB connection). We execute the SQL through Supabase's REST SQL
    endpoint which runs as the supabase_admin role.
    """
    import requests

    supabase_url = settings.SUPABASE_URL.rstrip("/")
    service_key = settings.SUPABASE_SERVICE_ROLE_KEY
    sql_url = f"{supabase_url}/rest/v1/rpc/exec_sql"

    # Use the Supabase DB URL directly via psycopg2 to the management port
    # For local Supabase, the 'authenticated' role exists on the Supabase-managed
    # PostgreSQL instance at port 54322 but must be accessed with supabase_admin.
    # For local Supabase, connect as supabase_admin to port 54322
    # which has the 'authenticated' role available
    admin_db_url = os.environ.get(
        "SUPABASE_ADMIN_DB_URL",
        "postgresql://supabase_admin:postgres@127.0.0.1:54322/postgres",
    )

    from sqlalchemy import create_engine, text

    print("Applying RLS policies via supabase_admin connection...")

    admin_engine = create_engine(admin_db_url)
    with admin_engine.connect() as conn:
        trans = conn.begin()
        try:
            for bucket_name in BUCKETS:
                select_policy = f"storage_select_{bucket_name}"
                conn.execute(text(f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_policies
                            WHERE policyname = '{select_policy}'
                            AND tablename = 'objects'
                            AND schemaname = 'storage'
                        ) THEN
                            CREATE POLICY "{select_policy}"
                            ON storage.objects
                            FOR SELECT
                            TO authenticated
                            USING (
                                bucket_id = '{bucket_name}'
                                AND (storage.foldername(name))[1] = (
                                    SELECT CAST(raw_user_meta_data->>'organization_id' AS TEXT)
                                    FROM auth.users
                                    WHERE id = auth.uid()
                                )
                            );
                        END IF;
                    END $$;
                """))

                insert_policy = f"storage_insert_{bucket_name}"
                conn.execute(text(f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_policies
                            WHERE policyname = '{insert_policy}'
                            AND tablename = 'objects'
                            AND schemaname = 'storage'
                        ) THEN
                            CREATE POLICY "{insert_policy}"
                            ON storage.objects
                            FOR INSERT
                            TO authenticated
                            WITH CHECK (
                                bucket_id = '{bucket_name}'
                                AND (storage.foldername(name))[1] = (
                                    SELECT CAST(raw_user_meta_data->>'organization_id' AS TEXT)
                                    FROM auth.users
                                    WHERE id = auth.uid()
                                )
                            );
                        END IF;
                    END $$;
                """))

                print(f"  RLS policies for '{bucket_name}' applied.")

            trans.commit()
            print("RLS policies applied successfully.")

        except Exception as e:
            trans.rollback()
            print(f"Failed to apply RLS policies via admin: {e}")
            print("\nYou can apply them manually via Supabase Studio SQL Editor:")
            _print_rls_sql()
            raise
    admin_engine.dispose()


def _print_rls_sql():
    """Print the RLS SQL statements for manual execution."""
    print("\n-- Copy and paste into Supabase Studio SQL Editor:\n")
    for bucket_name in BUCKETS:
        print(f"""
CREATE POLICY "storage_select_{bucket_name}"
ON storage.objects FOR SELECT TO authenticated
USING (
    bucket_id = '{bucket_name}'
    AND (storage.foldername(name))[1] = (
        SELECT CAST(raw_user_meta_data->>'organization_id' AS TEXT)
        FROM auth.users WHERE id = auth.uid()
    )
);

CREATE POLICY "storage_insert_{bucket_name}"
ON storage.objects FOR INSERT TO authenticated
WITH CHECK (
    bucket_id = '{bucket_name}'
    AND (storage.foldername(name))[1] = (
        SELECT CAST(raw_user_meta_data->>'organization_id' AS TEXT)
        FROM auth.users WHERE id = auth.uid()
    )
);
""")


def rollback():
    """Remove buckets and RLS policies."""
    from sqlalchemy import text
    from src.core.database import engine

    client = get_supabase_client()
    if not client:
        print("ERROR: Supabase client not configured.")
        sys.exit(1)

    # Drop RLS policies
    print("Dropping RLS policies...")
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            for bucket_name in BUCKETS:
                for action in ["select", "insert"]:
                    policy_name = f"storage_{action}_{bucket_name}"
                    conn.execute(text(f"""
                        DROP POLICY IF EXISTS "{policy_name}" ON storage.objects;
                    """))
            trans.commit()
            print("RLS policies dropped.")
        except Exception as e:
            trans.rollback()
            print(f"Failed to drop RLS policies: {e}")

    # Delete buckets (must be empty)
    print("Deleting buckets...")
    for bucket_name in BUCKETS:
        try:
            client.storage.delete_bucket(bucket_name)
            print(f"  Bucket '{bucket_name}' deleted.")
        except Exception as e:
            print(f"  Could not delete bucket '{bucket_name}': {e}")


def run_migration():
    """Run the full storage setup."""
    print("Setting up Supabase Storage...")
    create_buckets()
    apply_rls_policies()
    print("Supabase Storage setup complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Supabase Storage setup")
    parser.add_argument(
        "--rollback", action="store_true", help="Remove buckets and RLS policies"
    )
    args = parser.parse_args()

    if args.rollback:
        rollback()
    else:
        run_migration()
