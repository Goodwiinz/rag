"""
AI-Powered Document Analysis and Q&A System Models

This module contains SQLAlchemy models and Pydantic schemas for the document Q&A system,
including conversations, messages, analysis results, caching, and user interactions.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, validator
from sqlalchemy import DATE, JSON, Array, BigInteger, Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from ..base import GUID
from ..base import BaseModel as SQLBaseModel

# ============================================================================
# ENUMS
# ============================================================================


class ConversationType(str, Enum):
    """Types of conversations supported"""

    DOCUMENT_QA = "document_qa"
    GENERAL_INQUIRY = "general_inquiry"
    ANALYSIS_SESSION = "analysis_session"
    REVIEW_SESSION = "review_session"
    COLLABORATIVE_DISCUSSION = "collaborative_discussion"
    EXPERT_CONSULTATION = "expert_consultation"


class ConversationStatus(str, Enum):
    """Status of conversations"""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MessageType(str, Enum):
    """Types of messages in conversations"""

    QUESTION = "question"
    ANSWER = "answer"
    CLARIFICATION = "clarification"
    FOLLOW_UP = "follow_up"
    SUMMARY = "summary"
    FEEDBACK = "feedback"
    SYSTEM_MESSAGE = "system_message"
    ERROR_MESSAGE = "error_message"


class SourceType(str, Enum):
    """Source types for messages"""

    USER = "user"
    AI_ASSISTANT = "ai_assistant"
    SYSTEM = "system"
    IMPORT = "import"
    TEMPLATE = "template"


class ContentType(str, Enum):
    """Content types for messages"""

    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"


class ParticipantRole(str, Enum):
    """Roles for conversation participants"""

    OWNER = "owner"
    MODERATOR = "moderator"
    PARTICIPANT = "participant"
    VIEWER = "viewer"
    AI_ASSISTANT = "ai_assistant"


class ParticipantStatus(str, Enum):
    """Status of conversation participants"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"
    LEFT = "left"


class AnalysisType(str, Enum):
    """Types of document analysis"""

    CONTENT_SUMMARY = "content_summary"
    KEY_TOPICS = "key_topics"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    READABILITY_SCORE = "readability_score"
    ENTITY_EXTRACTION = "entity_extraction"
    RELATIONSHIP_ANALYSIS = "relationship_analysis"
    CONTENT_CLASSIFICATION = "content_classification"
    QUALITY_ASSESSMENT = "quality_assessment"
    COMPLIANCE_CHECK = "compliance_check"
    RISK_ASSESSMENT = "risk_assessment"
    FACT_EXTRACTION = "fact_extraction"
    INSIGHT_GENERATION = "insight_generation"
    RECOMMENDATION_ENGINE = "recommendation_engine"


