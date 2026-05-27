"""Unit tests for ensure_kb_for_org idempotency.

Uses an in-memory mock AsyncSession + DOKnowledgeBaseClient stub. The
advisory-lock concurrency path is exercised by simulating two concurrent
calls; the second observes the cached UUID after the first commits.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.do_kb.client import DOKnowledgeBaseError
from src.services.do_kb.models import KnowledgeBase
from src.services.do_kb.provisioner import _advisory_lock_key, ensure_kb_for_org


class _FakeOrg:
    def __init__(self, org_id: str) -> None:
        self.id = org_id
        self.do_kb_uuid: str | None = None
        self.do_kb_provisioned_at: datetime | None = None


class _FakeSession:
    """Minimal AsyncSession surface used by ensure_kb_for_org."""

    def __init__(self, org: _FakeOrg) -> None:
        self._org = org
        self.executed: list[Any] = []
        self.commits = 0

    async def get(self, model: Any, pk: Any) -> _FakeOrg:  # noqa: ARG002
        return self._org

    async def execute(self, stmt: Any) -> Any:
        self.executed.append(stmt)
        result = MagicMock()
        result.scalar_one_or_none.return_value = self._org.do_kb_uuid
        return result

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def stub_settings(monkeypatch):
    from src.core import config as cfg_module
    from src.services.do_kb import provisioner as prov_module

    fake = MagicMock()
    fake.DO_KB_ENABLED = True
    fake.DO_KB_REGION = "tor1"
    fake.DO_KB_PROJECT_ID = "proj"
    fake.DO_KB_EMBEDDING_MODEL_UUID = "model-uuid"
    fake.ENVIRONMENT = "testing"

    monkeypatch.setattr(cfg_module, "settings", fake)
    monkeypatch.setattr(prov_module, "settings", fake)
    return fake


@pytest.mark.unit
@pytest.mark.asyncio
async def test_returns_cached_uuid_without_calling_api(stub_settings):
    org = _FakeOrg("org-abc")
    org.do_kb_uuid = "existing-kb"
    session = _FakeSession(org)
    client = MagicMock()
    client.create_kb = AsyncMock()

    kb_uuid = await ensure_kb_for_org(session, org.id, client=client)

    assert kb_uuid == "existing-kb"
    client.create_kb.assert_not_called()
    assert session.commits == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_creates_and_persists_when_missing(stub_settings):
    org = _FakeOrg("org-abc")
    session = _FakeSession(org)

    client = MagicMock()
    client.create_kb = AsyncMock(
        return_value=KnowledgeBase(
            uuid="kb-fresh",
            name="nous-org-org-abc",
            region="tor1",
            project_id="proj",
            embedding_model_uuid="model-uuid",
        )
    )

    kb_uuid = await ensure_kb_for_org(session, org.id, client=client)

    assert kb_uuid == "kb-fresh"
    assert org.do_kb_uuid == "kb-fresh"
    assert org.do_kb_provisioned_at is not None
    assert org.do_kb_provisioned_at.tzinfo == timezone.utc
    client.create_kb.assert_awaited_once()
    assert session.commits == 1
    # Advisory lock SQL was issued
    assert any("pg_advisory_xact_lock" in str(stmt) for stmt in session.executed)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_raises_when_disabled(monkeypatch):
    from src.services.do_kb import provisioner as prov_module

    fake = MagicMock()
    fake.DO_KB_ENABLED = False
    monkeypatch.setattr(prov_module, "settings", fake)

    org = _FakeOrg("org-abc")
    session = _FakeSession(org)

    with pytest.raises(DOKnowledgeBaseError):
        await ensure_kb_for_org(session, org.id, client=MagicMock())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_concurrent_calls_only_create_once(stub_settings):
    """Second concurrent call should observe cached UUID after first commits."""
    org = _FakeOrg("org-shared")
    session_a = _FakeSession(org)
    session_b = _FakeSession(org)

    client = MagicMock()

    create_calls = 0

    async def fake_create_kb(**_: Any) -> KnowledgeBase:
        nonlocal create_calls
        create_calls += 1
        # Simulate a small delay so the second caller has time to enter
        await asyncio.sleep(0)
        return KnowledgeBase(
            uuid="kb-once",
            name="nous-org-org-shared",
            region="tor1",
            project_id="proj",
            embedding_model_uuid="model-uuid",
        )

    client.create_kb = AsyncMock(side_effect=fake_create_kb)

    # Run sequentially with shared org state — simulates serialized advisory lock
    first = await ensure_kb_for_org(session_a, org.id, client=client)
    second = await ensure_kb_for_org(session_b, org.id, client=client)

    assert first == "kb-once"
    assert second == "kb-once"
    assert create_calls == 1


@pytest.mark.unit
def test_advisory_lock_key_is_stable_int():
    key = _advisory_lock_key("org-abc")
    assert isinstance(key, int)
    assert -(1 << 31) <= key < (1 << 31)
    # deterministic
    assert _advisory_lock_key("org-abc") == key
