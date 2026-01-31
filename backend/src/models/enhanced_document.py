"""
Enhanced Document model with comprehensive multimodal metadata and processing capabilities
"""

import uuid
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from enum import Enum as PyEnum
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel
from .utils import StringArray


class DocumentModality(PyEnum):
    """Document modality types"""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PDF = "pdf"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    MULTIMODAL = "multimodal"


class ProcessingStage(PyEnum):
    """Document processing stages"""

    UPLOADED = "uploaded"
    VALIDATED = "validated"
    EXTRACTED = "extracted"
    INDEXED = "indexed"
    EMBEDDED = "embedded"
    ENRICHED = "enriched"
    COMPLETED = "completed"
    FAILED = "failed"


class QualityLevel(PyEnum):
    """Document quality levels"""

    HIGH = "high"  # >90% quality
    MEDIUM = "medium"  # 70-90% quality
    LOW = "low"  # 50-70% quality
    POOR = "poor"  # <50% quality


class EnhancedDocument(BaseModel):
    """Enhanced document model with comprehensive multimodal support"""

    __tablename__ = "enhanced_documents"

    # Basic document information
    title = Column(String(500), nullable=False, index=True)
    original_filename = Column(String(500), nullable=False)
    stored_filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    backup_path = Column(String(1000), nullable=True)

    # File characteristics
    file_size_bytes = Column(BigInteger, nullable=False, index=True)
    file_hash_md5 = Column(String(32), nullable=True, index=True)
    file_hash_sha256 = Column(String(64), nullable=True, index=True)
    mime_type = Column(String(100), nullable=False)
    file_extension = Column(String(10), nullable=False, index=True)

    # Document modality and classification
    primary_modality = Column(Enum(DocumentModality), nullable=False, index=True)
    modalities_present = Column(ARRAY(String), nullable=True)  # All modalities detected
    document_subtype = Column(
        String(50), nullable=True
    )  # Specific document type (e.g., "invoice", "contract")
    language_detected = Column(String(10), nullable=True, default="en")
    confidence_score = Column(Float, nullable=True)  # Confidence in classification

    # Ownership and access control
    organization_id = Column(
        GUID(), ForeignKey("organizations.id"), nullable=False, index=True
    )
    uploaded_by_user_id = Column(
        GUID(), ForeignKey("users.id"), nullable=False, index=True
    )
    owner_user_id = Column(GUID(), ForeignKey("users.id"), nullable=True, index=True)

    # Access permissions
    is_public = Column(Boolean, default=False, nullable=False)
    sharing_level = Column(
        String(20), nullable=False, default="private"
    )  # private, team, organization, public
    allowed_users = Column(ARRAY(GUID()), nullable=True)  # Specific users with access
    allowed_teams = Column(ARRAY(String), nullable=True)  # Teams with access
    access_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Document classification and tagging
    tags = Column(StringArray, nullable=True)
    categories = Column(StringArray, nullable=True)  # Hierarchical categories
    custom_attributes = Column(JSON, nullable=True)  # User-defined attributes
    domain_tags = Column(StringArray, nullable=True)  # Domain-specific tags
    sensitivity_level = Column(
        String(20), nullable=True, default="normal"
    )  # normal, sensitive, confidential

    # Processing information
    processing_status = Column(
        Enum(ProcessingStage),
        nullable=False,
        default=ProcessingStage.UPLOADED,
        index=True,
    )
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_duration_seconds = Column(Float, nullable=True)
    processing_priority = Column(Integer, default=5, nullable=False)  # 1-10 priority
    processing_queue = Column(String(50), nullable=True, default="default")

    # Processing errors and retries
    processing_errors = Column(JSON, nullable=True)  # List of processing errors
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)

    # Text content
    extracted_text = Column(Text, nullable=True)
    text_quality_score = Column(Float, nullable=True)  # Quality of OCR/text extraction
    text_language = Column(String(10), nullable=True)
    word_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)
    page_count = Column(Integer, nullable=True)

    # Full-text search
    search_vector = Column(
        TSVECTOR, nullable=True
    )  # PostgreSQL full-text search vector
    keywords_extracted = Column(StringArray, nullable=True)
    key_phrases = Column(StringArray, nullable=True)

    # Content analysis
    content_summary = Column(Text, nullable=True)  # AI-generated summary
    content_outline = Column(JSON, nullable=True)  # Document structure/outline
    topics_detected = Column(StringArray, nullable=True)  # Topics from content analysis
    sentiment_analysis = Column(JSON, nullable=True)  # Sentiment analysis results
    readability_score = Column(Float, nullable=True)
    complexity_score = Column(Float, nullable=True)

    # Vector and search integration
    embedding_id = Column(String(255), nullable=True, index=True)  # Qdrant vector ID
    embedding_model = Column(String(100), nullable=True)  # Model used for embedding
    embedding_dimensions = Column(Integer, nullable=True)
    embedding_created_at = Column(DateTime(timezone=True), nullable=True)
    is_embedded = Column(Boolean, default=False, nullable=False)
    is_indexed = Column(Boolean, default=False, nullable=False)

    # Multimodal content
    multimodal_content = Column(
        JSON, nullable=True
    )  # Information about non-text content
    extracted_images = Column(JSON, nullable=True)  # Information about extracted images
    extracted_audio = Column(JSON, nullable=True)  # Audio transcription information
    extracted_video = Column(JSON, nullable=True)  # Video analysis information
    extracted_tables = Column(JSON, nullable=True)  # Table extraction results
    extracted_charts = Column(JSON, nullable=True)  # Chart/diagram information

    # Entity extraction
    entities = Column(JSON, nullable=True)  # Named entities found in document
    entity_count = Column(Integer, default=0, nullable=False)
    relationships = Column(JSON, nullable=True)  # Relationships between entities
    knowledge_graph_nodes = Column(JSON, nullable=True)  # Neo4j node references

    # Quality metrics
    overall_quality_score = Column(Float, nullable=True, index=True)
    quality_level = Column(Enum(QualityLevel), nullable=True, index=True)
    quality_factors = Column(JSON, nullable=True)  # Factors affecting quality
    quality_evaluation_date = Column(DateTime(timezone=True), nullable=True)

    # Usage analytics
    view_count = Column(Integer, default=0, nullable=False)
    download_count = Column(Integer, default=0, nullable=False)
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)
    last_accessed_by_user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    search_hit_count = Column(Integer, default=0, nullable=False)
    average_relevance_score = Column(
        Float, nullable=True
    )  # Average relevance in search results

    # Version control
    version_number = Column(Integer, default=1, nullable=False)
    is_latest_version = Column(Boolean, default=True, nullable=False)
    parent_document_id = Column(
        GUID(), ForeignKey("enhanced_documents.id"), nullable=True
    )
    version_notes = Column(Text, nullable=True)

    # Retention and lifecycle
    retention_policy = Column(String(50), nullable=True)  # retention policy name
    expires_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    deleted_permanently_at = Column(DateTime(timezone=True), nullable=True)
    auto_delete_after_days = Column(Integer, nullable=True)

    # External integrations
    external_source = Column(String(100), nullable=True)  # Source system if imported
    external_id = Column(String(255), nullable=True)  # ID in external system
    sync_status = Column(String(20), nullable=True)  # synced, pending, error
    last_sync_at = Column(DateTime(timezone=True), nullable=True)

    # Compliance and security
    compliance_tags = Column(StringArray, nullable=True)  # GDPR, HIPAA, etc.
    data_classification = Column(
        String(50), nullable=True
    )  # public, internal, confidential, restricted
    encryption_status = Column(String(20), nullable=True)  # encrypted, partial, none
    audit_log_entries = Column(JSON, nullable=True)  # Recent audit events

    # Relationships
    organization = relationship("Organization", back_populates="enhanced_documents")
    uploaded_by_user = relationship(
        "User", foreign_keys=[uploaded_by_user_id], back_populates="uploaded_documents"
    )
    owner_user = relationship(
        "User", foreign_keys=[owner_user_id], back_populates="owned_documents"
    )
    last_accessed_by_user = relationship(
        "User", foreign_keys=[last_accessed_by_user_id]
    )
    parent_document = relationship(
        "EnhancedDocument", remote_side=[id], backref="child_versions"
    )

    # Processing relationships
    processing_jobs = relationship(
        "ProcessingJob", back_populates="document", cascade="all, delete-orphan"
    )
    quality_metrics = relationship(
        "DocumentQualityMetrics",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    access_logs = relationship(
        "DocumentAccessLog", back_populates="document", cascade="all, delete-orphan"
    )

    # Analytics relationships
    search_results = relationship(
        "SearchResult", back_populates="document", cascade="all, delete-orphan"
    )
    feedback_entries = relationship(
        "DocumentFeedback", back_populates="document", cascade="all, delete-orphan"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_documents_org_status", "organization_id", "processing_status"),
        Index("idx_documents_user_uploaded", "uploaded_by_user_id", "created_at"),
        Index("idx_documents_modality_quality", "primary_modality", "quality_level"),
        Index("idx_documents_tags", "tags"),
        Index("idx_documents_search", "search_vector"),
        Index("idx_documents_embedding", "embedding_id"),
        Index("idx_documents_expiry", "expires_at"),
        Index("idx_documents_file_hash", "file_hash_sha256"),
        Index("idx_documents_quality", "overall_quality_score"),
    )

    def __repr__(self):
        return f"<EnhancedDocument(id={self.id}, title={self.title}, modality={self.primary_modality.value}, status={self.processing_status.value})>"

    @property
    def file_size_mb(self) -> float:
        """Get file size in MB"""
        return self.file_size_bytes / (1024 * 1024)

    @property
    def is_processing_complete(self) -> bool:
        """Check if processing is complete"""
        return self.processing_status in [
            ProcessingStage.COMPLETED,
            ProcessingStage.FAILED,
        ]

    @property
    def is_processing_successful(self) -> bool:
        """Check if processing was successful"""
        return self.processing_status == ProcessingStage.COMPLETED

    @property
    def can_be_searched(self) -> bool:
        """Check if document can be searched"""
        return (
            self.is_processing_successful()
            and self.is_embedded
            and self.is_indexed
            and not self.is_deleted
        )

    @property
    def is_expired(self) -> bool:
        """Check if document has expired"""
        return self.expires_at and datetime.utcnow() > self.expires_at

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Get days until expiry"""
        if not self.expires_at:
            return None
        if self.is_expired:
            return 0
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)

    @property
    def processing_progress(self) -> Dict[str, Any]:
        """Get processing progress information"""
        stage_progress = {
            ProcessingStage.UPLOADED: 0,
            ProcessingStage.VALIDATED: 10,
            ProcessingStage.EXTRACTED: 30,
            ProcessingStage.INDEXED: 60,
            ProcessingStage.EMBEDDED: 80,
            ProcessingStage.ENRICHED: 95,
            ProcessingStage.COMPLETED: 100,
            ProcessingStage.FAILED: 0,
        }

        return {
            "current_stage": self.processing_status.value,
            "progress_percentage": stage_progress.get(self.processing_status, 0),
            "duration_seconds": self.processing_duration_seconds,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    @property
    def multimodal_summary(self) -> Dict[str, Any]:
        """Get summary of multimodal content"""
        summary = {
            "primary_modality": self.primary_modality.value,
            "modalities_present": self.modalities_present or [],
            "has_text": bool(self.extracted_text),
            "has_images": bool(self.extracted_images),
            "has_audio": bool(self.extracted_audio),
            "has_video": bool(self.extracted_video),
            "has_tables": bool(self.extracted_tables),
            "has_charts": bool(self.extracted_charts),
        }

        # Count content types
        content_counts = {}
        if self.extracted_images:
            content_counts["images"] = len(self.extracted_images)
        if self.extracted_audio:
            content_counts["audio_segments"] = len(self.extracted_audio)
        if self.extracted_video:
            content_counts["video_segments"] = len(self.extracted_video)
        if self.extracted_tables:
            content_counts["tables"] = len(self.extracted_tables)
        if self.extracted_charts:
            content_counts["charts"] = len(self.extracted_charts)

        summary["content_counts"] = content_counts
        return summary

    def update_processing_status(
        self, status: ProcessingStage, error_message: str = None
    ):
        """Update processing status with timestamp and error handling"""
        self.processing_status = status

        if status == ProcessingStage.VALIDATED and not self.processing_started_at:
            self.processing_started_at = datetime.utcnow()
        elif status in [ProcessingStage.COMPLETED, ProcessingStage.FAILED]:
            self.processing_completed_at = datetime.utcnow()
            if self.processing_started_at:
                self.processing_duration_seconds = (
                    self.processing_completed_at - self.processing_started_at
                ).total_seconds()

        if error_message:
            if not self.processing_errors:
                self.processing_errors = []
            self.processing_errors.append(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "stage": status.value,
                    "message": error_message,
                }
            )

    def add_processing_error(
        self,
        stage: ProcessingStage,
        error_message: str,
        error_details: Dict[str, Any] = None,
    ):
        """Add a processing error"""
        if not self.processing_errors:
            self.processing_errors = []

        error_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "stage": stage.value,
            "message": error_message,
            "retry_count": self.retry_count,
        }

        if error_details:
            error_entry["details"] = error_details

        self.processing_errors.append(error_entry)

    def calculate_quality_score(self):
        """Calculate overall document quality score"""
        quality_factors = {}

        # Text quality (30% weight)
        text_quality = 0.0
        if self.text_quality_score:
            text_quality = self.text_quality_score
        elif self.extracted_text and len(self.extracted_text.strip()) > 0:
            text_quality = 0.8  # Good default if text exists
        quality_factors["text_quality"] = text_quality * 0.3

        # Processing completeness (25% weight)
        processing_quality = 0.0
        if self.is_processing_successful():
            processing_quality = 1.0
        elif self.processing_status in [
            ProcessingStage.INDEXED,
            ProcessingStage.EMBEDDED,
        ]:
            processing_quality = 0.7
        elif self.processing_status == ProcessingStage.EXTRACTED:
            processing_quality = 0.5
        quality_factors["processing_quality"] = processing_quality * 0.25

        # Content richness (20% weight)
        content_quality = 0.0
        if self.multimodal_content:
            modality_count = (
                len(self.modalities_present) if self.modalities_present else 1
            )
            content_quality = min(
                1.0, modality_count / 3
            )  # Max quality at 3+ modalities
        elif self.extracted_text and len(self.extracted_text) > 100:
            content_quality = 0.6
        elif self.extracted_text:
            content_quality = 0.3
        quality_factors["content_quality"] = content_quality * 0.2

        # Entity extraction (15% weight)
        entity_quality = 0.0
        if self.entity_count > 10:
            entity_quality = 1.0
        elif self.entity_count > 5:
            entity_quality = 0.7
        elif self.entity_count > 0:
            entity_quality = 0.4
        quality_factors["entity_quality"] = entity_quality * 0.15

        # Metadata completeness (10% weight)
        metadata_quality = 0.0
        metadata_fields = [self.title, self.tags, self.categories, self.topics_detected]
        completed_fields = sum(1 for field in metadata_fields if field)
        metadata_quality = completed_fields / len(metadata_fields)
        quality_factors["metadata_quality"] = metadata_quality * 0.1

        # Calculate overall score
        self.overall_quality_score = sum(quality_factors.values())
        self.quality_factors = quality_factors

        # Determine quality level
        if self.overall_quality_score >= 0.9:
            self.quality_level = QualityLevel.HIGH
        elif self.overall_quality_score >= 0.7:
            self.quality_level = QualityLevel.MEDIUM
        elif self.overall_quality_score >= 0.5:
            self.quality_level = QualityLevel.LOW
        else:
            self.quality_level = QualityLevel.POOR

        self.quality_evaluation_date = datetime.utcnow()

    def add_access_event(
        self, user_id: uuid.UUID, action: str, metadata: Dict[str, Any] = None
    ):
        """Add document access event"""
        access_log = DocumentAccessLog(
            document_id=self.id, user_id=user_id, action=action, metadata=metadata
        )
        # Note: In actual implementation, this would be saved to database

        # Update counters
        if action == "view":
            self.view_count += 1
            self.last_viewed_at = datetime.utcnow()
            self.last_accessed_by_user_id = user_id
        elif action == "download":
            self.download_count += 1

    def add_tags(self, tags: List[str]):
        """Add tags to document"""
        if not self.tags:
            self.tags = []
        # Remove duplicates and preserve order
        unique_tags = []
        for tag in tags + self.tags:
            if tag not in unique_tags:
                unique_tags.append(tag)
        self.tags = unique_tags

    def remove_tags(self, tags: List[str]):
        """Remove tags from document"""
        if not self.tags:
            return
        for tag in tags:
            if tag in self.tags:
                self.tags.remove(tag)

    def can_user_access(self, user_id: uuid.UUID, user_teams: List[str] = None) -> bool:
        """Check if user can access this document"""
        # Owner can always access
        if self.owner_user_id == user_id or self.uploaded_by_user_id == user_id:
            return True

        # Public documents can be accessed by anyone
        if self.is_public or self.sharing_level == "public":
            return True

        # Organization-level access
        if self.sharing_level == "organization":
            return (
                True  # Assuming user is in same organization (handled at query level)
            )

        # Team-level access
        if self.sharing_level == "team" and user_teams:
            return (
                any(team in self.allowed_teams for team in user_teams)
                if self.allowed_teams
                else False
            )

        # Specific user access
        if self.allowed_users:
            return user_id in self.allowed_users

        return False

    def to_dict(
        self, include_content: bool = False, include_processing_details: bool = False
    ) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict()

        # Convert enum values
        data.update(
            {
                "primary_modality": self.primary_modality.value
                if self.primary_modality
                else None,
                "processing_status": self.processing_status.value
                if self.processing_status
                else None,
                "quality_level": self.quality_level.value
                if self.quality_level
                else None,
            }
        )

        # Add computed properties
        data.update(
            {
                "file_size_mb": self.file_size_mb,
                "is_processing_complete": self.is_processing_complete,
                "is_processing_successful": self.is_processing_successful,
                "can_be_searched": self.can_be_searched,
                "is_expired": self.is_expired,
                "days_until_expiry": self.days_until_expiry,
                "processing_progress": self.processing_progress,
                "multimodal_summary": self.multimodal_summary,
            }
        )

        # Include/exclude content based on parameters
        if not include_content:
            data.pop("extracted_text", None)
            data.pop("content_summary", None)

        if not include_processing_details:
            data.pop("processing_errors", None)
            data.pop("quality_factors", None)

        # Remove sensitive fields
        data.pop("file_path", None)
        data.pop("backup_path", None)
        data.pop("stored_filename", None)

        return data

    @classmethod
    def get_documents_by_modality(
        cls, modality: DocumentModality, organization_id: Optional[uuid.UUID] = None
    ) -> List:
        """Get documents by modality"""
        query = cls.query.filter(
            cls.primary_modality == modality, cls.is_deleted == False
        )

        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        return query.all()

    @classmethod
    def get_expired_documents(cls, organization_id: Optional[uuid.UUID] = None) -> List:
        """Get expired documents"""
        query = cls.query.filter(
            cls.expires_at < datetime.utcnow(), cls.is_deleted == False
        )

        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        return query.all()

    @classmethod
    def get_high_quality_documents(
        cls,
        organization_id: Optional[uuid.UUID] = None,
        min_quality: QualityLevel = QualityLevel.HIGH,
    ) -> List:
        """Get high-quality documents"""
        query = cls.query.filter(
            cls.quality_level >= min_quality, cls.is_deleted == False
        ).order_by(cls.overall_quality_score.desc())

        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        return query.all()

    @classmethod
    def search_by_content(
        cls,
        search_text: str,
        organization_id: Optional[uuid.UUID] = None,
        limit: int = 50,
    ) -> List:
        """Full-text search in document content"""
        from sqlalchemy import func

        query = cls.query.filter(
            cls.search_vector.match(search_text), cls.is_deleted == False
        )

        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        return query.limit(limit).all()


class DocumentQualityMetrics(BaseModel):
    """Detailed quality metrics for documents"""

    __tablename__ = "document_quality_metrics"

    document_id = Column(GUID(), ForeignKey("enhanced_documents.id"), nullable=False)

    # Text quality metrics
    ocr_confidence = Column(Float, nullable=True)
    text_completeness = Column(
        Float, nullable=True
    )  # How complete the text extraction is
    text_accuracy = Column(Float, nullable=True)  # Accuracy of extracted text
    formatting_preserved = Column(
        Float, nullable=True
    )  # How well formatting was preserved

    # Content quality metrics
    content_coherence = Column(Float, nullable=True)
    information_density = Column(Float, nullable=True)
    topical_relevance = Column(Float, nullable=True)
    language_quality = Column(Float, nullable=True)

    # Technical quality metrics
    resolution_quality = Column(Float, nullable=True)  # For images/videos
    audio_quality = Column(Float, nullable=True)  # For audio content
    compression_artifacts = Column(Float, nullable=True)  # Compression quality issues

    # Processing quality metrics
    extraction_success_rate = Column(Float, nullable=True)
    entity_extraction_accuracy = Column(Float, nullable=True)
    classification_confidence = Column(Float, nullable=True)

    # Evaluation metadata
    evaluated_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    evaluation_model = Column(String(100), nullable=True)
    evaluation_version = Column(String(50), nullable=True)

    # Relationships
    document = relationship("EnhancedDocument", back_populates="quality_metrics")


class DocumentAccessLog(BaseModel):
    """Document access and usage logging"""

    __tablename__ = "document_access_logs"

    document_id = Column(GUID(), ForeignKey("enhanced_documents.id"), nullable=False)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # Access details
    action = Column(String(50), nullable=False)  # view, download, share, edit, delete
    access_method = Column(String(50), nullable=True)  # web, api, mobile, sync
    session_id = Column(String(255), nullable=True)

    # Request information
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    referer = Column(String(500), nullable=True)

    # Access metadata
    access_timestamp = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    duration_seconds = Column(Integer, nullable=True)  # For view actions
    bytes_transferred = Column(Integer, nullable=True)
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)

    # Additional context
    search_query_id = Column(GUID(), nullable=True)  # If accessed via search
    access_metadata = Column(
        JSON, nullable=True
    )  # Renamed from 'metadata' to avoid SQLAlchemy conflict

    # Relationships
    document = relationship("EnhancedDocument", back_populates="access_logs")
    user = relationship("User")


class DocumentFeedback(BaseModel):
    """User feedback on documents"""

    __tablename__ = "document_feedback"

    document_id = Column(GUID(), ForeignKey("enhanced_documents.id"), nullable=False)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # Feedback details
    feedback_type = Column(
        String(50), nullable=False
    )  # quality, relevance, accuracy, completeness
    rating = Column(Integer, nullable=False)  # 1-5 rating
    feedback_text = Column(Text, nullable=True)
    feedback_categories = Column(StringArray, nullable=True)

    # Specific feedback aspects
    content_quality = Column(Integer, nullable=True)
    extraction_quality = Column(Integer, nullable=True)
    usefulness = Column(Integer, nullable=True)
    accuracy = Column(Integer, nullable=True)

    # Feedback metadata
    feedback_timestamp = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    context = Column(JSON, nullable=True)  # Context in which feedback was given
    helpful = Column(Boolean, nullable=True)

    # Relationships
    document = relationship("EnhancedDocument", back_populates="feedback_entries")
    user = relationship("User")
