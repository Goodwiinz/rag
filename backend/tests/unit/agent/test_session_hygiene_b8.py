"""Session hygiene for agent tools (audit B8).

Contract under test:

1. ``tool_session()`` — fresh per-call session with proper lifecycle:
   commit persists, an exception rolls the transaction back, and the
   session is always closed.
2. ``resolve_tool_user()`` — org-scoped acting-user load mirroring
   ``get_current_user`` (active + non-deleted only; org mismatch fails
   closed; invalid ids fail closed).
3. ``execute_tool`` is the ids→(session, user) boundary: with ids only it
   opens one tool_session and forwards the resolved user to the ``_tool_*``
   implementation; context-free tools and the explicit db/current_user
   injection seam never open a session.
4. ``_execute_single_tool`` (the graph tool node) passes scalar ids only —
   no ``db`` / ``current_user`` kwargs, nothing pulled from configurable
   beyond ids.
5. Source guard: no production configurable construction or consumer still
   smuggles ``db`` / ``current_user`` through LangGraph config.
"""

import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.models.organization import Organization
from src.models.user import User
from src.services.agent import tools_impl
from src.services.agent.tool_session import resolve_tool_user, tool_session

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

BACKEND_ROOT = Path(__file__).resolve().parents[3]

ORG_A = uuid.uuid4()
ORG_B = uuid.uuid4()
USER_ACTIVE = uuid.uuid4()
USER_INACTIVE = uuid.uuid4()
USER_DELETED = uuid.uuid4()
USER_ORG_B = uuid.uuid4()


