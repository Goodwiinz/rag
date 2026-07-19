"""Approval policy contracts independent of HTTP transport."""

import pytest

from src.services.project_skills.approval_service import (
    ProjectSkillApprovalError,
    validate_approval_acknowledgements,
)


def test_self_approval_requires_explicit_acknowledgement_and_note():
    with pytest.raises(ProjectSkillApprovalError, match="self-approval"):
        validate_approval_acknowledgements(
            is_self_approval=True,
            has_warnings=False,
            self_approval_acknowledged=False,
            warning_acknowledged=False,
            audit_note=None,
        )

    validate_approval_acknowledgements(
        is_self_approval=True,
        has_warnings=False,
        self_approval_acknowledged=True,
        warning_acknowledged=False,
        audit_note="I reviewed my own proposal.",
    )


def test_warnings_require_acknowledgement_and_note():
    with pytest.raises(ProjectSkillApprovalError, match="warnings"):
        validate_approval_acknowledgements(
            is_self_approval=False,
            has_warnings=True,
            self_approval_acknowledged=False,
            warning_acknowledged=False,
            audit_note="",
        )
