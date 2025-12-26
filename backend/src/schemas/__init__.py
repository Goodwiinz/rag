"""
API schemas for the multimodal RAG system
"""

# Quality metrics schemas
from .quality_metrics import (
    QualityMetricResponse,
    QualityAlertResponse,
    MetricAggregationResponse,
)

# Analytics schemas
from .analytics_query import *
from .analytics_response import *

# A/B Testing schemas
from .ab_testing import *

# Thread-centric chat schemas (Terminal Observatory)
from .chat import (
    # Enums
    WorkspaceRole,
    ThreadStatus,
    MessageRole,
    # Workspace schemas
    WorkspaceBase,
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceDetailResponse,
    # Conversation schemas
    ConversationBase,
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationListResponse,
    # Thread schemas
    ThreadBase,
    ThreadCreate,
    ThreadUpdate,
    ThreadResponse,
    ThreadDetailResponse,
    ThreadListResponse,
    # Message schemas
    ChatMessageBase,
    ChatMessageCreate,
    ChatMessageUpdate,
    ChatMessageResponse,
    ChatMessageListResponse,
    CitationResponse,
    MessageAttachmentResponse,
    # Collection schemas
    CollectionBase,
    CollectionCreate,
    CollectionUpdate,
    CollectionDocumentAdd,
    CollectionDocumentRemove,
    CollectionDocumentReorder,
    CollectionResponse,
    CollectionDetailResponse,
    CollectionListResponse,
    # Chat completion schemas
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamingChatChunk,
    # Search schemas
    WorkspaceSearchRequest,
    WorkspaceSearchResult,
    WorkspaceSearchResponse,
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
