#!/usr/bin/env python3
"""
Database migration script to add full-text search support
"""

import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.core.database import engine
from src.core.config import settings

def run_migration():
    """Run the full-text search migration"""
    print("🚀 Starting full-text search migration...")

    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()

            try:
                print("Adding search_vector column to documents table...")
                # Add search_vector column
                conn.execute(text("""
                    ALTER TABLE documents
                    ADD COLUMN IF NOT EXISTS search_vector TSVECTOR
                """))

                print("Creating GIN index for full-text search...")
                # Create GIN index for search_vector
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_documents_search_vector
                    ON documents USING GIN (search_vector)
                """))

                print("Creating additional search indexes...")
                # Create additional indexes for better search performance
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_documents_title_gin
                    ON documents USING GIN (to_tsvector('english', title))
                """))

                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_documents_content_gin
                    ON documents USING GIN (to_tsvector('english', coalesce(content_text, '')))
                """))

                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_documents_created_at
                    ON documents (created_at DESC)
                """))

                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_documents_type_status
                    ON documents (document_type, processing_status)
                """))

                print("Updating search vectors for existing documents...")
                # Update search vectors for existing completed documents
                conn.execute(text("""
                    UPDATE documents
                    SET search_vector =
                        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                        setweight(to_tsvector('english', coalesce(content_text, '')), 'B') ||
                        setweight(to_tsvector('english', coalesce(content_summary, '')), 'C') ||
                        setweight(to_tsvector('english', coalesce(array_to_string(tags, ' '), '')), 'D')
                    WHERE processing_status = 'COMPLETED'
                        AND is_deleted = false
                        AND (content_text IS NOT NULL OR content_summary IS NOT NULL OR title IS NOT NULL)
                """))

                # Commit transaction
                trans.commit()
                print("✅ Full-text search migration completed successfully!")

                # Print statistics
                print("\n📊 Migration Statistics:")

                # Count documents with search vectors
                result = conn.execute(text("""
                    SELECT COUNT(*) as count
                    FROM documents
                    WHERE search_vector IS NOT NULL
                """))
                count = result.scalar()
                print(f"   Documents with search vectors: {count}")

                # List created indexes
                result = conn.execute(text("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = 'documents'
                        AND (indexname LIKE '%search%' OR indexname LIKE '%gin%')
                    ORDER BY indexname
                """))
                indexes = result.fetchall()
                print(f"   Created indexes: {len(indexes)}")
                for index in indexes:
                    print(f"     - {index.indexname}")

                return True

            except Exception as e:
                # Rollback on error
                trans.rollback()
                print(f"❌ Migration failed: {e}")
                return False

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def rollback_migration():
    """Rollback the full-text search migration"""
    print("🔄 Rolling back full-text search migration...")

    try:
        with engine.connect() as conn:
            trans = conn.begin()

            try:
                print("Dropping search indexes...")
                # Drop indexes
                conn.execute(text("DROP INDEX IF EXISTS idx_documents_search_vector"))
                conn.execute(text("DROP INDEX IF EXISTS idx_documents_title_gin"))
                conn.execute(text("DROP INDEX IF EXISTS idx_documents_content_gin"))
                conn.execute(text("DROP INDEX IF EXISTS idx_documents_created_at"))
                conn.execute(text("DROP INDEX IF EXISTS idx_documents_type_status"))

                print("Dropping search_vector column...")
                # Drop column
                conn.execute(text("ALTER TABLE documents DROP COLUMN IF EXISTS search_vector"))

                trans.commit()
                print("✅ Full-text search migration rolled back successfully!")
                return True

            except Exception as e:
                trans.rollback()
                print(f"❌ Rollback failed: {e}")
                return False

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        success = rollback_migration()
    else:
        success = run_migration()

    sys.exit(0 if success else 1)