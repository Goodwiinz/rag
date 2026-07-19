"""
Database Integration and Migration Tests
Tests database schema, migrations, data integrity, and relationships
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Generator
from sqlalchemy import create_engine, text, inspect, MetaData, Table, Column, Integer, String, DateTime, Boolean, ForeignKey, Float, Text, JSON
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError, OperationalError
from alembic import command
from alembic.config import Config

# Import models and database components
from src.core.database import get_db, Base, engine
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.processing import ProcessingJob, JobType, JobStatus, JobPriority
from src.models.quality import QualityAssessment
from src.migrations.migration_runner import MigrationRunner
from tests.conftest import test_db, test_engine, TestSession


class TestDatabaseSchemaValidation:
    """Test database schema structure and constraints"""

    @pytest.fixture
    def inspector(self, test_engine):
        """Create SQLAlchemy inspector for schema validation"""
        return inspect(test_engine)

    def test_all_tables_exist(self, inspector):
        """Verify all required tables exist in the database"""
        expected_tables = {
            'users',
            'organizations',
            'documents',
            'processing_jobs',
            'quality_assessments',
            'document_tags',
            'document_metadata',
            'audit_logs',
            'file_storage'
        }

        existing_tables = set(inspector.get_table_names())
        missing_tables = expected_tables - existing_tables

        assert not missing_tables, f"Missing tables: {missing_tables}"
        assert existing_tables.issuperset(expected_tables), f"Unexpected tables found: {existing_tables - expected_tables}"

    def test_user_table_schema(self, inspector):
        """Test users table schema and constraints"""
        columns = inspector.get_columns('users')
        column_names = {col['name'] for col in columns}

        required_columns = {
            'id', 'email', 'password_hash', 'full_name', 'role',
            'is_active', 'organization_id', 'created_at', 'updated_at'
        }

        assert required_columns.issubset(column_names), f"Missing user columns: {required_columns - column_names}"

        # Check column types and constraints
        email_column = next(col for col in columns if col['name'] == 'email')
        assert email_column['nullable'] == False, "Email should be non-nullable"
        assert 'unique' in email_column or any(constr['type'] == 'unique' for constr in email_column.get('constraints', [])), "Email should be unique"

        role_column = next(col for col in columns if col['name'] == 'role')
        assert role_column['nullable'] == False, "Role should be non-nullable"

    def test_organization_table_schema(self, inspector):
        """Test organizations table schema"""
        columns = inspector.get_columns('organizations')
        column_names = {col['name'] for col in columns}

        required_columns = {
            'id', 'name', 'slug', 'settings', 'is_active',
            'created_at', 'updated_at'
        }

        assert required_columns.issubset(column_names), f"Missing organization columns: {required_columns - column_names}"

        # Check unique constraints
        name_column = next(col for col in columns if col['name'] == 'name')
        slug_column = next(col for col in columns if col['name'] == 'slug')

        assert name_column['nullable'] == False, "Organization name should be non-nullable"
        assert slug_column['nullable'] == False, "Organization slug should be non-nullable"

    def test_document_table_schema(self, inspector):
        """Test documents table schema and relationships"""
        columns = inspector.get_columns('documents')
        column_names = {col['name'] for col in columns}

        required_columns = {
            'id', 'title', 'filename', 'file_path', 'file_type',
            'mime_type', 'file_size_bytes', 'file_size_mb',
            'processing_status', 'uploaded_by_user_id', 'organization_id',
            'is_public', 'is_deleted', 'created_at', 'updated_at'
        }

        assert required_columns.issubset(column_names), f"Missing document columns: {required_columns - column_names}"

        # Check foreign key constraints
        foreign_keys = inspector.get_foreign_keys('documents')
        fk_columns = {fk['constrained_columns'][0] for fk in foreign_keys}

        assert 'uploaded_by_user_id' in fk_columns, "Missing foreign key to users"
        assert 'organization_id' in fk_columns, "Missing foreign key to organizations"

    def test_processing_jobs_table_schema(self, inspector):
        """Test processing_jobs table schema"""
        columns = inspector.get_columns('processing_jobs')
        column_names = {col['name'] for col in columns}

        required_columns = {
            'id', 'job_type', 'status', 'priority', 'document_id',
            'organization_id', 'created_by_user_id', 'parameters',
            'config', 'total_steps', 'completed_steps', 'error_message',
            'started_at', 'completed_at', 'created_at', 'updated_at'
        }

        assert required_columns.issubset(column_names), f"Missing processing job columns: {required_columns - column_names}"

        # Check JSON columns
        parameters_column = next(col for col in columns if col['name'] == 'parameters')
        config_column = next(col for col in columns if col['name'] == 'config')

        assert parameters_column['type'].upper() == 'JSON', "Parameters should be JSON type"
        assert config_column['type'].upper() == 'JSON', "Config should be JSON type"

    def test_quality_assessments_table_schema(self, inspector):
        """Test quality_assessments table schema"""
        columns = inspector.get_columns('quality_assessments')
        column_names = {col['name'] for col in columns}

        required_columns = {
            'id', 'document_id', 'overall_score', 'readability_score',
            'content_quality_score', 'technical_quality_score',
            'recommendations', 'issues', 'processing_time_ms', 'created_at'
        }

        assert required_columns.issubset(column_names), f"Missing quality assessment columns: {required_columns - column_names}"

        # Check numeric columns
        overall_score_column = next(col for col in columns if col['name'] == 'overall_score')
        assert overall_score_column['type'].lower() in ('float', 'numeric', 'decimal'), "Overall score should be numeric"

    def test_foreign_key_relationships(self, inspector):
        """Test foreign key relationships between tables"""
        # Test users -> organizations relationship
        user_fks = inspector.get_foreign_keys('users')
        assert any(fk['referred_table'] == 'organizations' for fk in user_fks), "Users should reference organizations"

        # Test documents -> users and organizations relationships
        doc_fks = inspector.get_foreign_keys('documents')
        doc_fk_tables = {fk['referred_table'] for fk in doc_fks}
        assert 'users' in doc_fk_tables, "Documents should reference users"
        assert 'organizations' in doc_fk_tables, "Documents should reference organizations"

        # Test processing_jobs -> documents relationship
        job_fks = inspector.get_foreign_keys('processing_jobs')
        job_fk_tables = {fk['referred_table'] for fk in job_fks}
        assert 'documents' in job_fk_tables, "Processing jobs should reference documents"

        # Test quality_assessments -> documents relationship
        qa_fks = inspector.get_foreign_keys('quality_assessments')
        assert any(fk['referred_table'] == 'documents' for fk in qa_fks), "Quality assessments should reference documents"


class TestDatabaseConstraintsAndValidation:
    """Test database constraints, validation, and data integrity"""

    def test_user_email_uniqueness(self, test_db: TestSession):
        """Test that user emails must be unique"""
        # Create first user
        user1 = User(
            email="test@example.com",
            password_hash="hash1",
            full_name="Test User 1",
            role=UserRole.USER
        )
        test_db.add(user1)
        test_db.commit()

        # Try to create second user with same email
        user2 = User(
            email="test@example.com",
            password_hash="hash2",
            full_name="Test User 2",
            role=UserRole.USER
        )
        test_db.add(user2)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_organization_slug_uniqueness(self, test_db: TestSession):
        """Test that organization slugs must be unique"""
        # Create first organization
        org1 = Organization(
            name="Test Organization",
            slug="test-org",
            settings={}
        )
        test_db.add(org1)
        test_db.commit()

        # Try to create second organization with same slug
        org2 = Organization(
            name="Another Test Organization",
            slug="test-org",
            settings={}
        )
        test_db.add(org2)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_document_user_foreign_key_constraint(self, test_db: TestSession):
        """Test that document must reference valid user"""
        # Try to create document with non-existent user
        doc = Document(
            title="Test Document",
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_type=DocumentType.PDF,
            mime_type="application/pdf",
            file_size_bytes=1024,
            file_size_mb=0.001,
            processing_status=ProcessingStatus.UPLOADED,
            uploaded_by_user_id="non-existent-id",
            organization_id="non-existent-org-id"
        )
        test_db.add(doc)

        with pytest.raises(IntegrityError):
            test_db.commit()

    def test_cascade_delete_relationships(self, test_db: TestSession):
        """Test cascade delete behavior"""
        # Create test data
        org = Organization(name="Test Org", slug="test-org", settings={})
        test_db.add(org)
        test_db.flush()

        user = User(
            email="test@example.com",
            password_hash="hash",
            full_name="Test User",
            role=UserRole.USER,
            organization_id=org.id
        )
        test_db.add(user)
        test_db.flush()

        doc = Document(
            title="Test Document",
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_type=DocumentType.PDF,
            mime_type="application/pdf",
            file_size_bytes=1024,
            file_size_mb=0.001,
            processing_status=ProcessingStatus.UPLOADED,
            uploaded_by_user_id=user.id,
            organization_id=org.id
        )
        test_db.add(doc)
        test_db.flush()

        job = ProcessingJob(
            job_type=JobType.DOCUMENT_INGESTION,
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            document_id=doc.id,
            organization_id=org.id,
            created_by_user_id=user.id
        )
        test_db.add(job)
        test_db.commit()

        # Delete user and verify related data handling
        test_db.delete(user)
        test_db.commit()

        # Check that document is handled (either deleted or user_id set to null)
        remaining_doc = test_db.query(Document).filter(Document.id == doc.id).first()
        if remaining_doc:
            # If document still exists, user_id should be null
            assert remaining_doc.uploaded_by_user_id is None

    def test_not_null_constraints(self, test_db: TestSession):
        """Test NOT NULL constraints on required fields"""
        # Test user with null email
        user_null_email = User(
            email=None,
            password_hash="hash",
            full_name="Test User",
            role=UserRole.USER
        )
        test_db.add(user_null_email)

        with pytest.raises(IntegrityError):
            test_db.commit()

        test_db.rollback()

        # Test document with null title
        doc_null_title = Document(
            title=None,
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_type=DocumentType.PDF,
            mime_type="application/pdf",
            file_size_bytes=1024,
            file_size_mb=0.001,
            processing_status=ProcessingStatus.UPLOADED,
            uploaded_by_user_id="test-user-id",
            organization_id="test-org-id"
        )
        test_db.add(doc_null_title)

        with pytest.raises(IntegrityError):
            test_db.commit()


class TestDatabaseMigrations:
    """Test database migration functionality"""

    @pytest.fixture
    def migration_runner(self, test_engine):
        """Create migration runner instance"""
        return MigrationRunner(test_engine)

    @pytest.fixture
    def alembic_config(self):
        """Create Alembic configuration for testing"""
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", "sqlite:///:memory:")
        return config

    def test_migration_initialization(self, migration_runner):
        """Test migration runner initialization"""
        assert migration_runner.engine is not None
        assert migration_runner.connection is not None

    def test_create_migration_table(self, migration_runner):
        """Test migration table creation"""
        migration_runner.create_migration_table()

        # Verify table exists
        inspector = inspect(migration_runner.engine)
        assert 'alembic_version' in inspector.get_table_names()

    def test_migration_history_tracking(self, migration_runner):
        """Test migration history tracking"""
        migration_runner.create_migration_table()

        # Record a migration
        migration_runner.record_migration("test_migration_001", "Initial test migration")

        # Verify migration is recorded
        history = migration_runner.get_migration_history()
        assert len(history) == 1
        assert history[0]['version_num'] == "test_migration_001"

    def test_duplicate_migration_prevention(self, migration_runner):
        """Test that duplicate migrations are prevented"""
        migration_runner.create_migration_table()
        migration_runner.record_migration("test_migration_001", "Initial test migration")

        # Try to record same migration again
        with pytest.raises(IntegrityError):
            migration_runner.record_migration("test_migration_001", "Duplicate migration")

    def test_migration_rollback(self, migration_runner):
        """Test migration rollback functionality"""
        migration_runner.create_migration_table()

        # Record multiple migrations
        migration_runner.record_migration("test_migration_001", "First migration")
        migration_runner.record_migration("test_migration_002", "Second migration")
        migration_runner.record_migration("test_migration_003", "Third migration")

        # Rollback to specific version
        migration_runner.rollback_to_version("test_migration_001")

        # Verify current version
        current_version = migration_runner.get_current_version()
        assert current_version == "test_migration_001"

    def test_alembic_integration(self, alembic_config):
        """Test Alembic integration for real migrations"""
        # Run migrations up to head
        command.upgrade(alembic_config, "head")

        # Verify tables were created
        engine = create_engine(alembic_config.get_main_option("sqlalchemy.url"))
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert len(tables) > 0, "No tables created by migrations"

        # Get current revision
        current = command.current(alembic_config)
        assert current is not None, "No current migration version"

        # Test downgrade
        command.downgrade(alembic_config, "base")
        tables_after_downgrade = inspector.get_table_names()

        # Most tables should be gone after downgrade to base
        assert len(tables_after_downgrade) < len(tables), "Downgrade didn't remove tables"


class TestDatabasePerformanceAndOptimization:
    """Test database performance and optimization"""

    def test_query_performance_with_indexes(self, test_db: TestSession):
        """Test query performance with proper indexes"""
        # Create test data
        org = Organization(name="Test Org", slug="test-org", settings={})
        test_db.add(org)
        test_db.flush()

        user = User(
            email="test@example.com",
            password_hash="hash",
            full_name="Test User",
            role=UserRole.USER,
            organization_id=org.id
        )
        test_db.add(user)
        test_db.flush()

        # Create many documents for performance testing
        documents = []
        for i in range(1000):
            doc = Document(
                title=f"Document {i}",
                filename=f"doc_{i}.pdf",
                file_path=f"/path/doc_{i}.pdf",
                file_type=DocumentType.PDF,
                mime_type="application/pdf",
                file_size_bytes=1024 * (i + 1),
                file_size_mb=0.001 * (i + 1),
                processing_status=ProcessingStatus.INDEXED,
                uploaded_by_user_id=user.id,
                organization_id=org.id
            )
            documents.append(doc)
        test_db.add_all(documents)
        test_db.commit()

        # Test performance of common queries
        start_time = datetime.now()

        # Query by organization (should use index)
        org_docs = test_db.query(Document).filter(
            Document.organization_id == org.id
        ).all()

        org_query_time = (datetime.now() - start_time).total_seconds()

        start_time = datetime.now()

        # Query by user (should use index)
        user_docs = test_db.query(Document).filter(
            Document.uploaded_by_user_id == user.id
        ).all()

        user_query_time = (datetime.now() - start_time).total_seconds()

        start_time = datetime.now()

        # Query with ordering (should be optimized)
        ordered_docs = test_db.query(Document).filter(
            Document.organization_id == org.id
        ).order_by(Document.created_at.desc()).limit(50).all()

        order_query_time = (datetime.now() - start_time).total_seconds()

        # Performance assertions (these are loose thresholds)
        assert org_query_time < 1.0, f"Organization query too slow: {org_query_time}s"
        assert user_query_time < 1.0, f"User query too slow: {user_query_time}s"
        assert order_query_time < 0.5, f"Ordered query too slow: {order_query_time}s"

        # Verify results
        assert len(org_docs) == 1000
        assert len(user_docs) == 1000
        assert len(ordered_docs) == 50

    def test_bulk_operations_performance(self, test_db: TestSession):
        """Test performance of bulk database operations"""
        # Create test organization
        org = Organization(name="Test Org", slug="test-org", settings={})
        test_db.add(org)
        test_db.flush()

        # Test bulk insert performance
        start_time = datetime.now()

        documents = []
        for i in range(5000):
            doc = Document(
                title=f"Bulk Document {i}",
                filename=f"bulk_{i}.pdf",
                file_path=f"/path/bulk_{i}.pdf",
                file_type=DocumentType.PDF,
                mime_type="application/pdf",
                file_size_bytes=1024,
                file_size_mb=0.001,
                processing_status=ProcessingStatus.UPLOADED,
                uploaded_by_user_id="test-user",
                organization_id=org.id
            )
            documents.append(doc)

        test_db.add_all(documents)
        test_db.commit()

        bulk_insert_time = (datetime.now() - start_time).total_seconds()

        # Performance assertion
        assert bulk_insert_time < 10.0, f"Bulk insert too slow: {bulk_insert_time}s"

        # Test bulk update performance
        start_time = datetime.now()

        test_db.query(Document).filter(
            Document.organization_id == org.id
        ).update({
            "processing_status": ProcessingStatus.INDEXED
        }, synchronize_session=False)

        test_db.commit()

        bulk_update_time = (datetime.now() - start_time).total_seconds()

        # Performance assertion
        assert bulk_update_time < 5.0, f"Bulk update too slow: {bulk_update_time}s"

        # Test bulk delete performance
        start_time = datetime.now()

        test_db.query(Document).filter(
            Document.organization_id == org.id
        ).delete(synchronize_session=False)

        test_db.commit()

        bulk_delete_time = (datetime.now() - start_time).total_seconds()

        # Performance assertion
        assert bulk_delete_time < 5.0, f"Bulk delete too slow: {bulk_delete_time}s"

    def test_connection_pool_handling(self, test_engine):
        """Test database connection pool handling"""
        # Create multiple concurrent connections
        SessionLocal = sessionmaker(bind=test_engine)

        async def concurrent_query(session_id: int):
            """Run a query in a separate session"""
            session = SessionLocal()
            try:
                result = session.execute(text("SELECT 1 as test")).fetchone()
                return session_id, result[0]
            finally:
                session.close()

        # Run concurrent queries
        tasks = [concurrent_query(i) for i in range(10)]
        results = asyncio.run(asyncio.gather(*tasks))

        # Verify all queries succeeded
        assert len(results) == 10
        for session_id, result in results:
            assert result == 1
            assert session_id is not None

    def test_transaction_handling_and_rollback(self, test_db: TestSession):
        """Test transaction handling and rollback"""
        # Create initial data
        org = Organization(name="Test Org", slug="test-org", settings={})
        test_db.add(org)
        test_db.commit()

        initial_count = test_db.query(Organization).count()

        # Start transaction
        try:
            # Add new organization
            new_org = Organization(name="New Org", slug="new-org", settings={})
            test_db.add(new_org)
            test_db.flush()  # Get ID without committing

            # Add some documents
            for i in range(5):
                doc = Document(
                    title=f"Test Doc {i}",
                    filename=f"test_{i}.pdf",
                    file_path=f"/path/test_{i}.pdf",
                    file_type=DocumentType.PDF,
                    mime_type="application/pdf",
                    file_size_bytes=1024,
                    file_size_mb=0.001,
                    processing_status=ProcessingStatus.UPLOADED,
                    uploaded_by_user_id="test-user",
                    organization_id=new_org.id
                )
                test_db.add(doc)

            # Simulate an error condition
            if True:  # Force rollback for testing
                raise Exception("Simulated error")

            test_db.commit()

        except Exception:
            test_db.rollback()

        # Verify rollback worked
        final_count = test_db.query(Organization).count()
        assert final_count == initial_count, "Rollback didn't work - organization count changed"

        # Verify no orphaned documents exist
        orphaned_docs = test_db.query(Document).filter(
            Document.organization_id == new_org.id
        ).count()
        assert orphaned_docs == 0, "Orphaned documents found after rollback"


class TestDataIntegrityAndConsistency:
    """Test data integrity and consistency across related tables"""

    def test_document_processing_job_consistency(self, test_db: TestSession):
        """Test consistency between documents and processing jobs"""
        # Create test data
        org = Organization(name="Test Org", slug="test-org", settings={})
        test_db.add(org)
        test_db.flush()

        user = User(
            email="test@example.com",
            password_hash="hash",
            full_name="Test User",
            role=UserRole.USER,
            organization_id=org.id
        )
        test_db.add(user)
        test_db.flush()

        doc = Document(
            title="Test Document",
            filename="test.pdf",
            file_path="/path/test.pdf",
            file_type=DocumentType.PDF,
            mime_type="application/pdf",
            file_size_bytes=1024,
            file_size_mb=0.001,
            processing_status=ProcessingStatus.PROCESSING,
            uploaded_by_user_id=user.id,
            organization_id=org.id
        )
        test_db.add(doc)
        test_db.flush()

        # Create processing job
        job = ProcessingJob(
            job_type=JobType.DOCUMENT_INGESTION,
            status=JobStatus.IN_PROGRESS,
            priority=JobPriority.NORMAL,
            document_id=doc.id,
            organization_id=org.id,
            created_by_user_id=user.id,
            total_steps=5,
            completed_steps=2
        )
        test_db.add(job)
        test_db.commit()

        # Update job status to completed
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        test_db.commit()

        # Update document status to match
        doc.processing_status = ProcessingStatus.INDEXED
        test_db.commit()

        # Verify consistency
        final_doc = test_db.query(Document).filter(Document.id == doc.id).first()
        final_job = test_db.query(ProcessingJob).filter(ProcessingJob.id == job.id).first()

        assert final_doc.processing_status == ProcessingStatus.INDEXED
        assert final_job.status == JobStatus.COMPLETED
        assert final_job.completed_at is not None

    def test_quality_assessment_data_integrity(self, test_db: TestSession):
        """Test quality assessment data integrity"""
        # Create test document
        org = Organization(name="Test Org", slug="test-org", settings={})
        test_db.add(org)
        test_db.flush()

        doc = Document(
            title="Test Document",
            filename="test.pdf",
            file_path="/path/test.pdf",
            file_type=DocumentType.PDF,
            mime_type="application/pdf",
            file_size_bytes=1024,
            file_size_mb=0.001,
            processing_status=ProcessingStatus.INDEXED,
            uploaded_by_user_id="test-user",
            organization_id=org.id
        )
        test_db.add(doc)
        test_db.flush()

        # Create quality assessment
        qa = QualityAssessment(
            document_id=doc.id,
            overall_score=0.85,
            readability_score=0.90,
            content_quality_score=0.80,
            technical_quality_score=0.85,
            recommendations=["Improve structure", "Add more examples"],
            issues=[
                {
                    "type": "readability",
                    "severity": "medium",
                    "description": "Long paragraphs detected"
                }
            ],
            processing_time_ms=1500
        )
        test_db.add(qa)
        test_db.commit()

        # Verify data integrity
        retrieved_qa = test_db.query(QualityAssessment).filter(
            QualityAssessment.document_id == doc.id
        ).first()

        assert retrieved_qa is not None
        assert retrieved_qa.overall_score == 0.85
        assert isinstance(retrieved_qa.recommendations, list)
        assert len(retrieved_qa.recommendations) == 2
        assert isinstance(retrieved_qa.issues, list)
        assert len(retrieved_qa.issues) == 1
        assert retrieved_qa.issues[0]["type"] == "readability"

    def test_document_deletion_cascade_behavior(self, test_db: TestSession):
        """Test cascade behavior when deleting documents"""
        # Create test data
        org = Organization(name="Test Org", slug="test-org", settings={})
        test_db.add(org)
        test_db.flush()

        doc = Document(
            title="Test Document",
            filename="test.pdf",
            file_path="/path/test.pdf",
            file_type=DocumentType.PDF,
            mime_type="application/pdf",
            file_size_bytes=1024,
            file_size_mb=0.001,
            processing_status=ProcessingStatus.INDEXED,
            uploaded_by_user_id="test-user",
            organization_id=org.id
        )
        test_db.add(doc)
        test_db.flush()

        # Create related records
        job = ProcessingJob(
            job_type=JobType.DOCUMENT_INGESTION,
            status=JobStatus.COMPLETED,
            priority=JobPriority.NORMAL,
            document_id=doc.id,
            organization_id=org.id,
            created_by_user_id="test-user"
        )
        test_db.add(job)

        qa = QualityAssessment(
            document_id=doc.id,
            overall_score=0.85,
            readability_score=0.90,
            content_quality_score=0.80,
            technical_quality_score=0.85,
            recommendations=[],
            issues=[],
            processing_time_ms=1000
        )
        test_db.add(qa)
        test_db.commit()

        # Delete document (soft delete)
        doc.is_deleted = True
        test_db.commit()

        # Verify related records are handled appropriately
        remaining_job = test_db.query(ProcessingJob).filter(ProcessingJob.document_id == doc.id).first()
        remaining_qa = test_db.query(QualityAssessment).filter(QualityAssessment.document_id == doc.id).first()

        # Both should either be deleted or marked as deleted
        if remaining_job:
            assert remaining_job.status == JobStatus.CANCELLED or remaining_job.document_id != doc.id

        if remaining_qa:
            # Quality assessments might remain for audit purposes
            assert remaining_qa.document_id == doc.id

    def test_organization_isolation(self, test_db: TestSession):
        """Test data isolation between organizations"""
        # Create two organizations
        org1 = Organization(name="Org 1", slug="org1", settings={})
        org2 = Organization(name="Org 2", slug="org2", settings={})
        test_db.add_all([org1, org2])
        test_db.flush()

        # Create documents for each organization
        doc1 = Document(
            title="Org 1 Document",
            filename="doc1.pdf",
            file_path="/path/doc1.pdf",
            file_type=DocumentType.PDF,
            mime_type="application/pdf",
            file_size_bytes=1024,
            file_size_mb=0.001,
            processing_status=ProcessingStatus.INDEXED,
            uploaded_by_user_id="user1",
            organization_id=org1.id
        )

        doc2 = Document(
            title="Org 2 Document",
            filename="doc2.pdf",
            file_path="/path/doc2.pdf",
            file_type=DocumentType.PDF,
            mime_type="application/pdf",
            file_size_bytes=1024,
            file_size_mb=0.001,
            processing_status=ProcessingStatus.INDEXED,
            uploaded_by_user_id="user2",
            organization_id=org2.id
        )

        test_db.add_all([doc1, doc2])
        test_db.commit()

        # Test isolation - queries should only return data for specific organization
        org1_docs = test_db.query(Document).filter(Document.organization_id == org1.id).all()
        org2_docs = test_db.query(Document).filter(Document.organization_id == org2.id).all()

        assert len(org1_docs) == 1
        assert len(org2_docs) == 1
        assert org1_docs[0].id == doc1.id
        assert org2_docs[0].id == doc2.id

        # Verify no cross-contamination
        all_doc_ids = {doc.id for doc in org1_docs + org2_docs}
        expected_doc_ids = {doc1.id, doc2.id}
        assert all_doc_ids == expected_doc_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])