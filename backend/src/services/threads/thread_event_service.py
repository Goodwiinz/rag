"""Thread Event Service for Real-time WebSocket Notifications.

This service broadcasts thread and message events to subscribed WebSocket clients,
enabling real-time updates for chat activity.

Channel naming convention:
- conversation:{conversation_id} - All activity in a conversation
- thread:{thread_id} - Activity in a specific thread
- user:{user_id}:threads - All thread activity for a user

Tenant isolation: every broadcast MUST carry ``target_organization`` so the
connection-manager gate (``ConnectionInfo.should_receive_message``) rejects
cross-org delivery. These channels (``thread:{id}``/``conversation:{id}``/
``user:{uid}:threads``) are NOT in the admin-only set, so any authenticated user
can subscribe to another tenant's channel mid-session; the org tag on the
message is the only thing that stops the payload (incl. ``content_preview``)
fanning out across tenants. The gate is SKIPPED when ``target_organization`` is
None, so ``organization_id`` is a required argument and is str-coerced
*unconditionally* — ``str(None) == "None"`` matches no authenticated connection
(``authenticate_websocket`` rejects orgless tokens), i.e. it fails CLOSED. Do
not "simplify" this back to a None/unrestricted default.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.services.websocket.websocket_manager import (
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
        self, channels: list[str], message: WebSocketMessage
    ) -> None:
        """Broadcast message to multiple channels with recipient deduplication.

        This prevents duplicate messages to clients subscribed to multiple channels.

        Thread-safety: This method is safe for concurrent async calls. The `sent_to`
        set is local to each invocation, and asyncio's single-threaded event loop
        ensures that dictionary/set operations on `channel_subscribers` and
        `active_connections` are atomic between await points. Each broadcast
        operation completes its iteration before yielding control.

        Args:
            channels: List of channel names to broadcast to
            message: WebSocket message to send
        """
        # Track which connection IDs have already received the message
        # Note: Local set is inherently thread-safe - no shared state between calls
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
                    # should_receive_message enforces the target_organization gate
                    # — a cross-org subscriber is dropped here.
                    if connection_info.should_receive_message(message):
                        await self._manager.send_message_to_connection(
                            connection_id, message
                        )
                        sent_to.add(connection_id)

    async def broadcast_thread_created(
        self,
        thread_id: str,
        conversation_id: str,
        user_id: str,
        organization_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Broadcast thread creation event.

        Args:
            thread_id: The created thread's ID
            conversation_id: Parent conversation ID
            user_id: User who created the thread
            organization_id: Owning organization (tenant scope — required)
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
            # Tenant scope — fail-closed (str(None)=="None" matches no connection).
            target_organization=str(organization_id),
        )

        # Broadcast to all channels with deduplication
        await self._broadcast_to_channels(
            [f"conversation:{conversation_id}", f"user:{user_id}:threads"], message
        )

        logger.debug(f"Broadcasted thread_created event for thread {thread_id}")

    async def broadcast_thread_updated(
        self,
        thread_id: str,
        conversation_id: str,
        user_id: str,
        organization_id: str,
        changes: Dict[str, Any],
    ) -> None:
        """Broadcast thread update event.

        Args:
            thread_id: The updated thread's ID
            conversation_id: Parent conversation ID
            user_id: User who updated the thread
            organization_id: Owning organization (tenant scope — required)
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
            target_organization=str(organization_id),
        )

        await self._broadcast_to_channels(
            [f"thread:{thread_id}", f"conversation:{conversation_id}"], message
        )

        logger.debug(f"Broadcasted thread_updated event for thread {thread_id}")

    async def broadcast_thread_deleted(
        self,
        thread_id: str,
        conversation_id: str,
        user_id: str,
        organization_id: str,
    ) -> None:
        """Broadcast thread deletion event.

        Args:
            thread_id: The deleted thread's ID
            conversation_id: Parent conversation ID
            user_id: User who deleted the thread
            organization_id: Owning organization (tenant scope — required)
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
            target_organization=str(organization_id),
        )

        await self._broadcast_to_channels(
            [f"thread:{thread_id}", f"conversation:{conversation_id}"], message
        )

        logger.debug(f"Broadcasted thread_deleted event for thread {thread_id}")

    async def broadcast_message_created(
        self,
        message_id: str,
        thread_id: str,
        conversation_id: str,
        user_id: str,
        organization_id: str,
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
            organization_id: Owning organization (tenant scope — required)
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
            target_organization=str(organization_id),
        )

        await self._broadcast_to_channels(
            [f"thread:{thread_id}", f"conversation:{conversation_id}"], message
        )

        logger.debug(f"Broadcasted message_created event for message {message_id}")

    async def broadcast_message_updated(
        self,
        message_id: str,
        thread_id: str,
        conversation_id: str,
        organization_id: str,
        changes: Dict[str, Any],
    ) -> None:
        """Broadcast message update event.

        Args:
            message_id: The updated message's ID
            thread_id: Parent thread ID
            conversation_id: Parent conversation ID
            organization_id: Owning organization (tenant scope — required)
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
            target_organization=str(organization_id),
        )

        await self._broadcast_to_channels(
            [f"thread:{thread_id}", f"conversation:{conversation_id}"], message
        )

        logger.debug(f"Broadcasted message_updated event for message {message_id}")

    async def broadcast_conversation_updated(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
        changes: Dict[str, Any],
    ) -> None:
        """Broadcast conversation update event.

        Args:
            conversation_id: The updated conversation's ID
            user_id: User who updated the conversation
            organization_id: Owning organization (tenant scope — required)
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
            target_organization=str(organization_id),
        )

        await self._broadcast_to_channels(
            [f"conversation:{conversation_id}", f"user:{user_id}:threads"], message
        )

        logger.debug(
            f"Broadcasted conversation_updated event for conversation {conversation_id}"
        )

    async def broadcast_threads_bulk_updated(
        self,
        thread_ids: list[str],
        action: str,
        user_id: str,
        organization_id: str,
    ) -> None:
        """Broadcast bulk thread operation event.

        Args:
            thread_ids: List of affected thread IDs
            action: The action performed ("resolved", "archived", "deleted")
            user_id: User who performed the operation
            organization_id: Owning organization (tenant scope — required)
        """
        if not thread_ids:
            return

        message = WebSocketMessage(
            type=MessageType.THREADS_BULK_UPDATED,
            data={
                "thread_ids": thread_ids,
                "action": action,
                "user_id": str(user_id),
                "count": len(thread_ids),
            },
            timestamp=datetime.now(timezone.utc),
            target_channels=[f"thread:{tid}" for tid in thread_ids],
            target_organization=str(organization_id),
        )

        # Broadcast to all affected thread channels
        channels = [f"thread:{tid}" for tid in thread_ids]
        await self._broadcast_to_channels(channels, message)

        logger.info(f"Broadcasted bulk {action} event for {len(thread_ids)} threads")


# Singleton instance
thread_event_service = ThreadEventService()
