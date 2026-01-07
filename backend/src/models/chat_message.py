"""
ChatMessage model for Terminal Observatory thread-centric chat schema
"""

from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Text, Integer, Float
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from datetime import datetime

from .base import BaseModel, GUID


class MessageRole(PyEnum):
    """Message role types"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ChatMessage(BaseModel):
    """
    ChatMessage model - individual messages within a thread.

    Represents a single message in a conversation thread, supporting
    user messages, AI responses, system messages, and tool outputs.
    """

    __tablename__ = "chat_messages"

    # Parent relationship
    thread_id = Column(GUID(), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False, index=True)

    # Sender
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)  # Nullable for AI/system messages
    role = Column(Enum(MessageRole, values_callable=lambda obj: [e.value for e in obj]), nullable=False)

    # Content
    content = Column(Text, nullable=False)

    # Metrics
    token_count = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Integer, nullable=True)  # Response latency for observability

    # Model information (for AI responses)
    model_name = Column(String(100), nullable=True)
    model_version = Column(String(50), nullable=True)

    # Tool/Function call tracking
    tool_name = Column(String(100), nullable=True)  # If this is a tool message
    tool_call_id = Column(String(255), nullable=True)  # Tool call identifier

    # Feedback
    feedback_rating = Column(Integer, nullable=True)  # 1-5 rating
    feedback_text = Column(Text, nullable=True)

    # Relationships
    thread = relationship("Thread", back_populates="messages")
    user = relationship("User", foreign_keys=[user_id])
    citations = relationship("Citation", back_populates="message", cascade="all, delete-orphan")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")

    def __repr__(self):
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ChatMessage(role={self.role.value}, content={content_preview})>"

    @property
    def is_user_message(self) -> bool:
        """Check if this is a user message"""
        return self.role == MessageRole.USER

    @property
    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message"""
        return self.role == MessageRole.ASSISTANT

    @property
    def is_system_message(self) -> bool:
        """Check if this is a system message"""
        return self.role == MessageRole.SYSTEM

    @property
    def is_tool_message(self) -> bool:
        """Check if this is a tool message"""
        return self.role == MessageRole.TOOL

    @property
    def has_citations(self) -> bool:
        """Check if message has citations"""
        return len(self.citations) > 0 if self.citations else False

    @property
    def has_attachments(self) -> bool:
        """Check if message has attachments"""
        return len(self.attachments) > 0 if self.attachments else False

    def add_feedback(self, rating: int, text: str = None):
        """Add user feedback to this message"""
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")
        self.feedback_rating = rating
        self.feedback_text = text

    def to_dict(self, include_citations: bool = False, include_attachments: bool = False) -> dict:
        """Convert to dictionary"""
        data = super().to_dict()
        data['role'] = self.role.value if self.role else None
        data['has_citations'] = self.has_citations
        data['has_attachments'] = self.has_attachments

        if include_citations and self.citations:
            data['citations'] = [c.to_dict() for c in self.citations]

        if include_attachments and self.attachments:
            data['attachments'] = [a.to_dict() for a in self.attachments]

        return data

    def to_llm_format(self) -> dict:
        """Convert to format suitable for LLM API calls"""
        return {
            "role": self.role.value,
            "content": self.content
        }

    @classmethod
    def create_user_message(cls, thread_id: str, user_id: str, content: str) -> "ChatMessage":
        """Factory method for creating user messages"""
        return cls(
            thread_id=thread_id,
            user_id=user_id,
            role=MessageRole.USER,
            content=content
        )

    @classmethod
    def create_assistant_message(
        cls,
        thread_id: str,
        content: str,
        model_name: str = None,
        token_count: int = 0,
        latency_ms: int = None
    ) -> "ChatMessage":
        """Factory method for creating assistant messages"""
        return cls(
            thread_id=thread_id,
            role=MessageRole.ASSISTANT,
            content=content,
            model_name=model_name,
            token_count=token_count,
            latency_ms=latency_ms
        )

    @classmethod
    def create_system_message(cls, thread_id: str, content: str) -> "ChatMessage":
        """Factory method for creating system messages"""
        return cls(
            thread_id=thread_id,
            role=MessageRole.SYSTEM,
            content=content
        )

    @classmethod
    def create_tool_message(
        cls,
        thread_id: str,
        tool_name: str,
        content: str,
        tool_call_id: str = None
    ) -> "ChatMessage":
        """Factory method for creating tool messages"""
        return cls(
            thread_id=thread_id,
            role=MessageRole.TOOL,
            content=content,
            tool_name=tool_name,
            tool_call_id=tool_call_id
        )
