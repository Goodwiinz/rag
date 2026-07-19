"""Durable, transport-neutral inputs for one agent turn.

Project skills are deliberately unavailable unless their catalog has first
been persisted in an :class:`AgentRuntimeSnapshot`.  This prevents a failed
write from accidentally making an in-memory (and therefore non-resumable)
skill version available to a streaming or queued graph.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import get_settings
from src.models import (
    AgentRuntimeSnapshot,
    ProjectSkill,
    ProjectSkillVersionScan,
)
from src.services.agent.tools import TOOL_REGISTRY
from src.services.project_skills.access import (
    ProjectSkillNotFound,
    get_authorized_project,
)

logger = logging.getLogger(__name__)

MAX_ACTIVE_PROJECT_SKILLS = 32


@dataclass(frozen=True)
class RuntimeSnapshot:
    """The safe state-facing projection of a persisted runtime snapshot."""

    id: str | None
    tool_registry_hash: str
    tool_registry_version: str
    tool_names: tuple[str, ...]
    project_skill_catalog: tuple[dict[str, Any], ...]
    expires_at: datetime | None


def empty_runtime_snapshot() -> RuntimeSnapshot:
    """Return the ordinary-tools-only fallback without a durable skill catalog."""
    metadata = TOOL_REGISTRY.metadata_snapshot()
    return RuntimeSnapshot(
        id=None,
        tool_registry_hash=metadata["hash"],
        tool_registry_version=metadata["version"],
        tool_names=(),
        project_skill_catalog=(),
        expires_at=None,
    )


def _as_uuid(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


async def _eligible_catalog(
    session: AsyncSession, *, project_id: UUID
) -> list[dict[str, Any]]:
    """Build a deterministic catalog from active versions with a latest passed scan.

    Scans are append-only.  Eligibility is therefore based on the latest scan
    row (ordered by created timestamp and id), rather than on any historical
    passed result that a later blocked/error scan could otherwise bypass.
    """
    skills = (
        await session.scalars(
            select(ProjectSkill)
            .where(
                ProjectSkill.project_id == project_id,
                ProjectSkill.active_version_id.is_not(None),
                ProjectSkill.is_archived.is_(False),
                ProjectSkill.is_deleted.is_(False),
            )
            .order_by(ProjectSkill.normalized_name.asc(), ProjectSkill.id.asc())
            .limit(MAX_ACTIVE_PROJECT_SKILLS)
            .options(selectinload(ProjectSkill.active_version))
        )
    ).all()

    catalog: list[dict[str, Any]] = []
    # Keep a defense-in-depth cap even when a mocked/nonstandard session
    # ignores the SQL LIMIT above.
    for skill in skills[:MAX_ACTIVE_PROJECT_SKILLS]:
        version = skill.active_version
        if version is None:
            continue
        latest_scan = await session.scalar(
            select(ProjectSkillVersionScan)
            .where(ProjectSkillVersionScan.version_id == version.id)
            .order_by(
                ProjectSkillVersionScan.created_at.desc(),
                ProjectSkillVersionScan.id.desc(),
            )
            .limit(1)
        )
        if latest_scan is None or latest_scan.scan_state != "passed":
            continue
        catalog.append(
            {
                # This is persisted only.  The state/prompt projection below
                # excludes it, so the model never receives a database id.
                "version_id": str(version.id),
                "name": skill.normalized_name,
                "description": version.description,
                "version": version.version,
                "content_hash": version.content_hash,
            }
        )
    return catalog


def _state_catalog(catalog: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Return only model-safe, compact catalog metadata in stable order."""
    return tuple(
        {
            "name": item["name"],
            "description": item["description"],
            "version": item["version"],
            "content_hash": item["content_hash"],
        }
        for item in catalog
    )


async def create_runtime_snapshot(
    session: AsyncSession,
    *,
    user_id: UUID | str,
    project_id: UUID | str | None,
    thread_id: UUID | str | None = None,
    job_id: str | None = None,
) -> RuntimeSnapshot:
    """Persist and return a frozen catalog, or the safe empty fallback.

    A missing/invalid/unauthorized project, disabled rollout flags, or any
    database persistence failure all degrade to ordinary tools.  In no case
    does this function return an in-memory skill catalog that was not first
    committed to the durable snapshot row.
    """
    settings = get_settings()
    if not (
        settings.PROJECT_SKILL_CATALOG_ENABLED
        and settings.PROJECT_SKILL_RUNTIME_ENABLED
    ):
        return empty_runtime_snapshot()

    actor_id = _as_uuid(user_id)
    scoped_project_id = _as_uuid(project_id)
    if actor_id is None or scoped_project_id is None:
        return empty_runtime_snapshot()

    try:
        await get_authorized_project(
            session,
            project_id=scoped_project_id,
            user_id=actor_id,
            capability="read",
        )
    except (ProjectSkillNotFound, PermissionError, ValueError):
        return empty_runtime_snapshot()

    metadata = TOOL_REGISTRY.metadata_snapshot()
    tool_names = tuple(
        descriptor.name
        for descriptor in TOOL_REGISTRY.descriptors
        if descriptor.enabled
    )
    try:
        catalog = await _eligible_catalog(session, project_id=scoped_project_id)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=max(1, settings.PROJECT_SKILL_SNAPSHOT_RETENTION_DAYS)
        )
        row = AgentRuntimeSnapshot(
            project_id=scoped_project_id,
            user_id=actor_id,
            thread_id=_as_uuid(thread_id),
            job_id=job_id,
            tool_registry_hash=metadata["hash"],
            tool_registry_version=metadata["version"],
            tool_metadata={"enabled_names": list(tool_names)},
            skill_catalog=catalog,
            loaded_skill_versions=[],
            expires_at=expires_at,
        )
        session.add(row)
        await session.commit()
    except Exception:
        # A catalog that never reached durable storage must never be supplied
        # to the graph; queued and HITL paths would be unable to reproduce it.
        await session.rollback()
        logger.warning(
            "runtime snapshot creation failed; continuing without skills", exc_info=True
        )
        return empty_runtime_snapshot()

    return RuntimeSnapshot(
        id=str(row.id),
        tool_registry_hash=metadata["hash"],
        tool_registry_version=metadata["version"],
        tool_names=tool_names,
        project_skill_catalog=_state_catalog(catalog),
        expires_at=expires_at,
    )
