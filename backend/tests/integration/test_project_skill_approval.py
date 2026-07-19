"""Database-backed approval and CAS behavior for project skills."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    ProjectSkill,
    ProjectSkillVersion,
    ProjectSkillVersionScan,
    WorkspaceMember,
    WorkspaceRole,
)
from src.services.project_skills.approval_service import (
    ProjectSkillApprovalService,
    ProjectSkillConflict,
)
from src.services.project_skills.catalog_service import (
    ProjectSkillCatalogError,
    ProjectSkillCatalogService,
)


def _document(name: str, body: str = "Use search_arxiv for papers.") -> str:
    return f"---\nname: {name}\ndescription: Safe research helper.\n---\n{body}\n"


@pytest.mark.asyncio
async def test_owner_approves_editor_proposal_and_activates_immutable_version(
    test_db: AsyncSession, test_project, test_workspace, test_user, other_user
):
    test_db.add(
        WorkspaceMember(
            id=uuid4(),
            workspace_id=test_workspace.id,
            user_id=other_user.id,
            role=WorkspaceRole.EDITOR,
        )
    )
    await test_db.commit()
    catalog = ProjectSkillCatalogService(test_db)
    skill, version, request = await catalog.create_skill(
        project_id=test_project.id,
        user_id=other_user.id,
        document_text=_document("literature-brief"),
    )

    approved = await ProjectSkillApprovalService(test_db).approve(
        project_id=test_project.id,
        request_id=request.id,
        user_id=test_user.id,
        audit_note="Reviewed editor proposal.",
    )

    active = await test_db.scalar(
        select(ProjectSkill).where(ProjectSkill.id == skill.id)
    )
    assert approved.status == "approved"
    assert active.active_version_id == version.id
    assert version.instructions == _document("literature-brief")


@pytest.mark.asyncio
async def test_stale_approval_is_superseded_by_expected_active_version_cas(
    test_db: AsyncSession, test_project, test_user
):
    catalog = ProjectSkillCatalogService(test_db)
    skill, _version_one, first_request = await catalog.create_skill(
        project_id=test_project.id,
        user_id=test_user.id,
        document_text=_document("cas-skill"),
    )
    approvals = ProjectSkillApprovalService(test_db)
    await approvals.approve(
        project_id=test_project.id,
        request_id=first_request.id,
        user_id=test_user.id,
        self_approval_acknowledged=True,
        audit_note="Initial version.",
    )
    _v2, request_two = await catalog.propose_version(
        project_id=test_project.id,
        skill_name=skill.normalized_name,
        user_id=test_user.id,
        document_text=_document("cas-skill", "Use search_arxiv."),
    )
    _v3, request_three = await catalog.propose_version(
        project_id=test_project.id,
        skill_name=skill.normalized_name,
        user_id=test_user.id,
        document_text=_document("cas-skill", "Use create_draft."),
    )
    await approvals.approve(
        project_id=test_project.id,
        request_id=request_two.id,
        user_id=test_user.id,
        self_approval_acknowledged=True,
        audit_note="Approve v2.",
    )

    with pytest.raises(ProjectSkillConflict):
        await approvals.approve(
            project_id=test_project.id,
            request_id=request_three.id,
            user_id=test_user.id,
            self_approval_acknowledged=True,
            audit_note="Attempt stale v3.",
        )

    assert request_three.status == "superseded"


@pytest.mark.asyncio
async def test_rescan_appends_history_without_mutating_an_immutable_version(
    test_db: AsyncSession, test_project, test_user
):
    catalog = ProjectSkillCatalogService(test_db)
    _skill, version, request = await catalog.create_skill(
        project_id=test_project.id,
        user_id=test_user.id,
        document_text=_document("scan-history"),
    )
    original = (version.instructions, version.description, version.content_hash)

    await ProjectSkillApprovalService(test_db).rescan_change_request(
        project_id=test_project.id, request_id=request.id, user_id=test_user.id
    )

    refreshed = await test_db.get(ProjectSkillVersion, version.id)
    scans = list(
        (
            await test_db.scalars(
                select(ProjectSkillVersionScan).where(
                    ProjectSkillVersionScan.version_id == version.id
                )
            )
        ).all()
    )
    assert (
        refreshed.instructions,
        refreshed.description,
        refreshed.content_hash,
    ) == original
    assert len(scans) == 2


@pytest.mark.asyncio
async def test_terminal_request_cannot_be_overwritten_by_a_later_terminal_action(
    test_db: AsyncSession, test_project, test_user
):
    _skill, _version, request = await ProjectSkillCatalogService(test_db).create_skill(
        project_id=test_project.id,
        user_id=test_user.id,
        document_text=_document("terminal-lock"),
    )
    service = ProjectSkillApprovalService(test_db)
    await service.approve(
        project_id=test_project.id,
        request_id=request.id,
        user_id=test_user.id,
        self_approval_acknowledged=True,
        audit_note="Approve exactly once.",
    )

    with pytest.raises(ProjectSkillConflict):
        await service.reject(
            project_id=test_project.id,
            request_id=request.id,
            user_id=test_user.id,
            audit_note="Too late.",
        )
    assert request.status == "approved"


@pytest.mark.asyncio
async def test_overlong_description_is_persisted_as_a_blocked_auditable_scan(
    test_db: AsyncSession, test_project, test_user
):
    document = f"---\nname: long-description\ndescription: {'x' * 241}\n---\nUse search_arxiv.\n"
    _skill, version, _request = await ProjectSkillCatalogService(test_db).create_skill(
        project_id=test_project.id, user_id=test_user.id, document_text=document
    )
    scan = await test_db.scalar(
        select(ProjectSkillVersionScan)
        .where(ProjectSkillVersionScan.version_id == version.id)
        .order_by(ProjectSkillVersionScan.created_at.desc())
    )

    assert len(version.description) == 241
    assert scan.scan_state == "blocked"
    assert {finding["code"] for finding in scan.findings} == {"description_too_long"}


@pytest.mark.asyncio
async def test_archive_cannot_be_staged_for_an_inactive_skill(
    test_db: AsyncSession, test_project, test_user
):
    skill, _version, _request = await ProjectSkillCatalogService(test_db).create_skill(
        project_id=test_project.id,
        user_id=test_user.id,
        document_text=_document("inactive-archive"),
    )

    with pytest.raises(ProjectSkillCatalogError, match="active skill"):
        await ProjectSkillCatalogService(test_db).stage_state_change(
            project_id=test_project.id,
            skill_name=skill.normalized_name,
            user_id=test_user.id,
            action="archive",
        )