class AnalysisStatus(str, Enum):
    """Status of analysis results"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class FeedbackType(str, Enum):
    """Types of feedback on analysis results"""

    ACCURACY_RATING = "accuracy_rating"
    USEFULNESS_RATING = "usefulness_rating"
    CORRECTION = "correction"
    SUGGESTION = "suggestion"
    ADDITIONAL_INSIGHT = "additional_insight"
    ERROR_REPORT = "error_report"
    FEATURE_REQUEST = "feature_request"


class QuestionType(str, Enum):
    """Types of questions"""

    FACTUAL = "factual"
    ANALYTICAL = "analytical"
    OPINION = "opinion"
    PROCEDURAL = "procedural"
    COMPARATIVE = "comparative"
    EXPLANATORY = "explanatory"
    PREDICTIVE = "predictive"
    EVALUATIVE = "evaluative"
    CREATIVE = "creative"


class QuestionComplexity(str, Enum):
    """Complexity levels of questions"""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    EXPERT = "expert"


class AnswerType(str, Enum):
    """Types of answers"""

    TEXT = "text"
    STRUCTURED = "structured"
    LIST = "list"
    COMPARISON = "comparison"
    TIMELINE = "timeline"
    HIERARCHY = "hierarchy"


class VerificationStatus(str, Enum):
    """Verification status of cached answers"""

    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    DISPUTED = "disputed"


class CacheStatus(str, Enum):
    """Status of cache entries"""

    ACTIVE = "active"
    STALE = "stale"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    DEPRECATED = "deprecated"


class InvalidationRuleType(str, Enum):
    """Types of cache invalidation rules"""

    DOCUMENT_CHANGE = "document_change"
    TIME_BASED = "time_based"
    USAGE_THRESHOLD = "usage_threshold"
    QUALITY_THRESHOLD = "quality_threshold"
    MANUAL_INVALIDATION = "manual_invalidation"
    MODEL_UPDATE = "model_update"
    SCHEMA_CHANGE = "schema_change"


class InvalidationActionType(str, Enum):
    """Actions for cache invalidation"""

    EXPIRE = "expire"
    DELETE = "delete"
    REFRESH = "refresh"
    FLAG_FOR_REVIEW = "flag_for_review"


class InteractionType(str, Enum):
    """Types of user interactions"""

    QUESTION_ASKED = "question_asked"
    ANSWER_VIEWED = "answer_viewed"
    ANSWER_RATED = "answer_rated"
    CONVERSATION_STARTED = "conversation_started"
    CONVERSATION_ENDED = "conversation_ended"
    DOCUMENT_REFERENCED = "document_referenced"
    ANALYSIS_REQUESTED = "analysis_requested"
    FEEDBACK_PROVIDED = "feedback_provided"
    SEARCH_PERFORMED = "search_performed"
    RESULT_CLICKED = "result_clicked"
    FILTER_APPLIED = "filter_applied"
    EXPORT_PERFORMED = "export_performed"
    SHARE_ACTION = "share_action"
    BOOKMARK_ADDED = "bookmark_added"


class ClientType(str, Enum):
    """Types of client applications"""

    WEB = "web"
    MOBILE = "mobile"
    API = "api"
    CLI = "cli"
    INTEGRATION = "integration"


class MetricPeriod(str, Enum):
    """Periods for engagement metrics"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class GapType(str, Enum):
    """Types of knowledge gaps"""

    MISSING_INFORMATION = "missing_information"
    OUTDATED_CONTENT = "outdated_content"
    POOR_QUALITY_ANSWERS = "poor_quality_answers"
    UNANSWERED_QUESTIONS = "unanswered_questions"
    LOW_CONFIDENCE_RESPONSES = "low_confidence_responses"
    USER_CONFUSION = "user_confusion"


class GapStatus(str, Enum):
    """Status of knowledge gaps"""

    IDENTIFIED = "identified"
    INVESTIGATING = "investigating"
    ADDRESSING = "addressing"
    RESOLVED = "resolved"
    DEFERRED = "deferred"


