"""Project-ownership guard for the RAG node's DO KB read.

`_try_primary_do_kb_read` scopes DO KB chunks by a client-supplied
``project_id`` (page_context / message text). The KB is org-scoped and
``resolve_and_filter_chunks`` filters by ANY project id it's handed, so an
unverified id would let a user learn which org documents belong to another
in-org project (membership inference). ``_user_owns_project`` is the guard (scalar user_id, audit B8):
only an owned project may scope the read; anything else drops to org-wide.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agent._nodes_rag import _user_owns_project


def _session_returning(scalar):
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.unit
@pytest.mark.asyncio
async def test_owned_project_returns_true():
    pid = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session = _session_returning(uuid.uuid4())  # a row matched

    assert await _user_owns_project(session, pid, user_id) is True
    session.execute.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unowned_project_returns_false():
    pid = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session = _session_returning(None)  # owner_id filter matched nothing

    assert await _user_owns_project(session, pid, user_id) is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_non_uuid_project_is_not_owned_without_db_call():
    user_id = str(uuid.uuid4())
    session = _session_returning(uuid.uuid4())

    assert await _user_owns_project(session, "proj_12345", user_id) is False
    # A malformed id must short-circuit before touching the DB.
    session.execute.assert_not_awaited()

    # A malformed user id must short-circuit too (fail closed, no DB call).
    assert await _user_owns_project(session, str(uuid.uuid4()), "u-1") is False
    session.execute.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_inputs_are_not_owned():
    user_id = str(uuid.uuid4())
    session = _session_returning(uuid.uuid4())

    assert await _user_owns_project(session, None, user_id) is False
    assert await _user_owns_project(session, str(uuid.uuid4()), None) is False
    assert await _user_owns_project(session, str(uuid.uuid4()), "") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_db_error_is_unverifiable_not_a_negative():
    pid = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session = MagicMock()
    session.execute = AsyncMock(side_effect=RuntimeError("db down"))

    # A DB error means "couldn't check", distinct from a verified "not
    # owned" (audit M2) — collapsing the two into False previously let a
    # transient DB blip drop the project scope and fall through to an
    # org-wide read at the caller, widening exposure during an outage
    # instead of narrowing it. Callers must branch on None separately.
    assert await _user_owns_project(session, pid, user_id) is None
