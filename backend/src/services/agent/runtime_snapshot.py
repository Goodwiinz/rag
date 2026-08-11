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
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import get_settings
from src.models import (
    AgentRuntimeSnapshot,
    ProjectSkill,
    ProjectSkillVersion,
    ProjectSkillVersionScan,
)
from src.services.agent.observability import record_project_skill_event
from src.services.agent.tools import TOOL_REGISTRY
from src.services.project_skills.access import (
    ProjectSkillNotFound,
    get_authorized_project,
)

logger = logging.getLogger(__name__)

MAX_ACTIVE_PROJECT_SKILLS = 32
MAX_LOADED_PROJECT_SKILLS = 3
MAX_LOADED_PROJECT_SKILL_TOKENS = 12_000


@dataclass(frozen=True)
class RuntimeSnapshot:
    """The safe state-facing projection of a persisted runtime snapshot."""

    id: str | None
    tool_registry_hash: str
    tool_registry_version: str
    tool_names: tuple[str, ...]
    project_skill_catalog: tuple[dict[str, Any], ...]
    expires_at: datetime | None


def runtime_state_fields(
    snapshot: RuntimeSnapshot, project_id: str | None
) -> dict[str, Any]:
    """Single initial-state projection used by streaming and queued turns."""
    return {
        "current_project_id": str(project_id or ""),
        "runtime_snapshot_id": snapshot.id or "",
        "project_skill_catalog": list(snapshot.project_skill_catalog),
        "loaded_skill_versions": [],
    }


def runtime_config_fields(
    snapshot_id: str | None, project_id: str | None
) -> dict[str, str]:
    """Server-owned configurable identifiers for every tool invocation."""
    return {
        "project_id": str(project_id or ""),
        "runtime_snapshot_id": str(snapshot_id or ""),
    }


def resume_runtime_config_fields(values: dict[str, Any]) -> dict[str, str]:
    """Recover immutable runtime context from checkpoint state for HITL resume."""
    page_context = values.get("page_context") or {}
    return runtime_config_fields(
        values.get("runtime_snapshot_id"),
        values.get("current_project_id") or page_context.get("project_id"),
    )


