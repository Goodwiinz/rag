"""API schemas retain canonical document and acknowledgement boundaries."""

import pytest
from pydantic import ValidationError

from src.schemas.project_skills import ApprovalRequest, SkillDocumentRequest


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
