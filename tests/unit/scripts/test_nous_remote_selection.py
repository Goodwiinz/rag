# mypy: disable-error-code=no-untyped-def

from pathlib import Path

import pytest

from scripts.loop_bridge import main as legacy_main
from scripts.nous.backend_local import (
    has_remote_required_sentinel,
    legacy_mutations_allowed,
    remove_remote_required_sentinel,
    write_remote_required_sentinel,
)
from scripts.nous.coordination import ClaimLost, CombinedBackend, Conflict


class Remote:
    def __init__(self, calls):
        self.calls = calls
        self.released = []

    def claim(self, **kwargs):
        from scripts.nous.coordination import Claim

        self.calls.append("remote.claim")
        return Claim(
            claim_id="c-a1b2c3d4e5f6",
            run_id=kwargs["run_id"],
            agent=kwargs["agent"],
            machine_id=kwargs["machine_id"],
            branch=kwargs["branch"],
            area=kwargs["area"],
            files=tuple(kwargs["files"]),
            pr=None,
            status="active",
            claimed_at="2026-08-27T04:00:00+00:00",
            expires_at="2026-08-27T07:00:00+00:00",
            renewed_at=None,
            candidate=None,
        )

    def release(self, **kwargs):
        self.calls.append("remote.release")
        self.released.append(kwargs)


class Local:
    def __init__(self, calls, error=None):
        self.calls = calls
        self.error = error

    def claim_legacy(self, **_kwargs):
        self.calls.append("local.claim")
        if self.error:
            raise self.error


def request():
    return {
        "run_id": "20260827T040000Z-agent-9f3a1c",
        "agent": "agent",
        "machine_id": "mac",
        "branch": "fix/bug",
        "area": "bug",
        "files": ("x.py",),
        "candidate": None,
        "pr": None,
        "ttl_seconds": 10_800,
        "base_sha": "23c3551a30ac5d230f68a01b76650c27144571f5",
        "evidence_head_sha": "23c3551a30ac5d230f68a01b76650c27144571f5",
    }


def test_combined_backend_acquires_remote_first_and_compensates_local_conflict():
    calls = []
    remote = Remote(calls)
    local = Local(calls, Conflict("same host"))

    with pytest.raises(Conflict):
        CombinedBackend(remote, local).claim(**request())

    assert calls == ["remote.claim", "local.claim", "remote.release"]
    assert remote.released[0]["remove_run"] is True


def test_cutover_sentinel_is_local_only_and_blocks_direct_legacy_mutations(tmp_path):
    sentinel = write_remote_required_sentinel(tmp_path)

    assert sentinel == tmp_path / ".remote-required"
    assert sentinel.read_bytes() == b""
    assert has_remote_required_sentinel(tmp_path)
    assert not legacy_mutations_allowed(tmp_path, mode="remote-required")


def test_direct_legacy_claim_refuses_after_cutover(tmp_path, monkeypatch):
    write_remote_required_sentinel(tmp_path)
    monkeypatch.setenv("LOOP_BRIDGE_DIR", str(tmp_path))
    monkeypatch.setenv("NOUS_COORD_MODE", "remote-required")

    assert (
        legacy_main(["claim", "--agent", "old", "--branch", "fix/old", "--area", "old"])
        == 1
    )
    assert not (tmp_path / "claims.json").exists()


def test_rollback_removes_only_the_sentinel_and_restores_local_mode(tmp_path):
    sentinel = write_remote_required_sentinel(tmp_path)
    keep = tmp_path / "claims.json"
    keep.write_text('{"claims": []}', encoding="utf-8")

    assert remove_remote_required_sentinel(tmp_path)
    assert not sentinel.exists()
    assert keep.exists()
    assert legacy_mutations_allowed(tmp_path, mode="local")
    assert not remove_remote_required_sentinel(tmp_path)


def test_stale_release_validates_remote_before_removing_local_mutex():
    calls = []

    class StaleRemote:
        def assert_claim(self, **_kwargs):
            calls.append("remote.assert")
            raise ClaimLost("stale")

        def release(self, **_kwargs):
            calls.append("remote.release")

    class ReleasingLocal:
        def release_legacy(self, *_args):
            calls.append("local.release")

    with pytest.raises(ClaimLost):
        CombinedBackend(StaleRemote(), ReleasingLocal()).release(
            run_id=request()["run_id"],
            claim_id="c-000000000000",
            reason="done",
        )

    assert calls == ["remote.assert"]
