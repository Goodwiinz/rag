"""Static contracts for the image-build workflow and the absence of
automatic deploy paths.

These tests intentionally inspect workflow structure instead of executing
GitHub Actions. The automatic exact-SHA dev release chain (``release-dev.yml``)
was removed because it was never bootstrapped (no ``deploy/dev`` branch, no
release-App credential); these tests now protect what remains: that
``docker-build.yml`` still builds and verifies an exact-SHA immutable image on
demand, and that neither ``gitops-image-update.yml`` nor ``deploy.yml`` has
grown an automatic trigger that could recreate an unproven auto-deploy path.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
DOCKER_PATH = WORKFLOWS / "docker-build.yml"
GITOPS_PATH = WORKFLOWS / "gitops-image-update.yml"
DEPLOY_PATH = WORKFLOWS / "deploy.yml"


def _load_workflow(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    # PyYAML follows YAML 1.1 and may deserialize the unquoted ``on`` key as True.
    return cast("dict[str, Any]", workflow.get("on") or workflow.get(True))  # type: ignore[call-overload]


def _steps(workflow: dict[str, Any], job_name: str) -> list[dict[str, Any]]:
    return cast("list[dict[str, Any]]", workflow["jobs"][job_name]["steps"])


def _step_with_run(
    workflow: dict[str, Any], job_name: str, fragment: str
) -> dict[str, Any]:
    for step in _steps(workflow, job_name):
        if fragment in str(step.get("run", "")):
            return step
    raise AssertionError(f"{job_name!r} has no step running {fragment!r}")


def _step_with_action(
    workflow: dict[str, Any], job_name: str, action: str
) -> dict[str, Any]:
    for step in _steps(workflow, job_name):
        if str(step.get("uses", "")).startswith(action):
            return step
    raise AssertionError(f"{job_name!r} has no step using {action!r}")


def test_reusable_docker_build_checks_out_and_asserts_a_full_sha() -> None:
    docker = _load_workflow(DOCKER_PATH)
    triggers = _triggers(docker)
    source_input = triggers["workflow_call"]["inputs"]["source_sha"]
    identity = _step_with_run(docker, "build-backend", "40-character commit SHA")
    checkout = _step_with_action(docker, "build-backend", "actions/checkout@")
    assertion = _step_with_run(docker, "build-backend", "git rev-parse HEAD")

    assert source_input["required"] is True
    assert source_input["type"] == "string"
    assert "[0-9a-f]{40}" in str(identity["run"])
    assert checkout["with"]["ref"] == "${{ steps.identity.outputs.source_sha }}"
    assert checkout["with"]["fetch-depth"] == 1
    assert checkout["with"]["persist-credentials"] is False
    assert assertion["env"]["SOURCE_SHA"] == (
        "${{ steps.identity.outputs.source_sha }}"
    )
    assert '[ "$ACTUAL_SHA" != "$SOURCE_SHA" ]' in str(assertion["run"])


def test_docker_outputs_full_sha_trace_tag_and_immutable_digest() -> None:
    docker = _load_workflow(DOCKER_PATH)
    call_outputs = _triggers(docker)["workflow_call"]["outputs"]
    job = docker["jobs"]["build-backend"]
    identity = _step_with_run(docker, "build-backend", 'IMAGE_TAG="$REGISTRY/backend')
    build = _step_with_action(docker, "build-backend", "docker/build-push-action@")
    verify = _step_with_run(docker, "build-backend", "valid registry digest")

    assert call_outputs["source_sha"]["value"] == (
        "${{ jobs.build-backend.outputs.source_sha }}"
    )
    assert call_outputs["image_tag"]["value"] == (
        "${{ jobs.build-backend.outputs.image_tag }}"
    )
    assert call_outputs["digest"]["value"] == (
        "${{ jobs.build-backend.outputs.digest }}"
    )
    assert job["outputs"]["digest"] == "${{ steps.verify-image.outputs.digest }}"
    assert 'IMAGE_TAG="$REGISTRY/backend:$SOURCE_SHA"' in str(identity["run"])
    assert build["with"]["tags"] == "${{ steps.identity.outputs.image_tag }}"
    assert "GIT_SHA=${{ steps.identity.outputs.source_sha }}" in str(
        build["with"]["build-args"]
    )
    assert ":latest" not in str(build["with"]["tags"])
    assert "sha256:[0-9a-f]{64}" in str(verify["run"])
    assert 'echo "digest=$DIGEST" >> "$GITHUB_OUTPUT"' in str(verify["run"])


def test_old_gitops_workflow_has_no_automatic_dev_update_path() -> None:
    gitops = _load_workflow(GITOPS_PATH)
    triggers = _triggers(gitops)
    jobs = cast("dict[str, Any]", gitops["jobs"])
    shell = "\n".join(
        str(step.get("run", ""))
        for job in jobs.values()
        for step in cast("list[dict[str, Any]]", job.get("steps", []))
    )

    assert set(triggers) == {"workflow_dispatch"}
    assert "workflow_run" not in triggers
    assert "update-dev" not in jobs
    assert not re.search(r"git\s+push[^\n]*(?:refs/heads/)?develop", shell)
    assert "refs/heads/develop" not in shell


def test_deploy_workflow_has_no_automatic_docker_build_trigger() -> None:
    deploy = _load_workflow(DEPLOY_PATH)
    triggers = _triggers(deploy)

    assert set(triggers) == {"workflow_dispatch"}
    assert "workflow_run" not in triggers
    assert "push" not in triggers
