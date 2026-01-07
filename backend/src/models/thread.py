"""
Thread model for Terminal Observatory thread-centric chat schema
"""

from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from datetime import datetime

from .base import BaseModel, GUID


class ThreadStatus(PyEnum):
    """Thread status states"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class Thread(BaseModel):
    """
    Thread model - granular line of inquiry within a conversation.

    A thread represents a specific investigation or topic (e.g., "Revenue Forecast Investigation")
    that contains messages between the user and the AI assistant.
    """

    __tablename__ = "threads"

    # Parent relationship
    conversation_id = Column(GUID(), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Basic information
    title = Column(String(500), nullable=True)  # Optional - can be auto-generated
    summary = Column(Text, nullable=True)  # AI-generated summary of thread

    # State - Use values_callable to use lowercase enum values matching the database
    status = Column(
        Enum(ThreadStatus, values_callable=lambda x: [e.value for e in x], native_enum=True, name='threadstatus'),
        nullable=False,
        default=ThreadStatus.ACTIVE
    )

    # Metadata
    last_message_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    message_count = Column(Integer, default=0, nullable=False)
    token_count = Column(Integer, default=0, nullable=False)

    # Creator tracking
    created_by_id = Column(GUID(), ForeignKey("users.id"), nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="threads")
    created_by = relationship("User", foreign_keys=[created_by_id])
    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan", order_by="ChatMessage.created_at.asc()")

    def __repr__(self):
        return f"<Thread(title={self.title}, status={self.status.value}, conversation_id={self.conversation_id})>"

    def update_message_stats(self, token_count: int = 0):
        """Update message count and last message timestamp"""
        self.message_count = len(self.messages) if self.messages else 0
        self.last_message_at = datetime.utcnow()
        if token_count > 0:
            self.token_count += token_count

    def resolve(self):
        """Mark thread as resolved"""
        self.status = ThreadStatus.RESOLVED

    def reopen(self):
        """Reopen a resolved thread"""
        self.status = ThreadStatus.ACTIVE

    def archive(self):
        """Archive the thread"""
        self.status = ThreadStatus.ARCHIVED

    @property
    def is_active(self) -> bool:
        """Check if thread is active"""
        return self.status == ThreadStatus.ACTIVE

    @property
    def is_resolved(self) -> bool:
        """Check if thread is resolved"""
        return self.status == ThreadStatus.RESOLVED

    def to_dict(self, include_messages: bool = False) -> dict:
        """Convert to dictionary"""
        data = super().to_dict()
        data['status'] = self.status.value if self.status else None
        data['message_count'] = self.message_count
        data['token_count'] = self.token_count

        if include_messages and self.messages:
            data['messages'] = [m.to_dict() for m in self.messages]

        return data

    def generate_title(self) -> str:
        """Generate a title from the first user message"""
        if self.title:
            return self.title

        if self.messages:
            from .chat_message import MessageRole
            for msg in self.messages:
                if msg.role == MessageRole.USER and msg.content:
                    # Take first 50 characters of user message
                    title = msg.content[:50]
                    if len(msg.content) > 50:
                        title += "..."
                    return title

        return f"Thread {str(self.id)[:8]}"
