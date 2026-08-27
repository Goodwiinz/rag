"""Tests for the concurrent-loop coordination bridge (scripts/loop_bridge.py).

Pure stdlib (no app imports), driven through the module's `main()` so exit
codes are exercised exactly as the loops invoke them.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "loop_bridge.py"


def _load():
    spec = importlib.util.spec_from_file_location("loop_bridge", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("LOOP_BRIDGE_DIR", str(tmp_path))
    return _load()


def _run(mod, *argv):
    return mod.main(list(argv))


def test_claim_then_conflicting_area_is_refused(bridge, monkeypatch):
    monkeypatch.setenv("LOOP_AGENT", "clawd")
    assert _run(bridge, "claim", "--branch", "b1", "--area", "ws cap") == 0
    # A different agent claiming the same area is refused (exit 2).
    monkeypatch.setenv("LOOP_AGENT", "zcode")
    assert _run(bridge, "claim", "--branch", "b2", "--area", "ws cap") == 2


def test_conflicting_file_is_refused(bridge, monkeypatch):
    monkeypatch.setenv("LOOP_AGENT", "clawd")
    assert (
        _run(bridge, "claim", "--branch", "b1", "--area", "a", "--files", "x.py") == 0
    )
    monkeypatch.setenv("LOOP_AGENT", "zcode")
    # Different area but an overlapping file → still a conflict.
    assert (
        _run(bridge, "claim", "--branch", "b2", "--area", "b", "--files", "x.py") == 2
    )


def test_same_agent_reclaim_is_idempotent_update(bridge, monkeypatch):
    monkeypatch.setenv("LOOP_AGENT", "clawd")
    assert _run(bridge, "claim", "--branch", "b1", "--area", "a") == 0
    # Re-claiming the same branch updates, never self-conflicts.
    assert _run(bridge, "claim", "--branch", "b1", "--area", "a") == 0


def test_distinct_areas_coexist(bridge, monkeypatch):
    monkeypatch.setenv("LOOP_AGENT", "clawd")
    assert _run(bridge, "claim", "--branch", "b1", "--area", "ws cap") == 0
    monkeypatch.setenv("LOOP_AGENT", "zcode")
    assert _run(bridge, "claim", "--branch", "b2", "--area", "arxiv crash") == 0


def test_release_frees_the_area(bridge, monkeypatch):
    monkeypatch.setenv("LOOP_AGENT", "clawd")
    _run(bridge, "claim", "--branch", "b1", "--area", "ws cap")
    assert _run(bridge, "release", "--branch", "b1", "--reason", "merged") == 0
    # Another agent can now take it.
    monkeypatch.setenv("LOOP_AGENT", "zcode")
    assert _run(bridge, "check", "--area", "ws cap") == 0


def test_expired_claim_is_not_resurrected_by_heartbeat(bridge, monkeypatch):
    """The regression this PR fixes: heartbeat must NOT extend an already-expired
    claim, else a tick that outran the TTL revives a claim another agent took."""
    monkeypatch.setenv("LOOP_AGENT", "clawd")
    # ttl=0 → expires immediately (expires_at == now, not > now).
    assert _run(bridge, "claim", "--branch", "b1", "--area", "a", "--ttl", "0") == 0
    assert _run(bridge, "list") == 0  # expired → not listed (smoke)
    # Heartbeat on the lapsed claim is refused, not silently revived.
    assert _run(bridge, "heartbeat", "--branch", "b1") == 1
    # And the area is free for another agent.
    monkeypatch.setenv("LOOP_AGENT", "zcode")
    assert _run(bridge, "check", "--area", "a") == 0


def test_heartbeat_extends_a_live_claim(bridge, monkeypatch):
    monkeypatch.setenv("LOOP_AGENT", "clawd")
    _run(bridge, "claim", "--branch", "b1", "--area", "a", "--ttl", "600")
    assert _run(bridge, "heartbeat", "--branch", "b1") == 0


def test_heartbeat_unknown_branch_refused(bridge):
    assert _run(bridge, "heartbeat", "--branch", "nope") == 1


def test_list_does_not_create_missing_bridge_storage(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "missing-bridge"
    monkeypatch.setenv("LOOP_BRIDGE_DIR", str(bridge_dir))
    mod = _load()

    assert _run(mod, "list") == 0
    assert not bridge_dir.exists()


@pytest.mark.parametrize(
    "raw_state",
    [
        "",
        "not-json",
        "[]",
        '{"claims": null}',
        '{"claims": [null]}',
        (
            '{"claims": [{"agent": "a", "branch": "b", "area": "x", '
            '"files": [], "pr": null, "status": "active", '
            '"claimed_at": "2026-01-01T00:00:00+00:00"}]}'
        ),
        (
            '{"claims": [{"agent": "a", "branch": "b", "area": "x", '
            '"files": [], "pr": null, "status": "active", '
            '"claimed_at": "2026-01-01T00:00:00+00:00", '
            '"expires_at": "not-a-time"}]}'
        ),
    ],
)
def test_list_reports_corrupt_state_without_mutating_it(
    tmp_path, monkeypatch, raw_state
):
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir()
    claims = bridge_dir / "claims.json"
    claims.write_text(raw_state)
    monkeypatch.setenv("LOOP_BRIDGE_DIR", str(bridge_dir))
    mod = _load()

    assert _run(mod, "list") == 1
    assert claims.read_text() == raw_state
    assert {path.name for path in bridge_dir.iterdir()} == {"claims.json"}


def test_list_reports_read_failure_without_mutating_storage(tmp_path, monkeypatch):
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir()
    claims = bridge_dir / "claims.json"
    claims.write_text('{"claims": []}')
    monkeypatch.setenv("LOOP_BRIDGE_DIR", str(bridge_dir))
    mod = _load()
    original_read_text = mod.Path.read_text

    def fail_claim_read(path, *args, **kwargs):
        if path == claims:
            raise OSError("simulated read race")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(mod.Path, "read_text", fail_claim_read)

    assert _run(mod, "list") == 1
    assert {path.name for path in bridge_dir.iterdir()} == {"claims.json"}
