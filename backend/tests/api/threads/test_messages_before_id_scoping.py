"""``before_id`` cursor must be scoped to the target thread (Batch C, Task C3).

Direct-API only (the UI's ``before_id`` is always the user's own message): the
cursor lookup resolved ``before_id`` by id alone, unscoped by thread. A foreign
message's ``created_at`` then drove pagination — a cross-tenant timestamp oracle
plus silently-wrong paging. A ``before_id`` that isn't in the target thread must
be ignored (results identical to omitting it); a valid in-thread ``before_id``
must still paginate.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.models import ChatMessage, MessageRole
from src.services.threads.chat_service import ChatService

pytestmark = pytest.mark.integration


async def _seed(db_session, thread, user, content, created_at) -> ChatMessage:
    m = ChatMessage(
        thread_id=thread.id,
        user_id=user.id,
        role=MessageRole.USER,
        content=content,
        created_at=created_at,
        updated_at=created_at,
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    db_session.info["_created"]["chat_messages"].append(m.id)
    return m


async def test_foreign_before_id_is_ignored(
    db_session, thread_factory, user_factory
):
    """A ``before_id`` from another thread does not filter this thread."""
    user = await user_factory()
    thread_a = await thread_factory(user=user)
    thread_b = await thread_factory(user=user)

    now = datetime.utcnow()
    a0 = await _seed(db_session, thread_a, user, "a0", now)
    a1 = await _seed(db_session, thread_a, user, "a1", now + timedelta(seconds=2))

    # Thread B message whose timestamp sits BETWEEN a0 and a1 — an unscoped
    # cursor would drop a1 from thread A's page.
    b_mid = await _seed(
        db_session, thread_b, user, "b", now + timedelta(seconds=1)
    )

    service = ChatService(db_session)
    scoped, scoped_total = await service.list_messages(
        thread_id=thread_a.id, user_id=user.id, before_id=b_mid.id
    )
    unscoped, unscoped_total = await service.list_messages(
        thread_id=thread_a.id, user_id=user.id
    )

    # Foreign cursor ignored -> identical to no before_id.
    assert [m.id for m in scoped] == [m.id for m in unscoped] == [a0.id, a1.id]
    assert scoped_total == unscoped_total == 2


async def test_valid_before_id_still_paginates(
    db_session, thread_factory, user_factory
):
    """An in-thread ``before_id`` still returns only older messages."""
    user = await user_factory()
    thread_a = await thread_factory(user=user)

    now = datetime.utcnow()
    a0 = await _seed(db_session, thread_a, user, "a0", now)
    a1 = await _seed(db_session, thread_a, user, "a1", now + timedelta(seconds=1))

    service = ChatService(db_session)
    out, total = await service.list_messages(
        thread_id=thread_a.id, user_id=user.id, before_id=a1.id
    )

    assert [m.id for m in out] == [a0.id]
    assert total == 1
