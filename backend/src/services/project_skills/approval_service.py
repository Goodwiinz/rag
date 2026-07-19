"""Atomic approval workflow for project-skill change requests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import (
    ProjectSkill,
    ProjectSkillChangeRequest,
    ProjectSkillVersion,
    ProjectSkillVersionScan,
)
from src.services.agent.observability import record_project_skill_event

from .access import get_authorized_project
from .catalog_service import ProjectSkillCatalogService


class ProjectSkillApprovalError(ValueError):
    """A request fails the staged approval policy."""


class ProjectSkillConflict(ProjectSkillApprovalError):
    """A terminal request or active version changed before this operation locked it."""


def validate_approval_acknowledgements(
    *,
    is_self_approval: bool,
    has_warnings: bool,
    self_approval_acknowledged: bool,
    warning_acknowledged: bool,
    audit_note: str | None,
) -> None:
    note_present = bool(audit_note and audit_note.strip())
    if is_self_approval and (not self_approval_acknowledged or not note_present):
        raise ProjectSkillApprovalError(
            "self-approval requires explicit acknowledgement and audit note"
        )
    if has_warnings and (not warning_acknowledged or not note_present):
        raise ProjectSkillApprovalError(
            "warnings require acknowledgement and audit note"
        )


class ProjectSkillApprovalService:
    """Uses one lock order: resolve IDs, lock skill, then lock and refresh request."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _lock_request_and_skill(
        self, *, project_id: UUID, request_id: UUID, user_id: UUID
    ) -> tuple[ProjectSkill, ProjectSkillChangeRequest]:
        """Return fresh locked rows; never decide from a stale request instance."""
        await get_authorized_project(
            self._session, project_id=project_id, user_id=user_id, capability="admin"
        )
        request_ref = await self._session.execute(
            select(ProjectSkillChangeRequest.skill_id)
            .join(ProjectSkill)
            .where(
                ProjectSkillChangeRequest.id == request_id,
                ProjectSkill.project_id == project_id,
            )
        )
        skill_id = request_ref.scalar_one_or_none()
        if skill_id is None:
            raise ProjectSkillApprovalError("change request not found")
        skill = await self._session.scalar(
            select(ProjectSkill)
            .where(ProjectSkill.id == skill_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        request = await self._session.scalar(
            select(ProjectSkillChangeRequest)
            .where(ProjectSkillChangeRequest.id == request_id)
            .options(selectinload(ProjectSkillChangeRequest.proposed_version))
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if skill is None or request is None:
            raise ProjectSkillApprovalError("change request not found")
        return cast(ProjectSkill, skill), cast(ProjectSkillChangeRequest, request)

    async def _latest_scan(self, version_id: UUID) -> ProjectSkillVersionScan | None:
        return cast(
            ProjectSkillVersionScan | None,
            await self._session.scalar(
                select(ProjectSkillVersionScan)
                .where(ProjectSkillVersionScan.version_id == version_id)
                .order_by(
                    ProjectSkillVersionScan.created_at.desc(),
                    ProjectSkillVersionScan.id.desc(),
                )
                .limit(1)
            ),
        )

    async def approve(
        self,
        *,
        project_id: UUID,
        request_id: UUID,
        user_id: UUID,
        self_approval_acknowledged: bool = False,
        warning_acknowledged: bool = False,
        audit_note: str | None = None,
    ) -> ProjectSkillChangeRequest:
        skill, request = await self._lock_request_and_skill(
            project_id=project_id, request_id=request_id, user_id=user_id
        )
        if request.status != "pending":
            raise ProjectSkillConflict("change request is no longer pending")
        if skill.active_version_id != request.expected_active_version_id:
            request.status = "superseded"
            request.reviewer_id = user_id
            request.reviewed_at = datetime.now(timezone.utc)
            request.audit_note = audit_note
            await self._session.commit()
            record_project_skill_event("supersede", "success")
            raise ProjectSkillConflict(
                "change request was superseded by a newer active version"
            )

        version = request.proposed_version
        latest_scan = (
            await self._latest_scan(version.id) if version is not None else None
        )
        findings = latest_scan.findings if latest_scan is not None else []
        has_warnings = any(finding.get("severity") == "warning" for finding in findings)
        if version is not None and (
            latest_scan is None or latest_scan.scan_state != "passed"
        ):
            raise ProjectSkillApprovalError(
                "scanner blockers must be cleared before approval"
            )
        validate_approval_acknowledgements(
            is_self_approval=request.requester_id == user_id,
            has_warnings=has_warnings,
            self_approval_acknowledged=self_approval_acknowledged,
            warning_acknowledged=warning_acknowledged,
            audit_note=audit_note,
        )
        will_add_active_skill = request.action in {
            "activate",
            "rollback",
            "restore",
        } and (skill.active_version_id is None or skill.is_archived)
        if will_add_active_skill:
            active_count = await self._session.scalar(
                select(func.count())
                .select_from(ProjectSkill)
                .where(
                    ProjectSkill.project_id == project_id,
                    ProjectSkill.active_version_id.is_not(None),
                    ProjectSkill.is_archived.is_(False),
                    ProjectSkill.is_deleted.is_(False),
                )
            )
            if active_count >= 32:
                raise ProjectSkillApprovalError("project already has 32 active skills")
        if request.action in {"activate", "rollback"}:
            if version is None:
                raise ProjectSkillApprovalError(
                    "activation requires a proposed version"
                )
            skill.active_version_id = version.id
            skill.is_archived = False
        elif request.action == "archive":
            if skill.active_version_id is None:
                raise ProjectSkillApprovalError("cannot archive an inactive skill")
            skill.is_archived = True
        elif request.action == "restore":
            if skill.active_version_id is None:
                raise ProjectSkillApprovalError(
                    "cannot restore a skill without an active version"
                )
            skill.is_archived = False
        else:
            raise ProjectSkillApprovalError("unknown change-request action")
        request.status = "approved"
        request.reviewer_id = user_id
        request.reviewed_at = datetime.now(timezone.utc)
        request.warning_acknowledged = warning_acknowledged
        request.audit_note = audit_note
        await self._session.commit()
        await self._session.refresh(request)
        record_project_skill_event("approval", "success")
        return request

    async def reject(
        self,
        *,
        project_id: UUID,
        request_id: UUID,
        user_id: UUID,
        audit_note: str,
    ) -> ProjectSkillChangeRequest:
        if not audit_note or not audit_note.strip():
            raise ProjectSkillApprovalError("rejection requires an audit note")
        _skill, request = await self._lock_request_and_skill(
            project_id=project_id, request_id=request_id, user_id=user_id
        )
        if request.status != "pending":
            raise ProjectSkillConflict("change request is no longer pending")
        request.status = "rejected"
        request.reviewer_id = user_id
        request.audit_note = audit_note
        request.reviewed_at = datetime.now(timezone.utc)
        await self._session.commit()
        record_project_skill_event("rejection", "success")
        return request

    async def rescan_change_request(
        self, *, project_id: UUID, request_id: UUID, user_id: UUID
    ) -> tuple[ProjectSkillVersion, ProjectSkillVersionScan]:
        """Append a scan result after the same skill/request lock ordering."""
        _skill, request = await self._lock_request_and_skill(
            project_id=project_id, request_id=request_id, user_id=user_id
        )
        if request.status != "pending" or request.proposed_version_id is None:
            raise ProjectSkillConflict(
                "change request has no scannable pending version"
            )
        version = await self._session.scalar(
            select(ProjectSkillVersion)
            .where(ProjectSkillVersion.id == request.proposed_version_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if version is None:
            raise ProjectSkillConflict("proposed version no longer exists")
        scan = await ProjectSkillCatalogService(self._session).record_scan(
            version=cast(ProjectSkillVersion, version), user_id=user_id
        )
        await self._session.commit()
        record_project_skill_event("rescan", getattr(scan, "scan_state", "completed"))
        return cast(ProjectSkillVersion, version), scan
