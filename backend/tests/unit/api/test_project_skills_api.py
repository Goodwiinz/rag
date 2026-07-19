"""Route-contract tests for the project-skills API surface."""

from src.api.research.project_skills import router


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
