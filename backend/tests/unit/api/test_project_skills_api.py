"""Route-contract tests for the project-skills API surface."""

import pytest
from fastapi import HTTPException

from src.api.research.project_skills import _translate_error, router
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
