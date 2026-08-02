"""Agent execution wire models shared by the API router and the service layer.

Moved verbatim from ``src.api.agent.execute`` (audit B5/C4-fold): the graph
runner (``agent_execution_service``) builds these payloads for the job store,
so they must live where the service layer can import them without inverting
the dependency direction (services must never import ``src.api`` — enforced by
``tests/unit/test_import_direction.py``). ``execute.py`` re-exports every name
here, so ``from src.api.agent.execute import AgentExecuteRequest`` keeps
resolving for existing callers.

Router-only schemas (job start/status, confirmation, thread listing) stay in
``execute.py`` — nothing below the API layer needs them.
"""

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class AgentMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(
        ..., description="Message role: user or assistant"
    )
    content: str = Field(..., max_length=32000, description="Message content")
    client_message_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Client-supplied idempotency key. Only honored for role='user'; "
            "ignored otherwise. Used to dedupe retries without a server-side SELECT."
        ),
    )

    @field_validator("client_message_id")
    @classmethod
    def _only_for_user(cls, v: Optional[UUID], info) -> Optional[UUID]:
        if v is not None and info.data.get("role") != "user":
            raise ValueError("client_message_id only valid on user messages")
        return v


class PageContextRequest(BaseModel):
    type: str = Field(default="unknown", description="Page context type")
    project_id: Optional[str] = Field(
        default=None, description="Project ID if on project page"
    )
    project_name: Optional[str] = Field(
        default=None, description="Project name for display"
    )
    label: Optional[str] = Field(
        default=None, description="Current page label (e.g., 'Documents', 'Notes')"
    )
    metadata: Optional[Dict[str, Any]] = None


SUPPORTED_MODELS: frozenset[str] = frozenset(
    {"", "model-router", "gpt-5-mini", "gpt-5.6-luna"}
)


class AgentExecuteRequest(BaseModel):
    messages: List[AgentMessage] = Field(
        ..., max_length=50, description="Conversation messages"
    )
    page_context: PageContextRequest = Field(default_factory=PageContextRequest)
    model: str = Field(
        default="",
        description=(
            "Azure deployment name to route the chat to. Empty string uses the "
            "server-configured deployment. See SUPPORTED_MODELS for the allow-list."
        ),
    )
    use_rag: bool = Field(default=True)
    max_context_docs: int = Field(default=5, ge=1, le=10)
    thread_id: Optional[str] = None
    supersedes_client_message_id: Optional[UUID] = Field(
        default=None,
        description=(
            "Edit-and-resend: the client_message_id of the USER turn being "
            "edited. The server tombstones that turn and everything after it in "
            "the thread atomically with persisting the new user turn, and drops "
            "the superseded messages from the LangGraph checkpoint. The edited "
            "turn itself must arrive as the normal last user message with a "
            "FRESH client_message_id — reusing the old one would be silently "
            "dropped by the ON CONFLICT dedup."
        ),
    )

    @model_validator(mode="after")
    def _edit_carries_a_fresh_cmid(self) -> "AgentExecuteRequest":
        """Reject an edit whose replacement reuses the superseded turn's key.

        Reusing the key is not a harmless no-op: the replacement INSERT hits the
        ``(thread_id, client_message_id)`` ON CONFLICT DO NOTHING and dedups
        onto the very row being edited, so the tombstone pass would then mark
        its own replacement superseded — the turn disappears from every reader.
        422 at the edge is the only place this is cheap to see.
        """
        supersedes = self.supersedes_client_message_id
        if supersedes is None:
            return self
        last_user = next((m for m in reversed(self.messages) if m.role == "user"), None)
        if last_user is None:
            return self
        if (
            last_user.client_message_id is not None
            and last_user.client_message_id == supersedes
        ):
            raise ValueError("edited turn must carry a fresh client_message_id")
        return self

    @field_validator("model")
    @classmethod
    def _validate_model(cls, value: str) -> str:
        if value not in SUPPORTED_MODELS:
            supported = ", ".join(sorted(name for name in SUPPORTED_MODELS if name))
            raise ValueError(
                f"Unsupported model {value!r}. Supported deployments: {supported}."
            )
        return value


class RetrievedContextResponse(BaseModel):
    document_id: Optional[str] = None
    title: str
    content: str
    score: float


class ToolExecutionResponse(BaseModel):
    id: str
    tool_name: str
    tool_display_name: str
    args: Dict[str, Any]
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class AgentExecuteResponse(BaseModel):
    message: AgentMessage
    model: str
    usage: Dict[str, int]
    finish_reason: str
    timestamp: str
    rag_enabled: bool = False
    retrieved_contexts: Optional[List[RetrievedContextResponse]] = None
    tool_executions: Optional[List[ToolExecutionResponse]] = None
    thread_id: str = ""
    conversation_id: str = ""
