"""Thread Event Service for Real-time WebSocket Notifications.

This service broadcasts thread and message events to subscribed WebSocket clients,
enabling real-time updates for chat activity.

Channel naming convention:
- conversation:{conversation_id} - All activity in a conversation
- thread:{thread_id} - Activity in a specific thread
- user:{user_id}:threads - All thread activity for a user
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.services.websocket_manager import (
    MessageType,
    WebSocketMessage,
    connection_manager,
)

logger = logging.getLogger(__name__)


class ThreadEventService:
    """Service for broadcasting thread and message events via WebSocket."""

    def __init__(self):
        self._manager = connection_manager

    async def _broadcast_to_channels(
        self, 
        channels: list[str], 
        message: WebSocketMessage
    ) -> None:
        """Broadcast message to multiple channels with recipient deduplication.
        
        This prevents duplicate messages to clients subscribed to multiple channels.
        
        Args:
            channels: List of channel names to broadcast to
            message: WebSocket message to send
        """
        # Track which connection IDs have already received the message
        sent_to: set[str] = set()
        
        for channel in channels:
            # Add channel to target channels if not already present
            if channel not in message.target_channels:
                message.target_channels.append(channel)
            
            # Get subscribers for this channel
            subscriber_ids = self._manager.channel_subscribers.get(channel, set())
            
            # Send only to subscribers we haven't sent to yet
            for connection_id in subscriber_ids:
                if connection_id in sent_to:
                    continue  # Skip - already received message
                    
                if connection_id in self._manager.active_connections:
                    connection_info = self._manager.active_connections[connection_id]
                    if connection_info.should_receive_message(message):
                        await self._manager.send_message_to_connection(connection_id, message)
                        sent_to.add(connection_id)

    async def broadcast_thread_created(
        self,
        thread_id: str,
        conversation_id: str,
        user_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Broadcast thread creation event.

        Args:
            thread_id: The created thread's ID
            conversation_id: Parent conversation ID
            user_id: User who created the thread
            title: Thread title if available
            metadata: Additional thread metadata
        """
        message = WebSocketMessage(
            type=MessageType.THREAD_CREATED,
            data={
                "thread_id": str(thread_id),
                "conversation_id": str(conversation_id),
                "user_id": str(user_id),
                "title": title,
                "metadata": metadata or {},
            },
            timestamp=datetime.now(timezone.utc),
            target_channels=[
                f"conversation:{conversation_id}",
                f"user:{user_id}:threads",
            ],
        )

        # Broadcast to all channels with deduplication
        await self._broadcast_to_channels(
            [f"conversation:{conversation_id}", f"user:{user_id}:threads"],
            message
        )

        logger.debug(
            f"Broadcasted thread_created event for thread {thread_id}"
        )

    async def broadcast_thread_updated(
        self,
        thread_id: str,
        conversation_id: str,
        user_id: str,
        changes: Dict[str, Any],
    ) -> None:
        """Broadcast thread update event.

        Args:
            thread_id: The updated thread's ID
            conversation_id: Parent conversation ID
            user_id: User who updated the thread
            changes: Dictionary of changed fields
        """
        message = WebSocketMessage(
            type=MessageType.THREAD_UPDATED,
            data={
                "thread_id": str(thread_id),
                "conversation_id": str(conversation_id),
                "user_id": str(user_id),
                "changes": changes,
            },
            timestamp=datetime.now(timezone.utc),
            target_channels=[
                f"thread:{thread_id}",
                f"conversation:{conversation_id}",
            ],
        )

        await self._broadcast_to_channels(
            [f"thread:{thread_id}", f"conversation:{conversation_id}"],
            message
        )

        logger.debug(
            f"Broadcasted thread_updated event for thread {thread_id}"
        )

    async def broadcast_thread_deleted(
        self,
        thread_id: str,
        conversation_id: str,
        user_id: str,
    ) -> None:
        """Broadcast thread deletion event.

        Args:
            thread_id: The deleted thread's ID
            conversation_id: Parent conversation ID
            user_id: User who deleted the thread
        """
        message = WebSocketMessage(
            type=MessageType.THREAD_DELETED,
            data={
                "thread_id": str(thread_id),
                "conversation_id": str(conversation_id),
                "user_id": str(user_id),
            },
            timestamp=datetime.now(timezone.utc),
            target_channels=[
                f"thread:{thread_id}",
                f"conversation:{conversation_id}",
            ],
        )

        await self._broadcast_to_channels(
            [f"thread:{thread_id}", f"conversation:{conversation_id}"],
            message
        )

        logger.debug(
            f"Broadcasted thread_deleted event for thread {thread_id}"
        )

    async def broadcast_message_created(
        self,
        message_id: str,
        thread_id: str,
        conversation_id: str,
        user_id: str,
        role: str,
        content_preview: Optional[str] = None,
        has_citations: bool = False,
    ) -> None:
        """Broadcast message creation event.

        Args:
            message_id: The created message's ID
            thread_id: Parent thread ID
            conversation_id: Parent conversation ID
            user_id: User who created the message
            role: Message role (user/assistant)
            content_preview: First 100 chars of content
            has_citations: Whether message has citations
        """
        message = WebSocketMessage(
            type=MessageType.MESSAGE_CREATED,
            data={
                "message_id": str(message_id),
                "thread_id": str(thread_id),
                "conversation_id": str(conversation_id),
                "user_id": str(user_id),
                "role": role,
                "content_preview": content_preview[:100] if content_preview else None,
                "has_citations": has_citations,
            },
            timestamp=datetime.now(timezone.utc),
            target_channels=[
                f"thread:{thread_id}",
                f"conversation:{conversation_id}",
            ],
        )

        await self._broadcast_to_channels(
            [f"thread:{thread_id}", f"conversation:{conversation_id}"],
            message
        )

        logger.debug(
            f"Broadcasted message_created event for message {message_id}"
        )

    async def broadcast_message_updated(
        self,
        message_id: str,
        thread_id: str,
        conversation_id: str,
        changes: Dict[str, Any],
    ) -> None:
        """Broadcast message update event.

        Args:
            message_id: The updated message's ID
            thread_id: Parent thread ID
            conversation_id: Parent conversation ID
            changes: Dictionary of changed fields
        """
        message = WebSocketMessage(
            type=MessageType.MESSAGE_UPDATED,
            data={
                "message_id": str(message_id),
                "thread_id": str(thread_id),
                "conversation_id": str(conversation_id),
                "changes": changes,
            },
            timestamp=datetime.now(timezone.utc),
            target_channels=[
                f"thread:{thread_id}",
                f"conversation:{conversation_id}",
            ],
        )

        await self._broadcast_to_channels(
            [f"thread:{thread_id}", f"conversation:{conversation_id}"],
            message
        )

        logger.debug(
            f"Broadcasted message_updated event for message {message_id}"
        )

    async def broadcast_conversation_updated(
        self,
        conversation_id: str,
        user_id: str,
        changes: Dict[str, Any],
    ) -> None:
        """Broadcast conversation update event.

        Args:
            conversation_id: The updated conversation's ID
            user_id: User who updated the conversation
            changes: Dictionary of changed fields
        """
        message = WebSocketMessage(
            type=MessageType.CONVERSATION_UPDATED,
            data={
                "conversation_id": str(conversation_id),
                "user_id": str(user_id),
                "changes": changes,
            },
            timestamp=datetime.now(timezone.utc),
            target_channels=[
                f"conversation:{conversation_id}",
                f"user:{user_id}:threads",
            ],
        )

        await self._broadcast_to_channels(
            [f"conversation:{conversation_id}", f"user:{user_id}:threads"],
            message
        )

        logger.debug(
            f"Broadcasted conversation_updated event for conversation {conversation_id}"
        )


# Singleton instance
thread_event_service = ThreadEventService()
