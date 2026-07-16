"""Unit tests for the OpenAPI contract-ratchet generator (audit C5).

These exercise the ratchet's pure logic — deterministic serialization and the
``--check`` diff/exit behavior — plus the invariant that the committed
``backend/openapi.json`` snapshot is in the generator's canonical form. None of
this imports the FastAPI app (the app import lives inside ``_build_schema``,
which the drift tests monkeypatch), so the suite is fast and infra-free.
"""

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci" / "generate_openapi.py"
SNAPSHOT_PATH = REPO_ROOT / "backend" / "openapi.json"


def _load_generator():
    """Import generate_openapi.py by path (it is not an installed package)."""
    spec = importlib.util.spec_from_file_location(
        "generate_openapi_under_test", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


gen = _load_generator()


def test_serialize_is_sorted_deterministic_and_newline_terminated():
    schema = {"b": 1, "a": {"y": 2, "x": 3}}
    out = gen._serialize(schema)

    assert out.endswith("\n")
    assert out.index('"a"') < out.index('"b"')  # keys sorted
    assert out.index('"x"') < out.index('"y"')  # nested keys sorted
    assert gen._serialize(schema) == out  # idempotent
    assert json.loads(out) == schema  # round-trips


def test_check_passes_when_snapshot_matches(tmp_path, monkeypatch):
    fake = {"openapi": "3.1.0", "info": {"title": "x"}, "paths": {}}
    monkeypatch.setattr(gen, "_build_schema", lambda: fake)
    snapshot = tmp_path / "openapi.json"
    snapshot.write_text(gen._serialize(fake), encoding="utf-8")

    assert gen.main(["--check", "--output", str(snapshot)]) == 0


def test_check_fails_and_reports_when_snapshot_drifts(tmp_path, monkeypatch, capsys):
    committed = {"openapi": "3.1.0", "paths": {}}
    regenerated = {"openapi": "3.1.0", "paths": {"/new": {"get": {}}}}
    monkeypatch.setattr(gen, "_build_schema", lambda: regenerated)
    snapshot = tmp_path / "openapi.json"
    snapshot.write_text(gen._serialize(committed), encoding="utf-8")

    assert gen.main(["--check", "--output", str(snapshot)]) == 1
    err = capsys.readouterr().err
    assert "backend contract changed" in err
    assert "generate_openapi.py" in err  # actionable remediation
    assert "/new" in err  # the drift is shown in the diff


def test_check_fails_when_snapshot_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "_build_schema", lambda: {"openapi": "3.1.0"})
    missing = tmp_path / "does-not-exist.json"

    assert gen.main(["--check", "--output", str(missing)]) == 1


def test_write_mode_emits_canonical_snapshot(tmp_path, monkeypatch):
    fake = {"openapi": "3.1.0", "paths": {"/z": {}, "/a": {}}}
    monkeypatch.setattr(gen, "_build_schema", lambda: fake)
    snapshot = tmp_path / "openapi.json"

    assert gen.main(["--output", str(snapshot)]) == 0
    written = snapshot.read_text(encoding="utf-8")
    assert written == gen._serialize(fake)
    # A freshly written snapshot must pass its own --check.
    assert gen.main(["--check", "--output", str(snapshot)]) == 0


def test_committed_snapshot_is_canonical_and_structurally_valid():
    """The tracked snapshot must be exactly what the generator would emit.

    Guards against a hand-edited or stale ``backend/openapi.json`` — either
    would make a CI regeneration non-idempotent and the ratchet noisy.
    """
    raw = SNAPSHOT_PATH.read_text(encoding="utf-8")
    document = json.loads(raw)

    assert raw == gen._serialize(document), (
        "backend/openapi.json is not in canonical form; regenerate with "
        "`python scripts/ci/generate_openapi.py` instead of hand-editing."
    )
    assert str(document.get("openapi", "")).startswith("3.")
    assert document.get("paths"), "snapshot has no paths"
    assert "components" in document


def test_contract_job_verifies_generated_typescript() -> None:
    """The openapi-contract CI job must regenerate and diff BOTH committed
    artifacts — the Python schema snapshot and the generated TypeScript —
    so frontend types can never silently drift from the app contract."""
    import yaml

    workflow_path = REPO_ROOT / ".github" / "workflows" / "test-pipeline.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    job = workflow["jobs"]["openapi-contract"]
    steps = job["steps"]

    def step_runs(fragment: str) -> bool:
        return any(fragment in (step.get("run") or "") for step in steps)

    uses = [step.get("uses", "") for step in steps]
    assert any(u.startswith("pnpm/action-setup") for u in uses), (
        "openapi-contract must set up pnpm to run the TypeScript generator"
    )
    node_steps = [s for s in steps if s.get("uses", "").startswith("actions/setup-node")]
    assert node_steps, "openapi-contract must set up Node"
    node_version = str(node_steps[0].get("with", {}).get("node-version", ""))
    assert "NODE_VERSION" in node_version or node_version == "24", (
        f"openapi-contract Node must be the canonical 24, got {node_version!r}"
    )
    assert step_runs("pnpm install --frozen-lockfile"), (
        "openapi-contract must install from the root pnpm-lock.yaml"
    )
    assert step_runs("generate:api-types"), (
        "openapi-contract must regenerate frontend/src/types/generated/api.d.ts"
    )
    assert step_runs(
        "git diff --exit-code -- backend/openapi.json "
        "frontend/src/types/generated/api.d.ts"
    ), "openapi-contract must fail on drift in EITHER committed artifact"
