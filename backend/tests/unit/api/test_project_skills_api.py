"""Route-contract tests for the project-skills API surface."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.api.research.project_skills import (
    _translate_error,
    require_project_skill_catalog,
    router,
)
from src.services.project_skills.catalog_service import ProjectSkillProposalConflict


def test_project_skill_router_exposes_staged_catalog_routes_once():
    paths = {route.path for route in router.routes}

    assert "/api/v1/projects/{project_id}/skills" in paths
    assert "/api/v1/projects/{project_id}/skills/{skill_name}" in paths
    assert "/api/v1/projects/{project_id}/skills/{skill_name}/versions" in paths
    assert (
        "/api/v1/projects/{project_id}/skills/change-requests/{request_id}/approve"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/skills/change-requests/{request_id}/rescan"
        in paths
    )
    assert "/api/v1/projects/{project_id}/skills/{skill_name}/rollback" in paths


def test_create_uniqueness_conflict_translates_to_http_409():
    with pytest.raises(HTTPException) as error:
        _translate_error(ProjectSkillProposalConflict("duplicate normalized name"))

    assert error.value.status_code == 409


def test_disabled_catalog_is_a_non_leaking_feature_unavailable_404():
    with (
        patch(
            "src.api.research.project_skills.get_settings",
            return_value=SimpleNamespace(PROJECT_SKILL_CATALOG_ENABLED=False),
        ),
        pytest.raises(HTTPException) as error,
    ):
        require_project_skill_catalog()

    assert error.value.status_code == 404
    assert error.value.detail == "Project skills are unavailable."
