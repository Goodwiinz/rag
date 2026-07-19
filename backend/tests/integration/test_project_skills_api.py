"""API schemas retain canonical document and acknowledgement boundaries."""

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.research.project_skills import (
    approve_change_request,
    get_skill,
    list_skills,
)
from src.models import Collection, User
from src.schemas.project_skills import ApprovalRequest, SkillDocumentRequest
from src.services.project_skills.catalog_service import ProjectSkillCatalogService


def test_api_rejects_empty_skill_document() -> None:
    with pytest.raises(ValidationError):
        SkillDocumentRequest(document_text="")


def test_api_requires_explicit_acknowledgement_fields() -> None:
    request = ApprovalRequest(
        self_approval_acknowledged=True,
        warning_acknowledged=True,
        audit_note="Reviewed warnings.",
    )

    assert request.warning_acknowledged is True


@pytest.mark.asyncio
async def test_catalog_endpoint_includes_pending_capabilities_and_canonical_history(
    test_db: AsyncSession, test_project: Collection, test_user: User
) -> None:
    document = "---\nname: endpoint-skill\ndescription: Endpoint contract.\n---\nUse search_arxiv.\n"
    await ProjectSkillCatalogService(test_db).create_skill(
        project_id=test_project.id, user_id=test_user.id, document_text=document
    )

    catalog = await list_skills(
        project_id=test_project.id, current_user=test_user, db=test_db
    )
    detail = await get_skill(
        project_id=test_project.id,
        skill_name="endpoint-skill",
        current_user=test_user,
        db=test_db,
    )

    assert catalog.capabilities.can_edit is True
    assert catalog.capabilities.can_admin is True
    assert len(catalog.pending_change_requests) == 1
    assert detail.versions[0].document_text == document


@pytest.mark.asyncio
async def test_catalog_endpoint_includes_active_version_summary(
    test_db: AsyncSession, test_project: Collection, test_user: User
) -> None:
    document = "---\nname: active-summary\ndescription: Active list summary.\n---\nUse search_arxiv.\n"
    _skill, _version, request = await ProjectSkillCatalogService(test_db).create_skill(
        project_id=test_project.id, user_id=test_user.id, document_text=document
    )
    await approve_change_request(
        project_id=test_project.id,
        request_id=request.id,
        payload=ApprovalRequest(
            self_approval_acknowledged=True, audit_note="Approve active summary."
        ),
        current_user=test_user,
        db=test_db,
    )

    catalog = await list_skills(
        project_id=test_project.id, current_user=test_user, db=test_db
    )

    active = catalog.skills[0].active_version
    assert active is not None
    assert active.version == 1
    assert active.description == "Active list summary."
    assert active.scan_state == "passed"
