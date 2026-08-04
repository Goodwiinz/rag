"""Static contracts for the exact-SHA development release chain.

These tests intentionally inspect workflow structure instead of executing GitHub
Actions.  They protect the trust boundaries that connect a successful Test
Pipeline run to an immutable image digest and the ``deploy/dev`` GitOps branch.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
RELEASE_PATH = WORKFLOWS / "release-dev.yml"
DOCKER_PATH = WORKFLOWS / "docker-build.yml"
GITOPS_PATH = WORKFLOWS / "gitops-image-update.yml"
DEPLOY_PATH = WORKFLOWS / "deploy.yml"


def _load_workflow(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    # PyYAML follows YAML 1.1 and may deserialize the unquoted ``on`` key as True.
    return cast("dict[str, Any]", workflow.get("on") or workflow.get(True))


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


def _step_with_id(
    workflow: dict[str, Any], job_name: str, step_id: str
) -> dict[str, Any]:
    for step in _steps(workflow, job_name):
        if step.get("id") == step_id:
            return step
    raise AssertionError(f"{job_name!r} has no step with id {step_id!r}")


def _job_with_run(
    workflow: dict[str, Any], fragment: str
) -> tuple[str, dict[str, Any]]:
    matches = [
        (job_name, cast("dict[str, Any]", job))
        for job_name, job in cast("dict[str, Any]", workflow["jobs"]).items()
        if any(
            fragment in str(step.get("run", ""))
            for step in cast("list[dict[str, Any]]", job.get("steps", []))
        )
    ]
    assert len(matches) == 1, (
        f"expected exactly one job running {fragment!r}, found "
        f"{[name for name, _ in matches]}"
    )
    return matches[0]


def _normalized_shell(step: dict[str, Any]) -> str:
    return " ".join(str(step.get("run", "")).split()).replace("\\ ", "")


def test_release_is_only_a_completed_test_pipeline_run_on_develop() -> None:
    release = _load_workflow(RELEASE_PATH)
    triggers = _triggers(release)

    assert set(triggers) == {"workflow_run"}
    producer = triggers["workflow_run"]
    assert producer["workflows"] == ["Test Pipeline"]
    assert producer["types"] == ["completed"]
    assert producer["branches"] == ["develop"]


def test_release_authorization_fails_closed_for_the_producer_identity() -> None:
    release = _load_workflow(RELEASE_PATH)
    condition = " ".join(str(release["jobs"]["authorize"]["if"]).split())

    for required in (
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'push'",
        "github.event.workflow_run.head_branch == 'develop'",
        "github.event.workflow_run.head_repository.full_name == github.repository",
    ):
        assert required in condition


def test_release_revalidates_exact_run_and_named_release_gate_via_api() -> None:
    release = _load_workflow(RELEASE_PATH)
    step = _step_with_id(release, "authorize", "producer")
    env = step["env"]
    run = str(step["run"])

    assert env["GH_TOKEN"] == "${{ github.token }}"
    assert env["EVENT_SOURCE_SHA"] == "${{ github.event.workflow_run.head_sha }}"
    assert env["TEST_RUN_ID"] == "${{ github.event.workflow_run.id }}"
    assert env["TEST_RUN_ATTEMPT"] == ("${{ github.event.workflow_run.run_attempt }}")
    assert '[[ ! "$TEST_RUN_ATTEMPT" =~ ^[1-9][0-9]*$ ]]' in run
    assert 'gh api "repos/$REPOSITORY/actions/runs/$TEST_RUN_ID"' in run
    assert ".event, .head_branch, .head_sha, .conclusion" in run
    assert ".head_repository.full_name, .run_attempt, .html_url" in run
    assert "RUN_REPOSITORY RUN_ATTEMPT RUN_URL" in run
    assert '[ "$RUN_EVENT" != "push" ]' in run
    assert '[ "$RUN_BRANCH" != "develop" ]' in run
    assert '[ "$RUN_SHA" != "$EVENT_SOURCE_SHA" ]' in run
    assert '[ "$RUN_CONCLUSION" != "success" ]' in run
    assert '[ "$RUN_REPOSITORY" != "$REPOSITORY" ]' in run
    assert '[ "$RUN_ATTEMPT" != "$TEST_RUN_ATTEMPT" ]' in run

    assert (
        "actions/runs/$TEST_RUN_ID/attempts/$TEST_RUN_ATTEMPT/jobs?per_page=100" in run
    )
    assert "filter=latest" not in run
    assert 'select(.name == "Release Gate")' in run
    assert "[.status, .conclusion, .head_sha]" in run
    assert '"${#RELEASE_GATES[@]}" -ne 1' in run
    assert '[ "$GATE_STATUS" != "completed" ]' in run
    assert '[ "$GATE_CONCLUSION" != "success" ]' in run
    assert '[ "$GATE_SHA" != "$RUN_SHA" ]' in run
    assert 'echo "test_run_attempt=$TEST_RUN_ATTEMPT" >> "$GITHUB_OUTPUT"' in run


def test_attempt_identity_is_preserved_in_release_and_audit_evidence() -> None:
    release = _load_workflow(RELEASE_PATH)
    authorize_outputs = release["jobs"]["authorize"]["outputs"]
    promotion = _step_with_id(release, "promote", "promotion")
    evidence = _step_with_id(release, "promote", "evidence")
    promotion_run = str(promotion["run"])
    evidence_run = str(evidence["run"])

    assert authorize_outputs["test_run_attempt"] == (
        "${{ steps.producer.outputs.test_run_attempt }}"
    )
    assert promotion["env"]["TEST_RUN_ATTEMPT"] == (
        "${{ needs.authorize.outputs.test_run_attempt }}"
    )
    assert '--arg test_run_attempt "$TEST_RUN_ATTEMPT"' in promotion_run
    assert "test_run_attempt: $test_run_attempt" in promotion_run
    assert promotion_run.index("test_run_attempt: $test_run_attempt") < (
        promotion_run.index('> "$RELEASE_FILE"')
    )

    assert evidence["env"]["TEST_RUN_ATTEMPT"] == (
        "${{ needs.authorize.outputs.test_run_attempt }}"
    )
    assert '--arg test_run_attempt "$TEST_RUN_ATTEMPT"' in evidence_run
    assert "test_run_attempt: $test_run_attempt" in evidence_run
    assert evidence_run.index("test_run_attempt: $test_run_attempt") < (
        evidence_run.index("> release-evidence.json")
    )

    summary = evidence_run[evidence_run.index('echo "## Dev Release Evidence"') :]
    assert "$TEST_RUN_ATTEMPT" in summary
    assert "GITHUB_STEP_SUMMARY" in summary


def test_release_attempts_are_serialized() -> None:
    release = _load_workflow(RELEASE_PATH)
    assert release["concurrency"] == {
        "group": "release-dev",
        "cancel-in-progress": True,
    }


def test_authorize_checks_out_and_rechecks_the_exact_develop_sha() -> None:
    release = _load_workflow(RELEASE_PATH)
    checkout = _step_with_action(release, "authorize", "actions/checkout@")
    prebuild = _step_with_id(release, "authorize", "prebuild")
    run = str(prebuild["run"])

    assert checkout["with"]["ref"] == "${{ steps.producer.outputs.source_sha }}"
    assert prebuild["env"]["SOURCE_SHA"] == "${{ steps.producer.outputs.source_sha }}"
    assert 'ACTUAL_SHA="$(git rev-parse HEAD)"' in run
    assert '[ "$ACTUAL_SHA" != "$SOURCE_SHA" ]' in run
    assert "+refs/heads/develop:refs/remotes/origin/develop" in run
    assert 'LATEST_DEVELOP_SHA="$(git rev-parse refs/remotes/origin/develop)"' in run
    assert '[ "$LATEST_DEVELOP_SHA" != "$SOURCE_SHA" ]' in run
    assert 'echo "current=false" >> "$GITHUB_OUTPUT"' in run
    assert 'echo "current=true" >> "$GITHUB_OUTPUT"' in run
    assert release["jobs"]["build"]["if"] == (
        "needs.authorize.outputs.current == 'true'"
    )


def test_release_passes_only_the_authorized_sha_to_reusable_build() -> None:
    release = _load_workflow(RELEASE_PATH)
    build = release["jobs"]["build"]

    assert build["needs"] == "authorize"
    assert build["uses"] == "./.github/workflows/docker-build.yml"
    assert build["with"] == {"source_sha": "${{ needs.authorize.outputs.source_sha }}"}


def test_fresh_promotion_rechecks_develop_before_commit_and_write_token() -> None:
    release = _load_workflow(RELEASE_PATH)
    promotion_job, _ = _job_with_run(release, "commit -m")
    identity = _step_with_run(release, promotion_job, "git rev-parse HEAD")
    last_head = _step_with_id(release, promotion_job, "last-head")
    promotion = _step_with_run(release, promotion_job, "git switch --force-create")
    last_head_run = str(last_head["run"])
    promotion_run = str(promotion["run"])

    assert 'ACTUAL_SHA="$(git rev-parse HEAD)"' in str(identity["run"])
    assert '[ "$ACTUAL_SHA" != "$SOURCE_SHA" ]' in str(identity["run"])
    develop_query = 'gh api "repos/$REPOSITORY/git/ref/heads/develop"'
    assert develop_query in promotion_run
    assert develop_query in last_head_run
    assert '[ "$LATEST_DEVELOP_SHA" != "$SOURCE_SHA" ]' in promotion_run
    assert '[ "$LATEST_DEVELOP_SHA" != "$SOURCE_SHA" ]' in last_head_run
    assert promotion["if"] == "needs.validate-release.outputs.current == 'true'"

    steps = _steps(release, promotion_job)
    assert steps.index(promotion) < steps.index(last_head)

    first_check = promotion_run.index(develop_query)
    first_comparison = promotion_run.index(
        '[ "$LATEST_DEVELOP_SHA" != "$SOURCE_SHA" ]', first_check
    )
    assert first_check < first_comparison < promotion_run.index("git switch")
    assert first_comparison < promotion_run.index("commit -m")


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


def test_promotion_uses_digest_as_identity_and_tag_as_trace_metadata() -> None:
    release = _load_workflow(RELEASE_PATH)
    promotion = _step_with_run(release, "promote", "backend.image.digest")
    run = str(promotion["run"])

    assert promotion["env"]["DIGEST"] == "${{ needs.build.outputs.digest }}"
    assert promotion["env"]["IMAGE_TAG"] == "${{ needs.build.outputs.image_tag }}"
    assert "sha256:[0-9a-f]{64}" in run
    assert "registry.digitalocean.com/ragsystemregistry/backend:$SOURCE_SHA" in run
    assert ".backend.image.digest = strenv(DIGEST)" in run
    assert ".backend.image.tag = strenv(SOURCE_SHA)" in run
    assert ".backend.image.sourceSha = strenv(SOURCE_SHA)" in run
    assert '--arg image_tag "$IMAGE_TAG"' in run
    assert '--arg digest "$DIGEST"' in run


def test_promotion_mints_a_dedicated_app_token_for_write_access() -> None:
    release = _load_workflow(RELEASE_PATH)
    promotion_job, promote = _job_with_run(release, "commit -m")
    steps = _steps(release, promotion_job)
    prepare = _step_with_run(release, promotion_job, "CHANGED_FILES")
    last_head = _step_with_id(release, promotion_job, "last-head")
    token = _step_with_action(
        release, promotion_job, "actions/create-github-app-token@"
    )
    checkout = _step_with_action(release, promotion_job, "actions/checkout@")
    push = _step_with_run(release, promotion_job, "--force-with-lease")

    assert promote["permissions"]["contents"] == "read"
    assert token["with"]["app-id"] == "${{ vars.DEV_RELEASE_APP_ID }}"
    assert token["with"]["private-key"] == (
        "${{ secrets.DEV_RELEASE_APP_PRIVATE_KEY }}"
    )
    assert token["with"]["permission-contents"] == "write"
    assert checkout["with"]["ref"] == "${{ needs.authorize.outputs.source_sha }}"
    assert checkout["with"]["persist-credentials"] is False
    assert "token" not in checkout["with"]

    assert "commit -m" in str(prepare["run"])
    assert "git push" not in str(prepare["run"])
    assert "push \\" in str(push["run"])
    assert "commit -m" not in str(push["run"])
    assert (
        steps.index(prepare)
        < steps.index(last_head)
        < steps.index(token)
        < steps.index(push)
    )
    assert token["if"] == "steps.last-head.outputs.current == 'true'"

    token_reference = "${{ steps.app-token.outputs.token }}"
    token_consumers = [step for step in steps if token_reference in str(step)]
    assert token_consumers == [push]


def test_promotion_uses_force_with_lease_only_for_deploy_dev() -> None:
    release = _load_workflow(RELEASE_PATH)
    promotion_job, _ = _job_with_run(release, "commit -m")
    prepare = _step_with_run(release, promotion_job, "CHANGED_FILES")
    push = _step_with_run(release, promotion_job, "--force-with-lease")
    prepare_run = str(prepare["run"])
    push_run = str(push["run"])

    assert "git/matching-refs/heads/deploy/dev?per_page=100" in prepare_run
    assert 'select(.ref == "refs/heads/deploy/dev")' in prepare_run
    assert '"${#DEPLOY_REFS[@]}" -gt 1' in prepare_run
    assert 'git switch --force-create deploy/dev "$SOURCE_SHA"' in prepare_run
    assert (
        '"--force-with-lease=refs/heads/deploy/dev:${EXPECTED_DEPLOY_SHA}"' in push_run
    )
    assert "HEAD:refs/heads/deploy/dev" in push_run
    assert "HEAD:refs/heads/develop" not in push_run


def test_release_commit_has_an_exact_two_file_allowlist() -> None:
    release = _load_workflow(RELEASE_PATH)
    promotion = _step_with_run(release, "promote", "CHANGED_FILES")
    run = str(promotion["run"])

    assert (
        'VALUES_FILE="infrastructure/helm/knowledge-graph-analytics/'
        'values-dev.yaml"' in run
    )
    assert (
        'RELEASE_FILE="infrastructure/helm/knowledge-graph-analytics/'
        'release-dev.json"' in run
    )
    assert '"${#CHANGED_FILES[@]}" -ne 2' in run
    assert 'grep -Fxq "$VALUES_FILE"' in run
    assert 'grep -Fxq "$RELEASE_FILE"' in run
    assert 'git add "$VALUES_FILE" "$RELEASE_FILE"' in run
    assert len(re.findall(r"\bgit add\b", run)) == 1


def test_helm_validation_uses_dev_overlay_and_finishes_before_push() -> None:
    release = _load_workflow(RELEASE_PATH)
    validation_job, validation = _job_with_run(
        release, "backend_image_digest_render_test.sh"
    )
    promotion_job, promotion = _job_with_run(release, "commit -m")
    validation_step = _step_with_run(release, validation_job, "helm lint")
    validation_run = _normalized_shell(validation_step)

    lint = 'helm lint "$CHART" -f "$CHART/values.yaml" -f "$VALUES_FILE"'
    template = (
        'helm template nous-dev "$CHART" -f "$CHART/values.yaml" '
        '-f "$VALUES_FILE" >/dev/null'
    )
    render_assertion = 'bash "$CHART/tests/backend_image_digest_render_test.sh"'
    assert lint in validation_run
    assert template in validation_run
    assert render_assertion in validation_run

    assert validation_job != promotion_job
    assert validation["permissions"] == {"contents": "read"}
    assert validation_job in cast("list[str]", promotion["needs"])
    assert "git push" not in str(validation)
    assert "actions/create-github-app-token" not in str(validation)
    assert "DEV_RELEASE_APP" not in str(validation)
    assert "secrets." not in str(validation)

    validation_checkout = _step_with_action(
        release, validation_job, "actions/checkout@"
    )
    assert validation_checkout["with"]["ref"] == (
        "${{ needs.authorize.outputs.source_sha }}"
    )
    assert validation_checkout["with"]["persist-credentials"] is False
    assert "token" not in validation_checkout["with"]

    all_run_blocks = [
        str(step.get("run", ""))
        for job in cast("dict[str, Any]", release["jobs"]).values()
        for step in cast("list[dict[str, Any]]", job.get("steps", []))
    ]
    assert (
        sum("backend_image_digest_render_test.sh" in run for run in all_run_blocks) == 1
    )


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
