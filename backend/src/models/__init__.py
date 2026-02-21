"""
Database models for the multimodal RAG system
"""

# A/B Testing models (import after User and Organization to avoid circular dependencies)
from .ab_testing import (
    Experiment,
    ExperimentAssignment,
    ExperimentMetric,
    ExperimentSegment,
    ExperimentStatus,
    ExperimentType,
    Variant,
)
from .analytics_event import AnalyticsEvent, EventSeverity, EventType

# Audit models
from .audit import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    ComplianceReport,
    DataRetentionPolicy,
    SecurityIncident,
)
from .base import Base, BaseModel
from .chat_message import ChatMessage, MessageRole
from .citation import Citation

# Research Assistant models
from .citation_relationship import CitationRelationship
from .collection import Collection, CollectionDocument
from .conversation import Conversation
from .document import Document, DocumentType, ProcessingStatus

# Enhanced document processing models
from .document_processing import (
    ContentType,
    DocumentAccessLog,
    DocumentQualityMetrics,
    DocumentVersion,
    MultimodalContent,
    ProcessingHistory,
    ProcessingStage,
    QualityMetricType,
)
from .draft_citation import DraftCitation

# Encrypted user models
from .encrypted_user import (
    EncryptedOrganizationProfile,
    EncryptedUserProfile,
    EncryptionAuditLog,
)
from .entity import Entity, EntityType, ExtractionMethod, entity_relationships
from .extraction_matrix import ExtractionCell, ExtractionMatrix
from .integrity_score import IntegrityScore
from .generated_draft import GeneratedDraft
from .message_attachment import MessageAttachment
from .organization import Organization, StorageTier
from .performance_log import MetricCategory, PerformanceLevel, PerformanceLog

# Permission and role models
from .permission import (
    Permission,
    PermissionCategory,
    PermissionScope,
    Role,
    UserRoleAssignment,
)
from .processing import JobPriority, JobStatus, JobType, ProcessingJob
from .project_note import ProjectNote
from .project_thread import ProjectThread, ProjectThreadLinkType
from .quality import EvaluationType, MetricScope, MetricType, QualityMetric
from .quality_metrics import SearchSession
from .search import SearchQuery, SearchResult, SearchType
from .thread import Thread, ThreadStatus
from .user import User, UserRole

# Analytics models (import after base models to avoid circular dependencies)
from .user_session import SessionStatus, UserSession

# Research Engine models
from .research_blueprint import ResearchBlueprint
from .research_evidence import GroundingStatus, ResearchEvidence
from .research_project import ResearchProject
from .research_run import ResearchRun, RunStatus
from .research_source import ResearchSource
from .research_step import ExecutionMode, ResearchStep, StepType

# Thread-centric chat models (Terminal Observatory)
from .workspace import Workspace, WorkspaceMember, WorkspaceRole

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
    # A/B Testing models
    "Experiment",
    "ExperimentStatus",
    "ExperimentType",
    "Variant",
    "ExperimentAssignment",
    "ExperimentMetric",
    "ExperimentSegment",
    # Extraction Matrix models
    "ExtractionMatrix",
    "ExtractionCell",
    # Integrity Score models
    "IntegrityScore",
    # Research Engine models
    "ResearchProject",
    "ResearchBlueprint",
    "ResearchRun",
    "RunStatus",
    "ResearchStep",
    "StepType",
    "ExecutionMode",
    "ResearchSource",
    "ResearchEvidence",
    "GroundingStatus",
]
