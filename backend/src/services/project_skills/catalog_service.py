"""Catalog identity and proposal operations for immutable project skills."""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ProjectSkill, ProjectSkillChangeRequest, ProjectSkillVersion

from .access import get_authorized_project
from .scanner import scan_skill_document
from .skill_document import parse_skill_document


class ProjectSkillCatalogError(ValueError):
    """A proposal cannot be created while preserving catalog invariants."""


class ProjectSkillCatalogService:
    """Creates identities, append-only versions, and staged change requests."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_skills(self, *, project_id, user_id):
        await get_authorized_project(
            self._session, project_id=project_id, user_id=user_id, capability="read"
        )
        return list(
            (
                await self._session.scalars(
                    select(ProjectSkill)
                    .where(
                        ProjectSkill.project_id == project_id,
                        ProjectSkill.is_deleted.is_(False),
                    )
                    .order_by(ProjectSkill.normalized_name)
                )
            ).all()
        )

    async def get_skill(
        self, *, project_id, skill_name: str, user_id, capability: str = "read"
    ) -> ProjectSkill:
        await get_authorized_project(
            self._session, project_id=project_id, user_id=user_id, capability=capability
        )
        skill = await self._session.scalar(
            select(ProjectSkill).where(
                ProjectSkill.project_id == project_id,
                ProjectSkill.normalized_name == skill_name,
                ProjectSkill.is_deleted.is_(False),
            )
        )
        if skill is None:
            raise ProjectSkillCatalogError("skill not found")
        return skill

    async def create_skill(self, *, project_id, user_id, document_text: str):
        await get_authorized_project(
            self._session, project_id=project_id, user_id=user_id, capability="edit"
        )
        document = parse_skill_document(document_text)
        existing_names = set(
            (
                await self._session.scalars(
                    select(ProjectSkill.normalized_name).where(
                        ProjectSkill.project_id == project_id
                    )
                )
            ).all()
        )
        if document.name in existing_names:
            raise ProjectSkillCatalogError("skill name already exists in this project")
        skill = ProjectSkill(
            project_id=project_id, normalized_name=document.name, created_by_id=user_id
        )
        self._session.add(skill)
        await self._session.flush()
        version = await self._new_version(
            skill=skill,
            user_id=user_id,
            document_text=document_text,
            version_number=1,
            existing_names=existing_names,
        )
        request = ProjectSkillChangeRequest(
            skill_id=skill.id,
            action="activate",
            proposed_version_id=version.id,
            expected_active_version_id=None,
            requester_id=user_id,
            status="pending",
        )
        self._session.add(request)
        await self._session.commit()
        await self._session.refresh(skill)
        await self._session.refresh(version)
        await self._session.refresh(request)
        return skill, version, request

    async def propose_version(
        self, *, project_id, skill_name: str, user_id, document_text: str
    ):
        skill = await self.get_skill(
            project_id=project_id,
            skill_name=skill_name,
            user_id=user_id,
            capability="edit",
        )
        document = parse_skill_document(document_text)
        if document.name != skill.normalized_name:
            raise ProjectSkillCatalogError("version name must match the skill identity")
        next_version = (
            await self._session.scalar(
                select(func.max(ProjectSkillVersion.version)).where(
                    ProjectSkillVersion.skill_id == skill.id
                )
            )
            or 0
        ) + 1
        existing_names = set(
            (
                await self._session.scalars(
                    select(ProjectSkill.normalized_name).where(
                        ProjectSkill.project_id == project_id,
                        ProjectSkill.id != skill.id,
                    )
                )
            ).all()
        )
        version = await self._new_version(
            skill=skill,
            user_id=user_id,
            document_text=document_text,
            version_number=next_version,
            existing_names=existing_names,
        )
        request = ProjectSkillChangeRequest(
            skill_id=skill.id,
            action="activate",
            proposed_version_id=version.id,
            prior_version_id=skill.active_version_id,
            expected_active_version_id=skill.active_version_id,
            requester_id=user_id,
            status="pending",
        )
        self._session.add(request)
        await self._session.commit()
        await self._session.refresh(version)
        await self._session.refresh(request)
        return version, request

    async def stage_state_change(
        self,
        *,
        project_id,
        skill_name: str,
        user_id,
        action: str,
        target_version_id=None,
    ):
        if action not in {"archive", "restore", "rollback"}:
            raise ProjectSkillCatalogError("unsupported state-change action")
        skill = await self.get_skill(
            project_id=project_id,
            skill_name=skill_name,
            user_id=user_id,
            capability="edit",
        )
        if action == "archive" and skill.is_archived:
            raise ProjectSkillCatalogError("skill is already archived")
        if action == "restore" and not skill.is_archived:
            raise ProjectSkillCatalogError("skill is not archived")
        if action == "rollback":
            target = await self._session.scalar(
                select(ProjectSkillVersion).where(
                    ProjectSkillVersion.id == target_version_id,
                    ProjectSkillVersion.skill_id == skill.id,
                )
            )
            if target is None:
                raise ProjectSkillCatalogError(
                    "rollback version is not part of this skill"
                )
            was_approved = await self._session.scalar(
                select(ProjectSkillChangeRequest.id).where(
                    ProjectSkillChangeRequest.skill_id == skill.id,
                    ProjectSkillChangeRequest.proposed_version_id == target.id,
                    ProjectSkillChangeRequest.status == "approved",
                )
            )
            if was_approved is None:
                raise ProjectSkillCatalogError(
                    "rollback target was not previously approved"
                )
        request = ProjectSkillChangeRequest(
            skill_id=skill.id,
            action=action,
            proposed_version_id=target_version_id if action == "rollback" else None,
            prior_version_id=skill.active_version_id,
            expected_active_version_id=skill.active_version_id,
            requester_id=user_id,
            status="pending",
        )
        self._session.add(request)
        await self._session.commit()
        await self._session.refresh(request)
        return request

    async def _new_version(
        self,
        *,
        skill: ProjectSkill,
        user_id,
        document_text: str,
        version_number: int,
        existing_names: set[str],
    ) -> ProjectSkillVersion:
        document = parse_skill_document(document_text)
        scan = scan_skill_document(document_text, existing_names=existing_names)
        version = ProjectSkillVersion(
            skill_id=skill.id,
            version=version_number,
            instructions=document.canonical_text,
            parsed_name=document.name,
            description=document.description,
            content_hash=document.content_hash,
            scan_state="blocked" if scan.is_blocking else "passed",
            scan_findings=[asdict(finding) for finding in scan.findings],
            scanner_version=scan.scanner_version,
            author_id=user_id,
        )
        self._session.add(version)
        await self._session.flush()
        return version
