"""IDOR guard for ``create_message`` attachment_ids (Batch C, Task C1).

Direct-API only (the /chat UI never sends ``attachment_ids``): a caller could
guess a foreign document UUID and attach it, leaking its title/mime into the
thread via the message-attachment response. ``create_message`` must only attach
documents the caller's organization owns — matching the documents-service
org-scoping convention (``Document.organization_id == <caller org>``,
``is_deleted == False``). Foreign / deleted ids are silently dropped (logged),
never raised, so a legitimate mixed batch still attaches the owned ones.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.models import (
    Document,
    DocumentType,
    MessageAttachment,
    MessageRole,
)
from src.schemas.chat import ChatMessageCreate
from src.services.threads.chat_service import ChatService
from sqlalchemy import select

pytestmark = pytest.mark.integration


async def _seed_document(db_session, organization, *, is_deleted: bool = False) -> Document:
    doc = Document(
        id=uuid4(),
        title="secret-title",
        filename="secret.pdf",
        file_path="s3://bucket/secret.pdf",
        file_size_bytes=123,
        mime_type="application/pdf",
        document_type=DocumentType.PDF,
        organization_id=organization.id,
        is_deleted=is_deleted,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


async def _attachments_for(db_session, message_id) -> list[MessageAttachment]:
    rows = await db_session.execute(
        select(MessageAttachment).where(MessageAttachment.message_id == message_id)
    )
    return list(rows.scalars().all())


async def test_foreign_org_document_is_not_attached(
    db_session, thread_factory, user_factory, organization_factory
):
    """A document owned by org B is dropped when an org-A user attaches it."""
    org_b = await organization_factory()
    foreign_doc = await _seed_document(db_session, org_b)

    user_a = await user_factory()  # own org, distinct from org_b
    thread = await thread_factory(user=user_a)

    service = ChatService(db_session)
    message = await service.create_message(
        ChatMessageCreate(
            thread_id=thread.id,
            content="hi",
            role=MessageRole.USER,
            attachment_ids=[foreign_doc.id],
        ),
        user_id=user_a.id,
    )

    assert message is not None
    assert await _attachments_for(db_session, message.id) == []


async def test_owned_document_is_attached(
    db_session, thread_factory, user_factory
):
    """A document in the caller's own org is attached normally."""
    user_a = await user_factory()
    owned_doc = await _seed_document(db_session, await _org_of(db_session, user_a))
    thread = await thread_factory(user=user_a)

    service = ChatService(db_session)
    message = await service.create_message(
        ChatMessageCreate(
            thread_id=thread.id,
            content="hi",
            role=MessageRole.USER,
            attachment_ids=[owned_doc.id],
        ),
        user_id=user_a.id,
    )

    assert message is not None
    attached = await _attachments_for(db_session, message.id)
    assert [a.document_id for a in attached] == [owned_doc.id]


async def test_mixed_batch_attaches_only_owned(
    db_session, thread_factory, user_factory, organization_factory
):
    """A mixed batch attaches the owned doc and drops the foreign one."""
    org_b = await organization_factory()
    foreign_doc = await _seed_document(db_session, org_b)

    user_a = await user_factory()
    owned_doc = await _seed_document(db_session, await _org_of(db_session, user_a))
    thread = await thread_factory(user=user_a)

    service = ChatService(db_session)
    message = await service.create_message(
        ChatMessageCreate(
            thread_id=thread.id,
            content="hi",
            role=MessageRole.USER,
            attachment_ids=[foreign_doc.id, owned_doc.id],
        ),
        user_id=user_a.id,
    )

    assert message is not None
    attached = await _attachments_for(db_session, message.id)
    assert [a.document_id for a in attached] == [owned_doc.id]


async def _org_of(db_session, user):
    """Fetch the Organization row for ``user`` (factory only exposes the id)."""
    from src.models import Organization

    row = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    return row.scalars().one()
