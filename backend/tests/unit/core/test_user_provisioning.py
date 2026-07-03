"""Unit tests for ``src.core.user_provisioning`` JIT provisioning.

Coverage gap (daily audit #923, finding #2): ``ensure_user_and_org`` runs on
every first-time authenticated request (via ``dependencies.get_current_user``)
and contains an ``IntegrityError``-retry-then-refetch path for org/user
creation that had zero coverage. That path is precisely what protects two
simultaneous first requests for the same subject from 500-ing.

We drive the race deterministically with a mock ``AsyncSession`` whose
``flush()`` raises ``IntegrityError`` on demand (as a concurrent transaction
committing first would) and whose ``execute()`` then returns the row the
"other" request created. A real SQLite session can't reproduce this reliably —
it serializes writers, so the unique-violation window never opens.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.core.security import TokenData
from src.core.user_provisioning import ensure_user_and_org
from src.models.organization import Organization
from src.models.user import User


def _result(value):
    """Mimic a SQLAlchemy Result: ``.scalars().first()`` -> value."""
    res = MagicMock()
    scalars = MagicMock()
    scalars.first.return_value = value
    res.scalars.return_value = scalars
    return res


def _integrity_error() -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception("duplicate key value"))


def _session(*, execute_results, flush_side_effects):
    """Build a mock AsyncSession.

    ``execute_results``    — values returned by successive ``execute()`` calls,
                             each wrapped so ``.scalars().first()`` yields it.
    ``flush_side_effects`` — per-call ``flush()`` behavior; an ``IntegrityError``
                             instance is raised, anything else is returned.
    """
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_result(v) for v in execute_results])
    db.flush = AsyncMock(side_effect=flush_side_effects)
    db.rollback = AsyncMock()
    db.add = MagicMock()
    return db


def _token(user_id="user-1", email="user@example.com", organization_id=None):
    return TokenData(
        user_id=user_id, email=email, organization_id=organization_id
    )


# ---------------------------------------------------------------------------
# Guard clauses / happy paths
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_returns_none_without_user_id():
    db = _session(execute_results=[], flush_side_effects=[])
    assert await ensure_user_and_org(db, _token(user_id=None)) is None
    db.execute.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_returns_existing_user_without_provisioning():
    existing = SimpleNamespace(id="user-1")
    db = _session(execute_results=[existing], flush_side_effects=[])

    result = await ensure_user_and_org(db, _token())

    assert result is existing
    db.add.assert_not_called()  # nothing created
    db.flush.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_happy_path_creates_org_and_user_with_org_id():
    db = _session(
        execute_results=[None, None],  # user missing, org missing
        flush_side_effects=[None, None],  # org flush ok, user flush ok
    )

    user = await ensure_user_and_org(
        db, _token(organization_id="org-42")
    )

    assert isinstance(user, User)
    assert user.id == "user-1"
    assert user.organization_id == "org-42"
    db.rollback.assert_not_called()
    # Two objects added (org, then user), two flushes.
    assert db.add.call_count == 2
    assert db.flush.await_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_happy_path_creates_default_org_without_org_id():
    db = _session(
        execute_results=[None, None],  # user missing, default org missing
        flush_side_effects=[None, None],
    )

    user = await ensure_user_and_org(db, _token(organization_id=None))

    assert isinstance(user, User)
    # First added object is the default Organization.
    added_org = db.add.call_args_list[0].args[0]
    assert isinstance(added_org, Organization)
    assert added_org.name == "Default Organization"
    db.rollback.assert_not_called()


# ---------------------------------------------------------------------------
# Race handling: IntegrityError -> rollback -> refetch
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_org_race_refetches_concurrently_created_org():
    """org_id branch: a concurrent request inserts the org between our SELECT
    and our flush → IntegrityError → rollback → refetch returns their row."""
    concurrent_org = SimpleNamespace(id="org-42")
    db = _session(
        execute_results=[None, None, concurrent_org],
        #                 ^user  ^org  ^org-refetch
        flush_side_effects=[_integrity_error(), None],
        #                    ^org flush races   ^user flush ok
    )

    user = await ensure_user_and_org(db, _token(organization_id="org-42"))

    assert isinstance(user, User)
    assert user.organization_id == "org-42"  # from the refetched org
    db.rollback.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_default_org_race_refetches_by_name():
    """No org_id: the default-org creation races and is refetched by name."""
    concurrent_org = SimpleNamespace(id="org-default")
    db = _session(
        execute_results=[None, None, concurrent_org],
        flush_side_effects=[_integrity_error(), None],
    )

    user = await ensure_user_and_org(db, _token(organization_id=None))

    assert isinstance(user, User)
    assert user.organization_id == "org-default"
    db.rollback.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_race_refetches_concurrently_created_user():
    """The org resolves fine, but the user INSERT loses the race → refetch
    returns the user the concurrent request created."""
    concurrent_user = SimpleNamespace(id="user-1", organization_id="org-42")
    db = _session(
        execute_results=[None, None, concurrent_user],
        #                 ^user  ^org  ^user-refetch
        flush_side_effects=[None, _integrity_error()],
        #                    ^org  ^user flush races
    )

    result = await ensure_user_and_org(db, _token(organization_id="org-42"))

    assert result is concurrent_user
    db.rollback.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_simultaneous_provisioning_converges_on_one_user():
    """Two first-time requests for the SAME subject provision concurrently.

    The winner creates the row; the loser hits the unique violation on its
    user flush and refetches the winner's row. Both return a user with the
    same id — no unhandled 500, no duplicate identity.
    """
    winner_user_id = "user-1"

    # Winner: everything succeeds, creates the canonical User.
    winner_db = _session(
        execute_results=[None, None],
        flush_side_effects=[None, None],
    )
    # Loser: user flush loses the race, refetch returns the winner's row.
    winners_row = SimpleNamespace(id=winner_user_id, organization_id="org-42")
    loser_db = _session(
        execute_results=[None, None, winners_row],
        flush_side_effects=[None, _integrity_error()],
    )

    token = _token(user_id=winner_user_id, organization_id="org-42")
    winner, loser = await asyncio.gather(
        ensure_user_and_org(winner_db, token),
        ensure_user_and_org(loser_db, token),
    )

    assert winner.id == winner_user_id
    assert loser.id == winner_user_id  # loser converged on the winner's row
    loser_db.rollback.assert_awaited_once()
    winner_db.rollback.assert_not_called()
