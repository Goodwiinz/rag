"""Tests for the legacy loop bridge's local-backend compatibility adapter."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "loop_bridge.py"


def _load_loop_bridge():
    spec = importlib.util.spec_from_file_location("loop_bridge_adapter", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adapter_delegates_claim_arguments_to_local_backend(tmp_path, monkeypatch):
    calls = []

    class SpyBackend:
        def __init__(self, bridge_dir):
            self.bridge_dir = bridge_dir

        def claim_legacy(self, agent, branch, area, files, pr, ttl_seconds):
            calls.append((agent, branch, area, files, pr, ttl_seconds))
            return {}

    monkeypatch.setenv("LOOP_BRIDGE_DIR", str(tmp_path / "bridge"))
    module = _load_loop_bridge()
    monkeypatch.setattr(module, "LocalBackend", SpyBackend, raising=False)

    assert (
        module.main(
            [
                "claim",
                "--agent",
                "agent",
                "--branch",
                "fix/bug",
                "--area",
                "area",
                "--ttl",
                "2700",
                "--pr",
                "12",
                "--files",
                "a.py",
            ]
        )
        == 0
    )
    assert calls == [("agent", "fix/bug", "area", ["a.py"], "12", 2700)]


def test_adapter_keeps_patchable_path_for_observational_list(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir()
    claims = bridge_dir / "claims.json"
    claims.write_text("not-json", encoding="utf-8")
    monkeypatch.setenv("LOOP_BRIDGE_DIR", str(bridge_dir))
    module = _load_loop_bridge()
    original = module.Path.read_text

    def fail_only_claims(path, *args, **kwargs):
        if path == claims:
            raise OSError("simulated read race")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(module.Path, "read_text", fail_only_claims)
    assert module.main(["list"]) == 1
    assert {p.name for p in bridge_dir.iterdir()} == {"claims.json"}


def test_adapter_uses_atomic_release_result_for_legacy_message(
    tmp_path, monkeypatch, capsys
):
    calls = []

    class SpyBackend:
        def __init__(self, bridge_dir):
            self.bridge_dir = bridge_dir

        def release_legacy(self, branch, reason):
            calls.append((branch, reason))
            return True

    monkeypatch.setenv("LOOP_BRIDGE_DIR", str(tmp_path / "bridge"))
    module = _load_loop_bridge()
    monkeypatch.setattr(module, "LocalBackend", SpyBackend, raising=False)

    assert module.main(["release", "--branch", "branch"]) == 0
    assert calls == [("branch", "done")]
    assert capsys.readouterr().out == "RELEASED branch (done)\n"