class ImpactSeverity(str, Enum):
    """Impact severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActivityLevel(str, Enum):
    """Activity level classifications"""

    VERY_ACTIVE = "very_active"
    ACTIVE = "active"
    RECENT = "recent"
    INACTIVE = "inactive"


# ============================================================================
# SQLALCHEMY MODELS
# ============================================================================


class DocumentConversation(SQLBaseModel):
    """Model for document conversations"""

    __tablename__ = "document_conversations"

    # Basic information
    title = Column(String(500), nullable=False)
    description = Column(Text)
    conversation_type = Column(
        SQLEnum(ConversationType), default=ConversationType.DOCUMENT_QA
    )

    # Document association
    document_id = Column(GUID(), ForeignKey("documents.id"), nullable=False)

    # Context and scope
    conversation_context = Column(JSONB, default={})
    language = Column(String(10), default="en")

    # Status and lifecycle
    status = Column(SQLEnum(ConversationStatus), default=ConversationStatus.ACTIVE)

    # Participant management
    participant_count = Column(Integer, default=1)
    is_public = Column(Boolean, default=False)
    is_moderated = Column(Boolean, default=False)

    # AI configuration
    ai_model_config = Column(JSONB, default={})
    response_style = Column(String(50), default="professional")

    # Organization and user
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    created_by_user_id = Column(GUID(), ForeignKey("users.id"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_activity_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    document = relationship("Document", back_populates="conversations")
    messages = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    participants = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    created_by_user = relationship("User")
    organization = relationship("Organization")


class ConversationMessage(SQLBaseModel):
    """Model for conversation messages"""

    __tablename__ = "conversation_messages"

    # Message identification
    conversation_id = Column(
        GUID(), ForeignKey("document_conversations.id"), nullable=False
    )
    message_sequence = Column(Integer, nullable=False)

    # Message content
    message_type = Column(SQLEnum(MessageType), nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(SQLEnum(ContentType), default=ContentType.TEXT)

    # Message metadata
    word_count = Column(Integer, default=0)
    character_count = Column(Integer, default=0)
    language = Column(String(10), default="en")

    # Source and context
    source_type = Column(SQLEnum(SourceType), default=SourceType.USER)
    source_id = Column(GUID())

    # Document references
    referenced_document_sections = Column(JSONB, default=[])
    referenced_entities = Column(JSONB, default=[])

    # AI processing metadata
    ai_model_used = Column(String(100))
    processing_time_ms = Column(Integer)
    confidence_score = Column(Float)

    # Feedback and quality
    user_rating = Column(Integer)
    user_feedback = Column(Text)
    is_helpful = Column(Boolean)

    # Visibility and status
    is_visible = Column(Boolean, default=True)
    is_edited = Column(Boolean, default=False)
    edited_at = Column(DateTime(timezone=True))
    edit_reason = Column(Text)

    # Organization and user
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    created_by_user_id = Column(GUID(), ForeignKey("users.id"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    conversation = relationship("DocumentConversation", back_populates="messages")
    created_by_user = relationship("User")
    organization = relationship("Organization")


class ConversationParticipant(SQLBaseModel):
    """Model for conversation participants"""

    __tablename__ = "conversation_participants"

    # Participant identification
    conversation_id = Column(
        GUID(), ForeignKey("document_conversations.id"), nullable=False
    )
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # Participant role
    role = Column(SQLEnum(ParticipantRole), default=ParticipantRole.PARTICIPANT)

    # Participation status
    status = Column(SQLEnum(ParticipantStatus), default=ParticipantStatus.ACTIVE)

    # Activity tracking
    message_count = Column(Integer, default=0)
    last_activity_at = Column(DateTime(timezone=True))
    joined_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    left_at = Column(DateTime(timezone=True))

    # Preferences and settings
    notification_preferences = Column(JSONB, default={})
    display_preferences = Column(JSONB, default={})

    # Organization
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    conversation = relationship("DocumentConversation", back_populates="participants")
    user = relationship("User")
    organization = relationship("Organization")


class DocumentAnalysisResult(SQLBaseModel):
    """Model for document analysis results"""

    __tablename__ = "document_analysis_results"

    # Analysis identification
    document_id = Column(GUID(), ForeignKey("documents.id"), nullable=False)
    analysis_type = Column(SQLEnum(AnalysisType), nullable=False)
    analysis_version = Column(String(50), default="1.0")

    # Analysis results
    results = Column(JSONB, nullable=False)
    insights = Column(JSONB, default=[])
    recommendations = Column(JSONB, default=[])

    # Quality and confidence metrics
    confidence_score = Column(Float)
    quality_score = Column(Float)
    completeness_score = Column(Float)

    # Processing metadata
    ai_model_used = Column(String(100), nullable=False)
    processing_time_ms = Column(Integer)
    computational_cost = Column(Float)

    # Analysis scope and parameters
    analysis_scope = Column(JSONB, default={})
    analysis_parameters = Column(JSONB, default={})
    data_sources = Column(JSONB, default=[])

    # Validation and verification
    is_validated = Column(Boolean, default=False)
    validated_by_user_id = Column(GUID(), ForeignKey("users.id"))
    validation_notes = Column(Text)

    # Status
    status = Column(SQLEnum(AnalysisStatus), default=AnalysisStatus.COMPLETED)
    error_message = Column(Text)

    # Organization
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    expires_at = Column(DateTime(timezone=True))
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    document = relationship("Document", back_populates="analysis_results")
    validated_by_user = relationship("User")
    feedback = relationship(
        "AnalysisFeedback",
        back_populates="analysis_result",
        cascade="all, delete-orphan",
    )
    organization = relationship("Organization")


class AnalysisFeedback(SQLBaseModel):
    """Model for analysis feedback"""

    __tablename__ = "analysis_feedback"

    # Feedback identification
    analysis_result_id = Column(
        GUID(), ForeignKey("document_analysis_results.id"), nullable=False
    )

    # Feedback provider
    user_id = Column(GUID(), ForeignKey("users.id"))
    feedback_type = Column(SQLEnum(FeedbackType), nullable=False)

    # Feedback content
    rating = Column(Integer)
    feedback_text = Column(Text)

    # Specific feedback details
    corrected_data = Column(JSONB)
    suggested_improvements = Column(JSONB, default=[])

    # System processing
    is_processed = Column(Boolean, default=False)
    processed_by_user_id = Column(GUID(), ForeignKey("users.id"))
    processing_notes = Column(Text)

    # Impact assessment
    impact_score = Column(Float)

    # Organization
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    analysis_result = relationship("DocumentAnalysisResult", back_populates="feedback")
    user = relationship("User", foreign_keys=[user_id])
    processed_by_user = relationship("User", foreign_keys=[processed_by_user_id])
    organization = relationship("Organization")


class QACache(SQLBaseModel):
    """Model for Q&A cache"""

    __tablename__ = "qa_cache"

    # Question identification and normalization
    question_hash = Column(String(64), nullable=False)
    normalized_question = Column(Text, nullable=False)
    original_question = Column(Text, nullable=False)

    # Question analysis
    question_type = Column(SQLEnum(QuestionType), nullable=False)
    question_complexity = Column(
        SQLEnum(QuestionComplexity), default=QuestionComplexity.MEDIUM
    )
    question_domain = Column(String(100))

    # Context specification
    context_document_ids = Column(Array(GUID()), default=[])
    context_entity_names = Column(Array(String), default=[])
    context_tags = Column(Array(String), default=[])

    # Answer information
    cached_answer = Column(Text, nullable=False)
    answer_type = Column(SQLEnum(AnswerType), default=AnswerType.TEXT)
    answer_confidence = Column(Float)

    # Source and verification
    source_documents = Column(JSONB, default=[])
    source_references = Column(JSONB, default=[])
    verification_status = Column(
        SQLEnum(VerificationStatus), default=VerificationStatus.VERIFIED
    )

    # Performance metrics
    generation_time_ms = Column(Integer)
    quality_score = Column(Float)

    # Usage statistics
    hit_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Feedback and validation
    user_ratings = Column(JSONB, default=[])
    average_rating = Column(Float)

    # AI processing metadata
    ai_model_used = Column(String(100), nullable=False)
    ai_model_version = Column(String(50))
    processing_parameters = Column(JSONB, default={})

    # Cache management
    cache_status = Column(SQLEnum(CacheStatus), default=CacheStatus.ACTIVE)

    # Validity and expiration
    valid_from = Column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True))
    refresh_scheduled = Column(Boolean, default=False)

    # Organization
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    organization = relationship("Organization")


class QACacheInvalidationRule(SQLBaseModel):
    """Model for Q&A cache invalidation rules"""

    __tablename__ = "qa_cache_invalidation_rules"

    # Rule identification
    rule_name = Column(String(200), nullable=False)
    rule_type = Column(SQLEnum(InvalidationRuleType), nullable=False)

    # Rule conditions
    conditions = Column(JSONB, nullable=False)

    # Rule scope
    scope_document_ids = Column(Array(GUID()), default=[])
    scope_question_types = Column(Array(String), default=[])
    scope_organizations = Column(Array(GUID()), default=[])

    # Invalidation actions
    action_type = Column(
        SQLEnum(InvalidationActionType), default=InvalidationActionType.EXPIRE
    )

    # Rule status
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=5)

    # Rule execution
    last_executed_at = Column(DateTime(timezone=True))
    execution_count = Column(Integer, default=0)

    # Organization
    organization_id = Column(GUID(), ForeignKey("organizations.id"))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    organization = relationship("Organization")


class UserQAInteraction(SQLBaseModel):
    """Model for user Q&A interactions"""

    __tablename__ = "user_qa_interactions"

    # Interaction identification
    user_id = Column(GUID(), ForeignKey("users.id"))
    session_id = Column(GUID())
    interaction_type = Column(SQLEnum(InteractionType), nullable=False)

    # Context information
    conversation_id = Column(GUID(), ForeignKey("document_conversations.id"))
    document_id = Column(GUID(), ForeignKey("documents.id"))
    message_id = Column(GUID(), ForeignKey("conversation_messages.id"))

    # Interaction details
    interaction_data = Column(JSONB, default={})
    interaction_value = Column(Text)

    # Performance metrics
    response_time_ms = Column(Integer)
    success = Column(Boolean, default=True)
    error_code = Column(String(50))
    error_message = Column(Text)

    # Client information
    client_type = Column(SQLEnum(ClientType), default=ClientType.WEB)
    client_version = Column(String(50))

    # User environment
    ip_address = Column(String(45))
    user_agent = Column(Text)
    referrer = Column(String(500))

    # Geographic and temporal context
    country_code = Column(String(2))
    timezone = Column(String(50))

    # Organization
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User")
    conversation = relationship("DocumentConversation")
    document = relationship("Document")
    message = relationship("ConversationMessage")
    organization = relationship("Organization")


class UserEngagementMetric(SQLBaseModel):
    """Model for user engagement metrics"""

    __tablename__ = "user_engagement_metrics"

    # Metrics identification
    user_id = Column(GUID(), ForeignKey("users.id"))
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)

    # Time period
    metric_period = Column(SQLEnum(MetricPeriod), nullable=False)
    period_start_date = Column(DATE, nullable=False)
    period_end_date = Column(DATE, nullable=False)

    # Q&A engagement metrics
    questions_asked = Column(Integer, default=0)
    answers_received = Column(Integer, default=0)
    conversations_started = Column(Integer, default=0)
    average_conversation_length = Column(Float)

    # Quality metrics
    average_question_rating = Column(Float)
    average_answer_rating = Column(Float)
    satisfaction_score = Column(Float)

    # Usage patterns
    peak_activity_hour = Column(Integer)
    most_active_day_of_week = Column(Integer)

    # Document interaction metrics
    documents_analyzed = Column(Integer, default=0)
    unique_documents_viewed = Column(Integer, default=0)

    # Performance metrics
    average_response_time_ms = Column(Integer)
    session_duration_avg_ms = Column(Integer)

    # Additional metrics
    metrics_json = Column(JSONB, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User")
    organization = relationship("Organization")


class KnowledgeGapAnalysis(SQLBaseModel):
    """Model for knowledge gap analysis"""

    __tablename__ = "knowledge_gap_analysis"

    # Gap identification
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False)
    gap_type = Column(SQLEnum(GapType), nullable=False)

    # Gap description
    gap_title = Column(String(500), nullable=False)
    gap_description = Column(Text, nullable=False)

    # Gap scope and impact
    affected_document_ids = Column(Array(GUID()), default=[])
    affected_question_patterns = Column(Array(String), default=[])
    impact_severity = Column(SQLEnum(ImpactSeverity), default=ImpactSeverity.MEDIUM)

    # Evidence and metrics
    supporting_evidence = Column(JSONB, default={})
    frequency = Column(Integer, default=0)
    user_reports = Column(Integer, default=0)

    # Resolution tracking
    status = Column(SQLEnum(GapStatus), default=GapStatus.IDENTIFIED)

    # Resolution details
    resolution_strategy = Column(Text)
    resolution_actions = Column(JSONB, default=[])
    resolved_by_user_id = Column(GUID(), ForeignKey("users.id"))

    # Timestamps
    identified_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True))

    # Relationships
    organization = relationship("Organization")
    resolved_by_user = relationship("User")


# ============================================================================
# PYDANTIC SCHEMAS FOR API SERIALIZATION
# ============================================================================


class DocumentConversationBase(BaseModel):
    """Base schema for document conversations"""

    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    conversation_type: ConversationType = ConversationType.DOCUMENT_QA
    conversation_context: Dict[str, Any] = {}
    language: str = "en"
    response_style: str = "professional"
    ai_model_config: Dict[str, Any] = {}
    is_public: bool = False
    is_moderated: bool = False

    @validator("language")
    def validate_language(cls, v):
        if len(v) not in [2, 3]:
            raise ValueError("Language code must be 2 or 3 characters")
        return v.lower()

    model_config = ConfigDict(from_attributes=True)


class DocumentConversationCreate(DocumentConversationBase):
    """Schema for creating document conversations"""

    document_id: uuid.UUID
    participant_ids: Optional[List[uuid.UUID]] = None  # Additional participants to add


class DocumentConversationResponse(DocumentConversationBase):
    """Schema for document conversation responses"""

    id: uuid.UUID
    document_id: uuid.UUID
    status: ConversationStatus
    participant_count: int
    organization_id: uuid.UUID
    created_by_user_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    document_title: Optional[str] = None  # Include document title in response
    created_by_user_name: Optional[str] = None  # Include creator name in response

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageBase(BaseModel):
    """Base schema for conversation messages"""

    content: str = Field(..., min_length=1)
    content_type: ContentType = ContentType.TEXT
    message_type: MessageType
    referenced_document_sections: List[Dict[str, Any]] = []
    referenced_entities: List[Dict[str, Any]] = []
    source_type: SourceType = SourceType.USER

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageCreate(ConversationMessageBase):
    """Schema for creating conversation messages"""

    conversation_id: uuid.UUID


class ConversationMessageResponse(ConversationMessageBase):
    """Schema for conversation message responses"""

    id: uuid.UUID
    conversation_id: uuid.UUID
    message_sequence: int
    word_count: int
    character_count: int
    language: str
    source_id: Optional[uuid.UUID]
    ai_model_used: Optional[str]
    processing_time_ms: Optional[int]
    confidence_score: Optional[float]
    user_rating: Optional[int]
    user_feedback: Optional[str]
    is_helpful: Optional[bool]
    is_visible: bool
    is_edited: bool
    edited_at: Optional[datetime]
    edit_reason: Optional[str]
    organization_id: uuid.UUID
    created_by_user_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    created_by_user_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationParticipantBase(BaseModel):
    """Base schema for conversation participants"""

    role: ParticipantRole = ParticipantRole.PARTICIPANT
    notification_preferences: Dict[str, Any] = {}
    display_preferences: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class ConversationParticipantCreate(ConversationParticipantBase):
    """Schema for adding conversation participants"""

    conversation_id: uuid.UUID
    user_id: uuid.UUID


class ConversationParticipantResponse(ConversationParticipantBase):
    """Schema for conversation participant responses"""

    id: uuid.UUID
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    status: ParticipantStatus
    message_count: int
    last_activity_at: Optional[datetime]
    joined_at: datetime
    left_at: Optional[datetime]
    organization_id: uuid.UUID
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentAnalysisResultBase(BaseModel):
    """Base schema for document analysis results"""

    analysis_type: AnalysisType
    analysis_version: str = "1.0"
    analysis_scope: Dict[str, Any] = {}
    analysis_parameters: Dict[str, Any] = {}
    data_sources: List[Dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)


class DocumentAnalysisResultCreate(DocumentAnalysisResultBase):
    """Schema for creating document analysis results"""

    document_id: uuid.UUID
    results: Dict[str, Any]
    insights: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []
    ai_model_used: str
    processing_time_ms: Optional[int] = None
    computational_cost: Optional[float] = None
    confidence_score: Optional[float] = None
    quality_score: Optional[float] = None
    completeness_score: Optional[float] = None


class DocumentAnalysisResultResponse(DocumentAnalysisResultBase):
    """Schema for document analysis result responses"""

    id: uuid.UUID
    document_id: uuid.UUID
    results: Dict[str, Any]
    insights: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    confidence_score: Optional[float]
    quality_score: Optional[float]
    completeness_score: Optional[float]
    ai_model_used: str
    processing_time_ms: Optional[int]
    computational_cost: Optional[float]
    is_validated: bool
    validated_by_user_id: Optional[uuid.UUID]
    validation_notes: Optional[str]
    status: AnalysisStatus
    error_message: Optional[str]
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    document_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class QACacheResponse(BaseModel):
    """Schema for Q&A cache responses"""

    id: uuid.UUID
    question_hash: str
    normalized_question: str
    original_question: str
    question_type: QuestionType
    question_complexity: QuestionComplexity
    question_domain: Optional[str]
    context_document_ids: List[uuid.UUID]
    context_entity_names: List[str]
    context_tags: List[str]
    cached_answer: str
    answer_type: AnswerType
    answer_confidence: Optional[float]
    source_documents: List[Dict[str, Any]]
    source_references: List[Dict[str, Any]]
    verification_status: VerificationStatus
    generation_time_ms: Optional[int]
    quality_score: Optional[float]
    hit_count: int
    last_accessed_at: datetime
    user_ratings: List[Dict[str, Any]]
    average_rating: Optional[float]
    ai_model_used: str
    ai_model_version: Optional[str]
    processing_parameters: Dict[str, Any]
    cache_status: CacheStatus
    valid_from: datetime
    expires_at: Optional[datetime]
    refresh_scheduled: bool
    organization_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserQAInteractionResponse(BaseModel):
    """Schema for user Q&A interaction responses"""

    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    session_id: Optional[uuid.UUID]
    interaction_type: InteractionType
    conversation_id: Optional[uuid.UUID]
    document_id: Optional[uuid.UUID]
    message_id: Optional[uuid.UUID]
    interaction_data: Dict[str, Any]
    interaction_value: Optional[str]
    response_time_ms: Optional[int]
    success: bool
    error_code: Optional[str]
    error_message: Optional[str]
    client_type: ClientType
    client_version: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    referrer: Optional[str]
    country_code: Optional[str]
    timezone: Optional[str]
    organization_id: uuid.UUID
    created_at: datetime
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserEngagementMetricResponse(BaseModel):
    """Schema for user engagement metric responses"""

    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    organization_id: uuid.UUID
    metric_period: MetricPeriod
    period_start_date: date
    period_end_date: date
    questions_asked: int
    answers_received: int
    conversations_started: int
    average_conversation_length: Optional[float]
    average_question_rating: Optional[float]
    average_answer_rating: Optional[float]
    satisfaction_score: Optional[float]
    peak_activity_hour: Optional[int]
    most_active_day_of_week: Optional[int]
    documents_analyzed: int
    unique_documents_viewed: int
    average_response_time_ms: Optional[int]
    session_duration_avg_ms: Optional[int]
    metrics_json: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationSummaryResponse(BaseModel):
    """Schema for conversation summary responses (from materialized view)"""

    id: uuid.UUID
    title: str
    description: Optional[str]
    conversation_type: ConversationType
    status: ConversationStatus
    document_id: Optional[uuid.UUID]
    document_title: Optional[str]
    participant_count: int
    created_at: datetime
    last_activity_at: datetime
    created_by_user_id: Optional[uuid.UUID]
    created_by_email: Optional[str]
    created_by_name: Optional[str]
    total_messages: int
    question_count: int
    answer_count: int
    avg_confidence: Optional[float]
    avg_rating: Optional[float]
    last_message_at: Optional[datetime]
    activity_level: ActivityLevel

    model_config = ConfigDict(from_attributes=True)


class QACachePerformanceResponse(BaseModel):
    """Schema for Q&A cache performance responses"""

    organization_id: uuid.UUID
    total_cache_entries: int
    total_hits: int
    avg_hits_per_entry: float
    avg_quality: Optional[float]
    avg_confidence: Optional[float]
    stale_entries: int
    expired_entries: int
    entries_used_last_week: int
    total_generation_time: int
    avg_generation_time: Optional[float]

    model_config = ConfigDict(from_attributes=True)


class UserEngagementDashboardResponse(BaseModel):
    """Schema for user engagement dashboard responses"""

    organization_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    questions_asked: int
    avg_question_rating: float
    satisfaction_score: float
    conversations_participated: int
    conversations_owned: int
    documents_interacted: int
    last_interaction: Optional[datetime]
    active_days: int
    avg_response_time: int

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# UTILITY CLASSES
# ============================================================================


class QACacheLookupResult(BaseModel):
    """Result from Q&A cache lookup operation"""

    cache_hit: bool
    answer: Optional[str]
    confidence: Optional[float]
    source_info: Optional[Dict[str, Any]]
    cache_id: Optional[uuid.UUID]

    model_config = ConfigDict(from_attributes=True)


class ConversationQualityMetrics(BaseModel):
    """Quality metrics for a conversation"""

    total_messages: int
    question_count: int
    answer_count: int
    avg_confidence: Optional[float]
    avg_user_rating: Optional[float]
    response_time_avg: Optional[float]
    satisfaction_score: Optional[float]

    model_config = ConfigDict(from_attributes=True)


class KnowledgeGapResult(BaseModel):
    """Result from knowledge gap analysis"""

    gap_type: GapType
    gap_title: str
    affected_questions: List[str]
    frequency: int
    impact_severity: ImpactSeverity

    model_config = ConfigDict(from_attributes=True)
