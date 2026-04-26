#!/usr/bin/env python3
"""
Migration script: Upload existing local files to Supabase Storage.

Queries documents where storage_backend='local' and is_deleted=False, uploads
each file to the appropriate Supabase Storage bucket, and updates the document
record with storage_path/storage_backend.

Usage:
    python migrations/migrate_files_to_storage.py                    # dry run
    python migrations/migrate_files_to_storage.py --execute          # real migration
    python migrations/migrate_files_to_storage.py --execute --verify # verify hashes
    python migrations/migrate_files_to_storage.py --execute --verify --cleanup-local  # remove local

Options:
    --dry-run         Show what would be migrated (default)
    --execute         Actually perform the migration
    --batch-size N    Process N documents per batch (default 50)
    --verify          After upload, download and compare SHA-256 hashes
    --cleanup-local   After verification, remove local files
"""

import argparse
import hashlib
import mimetypes
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.core.database import engine
from src.core.supabase_client import StorageHelper


# Map document_type enum values to bucket names
TYPE_TO_BUCKET = {
    "text": "documents",
    "pdf": "documents",
    "spreadsheet": "documents",
    "presentation": "documents",
    "image": "images",
    "audio": "audio",
    "video": "video",
    "multimodal": "documents",
}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def migrate(
    execute: bool = False,
    batch_size: int = 50,
    verify: bool = False,
    cleanup_local: bool = False,
):
    helper = None
    if execute:
        helper = StorageHelper()

    with engine.connect() as conn:
        # Fetch documents to migrate
        result = conn.execute(
            text("""
                SELECT id, file_path, document_type, organization_id, filename
                FROM documents
                WHERE storage_backend = 'local'
                  AND is_deleted = FALSE
                  AND file_path IS NOT NULL
                ORDER BY created_at
            """)
        )
        rows = result.fetchall()

    total = len(rows)
    print(f"Found {total} documents with storage_backend='local'.")

    if total == 0:
        print("Nothing to migrate.")
        return

    migrated = 0
    skipped = 0
    failed = 0

    for i in range(0, total, batch_size):
        batch = rows[i : i + batch_size]
        print(f"\nBatch {i // batch_size + 1} ({len(batch)} documents)...")

        for row in batch:
            doc_id = str(row[0])
            file_path = row[1]
            doc_type = row[2]
            org_id = str(row[3])
            filename = row[4]

            # Skip if file doesn't exist locally
            if not file_path or not os.path.exists(file_path):
                print(f"  SKIP {doc_id}: file not found at {file_path}")
                skipped += 1
                continue

            bucket = TYPE_TO_BUCKET.get(doc_type, "documents")
            ext = os.path.splitext(filename)[1] if filename else ""
            storage_key = f"{org_id}/{doc_id}/{int(time.time())}_{os.urandom(4).hex()}{ext}"
            full_key = f"{bucket}/{storage_key}"

            if not execute:
                print(f"  DRY-RUN {doc_id}: {file_path} -> {full_key}")
                migrated += 1
                continue

            try:
                # Read file
                with open(file_path, "rb") as f:
                    file_data = f.read()

                local_hash = sha256_bytes(file_data)

                # Determine content type
                content_type = mimetypes.guess_type(filename or file_path)[0] or "application/octet-stream"

                # Upload to Supabase Storage
                helper.upload_file(bucket, storage_key, file_data, content_type)

                # Verify if requested
                if verify:
                    downloaded = helper.download_file(bucket, storage_key)
                    remote_hash = sha256_bytes(downloaded)
                    if local_hash != remote_hash:
                        print(f"  FAIL {doc_id}: hash mismatch! local={local_hash} remote={remote_hash}")
                        failed += 1
                        continue
                    print(f"  VERIFIED {doc_id}: hashes match ({local_hash[:12]}...)")

                # Update database record
                with engine.connect() as conn:
                    trans = conn.begin()
                    conn.execute(
                        text("""
                            UPDATE documents
                            SET storage_path = :storage_path,
                                storage_backend = 'supabase',
                                file_path = :new_file_path
                            WHERE id = :doc_id
                        """),
                        {
                            "storage_path": full_key,
                            "new_file_path": f"supabase://{full_key}",
                            "doc_id": doc_id,
                        },
                    )
                    trans.commit()

                # Cleanup local file if requested and verified
                if cleanup_local and verify:
                    os.remove(file_path)
                    print(f"  CLEANED {doc_id}: removed {file_path}")

                migrated += 1
                print(f"  OK {doc_id}: -> {full_key}")

            except Exception as e:
                print(f"  ERROR {doc_id}: {e}")
                failed += 1

    print(f"\n--- Migration Summary ---")
    print(f"Total:    {total}")
    print(f"Migrated: {migrated}")
    print(f"Skipped:  {skipped}")
    print(f"Failed:   {failed}")

    if not execute:
        print("\nThis was a DRY RUN. Use --execute to perform the actual migration.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate local files to Supabase Storage")
    parser.add_argument("--execute", action="store_true", help="Actually perform migration")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size (default 50)")
    parser.add_argument("--verify", action="store_true", help="Verify SHA-256 after upload")
    parser.add_argument("--cleanup-local", action="store_true", help="Remove local files after verified upload")
    args = parser.parse_args()

    if args.cleanup_local and not args.verify:
        print("ERROR: --cleanup-local requires --verify for safety.")
        sys.exit(1)

    migrate(
        execute=args.execute,
        batch_size=args.batch_size,
        verify=args.verify,
        cleanup_local=args.cleanup_local,
    )
