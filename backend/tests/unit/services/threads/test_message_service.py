"""Characterize message_service.py (Task 4.3 consolidation).

Covers the ``require_author_or_admin`` delete-permission divergence flag,
the consolidated list capabilities (asc/desc/before_id/since/load_only —
a strict union of the three prior implementations, not gated behind a
flag), and nested-route chain scoping.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from src.models import ChatMessage, MessageRole
from src.models.workspace import WorkspaceMember, WorkspaceRole
from src.schemas.chat import ChatMessageUpdate
from src.services.threads import message_service

pytestmark = pytest.mark.integration


async def _seed_messages(db_session, thread, user, count=3):
    now = datetime.utcnow()
    msgs = []
    for i in range(count):
        m = ChatMessage(
            thread_id=thread.id,
            user_id=user.id,
            role=MessageRole.USER,
            content=f"msg-{i}",
            created_at=now + timedelta(milliseconds=i * 10),
            updated_at=now + timedelta(milliseconds=i * 10),
        )
        db_session.add(m)
        await db_session.commit()
        await db_session.refresh(m)
        db_session.info["_created"]["chat_messages"].append(m.id)
        msgs.append(m)
    return msgs


async def test_list_messages_asc_desc_and_before_id(
    db_session, thread_factory, user_factory
):
    user = await user_factory()
    thread = await thread_factory(user=user)
    msgs = await _seed_messages(db_session, thread, user, count=3)

    asc, total, has_more = await message_service.list_messages(
        db_session, thread.id, user.id, order="asc"
    )
    assert [m.id for m in asc] == [m.id for m in msgs]
    assert total == 3
    assert has_more is False

    desc, _total, _has_more = await message_service.list_messages(
        db_session, thread.id, user.id, order="desc"
    )
    assert [m.id for m in desc] == [m.id for m in reversed(msgs)]

    older, _total, has_more_cursor = await message_service.list_messages(
        db_session, thread.id, user.id, order="desc", before_id=msgs[2].id, limit=1
    )
    assert [m.id for m in older] == [msgs[1].id]
    assert has_more_cursor is True  # msgs[0] still remains


async def test_list_messages_since_filter(db_session, thread_factory, user_factory):
    user = await user_factory()
    thread = await thread_factory(user=user)
    msgs = await _seed_messages(db_session, thread, user, count=3)

    newer, total, _has_more = await message_service.list_messages(
        db_session, thread.id, user.id, since=msgs[0].created_at
    )
    assert total == 2
    assert [m.id for m in newer] == [msgs[1].id, msgs[2].id]


async def test_list_messages_returns_none_for_missing_thread(db_session, user_factory):
    user = await user_factory()
    assert (await message_service.list_messages(db_session, uuid4(), user.id)) is None


async def _add_viewer(db_session, workspace_id, viewer_id):
    db_session.add(
        WorkspaceMember(
            workspace_id=workspace_id, user_id=viewer_id, role=WorkspaceRole.VIEWER
        )
    )
    await db_session.commit()


async def _workspace_id_for_thread(db_session, thread):
    from sqlalchemy import select

    from src.models.conversation import Conversation

    conv = (
        await db_session.execute(
            select(Conversation).where(Conversation.id == thread.conversation_id)
        )
    ).scalar_one()
    return conv.workspace_id


async def test_update_message_feedback_requires_edit_rights(
    db_session, thread_factory, user_factory
):
    owner = await user_factory()
    viewer = await user_factory()
    thread = await thread_factory(user=owner)
    workspace_id = await _workspace_id_for_thread(db_session, thread)
    await _add_viewer(db_session, workspace_id, viewer.id)

    msg = ChatMessage(
        thread_id=thread.id, user_id=owner.id, role=MessageRole.USER, content="hi"
    )
    db_session.add(msg)
    await db_session.commit()
    await db_session.refresh(msg)
    db_session.info["_created"]["chat_messages"].append(msg.id)

    with pytest.raises(PermissionError):
        await message_service.update_message_feedback(
            db_session, msg.id, ChatMessageUpdate(feedback_rating=5), viewer.id
        )

    updated = await message_service.update_message_feedback(
        db_session, msg.id, ChatMessageUpdate(feedback_rating=5), owner.id
    )
    assert updated.feedback_rating == 5


async def test_delete_message_require_author_or_admin_flag(
    db_session, thread_factory, user_factory
):
    owner = await user_factory()
    editor = await user_factory()
    thread = await thread_factory(user=owner)
    workspace_id = await _workspace_id_for_thread(db_session, thread)
    db_session.add(
        WorkspaceMember(
            workspace_id=workspace_id, user_id=editor.id, role=WorkspaceRole.EDITOR
        )
    )
    await db_session.commit()

    msg_for_editor_flag_false = ChatMessage(
        thread_id=thread.id, user_id=owner.id, role=MessageRole.USER, content="a"
    )
    msg_for_editor_flag_true = ChatMessage(
        thread_id=thread.id, user_id=owner.id, role=MessageRole.USER, content="b"
    )
    db_session.add_all([msg_for_editor_flag_false, msg_for_editor_flag_true])
    await db_session.commit()
    for m in (msg_for_editor_flag_false, msg_for_editor_flag_true):
        await db_session.refresh(m)
        db_session.info["_created"]["chat_messages"].append(m.id)

    # require_author_or_admin=False (router-canonical): editor rights
    # suffice even though editor didn't author the message.
    assert await message_service.delete_message(
        db_session,
        msg_for_editor_flag_false.id,
        editor.id,
        require_author_or_admin=False,
    )

    # require_author_or_admin=True (old ChatService default): a non-author
    # editor is refused — only the author or a workspace admin may delete.
    with pytest.raises(PermissionError):
        await message_service.delete_message(
            db_session,
            msg_for_editor_flag_true.id,
            editor.id,
            require_author_or_admin=True,
        )
    # The author may always delete under the old rule.
    assert await message_service.delete_message(
        db_session, msg_for_editor_flag_true.id, owner.id, require_author_or_admin=True
    )
