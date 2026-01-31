"""
API schemas for the multimodal RAG system
"""

# A/B Testing schemas
from .ab_testing import *

# Analytics schemas
from .analytics_query import *
from .analytics_response import *

# Thread-centric chat schemas (Terminal Observatory)
from .chat import (  # Enums; Workspace schemas; Conversation schemas; Thread schemas; Message schemas; Collection schemas; Chat completion schemas; Search schemas
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessageBase,
    ChatMessageCreate,
    ChatMessageListResponse,
    ChatMessageResponse,
    ChatMessageUpdate,
    CitationResponse,
    CollectionBase,
    CollectionCreate,
    CollectionDetailResponse,
    CollectionDocumentAdd,
    CollectionDocumentRemove,
    CollectionDocumentReorder,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdate,
    ConversationBase,
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageAttachmentResponse,
    MessageRole,
    StreamingChatChunk,
    ThreadBase,
    ThreadCreate,
    ThreadDetailResponse,
    ThreadListResponse,
    ThreadResponse,
    ThreadStatus,
    ThreadUpdate,
    WorkspaceBase,
    WorkspaceCreate,
    WorkspaceDetailResponse,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
    WorkspaceResponse,
    WorkspaceRole,
    WorkspaceSearchRequest,
    WorkspaceSearchResponse,
    WorkspaceSearchResult,
    WorkspaceUpdate,
)

# Quality metrics schemas
from .quality_metrics import (
    MetricAggregationResponse,
    QualityAlertResponse,
    QualityMetricResponse,
)

__all__ = [
    # Quality metrics
    "QualityMetricResponse",
    "QualityAlertResponse",
    "MetricAggregationResponse",
    # Enums
    "WorkspaceRole",
    "ThreadStatus",
    "MessageRole",
    # Workspace schemas
    "WorkspaceBase",
    "WorkspaceCreate",
    "WorkspaceUpdate",
    "WorkspaceMemberCreate",
    "WorkspaceMemberUpdate",
    "WorkspaceMemberResponse",
    "WorkspaceResponse",
    "WorkspaceDetailResponse",
    # Conversation schemas
    "ConversationBase",
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationResponse",
    "ConversationListResponse",
    # Thread schemas
    "ThreadBase",
    "ThreadCreate",
    "ThreadUpdate",
    "ThreadResponse",
    "ThreadDetailResponse",
    "ThreadListResponse",
    # Message schemas
    "ChatMessageBase",
    "ChatMessageCreate",
    "ChatMessageUpdate",
    "ChatMessageResponse",
    "ChatMessageListResponse",
    "CitationResponse",
    "MessageAttachmentResponse",
    # Collection schemas
    "CollectionBase",
    "CollectionCreate",
    "CollectionUpdate",
    "CollectionDocumentAdd",
    "CollectionDocumentRemove",
    "CollectionDocumentReorder",
    "CollectionResponse",
    "CollectionDetailResponse",
    "CollectionListResponse",
    # Chat completion schemas
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "StreamingChatChunk",
    # Search schemas
    "WorkspaceSearchRequest",
    "WorkspaceSearchResult",
    "WorkspaceSearchResponse",
]
