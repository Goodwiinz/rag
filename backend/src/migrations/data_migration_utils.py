"""
Data migration utilities for enhanced document processing schema
"""

import hashlib
import uuid
from datetime import datetime, timezone as dt_timezone
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_
import logging

from ..models.base import Base
from ..models.document import Document, ProcessingStatus
from ..models.document_processing import (
    ProcessingHistory, ProcessingStage, DocumentVersion,
    MultimodalContent, ContentType, DocumentQualityMetrics,
    QualityMetricType, DocumentAccessLog
)
from ..models.user import User
from ..models.organization import Organization

logger = logging.getLogger(__name__)


class DataMigrationManager:
    """
    Manages data migration for enhanced document processing schema
    """

    def __init__(self, db: Session):
        self.db = db

    def migrate_existing_documents(self, batch_size: int = 100) -> Dict[str, int]:
        """
        Migrate existing documents to new schema structure

        Returns migration statistics
        """
        stats = {
            'documents_processed': 0,
            'versions_created': 0,
            'processing_history_created': 0,
            'multimodal_content_created': 0,
            'quality_metrics_created': 0,
            'errors': 0
        }

        try:
            # Get all existing documents that haven't been migrated
            query = self.db.query(Document).filter(
                and_(
                    Document.is_deleted == False,
                    ~Document.versions.any()  # No versions exist yet
                )
            ).order_by(Document.created_at)

            total_documents = query.count()
            logger.info(f"Starting migration of {total_documents} documents")

            # Process in batches
            offset = 0
            while offset < total_documents:
                documents = query.limit(batch_size).offset(offset).all()

                for document in documents:
                    try:
                        self._migrate_single_document(document)
                        stats['documents_processed'] += 1
                        stats['versions_created'] += 1

                        # Create initial processing history
                        self._create_initial_processing_history(document)
                        stats['processing_history_created'] += 1

                        # Create initial multimodal content for text documents
                        if document.content_text:
                            self._create_initial_multimodal_content(document)
                            stats['multimodal_content_created'] += 1

                        # Create initial quality metrics
                        self._create_initial_quality_metrics(document)
                        stats['quality_metrics_created'] += 1

                        # Commit each document to avoid large transactions
                        self.db.commit()

                    except Exception as e:
                        logger.error(f"Error migrating document {document.id}: {e}")
                        stats['errors'] += 1
                        self.db.rollback()

                offset += batch_size
                logger.info(f"Migrated {offset}/{total_documents} documents")

            logger.info(f"Migration completed. Stats: {stats}")

        except Exception as e:
            logger.error(f"Critical error during migration: {e}")
            self.db.rollback()
            raise

        return stats

    def _migrate_single_document(self, document: Document):
        """Migrate a single document to the new schema"""

        # Create initial version (v1)
        version = DocumentVersion(
            document_id=document.id,
            version_number=1,
            version_label="v1.0.0",
            change_description="Initial version created during migration",
            is_major_version=True,
            is_current_version=True,
            file_path=document.file_path,
            file_size_bytes=document.file_size_bytes,
            file_hash=self._calculate_file_hash(document.file_path),
            mime_type=document.mime_type,
            created_by_user_id=document.uploaded_by_user_id,
            organization_id=document.organization_id
        )

        self.db.add(version)

        # Update document with new fields if needed
        if not document.uploaded_by_user_id:
            # Find a user from the same organization
            user = self.db.query(User).filter(
                User.organization_id == document.organization_id
            ).first()
            if user:
                document.uploaded_by_user_id = user.id

        # Set default values for new fields
        if not document.document_metadata:
            document.document_metadata = {
                'migration_timestamp': datetime.utcnow().isoformat(),
                'migration_version': '1.0.0'
            }

    def _create_initial_processing_history(self, document: Document):
        """Create initial processing history for migrated document"""

        # Create upload stage history
        upload_history = ProcessingHistory(
            document_id=document.id,
            stage=ProcessingStage.UPLOADED,
            status="completed",
            started_at=document.created_at,
            completed_at=document.created_at,
            duration_seconds=0.0,
            processing_metadata={
                'migration': True,
                'original_upload_time': document.created_at.isoformat()
            },
            progress_percentage=100.0,
            organization_id=document.organization_id
        )

        # Create processing stage history based on current status
        processing_history = ProcessingHistory(
            document_id=document.id,
            stage=self._map_processing_status_to_stage(document.processing_status),
            status="completed" if document.processing_status == ProcessingStatus.COMPLETED else "pending",
            started_at=document.processing_started_at or document.created_at,
            completed_at=document.processing_completed_at,
            duration_seconds=document.processing_duration_seconds,
            error_message=document.processing_error,
            retry_count=document.processing_retry_count,
            processing_metadata={
                'migration': True,
                'original_status': document.processing_status.value
            },
            progress_percentage=100.0 if document.processing_status == ProcessingStatus.COMPLETED else 0.0,
            organization_id=document.organization_id
        )

        self.db.add(upload_history)
        self.db.add(processing_history)

    def _create_initial_multimodal_content(self, document: Document):
        """Create initial multimodal content for text documents"""

        content = MultimodalContent(
            document_id=document.id,
            content_type=ContentType.TEXT,
            content_id="main_content",
            sequence_order=0,
            raw_content=document.content_text,
            processed_content=document.content_text,
            content_metadata={
                'migration': True,
                'extraction_method': 'legacy',
                'original_extraction_time': document.created_at.isoformat()
            },
            quality_score=0.8,  # Default quality score
            extraction_method="legacy_migration",
            extraction_confidence=0.9,
            language_code="en",  # Default to English
            word_count=len(document.content_text.split()) if document.content_text else 0,
            character_count=len(document.content_text) if document.content_text else 0,
            is_indexed=document.is_indexed,
            embedding_id=document.embedding_id,
            organization_id=document.organization_id
        )

        self.db.add(content)

    def _create_initial_quality_metrics(self, document: Document):
        """Create initial quality metrics for migrated document"""

        # Content richness metric
        content_richness = DocumentQualityMetrics(
            document_id=document.id,
            content_id="main_content",
            metric_type=QualityMetricType.CONTENT_RICHNESS,
            metric_value=self._calculate_content_richness(document.content_text),
            metric_unit="score",
            assessment_method="automated",
            assessment_version="1.0.0",
            confidence_score=0.8,
            threshold_min=0.3,
            threshold_target=0.7,
            meets_threshold=True,
            metric_details={
                'word_count': len(document.content_text.split()) if document.content_text else 0,
                'character_count': len(document.content_text) if document.content_text else 0,
                'unique_words': len(set(document.content_text.lower().split())) if document.content_text else 0
            },
            organization_id=document.organization_id
        )

        # Text clarity metric (for text documents)
        if document.document_type.value in ['text', 'pdf']:
            text_clarity = DocumentQualityMetrics(
                document_id=document.id,
                content_id="main_content",
                metric_type=QualityMetricType.TEXT_CLARITY,
                metric_value=self._calculate_text_clarity(document.content_text),
                metric_unit="score",
                assessment_method="automated",
                assessment_version="1.0.0",
                confidence_score=0.7,
                threshold_min=0.4,
                threshold_target=0.8,
                meets_threshold=True,
                metric_details={
                    'avg_sentence_length': self._calculate_avg_sentence_length(document.content_text),
                    'complexity_score': 0.6  # Placeholder
                },
                organization_id=document.organization_id
            )

            self.db.add(text_clarity)

        self.db.add(content_richness)

    def _calculate_file_hash(self, file_path: str) -> Optional[str]:
        """Calculate SHA-256 hash of file (placeholder implementation)"""
        # In a real implementation, this would read the file and calculate hash
        # For now, return a mock hash
        return hashlib.sha256(file_path.encode()).hexdigest()[:64]

    def _map_processing_status_to_stage(self, status: ProcessingStatus) -> ProcessingStage:
        """Map legacy processing status to new processing stage"""
        mapping = {
            ProcessingStatus.PENDING: ProcessingStage.UPLOADED,
            ProcessingStatus.PROCESSING: ProcessingStage.PROCESSING,
            ProcessingStatus.COMPLETED: ProcessingStage.COMPLETED,
            ProcessingStatus.FAILED: ProcessingStage.PROCESSING,
            ProcessingStatus.RETRYING: ProcessingStage.PROCESSING
        }
        return mapping.get(status, ProcessingStage.UPLOADED)

    def _calculate_content_richness(self, text: str) -> float:
        """Calculate content richness score"""
        if not text:
            return 0.0

        words = text.split()
        unique_words = set(word.lower() for word in words)

        # Basic richness calculation based on unique word ratio
        if len(words) == 0:
            return 0.0

        richness = len(unique_words) / len(words)
        return min(1.0, richness * 2)  # Scale to 0-1 range

    def _calculate_text_clarity(self, text: str) -> float:
        """Calculate text clarity score"""
        if not text:
            return 0.0

        # Basic clarity calculation based on sentence length variance
        sentences = text.split('.')
        if len(sentences) == 0:
            return 0.0

        avg_length = sum(len(s.split()) for s in sentences) / len(sentences)

        # Prefer moderate sentence lengths (10-20 words)
        if 10 <= avg_length <= 20:
            clarity = 0.8
        elif 5 <= avg_length <= 30:
            clarity = 0.6
        else:
            clarity = 0.4

        return clarity

    def _calculate_avg_sentence_length(self, text: str) -> float:
        """Calculate average sentence length"""
        if not text:
            return 0.0

        sentences = [s.strip() for s in text.split('.') if s.strip()]
        if len(sentences) == 0:
            return 0.0

        total_words = sum(len(s.split()) for s in sentences)
        return total_words / len(sentences)

    def create_access_log_backfill(self, days_back: int = 30, batch_size: int = 1000) -> Dict[str, int]:
        """
        Create sample access logs for testing and demonstration
        Note: This is for demonstration purposes only
        """
        stats = {
            'logs_created': 0,
            'documents_processed': 0,
            'errors': 0
        }

        try:
            # Get recent documents
            documents = self.db.query(Document).filter(
                and_(
                    Document.is_deleted == False,
                    Document.created_at >= datetime.utcnow() - timedelta(days=days_back)
                )
            ).all()

            logger.info(f"Creating access logs for {len(documents)} documents")

            for document in documents:
                try:
                    # Create sample access logs
                    self._create_sample_access_logs(document)
                    stats['documents_processed'] += 1
                    stats['logs_created'] += 5  # 5 sample logs per document

                except Exception as e:
                    logger.error(f"Error creating access logs for document {document.id}: {e}")
                    stats['errors'] += 1

            self.db.commit()
            logger.info(f"Access log creation completed. Stats: {stats}")

        except Exception as e:
            logger.error(f"Critical error during access log creation: {e}")
            self.db.rollback()
            raise

        return stats

    def _create_sample_access_logs(self, document: Document):
        """Create sample access logs for a document"""

        current_time = datetime.utcnow()

        # Sample access log entries
        sample_logs = [
            {
                'access_type': 'view',
                'access_result': 'success',
                'created_at': document.created_at,
                'user_id': document.uploaded_by_user_id,
                'ip_address': '192.168.1.100',
                'user_agent': 'Mozilla/5.0 (Sample User Agent)',
                'response_status_code': 200,
                'response_time_ms': 150.0
            },
            {
                'access_type': 'view',
                'access_result': 'success',
                'created_at': document.created_at + timedelta(hours=1),
                'user_id': document.uploaded_by_user_id,
                'ip_address': '192.168.1.100',
                'user_agent': 'Mozilla/5.0 (Sample User Agent)',
                'response_status_code': 200,
                'response_time_ms': 120.0
            },
            {
                'access_type': 'download',
                'access_result': 'success',
                'created_at': document.created_at + timedelta(hours=2),
                'user_id': document.uploaded_by_user_id,
                'ip_address': '192.168.1.100',
                'user_agent': 'Mozilla/5.0 (Sample User Agent)',
                'response_status_code': 200,
                'response_time_ms': 300.0,
                'response_size_bytes': document.file_size_bytes
            },
            {
                'access_type': 'view',
                'access_result': 'success',
                'created_at': current_time - timedelta(days=1),
                'user_id': document.uploaded_by_user_id,
                'ip_address': '10.0.0.50',
                'user_agent': 'Mozilla/5.0 (Sample User Agent)',
                'response_status_code': 200,
                'response_time_ms': 180.0
            },
            {
                'access_type': 'view',
                'access_result': 'denied',
                'created_at': current_time - timedelta(hours=6),
                'ip_address': '203.0.113.10',
                'user_agent': 'Suspicious Bot 1.0',
                'response_status_code': 403,
                'response_time_ms': 50.0,
                'is_suspicious': True,
                'threat_score': 0.8,
                'security_flags': {'ip_reputation': 'poor', 'user_agent': 'bot'}
            }
        ]

        for log_data in sample_logs:
            access_log = DocumentAccessLog(
                document_id=document.id,
                organization_id=document.organization_id,
                **log_data
            )
            self.db.add(access_log)