def empty_runtime_snapshot() -> RuntimeSnapshot:
    """Return the ordinary-tools-only fallback without a durable skill catalog."""
    metadata = TOOL_REGISTRY.metadata_snapshot()
    return RuntimeSnapshot(
        id=None,
        tool_registry_hash=metadata["hash"],
        tool_registry_version=metadata["version"],
        tool_names=TOOL_REGISTRY.available_descriptor_names(),
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


def render_project_skill_catalog(
    catalog: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> str:
    """Render only frozen, compact catalog metadata for an LLM system prompt."""
    entries = sorted(catalog or (), key=lambda item: item.get("name", ""))
    if not entries:
        return ""
    lines = ["Project skills available for this turn (load only when relevant):"]
    for item in entries[:MAX_ACTIVE_PROJECT_SKILLS]:
        description = " ".join(str(item.get("description", "")).split())[:240]
        lines.append(
            f"- {item.get('name', '')} (v{item.get('version', '')}): " f"{description}"
        )
    lines.append(
        "Call load_project_skill(skill_name) to read the exact instructions for one listed skill."
    )
    lines.append(
        "When the user explicitly names a listed skill, call "
        "load_project_skill(skill_name) before any other project tool."
    )
    return "\n".join(lines)


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
    skill_runtime = (
        settings.PROJECT_SKILL_CATALOG_ENABLED
        and settings.PROJECT_SKILL_RUNTIME_ENABLED
    )
    if not skill_runtime and not getattr(
        settings, "AGENT_TOOL_REGISTRY_ENFORCEMENT_ENABLED", False
    ):
        record_project_skill_event("snapshot", "skipped")
        return empty_runtime_snapshot()

    actor_id = _as_uuid(user_id)
    scoped_project_id = _as_uuid(project_id)
    if actor_id is None:
        record_project_skill_event("snapshot", "rejected")
        return empty_runtime_snapshot()

    if not skill_runtime and scoped_project_id is None:
        scoped_project_id = None
    elif scoped_project_id is None:
        record_project_skill_event("snapshot", "rejected")
        return empty_runtime_snapshot()

    try:
        if scoped_project_id is not None:
            await get_authorized_project(
                session,
                project_id=scoped_project_id,
                user_id=actor_id,
                capability="read",
            )
    except (ProjectSkillNotFound, PermissionError, ValueError):
        record_project_skill_event("snapshot", "rejected")
        return empty_runtime_snapshot()

    metadata = TOOL_REGISTRY.metadata_snapshot()
    try:
        catalog = (
            await _eligible_catalog(session, project_id=scoped_project_id)
            if skill_runtime and scoped_project_id is not None
            else []
        )
        conditions = {"project_skill_catalog"} if skill_runtime and catalog else set()
        tool_names = TOOL_REGISTRY.available_descriptor_names(conditions=conditions)
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
            tool_metadata={
                "descriptors": TOOL_REGISTRY.frozen_descriptor_metadata(
                    conditions=conditions
                )
            },
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
        record_project_skill_event("snapshot", "failure")
        return empty_runtime_snapshot()

    record_project_skill_event("snapshot", "success")
    return RuntimeSnapshot(
        id=str(row.id),
        tool_registry_hash=metadata["hash"],
        tool_registry_version=metadata["version"],
        tool_names=tool_names,
        project_skill_catalog=_state_catalog(catalog),
        expires_at=expires_at,
    )


def _snapshot_error(error_type: str, error: str) -> dict[str, str]:
    """Keep loader failures structured for the model and tool audit trail."""
    record_project_skill_event("loader", "rejected")
    return {"error_type": error_type, "error": error}


def _estimated_instruction_tokens(instructions: str) -> int:
    """Match the conservative catalog scanner approximation without model I/O."""
    return (len(instructions) + 3) // 4


async def load_project_skill_from_snapshot(
    session: AsyncSession,
    *,
    snapshot_id: str | None,
    user_id: UUID | str | None,
    project_id: UUID | str | None,
    skill_name: str,
) -> dict[str, Any]:
    """Load one exact, frozen instruction document from a durable snapshot.

    The caller supplies all context from server-owned config.  ``skill_name``
    is intentionally the only model-controlled value; it must match an entry
    already persisted in the snapshot catalog.
    """
    if not get_settings().PROJECT_SKILL_RUNTIME_ENABLED:
        return _snapshot_error(
            "project_skill_runtime_disabled", "Project skill runtime is disabled."
        )
    snapshot_uuid = _as_uuid(snapshot_id)
    actor_id = _as_uuid(user_id)
    expected_project_id = _as_uuid(project_id)
    if snapshot_uuid is None or actor_id is None or expected_project_id is None:
        return _snapshot_error(
            "runtime_snapshot_required",
            "Project skill loading requires server runtime snapshot context.",
        )

    snapshot = await session.get(
        AgentRuntimeSnapshot, snapshot_uuid, with_for_update=True
    )
    now = datetime.now(timezone.utc)
    if (
        snapshot is None
        or snapshot.user_id != actor_id
        or snapshot.project_id != expected_project_id
        or (
            snapshot.expires_at is not None
            and snapshot.expires_at.replace(tzinfo=timezone.utc) <= now
        )
    ):
        return _snapshot_error(
            "runtime_snapshot_unavailable",
            "The project skill snapshot is unavailable for this run.",
        )

    try:
        from src.services.project_skills.skill_document import normalize_skill_name

        normalized_name = normalize_skill_name(skill_name)
    except ValueError:
        return _snapshot_error(
            "invalid_skill_name", "skill_name must be lowercase kebab-case."
        )

    entry = next(
        (
            item
            for item in snapshot.skill_catalog or []
            if item.get("name") == normalized_name
        ),
        None,
    )
    if entry is None:
        return _snapshot_error(
            "skill_not_in_snapshot",
            "That skill is not available in this run's snapshot.",
        )

    prior_loads = list(snapshot.loaded_skill_versions or [])
    prior = next(
        (item for item in prior_loads if item.get("name") == normalized_name), None
    )
    if (
        prior is None
        and len({item.get("name") for item in prior_loads}) >= MAX_LOADED_PROJECT_SKILLS
    ):
        return _snapshot_error(
            "project_skill_load_limit",
            "At most three project skills may be loaded per turn.",
        )

    version_id = _as_uuid(entry.get("version_id"))
    version = await session.get(ProjectSkillVersion, version_id) if version_id else None
    if (
        version is None
        or str(version.id) != str(entry.get("version_id"))
        or version.parsed_name != normalized_name
        or version.version != entry.get("version")
        or version.content_hash != entry.get("content_hash")
        or sha256(version.instructions.encode("utf-8")).hexdigest()
        != version.content_hash
    ):
        return _snapshot_error(
            "skill_version_unavailable",
            "The frozen project skill version is unavailable.",
        )
    version_project_id = await session.scalar(
        select(ProjectSkill.project_id)
        .join(ProjectSkillVersion, ProjectSkill.id == ProjectSkillVersion.skill_id)
        .where(ProjectSkillVersion.id == version.id)
    )
    if version_project_id != snapshot.project_id:
        return _snapshot_error(
            "skill_version_unavailable",
            "The frozen project skill version is unavailable.",
        )

    token_count = _estimated_instruction_tokens(version.instructions)
    loaded_tokens = sum(int(item.get("token_count", 0) or 0) for item in prior_loads)
    if prior is None and loaded_tokens + token_count > MAX_LOADED_PROJECT_SKILL_TOKENS:
        return _snapshot_error(
            "project_skill_token_limit",
            "Loading this skill would exceed the per-turn project skill token limit.",
        )

    record = prior or {
        "version_id": str(version.id),
        "name": normalized_name,
        "content_hash": version.content_hash,
        "token_count": token_count,
    }
    if prior is None:
        snapshot.loaded_skill_versions = [*prior_loads, record]
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            logger.warning("failed to record loaded project skill", exc_info=True)
            return _snapshot_error(
                "runtime_snapshot_unavailable",
                "The project skill snapshot could not be updated.",
            )

    record_project_skill_event(
        "loader",
        "success",
        loaded_skill_count=1 if prior is None else 0,
        loaded_skill_tokens=token_count if prior is None else 0,
    )
    return {
        "name": normalized_name,
        "version": version.version,
        "content_hash": version.content_hash,
        "instructions": version.instructions,
        "loaded_skill_version": record,
    }
