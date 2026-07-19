"""API schemas retain canonical document and acknowledgement boundaries."""

import pytest
from pydantic import ValidationError

from src.api.research.project_skills import get_skill, list_skills
from src.schemas.project_skills import ApprovalRequest, SkillDocumentRequest
from src.services.project_skills.catalog_service import ProjectSkillCatalogService


def test_api_rejects_empty_skill_document():
    with pytest.raises(ValidationError):
        SkillDocumentRequest(document_text="")


def test_api_requires_explicit_acknowledgement_fields():
    request = ApprovalRequest(
        self_approval_acknowledged=True,
        warning_acknowledged=True,
        audit_note="Reviewed warnings.",
    )

    assert request.warning_acknowledged is True


@pytest.mark.asyncio
async def test_catalog_endpoint_includes_pending_capabilities_and_canonical_history(
    test_db, test_project, test_user
):
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
