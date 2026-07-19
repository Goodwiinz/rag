"""Database-backed approval and CAS behavior for project skills."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ProjectSkill, WorkspaceMember, WorkspaceRole
from src.services.project_skills.approval_service import (
    ProjectSkillApprovalService,
    ProjectSkillConflict,
)
from src.services.project_skills.catalog_service import ProjectSkillCatalogService


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
