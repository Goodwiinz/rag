"""Contracts for immutable, transport-neutral agent runtime snapshots."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_snapshot_commits_frozen_registry_and_verified_active_skill_catalog():
    from src.services.agent.runtime_snapshot import create_runtime_snapshot

    user_id = uuid4()
    project_id = uuid4()
    version_id = uuid4()
    skill = SimpleNamespace(
        normalized_name="literature-review",
        is_archived=False,
        active_version=SimpleNamespace(
            id=version_id,
            version=2,
            description="Review literature with project conventions.",
            content_hash="a" * 64,
        ),
    )
    session = AsyncMock()
    session.add = Mock()
    session.scalars.return_value = SimpleNamespace(all=Mock(return_value=[skill]))
    session.scalar.return_value = SimpleNamespace(scan_state="passed")
    settings = SimpleNamespace(
        PROJECT_SKILL_CATALOG_ENABLED=True,
        PROJECT_SKILL_RUNTIME_ENABLED=True,
        PROJECT_SKILL_SNAPSHOT_RETENTION_DAYS=30,
    )

    with (
        patch(
            "src.services.agent.runtime_snapshot.get_authorized_project",
            new=AsyncMock(return_value=SimpleNamespace()),
        ),
        patch(
            "src.services.agent.runtime_snapshot.get_settings",
            return_value=settings,
        ),
        patch(
            "src.services.agent.runtime_snapshot.TOOL_REGISTRY.metadata_snapshot",
            return_value={"version": "7", "hash": "b" * 64},
        ),
    ):
        snapshot = await create_runtime_snapshot(
            session,
            user_id=user_id,
            project_id=project_id,
            thread_id=uuid4(),
        )

    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    row = session.add.call_args.args[0]
    assert row.tool_registry_hash == "b" * 64
    assert row.tool_registry_version == "7"
    assert row.tool_metadata["descriptors"]
    assert "load_project_skill" in snapshot.tool_names
    assert row.skill_catalog == [
        {
            "version_id": str(version_id),
            "name": "literature-review",
            "description": "Review literature with project conventions.",
            "version": 2,
            "content_hash": "a" * 64,
        }
    ]
    assert snapshot.project_skill_catalog == (
        {
            "name": "literature-review",
            "description": "Review literature with project conventions.",
            "version": 2,
            "content_hash": "a" * 64,
        },
    )


@pytest.mark.asyncio
async def test_snapshot_hides_conditional_loader_without_a_durable_catalog():
    from src.services.agent.runtime_snapshot import create_runtime_snapshot

    session = AsyncMock()
    session.add = Mock()
    session.scalars.return_value = SimpleNamespace(all=Mock(return_value=[]))
    settings = SimpleNamespace(
        PROJECT_SKILL_CATALOG_ENABLED=True,
        PROJECT_SKILL_RUNTIME_ENABLED=True,
        PROJECT_SKILL_SNAPSHOT_RETENTION_DAYS=30,
    )
    with (
        patch(
            "src.services.agent.runtime_snapshot.get_authorized_project",
            new=AsyncMock(return_value=SimpleNamespace()),
        ),
        patch(
            "src.services.agent.runtime_snapshot.get_settings",
            return_value=settings,
        ),
    ):
        snapshot = await create_runtime_snapshot(
            session, user_id=uuid4(), project_id=uuid4()
        )

    row = session.add.call_args.args[0]
    assert "load_project_skill" not in snapshot.tool_names
    assert "load_project_skill" not in {
        descriptor["name"] for descriptor in row.tool_metadata["descriptors"]
    }


@pytest.mark.asyncio
async def test_unverified_or_disabled_turn_has_no_snapshot_catalog():
    from src.services.agent.runtime_snapshot import create_runtime_snapshot

    session = AsyncMock()
    session.add = Mock()
    settings = SimpleNamespace(
        PROJECT_SKILL_CATALOG_ENABLED=True,
        PROJECT_SKILL_RUNTIME_ENABLED=True,
        PROJECT_SKILL_SNAPSHOT_RETENTION_DAYS=30,
    )
    with (
        patch(
            "src.services.agent.runtime_snapshot.get_authorized_project",
            new=AsyncMock(side_effect=PermissionError),
        ),
        patch(
            "src.services.agent.runtime_snapshot.get_settings",
            return_value=settings,
        ),
    ):
        snapshot = await create_runtime_snapshot(
            session,
            user_id=uuid4(),
            project_id=uuid4(),
        )

    assert snapshot.id is None
    assert snapshot.project_skill_catalog == ()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_persistence_failure_never_returns_an_in_memory_catalog():
    from src.services.agent.runtime_snapshot import create_runtime_snapshot

    session = AsyncMock()
    session.add = Mock()
    session.commit.side_effect = RuntimeError("database unavailable")
    session.scalars.return_value = SimpleNamespace(all=Mock(return_value=[]))
    settings = SimpleNamespace(
        PROJECT_SKILL_CATALOG_ENABLED=True,
        PROJECT_SKILL_RUNTIME_ENABLED=True,
        PROJECT_SKILL_SNAPSHOT_RETENTION_DAYS=30,
    )
    with (
        patch(
            "src.services.agent.runtime_snapshot.get_authorized_project",
            new=AsyncMock(return_value=SimpleNamespace()),
        ),
        patch(
            "src.services.agent.runtime_snapshot.get_settings",
            return_value=settings,
        ),
    ):
        snapshot = await create_runtime_snapshot(
            session, user_id=uuid4(), project_id=uuid4()
        )

    session.rollback.assert_awaited_once()
    assert snapshot.id is None
    assert snapshot.project_skill_catalog == ()


@pytest.mark.asyncio
async def test_only_the_latest_passed_scan_makes_an_active_skill_eligible():
    from src.services.agent.runtime_snapshot import create_runtime_snapshot

    skill = SimpleNamespace(
        normalized_name="blocked-later",
        is_archived=False,
        active_version=SimpleNamespace(
            id=uuid4(), version=1, description="x", content_hash="c" * 64
        ),
    )
    session = AsyncMock()
    session.add = Mock()
    session.scalars.return_value = SimpleNamespace(all=Mock(return_value=[skill]))
    session.scalar.return_value = SimpleNamespace(scan_state="blocked")
    settings = SimpleNamespace(
        PROJECT_SKILL_CATALOG_ENABLED=True,
        PROJECT_SKILL_RUNTIME_ENABLED=True,
        PROJECT_SKILL_SNAPSHOT_RETENTION_DAYS=30,
    )
    with (
        patch(
            "src.services.agent.runtime_snapshot.get_authorized_project",
            new=AsyncMock(return_value=SimpleNamespace()),
        ),
        patch(
            "src.services.agent.runtime_snapshot.get_settings",
            return_value=settings,
        ),
    ):
        snapshot = await create_runtime_snapshot(
            session, user_id=uuid4(), project_id=uuid4()
        )

    assert snapshot.project_skill_catalog == ()


@pytest.mark.asyncio
async def test_catalog_is_hard_capped_to_32_even_if_query_returns_more_rows():
    from src.services.agent.runtime_snapshot import create_runtime_snapshot

    skills = [
        SimpleNamespace(
            normalized_name=f"skill-{index:02d}",
            is_archived=False,
            active_version=SimpleNamespace(
                id=uuid4(),
                version=1,
                description="d",
                content_hash=f"{index:064x}",
            ),
        )
        for index in range(33)
    ]
    session = AsyncMock()
    session.add = Mock()
    session.scalars.return_value = SimpleNamespace(all=Mock(return_value=skills))
    session.scalar.return_value = SimpleNamespace(scan_state="passed")
    settings = SimpleNamespace(
        PROJECT_SKILL_CATALOG_ENABLED=True,
        PROJECT_SKILL_RUNTIME_ENABLED=True,
        PROJECT_SKILL_SNAPSHOT_RETENTION_DAYS=30,
    )
    with (
        patch(
            "src.services.agent.runtime_snapshot.get_authorized_project",
            new=AsyncMock(return_value=SimpleNamespace()),
        ),
        patch(
            "src.services.agent.runtime_snapshot.get_settings",
            return_value=settings,
        ),
    ):
        snapshot = await create_runtime_snapshot(
            session, user_id=uuid4(), project_id=uuid4()
        )

    assert len(snapshot.project_skill_catalog) == 32
