"""Metadata contracts for the immutable project-skill catalog."""

from src.models import (
    AgentRuntimeSnapshot,
    ProjectSkill,
    ProjectSkillChangeRequest,
    ProjectSkillVersion,
    ProjectSkillVersionScan,
)


def _constraint_names(model):
    return {
        constraint.name for constraint in model.__table__.constraints if constraint.name
    }


def test_project_skill_identity_is_project_scoped_and_versioned():
    columns = ProjectSkill.__table__.c

    assert {
        "project_id",
        "normalized_name",
        "active_version_id",
        "is_archived",
        "created_by_id",
    } <= set(columns.keys())
    assert "uq_project_skills_project_normalized_name" in _constraint_names(
        ProjectSkill
    )
    assert columns.project_id.foreign_keys
    assert columns.active_version_id.foreign_keys


def test_project_skill_versions_are_immutable_catalog_records():
    columns = ProjectSkillVersion.__table__.c

    assert {
        "skill_id",
        "version",
        "instructions",
        "parsed_name",
        "description",
        "content_hash",
        "author_id",
    } <= set(columns.keys())
    assert "uq_project_skill_versions_skill_version" in _constraint_names(
        ProjectSkillVersion
    )
    assert "scan_state" not in columns


def test_project_skill_scans_are_append_only_audit_records():
    columns = ProjectSkillVersionScan.__table__.c

    assert {
        "version_id",
        "scan_state",
        "findings",
        "scanner_version",
        "scanned_by_id",
    } <= set(columns.keys())
    assert "ck_project_skill_version_scans_state" in _constraint_names(
        ProjectSkillVersionScan
    )


def test_change_requests_capture_staged_audit_state():
    columns = ProjectSkillChangeRequest.__table__.c

    assert {
        "skill_id",
        "action",
        "proposed_version_id",
        "prior_version_id",
        "expected_active_version_id",
        "requester_id",
        "reviewer_id",
        "status",
        "warning_acknowledged",
        "audit_note",
        "reviewed_at",
    } <= set(columns.keys())
    names = _constraint_names(ProjectSkillChangeRequest)
    assert "ck_project_skill_change_requests_action" in names
    assert "ck_project_skill_change_requests_status" in names


def test_runtime_snapshot_freezes_transport_neutral_metadata():
    columns = AgentRuntimeSnapshot.__table__.c

    assert {
        "project_id",
        "user_id",
        "thread_id",
        "job_id",
        "tool_registry_hash",
        "tool_registry_version",
        "tool_metadata",
        "skill_catalog",
        "loaded_skill_versions",
        "expires_at",
    } <= set(columns.keys())
    assert columns.project_id.foreign_keys
    assert columns.user_id.foreign_keys