def run_migration(db: Session, batch_size: int = 100) -> Dict[str, int]:
    """
    Run the complete data migration

    Args:
        db: Database session
        batch_size: Number of documents to process in each batch

    Returns:
        Migration statistics
    """
    manager = DataMigrationManager(db)

    logger.info("Starting data migration for enhanced document processing")

    # Run main migration
    stats = manager.migrate_existing_documents(batch_size)

    # Create sample access logs (optional)
    access_log_stats = manager.create_access_log_backfill()
    stats.update(access_log_stats)

    logger.info("Data migration completed successfully")
    return stats


def validate_migration(db: Session) -> Dict[str, int]:
    """
    Validate migration results

    Args:
        db: Database session

    Returns:
        Validation statistics
    """
    stats = {
        'total_documents': db.query(Document).filter(Document.is_deleted == False).count(),
        'documents_with_versions': db.query(Document).join(DocumentVersion).filter(Document.is_deleted == False).count(),
        'total_versions': db.query(DocumentVersion).count(),
        'total_processing_history': db.query(ProcessingHistory).count(),
        'total_multimodal_content': db.query(MultimodalContent).count(),
        'total_quality_metrics': db.query(DocumentQualityMetrics).count(),
        'total_access_logs': db.query(DocumentAccessLog).count(),
        'migration_errors': 0
    }

    # Check for data consistency
    stats['migration_errors'] = db.query(Document).filter(
        and_(
            Document.is_deleted == False,
            ~Document.versions.any()
        )
    ).count()

    logger.info(f"Migration validation completed. Stats: {stats}")
    return stats