# ---------------------------------------------------------------------------
# Fixtures — throwaway sqlite engine (users + organizations tables only; the
# shared Base carries postgres-only types elsewhere, so never create_all).
# ---------------------------------------------------------------------------


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Organization.__table__.create)
        await conn.run_sync(User.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _user(user_id, org_id, *, active=True, deleted=False) -> User:
    return User(
        id=user_id,
        email=f"{user_id}@example.com",
        password_hash="x",
        first_name="Test",
        last_name="User",
        is_active=active,
        is_deleted=deleted,
        organization_id=org_id,
    )


@pytest.fixture
async def seeded_factory(session_factory):
    """users: active/inactive/deleted in org A, one active in org B."""
    # first_name/last_name are encrypted-at-bind columns; the unit-test env
    # has no PII key, so store plaintext (the read path treats plaintext as
    # the documented graceful fallback for encryption-disabled writes).
    with patch(
        "src.models.encrypted_fields.encrypt_sensitive_field",
        side_effect=lambda value, field_name: value,
    ):
        async with session_factory() as db:
            db.add(Organization(id=ORG_A, name="Org A", storage_limit_bytes=10**9))
            db.add(Organization(id=ORG_B, name="Org B", storage_limit_bytes=10**9))
            db.add(_user(USER_ACTIVE, ORG_A))
            db.add(_user(USER_INACTIVE, ORG_A, active=False))
            db.add(_user(USER_DELETED, ORG_A, deleted=True))
            db.add(_user(USER_ORG_B, ORG_B))
            await db.commit()
    return session_factory


@pytest.fixture
def patched_sessionmaker(session_factory):
    """Point tool_session()'s lazy AsyncSessionLocal at the sqlite factory."""
    with patch("src.core.database.AsyncSessionLocal", session_factory):
        yield session_factory


# ---------------------------------------------------------------------------
# 1. tool_session lifecycle
# ---------------------------------------------------------------------------


async def test_tool_session_commit_persists(patched_sessionmaker):
    org_id = uuid.uuid4()
    async with tool_session() as session:
        session.add(
            Organization(id=org_id, name="Committed", storage_limit_bytes=10**9)
        )
        await session.commit()

    async with patched_sessionmaker() as check:
        row = await check.get(Organization, org_id)
        assert row is not None and row.name == "Committed"


async def test_tool_session_rolls_back_on_exception(patched_sessionmaker):
    org_id = uuid.uuid4()
    with pytest.raises(RuntimeError, match="boom"):
        async with tool_session() as session:
            session.add(
                Organization(id=org_id, name="Doomed", storage_limit_bytes=10**9)
            )
            await session.flush()  # write is pending inside the transaction
            raise RuntimeError("boom")

    async with patched_sessionmaker() as check:
        assert await check.get(Organization, org_id) is None


async def test_tool_session_uncommitted_write_discarded_on_close(
    patched_sessionmaker,
):
    """No commit inside the block ⇒ the close discards the transaction."""
    org_id = uuid.uuid4()
    async with tool_session() as session:
        session.add(Organization(id=org_id, name="Never", storage_limit_bytes=10**9))
        await session.flush()

    async with patched_sessionmaker() as check:
        assert await check.get(Organization, org_id) is None


async def test_tool_session_always_closes(patched_sessionmaker):
    captured = {}
    async with tool_session() as session:
        captured["session"] = session
    assert not captured["session"].in_transaction()

    with pytest.raises(ValueError):
        async with tool_session() as session:
            captured["failed"] = session
            raise ValueError("x")
    assert not captured["failed"].in_transaction()


# ---------------------------------------------------------------------------
# 2. resolve_tool_user org-scoping
# ---------------------------------------------------------------------------


async def test_resolve_tool_user_happy_path_org_scoped(seeded_factory):
    async with seeded_factory() as db:
        user = await resolve_tool_user(db, str(USER_ACTIVE), str(ORG_A))
    assert user is not None
    assert user.id == USER_ACTIVE
    assert user.organization_id == ORG_A
    # organization eager-loaded — usable after the session is gone.
    assert user.organization is not None and user.organization.id == ORG_A


async def test_resolve_tool_user_org_mismatch_fails_closed(seeded_factory):
    async with seeded_factory() as db:
        assert await resolve_tool_user(db, str(USER_ACTIVE), str(ORG_B)) is None


async def test_resolve_tool_user_without_org_filter(seeded_factory):
    async with seeded_factory() as db:
        user = await resolve_tool_user(db, str(USER_ORG_B), "")
    assert user is not None and user.id == USER_ORG_B


async def test_resolve_tool_user_inactive_and_deleted_fail_closed(seeded_factory):
    async with seeded_factory() as db:
        assert await resolve_tool_user(db, str(USER_INACTIVE), str(ORG_A)) is None
        assert await resolve_tool_user(db, str(USER_DELETED), str(ORG_A)) is None


async def test_resolve_tool_user_invalid_ids_fail_closed(seeded_factory):
    async with seeded_factory() as db:
        assert await resolve_tool_user(db, "", str(ORG_A)) is None
        assert await resolve_tool_user(db, "not-a-uuid", str(ORG_A)) is None
        # org asserted but unparseable — must not widen to all tenants.
        assert await resolve_tool_user(db, str(USER_ACTIVE), "not-a-uuid") is None
        assert await resolve_tool_user(db, str(uuid.uuid4()), str(ORG_A)) is None


# ---------------------------------------------------------------------------
# 3. execute_tool: the ids -> (session, user) boundary
# ---------------------------------------------------------------------------


async def test_execute_tool_ids_only_opens_session_and_resolves_user():
    sentinel_session = MagicMock()
    sentinel_session.commit = AsyncMock()
    sentinel_user = SimpleNamespace(id=uuid.uuid4(), organization_id=uuid.uuid4())
    opened = {"count": 0}

    @asynccontextmanager
    async def fake_tool_session():
        opened["count"] += 1
        yield sentinel_session

    resolve = AsyncMock(return_value=sentinel_user)
    impl = AsyncMock(return_value={"documents": [], "total": 0})

    with (
        patch("src.services.agent.tool_session.tool_session", fake_tool_session),
        patch("src.services.agent.tool_session.resolve_tool_user", resolve),
        patch.object(tools_impl, "_tool_search_documents", impl),
    ):
        result = await tools_impl.execute_tool(
            "search_documents",
            {"query": "q"},
            user_id="11111111-1111-1111-1111-111111111111",
            organization_id="22222222-2222-2222-2222-222222222222",
            thread_id="t-1",
        )

    assert result == {"documents": [], "total": 0}
    assert opened["count"] == 1
    resolve.assert_awaited_once_with(
        sentinel_session,
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    )
    # The resolve transaction is committed so the pooled connection is
    # released while the tool body runs.
    sentinel_session.commit.assert_awaited()
    impl.assert_awaited_once()
    call_args = impl.await_args.args
    assert call_args[1] is sentinel_session
    assert call_args[2] is sentinel_user


async def test_execute_tool_context_free_tool_opens_no_session():
    @asynccontextmanager
    async def exploding_tool_session():
        raise AssertionError("context-free tool must not open a session")
        yield  # pragma: no cover

    impl = AsyncMock(return_value={"papers": []})
    with (
        patch("src.services.agent.tool_session.tool_session", exploding_tool_session),
        patch.object(tools_impl, "_tool_search_arxiv", impl),
    ):
        result = await tools_impl.execute_tool(
            "search_arxiv", {"query": "q"}, user_id=str(uuid.uuid4())
        )
    assert result == {"papers": []}
    impl.assert_awaited_once()


async def test_execute_tool_unknown_tool_opens_no_session():
    @asynccontextmanager
    async def exploding_tool_session():
        raise AssertionError("unknown tool must not open a session")
        yield  # pragma: no cover

    with patch("src.services.agent.tool_session.tool_session", exploding_tool_session):
        result = await tools_impl.execute_tool("definitely_not_a_tool", {})
    assert "Unknown tool" in result["error"]


async def test_execute_tool_injection_seam_bypasses_session_open():
    """Direct callers/tests may inject db/current_user — no session opened."""
    injected_db = MagicMock()
    injected_user = SimpleNamespace(id=uuid.uuid4(), organization_id=uuid.uuid4())

    @asynccontextmanager
    async def exploding_tool_session():
        raise AssertionError("injection seam must not open a session")
        yield  # pragma: no cover

    impl = AsyncMock(return_value={"documents": [], "total": 0})
    with (
        patch("src.services.agent.tool_session.tool_session", exploding_tool_session),
        patch.object(tools_impl, "_tool_search_documents", impl),
    ):
        await tools_impl.execute_tool(
            "search_documents",
            {"query": "q"},
            db=injected_db,
            current_user=injected_user,
        )
    call_args = impl.await_args.args
    assert call_args[1] is injected_db
    assert call_args[2] is injected_user


# ---------------------------------------------------------------------------
# 4. The graph tool node passes scalar ids only
# ---------------------------------------------------------------------------


async def test_execute_single_tool_passes_ids_only():
    from src.services.agent._nodes_tools import _execute_single_tool

    executor = AsyncMock(return_value={"result": "ok"})
    config = {
        "configurable": {
            "user_id": "u-1",
            "organization_id": "o-1",
            "thread_id": "t-1",
        }
    }
    with patch("src.services.agent.graph._get_execute_tool", return_value=executor):
        out = await _execute_single_tool(
            {"name": "search_documents", "args": {"query": "x"}, "id": "tc1"},
            config,
            {},
        )

    assert out["execution"]["status"] == "completed"
    kwargs = executor.await_args.kwargs
    assert kwargs["user_id"] == "u-1"
    assert kwargs["organization_id"] == "o-1"
    assert kwargs["thread_id"] == "t-1"
    assert "db" not in kwargs
    assert "current_user" not in kwargs


async def test_hitl_actor_reads_scalar_ids():
    from src.services.agent._nodes_tools import _hitl_actor

    user_id, org_id, thread_id = _hitl_actor(
        {
            "configurable": {
                "user_id": "u-9",
                "organization_id": "o-9",
                "thread_id": "t-9",
            }
        }
    )
    assert (user_id, org_id, thread_id) == ("u-9", "o-9", "t-9")


# ---------------------------------------------------------------------------
# 5. Source guard — nothing smuggles db/current_user through configurable
# ---------------------------------------------------------------------------

_FORBIDDEN_CONSUMER_PATTERNS = (
    re.compile(r"""configurable\.get\(\s*["']db["']"""),
    re.compile(r"""configurable\.get\(\s*["']current_user["']"""),
    re.compile(r"""configurable\[["']db["']\]"""),
    re.compile(r"""configurable\[["']current_user["']\]"""),
)

_FORBIDDEN_CONSTRUCTION_PATTERNS = (
    re.compile(r"""["']db["']\s*:\s*(db|self\.db|session)\b"""),
    re.compile(r"""["']current_user["']\s*:"""),
)


def _agent_source_files():
    roots = [
        BACKEND_ROOT / "src" / "services" / "agent",
        BACKEND_ROOT / "src" / "api" / "agent",
    ]
    files = [p for root in roots for p in root.rglob("*.py")]
    files.append(BACKEND_ROOT / "scripts" / "synthetic_traffic.py")
    return files


async def test_no_source_reads_db_or_current_user_from_configurable():
    offenders = []
    for path in _agent_source_files():
        text = path.read_text(encoding="utf-8")
        for pattern in _FORBIDDEN_CONSUMER_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{path}: {pattern.pattern}")
    assert not offenders, (
        "configurable must carry ids only (audit B8); consumers must use "
        "tool_session()/resolve_tool_user instead of reading db/current_user "
        f"from LangGraph config: {offenders}"
    )


async def test_no_source_constructs_configurable_with_db_or_current_user():
    offenders = []
    for path in _agent_source_files():
        text = path.read_text(encoding="utf-8")
        for pattern in _FORBIDDEN_CONSTRUCTION_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{path}: {pattern.pattern}")
    assert not offenders, (
        "graph config construction must pass scalar ids only "
        f"(audit B8): {offenders}"
    )
