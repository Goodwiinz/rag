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
