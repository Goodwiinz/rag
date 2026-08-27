"""Direct parity tests for the branch-keyed local NOUS backend."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from scripts.nous.backend_local import (
    DEFAULT_TTL_SECONDS,
    LocalBackend,
    decode_state,
    live_claims,
    overlap,
    read_observational,
    resolve_bridge_dir,
    write_state,
)
from scripts.nous.coordination import BackendUnavailable, Conflict, ValidationError

pytestmark = pytest.mark.unit


def _claim(
    *,
    agent: str = "agent",
    branch: str = "fix/bug",
    area: str = "bug",
    files: list[str] | None = None,
    claimed_at: str = "2026-08-27T04:00:00+00:00",
    expires_at: str = "2026-08-27T05:00:00+00:00",
    **extra: object,
) -> dict[str, object]:
    claim: dict[str, object] = {
        "agent": agent,
        "branch": branch,
        "area": area,
        "files": [] if files is None else files,
        "pr": None,
        "status": "active",
        "claimed_at": claimed_at,
        "expires_at": expires_at,
    }
    claim.update(extra)
    return claim


def test_observational_read_of_missing_dir_does_not_create_storage(tmp_path):
    missing = tmp_path / "bridge"

    state, error = read_observational(missing)

    assert state == {"claims": []} and error is None
    assert not missing.exists()


def test_corrupt_mutation_fails_closed_and_preserves_bytes(tmp_path):
    bridge = tmp_path / "bridge"
    bridge.mkdir()
    claims = bridge / "claims.json"
    raw = '{"claims": [{"area": "live-but-malformed"}]}'
    claims.write_text(raw, encoding="utf-8")

    with pytest.raises(ValidationError):
        LocalBackend(bridge).check_legacy(area="x", files=())

    assert claims.read_text(encoding="utf-8") == raw


def test_overlap_is_case_insensitive_and_file_based():
    assert overlap({"area": "WS Cap", "files": ["a.py"]}, "ws cap", ())
    assert overlap({"area": "other", "files": ["a.py"]}, "new", ("a.py",))
    assert overlap({"area": "other", "files": ["a.py"]}, "new", ("b.py",)) is None


def test_resolve_bridge_dir_prefers_configured_and_requires_established_default(
    tmp_path,
):
    configured = tmp_path / "configured"
    default = tmp_path / "default"

    assert resolve_bridge_dir(str(configured), default) == configured
    with pytest.raises(BackendUnavailable):
        resolve_bridge_dir(None, default)
    default.mkdir()
    assert resolve_bridge_dir(None, default) == default
    assert DEFAULT_TTL_SECONDS == 45 * 60


def test_decode_and_write_preserve_legacy_json_shape_and_unknown_keys(tmp_path):
    bridge = tmp_path / "bridge"
    bridge.mkdir()
    state = {
        "legacy": {"keep": True},
        "claims": [_claim(future_key={"untouched": [1, 2]})],
    }

    write_state(bridge, state)

    expected = json.dumps(state, indent=2, sort_keys=True)
    assert (bridge / "claims.json").read_text(encoding="utf-8") == expected
    assert decode_state(expected) == state
    assert not (bridge / "claims.json.tmp").exists()


def test_live_claims_uses_strict_expiry_and_active_status():
    now = datetime(2026, 8, 27, 5, 0, tzinfo=timezone.utc)
    state = {
        "claims": [
            _claim(branch="live", expires_at="2026-08-27T05:00:01+00:00"),
            _claim(branch="equal", expires_at="2026-08-27T05:00:00+00:00"),
            _claim(
                branch="inactive", expires_at="2026-08-27T06:00:00+00:00", status="done"
            ),
        ]
    }

    assert [claim["branch"] for claim in live_claims(state, now=now)] == ["live"]


def test_claim_returns_legacy_claim_and_replaces_same_branch(tmp_path, monkeypatch):
    bridge = tmp_path / "bridge"
    backend = LocalBackend(bridge)
    timestamps = iter(
        [
            datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc),
            datetime(2026, 8, 27, 4, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 27, 4, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 8, 27, 4, 0, 1, tzinfo=timezone.utc),
        ]
    )
    monkeypatch.setattr("scripts.nous.backend_local._now", lambda: next(timestamps))

    first = backend.claim_legacy("agent", "fix/bug", "bug", ("x.py",), None, 60)
    second = backend.claim_legacy("agent", "fix/bug", "new-bug", (), "42", 120)

    assert first["area"] == "bug"
    assert second["area"] == "new-bug"
    assert second["claimed_at"] == "2026-08-27T04:00:01+00:00"
    assert second["expires_at"] == "2026-08-27T04:02:01+00:00"
    state = json.loads((bridge / "claims.json").read_text(encoding="utf-8"))
    assert state["claims"] == [second]
    assert len((bridge / "log.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_claim_raises_conflict_for_other_agent_but_allows_same_branch_agent(
    tmp_path,
):
    backend = LocalBackend(tmp_path / "bridge")
    backend.claim_legacy("owner", "owner-branch", "same area", ("x.py",), None, 60)

    with pytest.raises(Conflict):
        backend.claim_legacy("other", "other-branch", "SAME AREA", (), None, 60)

    updated = backend.claim_legacy(
        "owner", "owner-branch", "updated area", ("y.py",), None, 60
    )
    assert updated["area"] == "updated area"


def test_heartbeat_refuses_expired_or_unknown_branch_and_release_always_audits(
    tmp_path, monkeypatch
):
    bridge = tmp_path / "bridge"
    backend = LocalBackend(bridge)
    now = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("scripts.nous.backend_local._now", lambda: now)
    backend.claim_legacy("agent", "branch", "area", (), None, 60)
    monkeypatch.setattr(
        "scripts.nous.backend_local._now",
        lambda: datetime(2026, 8, 27, 5, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(BackendUnavailable):
        backend.heartbeat_legacy("branch", 60)
    with pytest.raises(BackendUnavailable):
        backend.heartbeat_legacy("unknown", 60)

    backend.release_legacy("branch", "done")
    backend.release_legacy("branch", "done-again")
    assert backend.list_legacy() == []
    assert len((bridge / "log.jsonl").read_text(encoding="utf-8").splitlines()) == 3


def test_list_is_observational_and_check_reads_under_lock(tmp_path):
    bridge = tmp_path / "bridge"
    backend = LocalBackend(bridge)

    assert backend.list_legacy() == []
    assert not bridge.exists()
    assert backend.check_legacy("area", ()) == []
    assert {path.name for path in bridge.iterdir()} == {".lock"}
