"""
Document model for multimodal content storage and management
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum, ForeignKey, Text, JSON, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship, selectinload, joinedload
from enum import Enum as PyEnum
from datetime import datetime

from .base import BaseModel, GUID
from .utils import StringArray

class DocumentType(PyEnum):
    """Document types for different modalities"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PDF = "pdf"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    MULTIMODAL = "multimodal"

class ProcessingStatus(PyEnum):
    """Processing status for documents"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class Document(BaseModel):
    """Document model for multimodal content"""

    __tablename__ = "documents"

    # Basic information
    title = Column(String(500), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False, index=True)

    # Content
    content_text = Column(Text, nullable=True)  # Extracted text content
    content_summary = Column(Text, nullable=True)  # AI-generated summary
    document_metadata = Column(JSON, nullable=True)  # Document-specific metadata

    # Full-text search
    search_vector = Column(TSVECTOR, nullable=True)  # PostgreSQL full-text search vector

    # Processing
    processing_status = Column(Enum(ProcessingStatus), nullable=False, default=ProcessingStatus.PENDING)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_error = Column(Text, nullable=True)
    processing_retry_count = Column(Integer, default=0, nullable=False)

    # Vector and search
    embedding_id = Column(String(255), nullable=True, index=True)  # Qdrant vector ID
    is_embedded = Column(Boolean, default=False, nullable=False)
    is_indexed = Column(Boolean, default=False, nullable=False)

    # Access control
    is_public = Column(Boolean, default=False, nullable=False)
    tags = Column(StringArray, nullable=True)

    # Organization
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    uploaded_by_user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="documents")
    uploaded_by_user = relationship("User", back_populates="documents")
    entities = relationship("Entity", back_populates="document", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="document", cascade="all, delete-orphan")
    search_results = relationship("SearchResult", back_populates="document", cascade="all, delete-orphan")

    # Enhanced document processing relationships
    processing_history = relationship("ProcessingHistory", back_populates="document", cascade="all, delete-orphan")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    multimodal_content = relationship("MultimodalContent", back_populates="document", cascade="all, delete-orphan")
    quality_metrics = relationship("DocumentQualityMetrics", back_populates="document", cascade="all, delete-orphan")
    access_logs = relationship("DocumentAccessLog", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(title={self.title}, type={self.document_type.value}, status={self.processing_status.value})>"

    def get_metadata(self):
        """Get document metadata as dict"""
        return self.document_metadata or {}

    def set_metadata(self, value):
        """Set document metadata"""
        self.document_metadata = value

    @property
    def file_size_mb(self) -> float:
        """Get file size in MB"""
        return self.file_size_bytes / (1024 * 1024)

    @property
    def processing_duration_seconds(self) -> float:
        """Get processing duration in seconds"""
        if self.processing_started_at and self.processing_completed_at:
            return (self.processing_completed_at - self.processing_started_at).total_seconds()
        return 0.0

    @property
    def is_processing_complete(self) -> bool:
        """Check if processing is complete (success or failure)"""
        return self.processing_status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]

    @property
    def is_processing_successful(self) -> bool:
        """Check if processing was successful"""
        return self.processing_status == ProcessingStatus.COMPLETED

    def can_be_searched(self) -> bool:
        """Check if document can be searched"""
        return (
            self.is_processing_successful and
            self.is_embedded and
            self.is_indexed and
            not self.is_deleted
        )

    def update_processing_status(self, status: ProcessingStatus, error: str = None):
        """Update processing status with timestamp"""
        self.processing_status = status

        if status == ProcessingStatus.PROCESSING and not self.processing_started_at:
            self.processing_started_at = datetime.utcnow()
            self.processing_retry_count += 1
        elif status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
            self.processing_completed_at = datetime.utcnow()
            if error:
                self.processing_error = error

    def add_metadata(self, key: str, value):
        """Add metadata entry"""
        current_metadata = self.get_metadata()
        current_metadata[key] = value
        self.set_metadata(current_metadata)

    def get_metadata_value(self, key: str, default=None):
        """Get metadata value"""
        current_metadata = self.get_metadata()
        return current_metadata.get(key, default)

    def add_tags(self, tags: list):
        """Add tags to document"""
        if not self.tags:
            self.tags = []
        # Remove duplicates and preserve order
        unique_tags = []
        for tag in tags + self.tags:
            if tag not in unique_tags:
                unique_tags.append(tag)
        self.tags = unique_tags

    def remove_tags(self, tags: list):
        """Remove tags from document"""
        if not self.tags:
            return
        for tag in tags:
            if tag in self.tags:
                self.tags.remove(tag)

    def get_content_preview(self, max_length: int = 200) -> str:
        """Get content preview"""
        if not self.content_text:
            return ""
        if len(self.content_text) <= max_length:
            return self.content_text
        return self.content_text[:max_length] + "..."

    def get_mapped_status(self) -> str:
        """Get processing status mapped to frontend-compatible values"""
        status_mapping = {
            'pending': 'queued',
            'processing': 'processing',
            'completed': 'indexed',
            'failed': 'failed',
            'retrying': 'processing'  # Map retrying to processing
        }
        backend_status = self.processing_status.value if self.processing_status else None
        return status_mapping.get(backend_status, 'queued')

    def to_dict(self, include_content: bool = False) -> dict:
        """Convert to dictionary"""
        data = super().to_dict()

        # Convert enum values
        data['document_type'] = self.document_type.value if self.document_type else None

        # Map processing status to frontend-compatible lowercase values
        status_mapping = {
            'pending': 'queued',
            'processing': 'processing',
            'completed': 'indexed',
            'failed': 'failed'
        }
        backend_status = self.processing_status.value if self.processing_status else None
        data['processing_status'] = status_mapping.get(backend_status, 'queued')

        # Add computed fields
        data['file_size_mb'] = self.file_size_mb
        data['processing_duration_seconds'] = self.processing_duration_seconds
        data['is_processing_complete'] = self.is_processing_complete
        data['is_processing_successful'] = self.is_processing_successful
        data['can_be_searched'] = self.can_be_searched()

        # Include content if requested
        if not include_content:
            data.pop('content_text', None)

        # Remove sensitive fields
        data.pop('file_path', None)

        return data

    @classmethod
    def get_documents_by_type(cls, document_type: DocumentType) -> list:
        """Get documents by type"""
        return cls.query.filter(
            cls.document_type == document_type,
            cls.is_deleted == False
        ).all()

    @classmethod
    def get_processing_queue(cls, limit: int = 50) -> list:
        """Get documents in processing queue"""
        return cls.query.filter(
            cls.processing_status == ProcessingStatus.PENDING,
            cls.is_deleted == False
        ).order_by(cls.created_at).limit(limit).all()

    @classmethod
    def get_failed_documents(cls, retry_threshold: int = 3) -> list:
        """Get failed documents that haven't exceeded retry threshold"""
        return cls.query.filter(
            cls.processing_status == ProcessingStatus.FAILED,
            cls.processing_retry_count < retry_threshold,
            cls.is_deleted == False
        ).order_by(cls.processing_retry_count).all()