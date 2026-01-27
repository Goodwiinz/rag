"""
Database models for the multimodal RAG system
"""

from .base import Base, BaseModel
from .user import User, UserRole
from .organization import Organization, StorageTier
from .document import Document, DocumentType, ProcessingStatus
from .entity import Entity, EntityType, ExtractionMethod, entity_relationships
from .search import SearchQuery, SearchResult, SearchType
from .quality_metrics import SearchSession
from .processing import ProcessingJob, JobType, JobStatus, JobPriority
from .quality import QualityMetric, MetricType, EvaluationType, MetricScope

# Thread-centric chat models (Terminal Observatory)
from .workspace import Workspace, WorkspaceMember, WorkspaceRole
from .conversation import Conversation
from .thread import Thread, ThreadStatus
from .chat_message import ChatMessage, MessageRole
from .collection import Collection, CollectionDocument
from .citation import Citation
from .message_attachment import MessageAttachment

# Research Assistant models
from .citation_relationship import CitationRelationship
from .project_note import ProjectNote
from .generated_draft import GeneratedDraft
from .draft_citation import DraftCitation
from .project_thread import ProjectThread, ProjectThreadLinkType

# Permission and role models
from .permission import Permission, Role, UserRoleAssignment, PermissionCategory, PermissionScope

# Encrypted user models
from .encrypted_user import EncryptedUserProfile, EncryptedOrganizationProfile, EncryptionAuditLog

# Audit models
from .audit import AuditEvent, ComplianceReport, DataRetentionPolicy, SecurityIncident, AuditEventType, AuditSeverity

# Enhanced document processing models
from .document_processing import (
    ProcessingHistory, ProcessingStage,
    DocumentVersion,
    MultimodalContent, ContentType,
    DocumentQualityMetrics, QualityMetricType,
    DocumentAccessLog
)

# Analytics models (import after base models to avoid circular dependencies)
from .user_session import UserSession, SessionStatus
from .analytics_event import AnalyticsEvent, EventType, EventSeverity
from .performance_log import PerformanceLog, MetricCategory, PerformanceLevel

# Export all models for easy importing
__all__ = [
    # Base classes
    "Base",
    "BaseModel",

    # User models
    "User",
    "UserRole",

    # Organization models
    "Organization",
    "StorageTier",

    # Document models
    "Document",
    "DocumentType",
    "ProcessingStatus",

    # Entity models
    "Entity",
    "EntityType",
    "ExtractionMethod",
    "entity_relationships",

    # Search models
    "SearchQuery",
    "SearchResult",
    "SearchType",
    "SearchSession",

    # Processing models
    "ProcessingJob",
    "JobType",
    "JobStatus",
    "JobPriority",

    # Quality models
    "QualityMetric",
    "MetricType",
    "EvaluationType",
    "MetricScope",

    # Thread-centric chat models (Terminal Observatory)
    "Workspace",
    "WorkspaceMember",
    "WorkspaceRole",
    "Conversation",
    "Thread",
    "ThreadStatus",
    "ChatMessage",
    "MessageRole",
    "Collection",
    "CollectionDocument",
    "Citation",
    "MessageAttachment",

    # Research Assistant models
    "CitationRelationship",
    "ProjectNote",
    "GeneratedDraft",
    "DraftCitation",
    "ProjectThread",
    "ProjectThreadLinkType",

    # Permission and role models
    "Permission",
    "Role",
    "UserRoleAssignment",
    "PermissionCategory",
    "PermissionScope",

    # Encrypted user models
    "EncryptedUserProfile",
    "EncryptedOrganizationProfile",
    "EncryptionAuditLog",

    # Audit models
    "AuditEvent",
    "ComplianceReport",
    "DataRetentionPolicy",
    "SecurityIncident",
    "AuditEventType",
    "AuditSeverity",

    # Analytics models
    "UserSession",
    "SessionStatus",
    "AnalyticsEvent",
    "EventType",
    "EventSeverity",
    "PerformanceLog",
    "MetricCategory",
    "PerformanceLevel",

    # Enhanced document processing models
    "ProcessingHistory",
    "ProcessingStage",
    "DocumentVersion",
    "MultimodalContent",
    "ContentType",
    "DocumentQualityMetrics",
    "QualityMetricType",
    "DocumentAccessLog",
]