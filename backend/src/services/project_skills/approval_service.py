"""Atomic approval workflow for project-skill change requests."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import ProjectSkill, ProjectSkillChangeRequest, ProjectSkillVersion

from .access import get_authorized_project
from .scanner import scan_skill_document


class ProjectSkillApprovalError(ValueError):
    """A request fails the staged approval policy."""


class ProjectSkillConflict(ProjectSkillApprovalError):
    """The expected active version changed before the locked approval."""


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
    """Locks one identity row and applies a compare-and-swap activation."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def approve(
        self,
        *,
        project_id,
        request_id,
        user_id,
        self_approval_acknowledged: bool = False,
        warning_acknowledged: bool = False,
        audit_note: str | None = None,
    ):
        await get_authorized_project(
            self._session, project_id=project_id, user_id=user_id, capability="admin"
        )
        request = await self._session.scalar(
            select(ProjectSkillChangeRequest)
            .join(ProjectSkill)
            .where(
                ProjectSkillChangeRequest.id == request_id,
                ProjectSkill.project_id == project_id,
            )
            .options(selectinload(ProjectSkillChangeRequest.proposed_version))
        )
        if request is None:
            raise ProjectSkillApprovalError("change request not found")
        if request.status != "pending":
            raise ProjectSkillConflict("change request is no longer pending")
        skill = await self._session.scalar(
            select(ProjectSkill)
            .where(ProjectSkill.id == request.skill_id)
            .with_for_update()
        )
        if skill is None:
            raise ProjectSkillApprovalError("skill not found")
        if skill.active_version_id != request.expected_active_version_id:
            request.status = "superseded"
            request.reviewer_id = user_id
            request.reviewed_at = datetime.now(timezone.utc)
            request.audit_note = audit_note
            await self._session.commit()
            raise ProjectSkillConflict(
                "change request was superseded by a newer active version"
            )

        version = request.proposed_version
        findings = version.scan_findings if version is not None else []
        has_warnings = any(finding.get("severity") == "warning" for finding in findings)
        if version is not None and version.scan_state != "passed":
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
            skill.is_archived = True
        elif request.action == "restore":
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
        return request

    async def reject(self, *, project_id, request_id, user_id, audit_note: str):
        await get_authorized_project(
            self._session, project_id=project_id, user_id=user_id, capability="admin"
        )
        if not audit_note or not audit_note.strip():
            raise ProjectSkillApprovalError("rejection requires an audit note")
        request = await self._session.scalar(
            select(ProjectSkillChangeRequest)
            .join(ProjectSkill)
            .where(
                ProjectSkillChangeRequest.id == request_id,
                ProjectSkill.project_id == project_id,
            )
        )
        if request is None or request.status != "pending":
            raise ProjectSkillApprovalError("pending change request not found")
        request.status = "rejected"
        request.reviewer_id = user_id
        request.audit_note = audit_note
        request.reviewed_at = datetime.now(timezone.utc)
        await self._session.commit()
        return request

    async def rescan(self, *, project_id, version_id, user_id):
        await get_authorized_project(
            self._session, project_id=project_id, user_id=user_id, capability="admin"
        )
        version = await self._session.scalar(
            select(ProjectSkillVersion)
            .join(ProjectSkill)
            .where(
                ProjectSkillVersion.id == version_id,
                ProjectSkill.project_id == project_id,
            )
        )
        if version is None:
            raise ProjectSkillApprovalError("skill version not found")
        scan = scan_skill_document(version.instructions)
        version.scan_state = "blocked" if scan.is_blocking else "passed"
        version.scan_findings = [finding.__dict__ for finding in scan.findings]
        version.scanner_version = scan.scanner_version
        await self._session.commit()
        return version
