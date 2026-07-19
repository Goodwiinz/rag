"""Authorization and proposal contracts for the project-skill catalog."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.services.project_skills.access import (
    ProjectSkillAccessDenied,
    assert_workspace_access,
)


def _workspace(owner_id, role=None):
    workspace = SimpleNamespace(owner_id=owner_id)
    workspace.can_user_edit = lambda user_id: role == "editor" or user_id == owner_id
    workspace.can_user_admin = lambda user_id: role == "admin" or user_id == owner_id
    workspace.is_member = lambda user_id: role is not None or user_id == owner_id
    return workspace


def test_viewer_can_read_but_not_propose():
    user_id = uuid4()
    workspace = _workspace(uuid4(), role="viewer")

    assert_workspace_access(workspace, user_id, "read")
    with pytest.raises(ProjectSkillAccessDenied):
        assert_workspace_access(workspace, user_id, "edit")


def test_editor_can_propose_but_not_approve():
    user_id = uuid4()
    workspace = _workspace(uuid4(), role="editor")

    assert_workspace_access(workspace, user_id, "edit")
    with pytest.raises(ProjectSkillAccessDenied):
        assert_workspace_access(workspace, user_id, "admin")
