"""
Conversation persistence (Task 4.3 consolidation).

Canonical owner for conversation CRUD — the router-inline copy in
``backend/src/api/threads/workspace_routes/conversations.py`` and
``ChatService``'s conversation methods both implemented this independently;
this is now the one implementation.

Divergence flag (see the Task 4.3 amendment, A2): list ordering differed —
``ChatService.list_conversations`` ordered pinned-first
(``desc(is_pinned), desc(last_activity_at)``); the router-inline nested/
standalone list endpoints ordered by activity only, so a pinned conversation
never floated to the top there. Router semantics are canonical for the
endpoints the router serves; ``ChatService``'s own (pre-4.3, currently
uncalled) callers keep their observed ordering via ``order_pinned_first``,
default ``True`` (old ``ChatService`` behavior).

The two conversation-list count strategies (the router's grouped COUNT/SUM
aggregate vs. the service's ``selectinload(Conversation.threads)`` +
``len()``) are not a behavioral divergence — both mirror the same
unfiltered ``Conversation.threads`` relationship and produce identical
thread_count/message_count values (verified in the recon backing this
plan). This module keeps both: the aggregate for the efficient per-page
count, and the eager load so any caller reading ``conversation.threads``/
``.thread_count`` directly still gets a populated relationship, matching
``ChatService``'s original return shape exactly.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.conversation import Conversation
from src.models.thread import Thread
from src.schemas.chat import ConversationCreate, ConversationUpdate
from src.services.threads import workspace_access


async def create_conversation(
    db: AsyncSession, data: ConversationCreate, user_id: UUID
) -> Optional[Conversation]:
    """Create a conversation. ``None`` if the workspace isn't found/
    accessible; raises ``PermissionError`` if found but the caller lacks
    edit rights."""
    workspace = await workspace_access.get_workspace(
        db, data.workspace_id, user_id, load_conversations=False, load_collections=False
    )
    if not workspace:
        return None
    if not workspace.can_user_edit(str(user_id)):
        raise PermissionError("Insufficient permissions")

    conversation = Conversation(
        workspace_id=data.workspace_id,
        title=data.title,
        description=data.description,
        created_by_id=user_id,
        last_activity_at=datetime.utcnow(),
    )
    db.add(conversation)
    await db.commit()

    created = await workspace_access.get_conversation(
        db, conversation.id, user_id, load_threads=True
    )
    if created is None:
        raise RuntimeError(
            "Conversation lookup failed immediately after creation"
        )  # pragma: no cover
    return created


async def list_conversations(
    db: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    *,
    include_archived: bool = False,
    search_query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    order_pinned_first: bool = True,
) -> Optional[Tuple[List[Conversation], int, Dict[UUID, Tuple[int, int]]]]:
    """List conversations in a workspace.

    Returns ``None`` if the workspace isn't found/accessible (distinct from
    a legitimately empty list); otherwise ``(conversations, total, counts)``
    where ``counts`` maps conversation id -> ``(thread_count, message_count)``
    from one grouped aggregate query. ``conversations`` also carries
    ``.threads`` eager-loaded so callers that read the relationship directly
    (the pre-4.3 ``ChatService`` contract) keep working unchanged.
    """
    workspace = await workspace_access.get_workspace(
        db, workspace_id, user_id, load_conversations=False, load_collections=False
    )
    if not workspace:
        return None

    base_conditions = [
        Conversation.workspace_id == workspace_id,
        Conversation.is_deleted == False,  # noqa: E712
    ]
    if not include_archived:
        base_conditions.append(Conversation.is_archived == False)  # noqa: E712
    if search_query:
        pattern = f"%{search_query}%"
        base_conditions.append(
            or_(
                Conversation.title.ilike(pattern),
                Conversation.description.ilike(pattern),
            )
        )

    total = (
        await db.execute(select(func.count(Conversation.id)).where(*base_conditions))
    ).scalar() or 0

    order_clauses = (
        (desc(Conversation.is_pinned), desc(Conversation.last_activity_at))
        if order_pinned_first
        else (desc(Conversation.last_activity_at),)
    )
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.threads))
        .where(*base_conditions)
        .order_by(*order_clauses)
        .offset(offset)
        .limit(limit)
    )
    conversations = list((await db.execute(stmt)).scalars().all())

    counts: Dict[UUID, Tuple[int, int]] = {}
    conv_ids = [c.id for c in conversations]
    if conv_ids:
        agg_stmt = (
            select(
                Thread.conversation_id,
                func.count(Thread.id),
                func.coalesce(func.sum(Thread.message_count), 0),
            )
            .where(Thread.conversation_id.in_(conv_ids))
            .group_by(Thread.conversation_id)
        )
        counts = {
            row[0]: (row[1], row[2]) for row in (await db.execute(agg_stmt)).all()
        }

    return conversations, total, counts


async def update_conversation(
    db: AsyncSession,
    conversation_id: UUID,
    data: ConversationUpdate,
    user_id: UUID,
    *,
    workspace_id: Optional[UUID] = None,
) -> Optional[Conversation]:
    """Update a conversation. ``None`` if not found/accessible; raises
    ``PermissionError`` if found but the caller lacks edit rights.

    ``workspace_id``, when given, scopes the lookup to that parent (the
    nested-route chain check); standalone callers pass ``None``.
    """
    conversation = await workspace_access.get_conversation(
        db, conversation_id, user_id, workspace_id=workspace_id
    )
    if not conversation:
        return None
    if not conversation.workspace.can_user_edit(str(user_id)):
        raise PermissionError("Insufficient permissions")

    if data.title is not None:
        conversation.title = data.title
    if data.description is not None:
        conversation.description = data.description
    if data.is_archived is not None:
        conversation.is_archived = data.is_archived
    if data.is_pinned is not None:
        conversation.is_pinned = data.is_pinned

    conversation.updated_at = datetime.utcnow()
    await db.commit()
    # No db.refresh(): every mutated field is a Python-side assignment already
    # reflecting final state, and a bare refresh() would expire `.threads`
    # (eager-loaded above via get_conversation, untouched by this mutation)
    # — the presenter's thread_count/message_count fallback reads it right
    # after, and an expired-then-accessed relationship MissingGreenlets under
    # the async session.
    return conversation


async def delete_conversation(
    db: AsyncSession,
    conversation_id: UUID,
    user_id: UUID,
    *,
    workspace_id: Optional[UUID] = None,
    stamp_deleted_at: bool = False,
    require_admin: bool = False,
) -> Optional[bool]:
    """Soft-delete a conversation. ``None`` if not found/accessible; raises
    ``PermissionError`` if found but the caller lacks the required rights.

    ``workspace_id``, when given, scopes the lookup to that parent (the
    nested-route chain check); standalone callers pass ``None``.

    ``stamp_deleted_at=True`` (router-canonical) also sets ``deleted_at``;
    ``False`` (old ``ChatService`` default) leaves it ``NULL``.

    ``require_admin`` mirrors a second, smaller divergence: the router-inline
    delete endpoints (nested + standalone) require edit rights, matching
    every other mutator in this file; old ``ChatService.delete_conversation``
    required *admin* rights instead. Default ``False`` (edit — router
    canonical); pass ``True`` to reproduce the old ``ChatService`` gate for
    its own (pre-4.3, currently uncalled) callers.
    """
    conversation = await workspace_access.get_conversation(
        db, conversation_id, user_id, workspace_id=workspace_id
    )
    if not conversation:
        return None

    workspace = conversation.workspace
    allowed = (
        workspace.can_user_admin(str(user_id))
        if require_admin
        else workspace.can_user_edit(str(user_id))
    )
    if not allowed:
        raise PermissionError("Insufficient permissions")

    conversation.is_deleted = True
    if stamp_deleted_at:
        conversation.deleted_at = datetime.utcnow()
    conversation.updated_at = datetime.utcnow()
    await db.commit()
    return True
