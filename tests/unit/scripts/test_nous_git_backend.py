# mypy: disable-error-code=no-untyped-def

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.nous.backend_git import (
    CoordinationSnapshot,
    GitBackend,
    GitBackendConfig,
    decode_claims_document,
)
from scripts.nous.coordination import (
    FIXED,
    READY_FOR_HUMAN,
    ClaimLost,
    Conflict,
    Milestone,
    ValidationError,
)
from scripts.nous.gitio import GitIO, NonFastForward, TransportFailure

RUN_A = "20260827T040000Z-mac-agent-9f3a1c"
RUN_B = "20260827T040001Z-linux-agent-a1b2c3"
HEAD = "23c3551a30ac5d230f68a01b76650c27144571f5"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


@pytest.fixture
def two_backends(tmp_path):
    remote = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", str(remote)], check=True, capture_output=True
    )
    backends = []
    for name, machine in (("left", "mac"), ("right", "linux")):
        clone = tmp_path / name
        subprocess.run(
            ["git", "clone", str(remote), str(clone)], check=True, capture_output=True
        )
        backends.append(
            GitBackend(
                GitBackendConfig(
                    remote="origin",
                    branch="nous-coordination",
                    mode="remote-required",
                    machine_id=machine,
                ),
                GitIO(clone, sleep=lambda _: None, jitter=lambda _a, _b: 0),
            )
        )
    return remote, tuple(backends)


def claim_kwargs(run_id: str, machine_id: str, branch: str, area: str, files=("x.py",)):
    return {
        "run_id": run_id,
        "agent": f"{machine_id}-agent",
        "machine_id": machine_id,
        "branch": branch,
        "area": area,
        "files": files,
        "candidate": None,
        "pr": None,
        "ttl_seconds": 10_800,
        "base_sha": HEAD,
        "evidence_head_sha": HEAD,
    }


def test_bootstrap_is_orphan_and_claim_writes_one_atomic_snapshot(two_backends):
    remote, (left, _) = two_backends
    root = left.bootstrap()
    claim = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    probe = remote.parent / "probe"
    subprocess.run(
        ["git", "clone", str(remote), str(probe)], check=True, capture_output=True
    )
    git(probe, "fetch", "origin", "nous-coordination")
    tip = git(probe, "rev-parse", "FETCH_HEAD")

    assert git(probe, "rev-list", "--max-parents=0", root) == root
    assert git(probe, "rev-parse", f"{tip}^") == root
    assert git(probe, "ls-tree", "-r", "--name-only", tip).splitlines() == [
        "claims.json",
        f"runs/{RUN_A}.json",
    ]
    claims = json.loads(git(probe, "show", f"{tip}:claims.json"))
    run = json.loads(git(probe, "show", f"{tip}:runs/{RUN_A}.json"))
    assert claims["claims"][0]["claim_id"] == claim.claim_id
    assert run["claim_id"] == claim.claim_id


def test_concurrent_bootstrap_has_one_winning_orphan_root(two_backends):
    remote, backends = two_backends
    with ThreadPoolExecutor(max_workers=2) as executor:
        tips = tuple(executor.map(lambda backend: backend.bootstrap(), backends))
    assert len(set(tips)) == 1
    probe = remote.parent / "root-probe"
    subprocess.run(
        ["git", "clone", str(remote), str(probe)], check=True, capture_output=True
    )
    git(probe, "fetch", "origin", "nous-coordination")
    assert (
        len(git(probe, "rev-list", "--max-parents=0", "FETCH_HEAD").splitlines()) == 1
    )


def test_two_clones_observe_conflicts_disjoint_claims_renewal_and_release(two_backends):
    _, (left, right) = two_backends
    left.bootstrap()
    first = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))

    with pytest.raises(Conflict):
        right.claim(**claim_kwargs(RUN_B, "linux", "fix/b", "STREAMING"))

    second = right.claim(
        **claim_kwargs(RUN_B, "linux", "fix/b", "retrieval", ("y.py",))
    )
    assert {claim.run_id for claim in left.list()} == {RUN_A, RUN_B}

    renewed = left.renew(run_id=RUN_A, claim_id=first.claim_id, ttl_seconds=10_800)
    assert renewed.renewed_at is not None
    left.release(run_id=RUN_A, claim_id=first.claim_id, reason="smoke")
    assert [claim.run_id for claim in right.list()] == [RUN_B]

    with pytest.raises(ClaimLost):
        left.renew(run_id=RUN_A, claim_id=first.claim_id, ttl_seconds=10_800)
    right.release(run_id=RUN_B, claim_id=second.claim_id, reason="smoke")


def test_push_race_is_bounded_and_rederived(two_backends):
    _, (left, _) = two_backends
    left.bootstrap()
    original = left.io.push_fast_forward
    calls = 0

    def reject_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise NonFastForward("race")
        return original(*args, **kwargs)

    left.io.push_fast_forward = reject_once
    claim = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    assert claim.run_id == RUN_A
    assert calls == 2


def test_push_race_exhaustion_stops_after_five_attempts(two_backends):
    _, (left, _) = two_backends
    left.bootstrap()
    calls = 0

    def always_reject(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise NonFastForward("race")

    left.io.push_fast_forward = always_reject
    with pytest.raises(TransportFailure) as caught:
        left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    assert calls == 5
    assert RUN_A in str(caught.value)
    assert "possible_claim_id=c-" in str(caught.value)


def test_accepted_claim_with_lost_push_ack_recovers_the_same_token(two_backends):
    _, (left, _) = two_backends
    left.bootstrap()
    original = left.io.push_fast_forward
    calls = 0

    def accept_then_lose_ack(*args, **kwargs):
        nonlocal calls
        calls += 1
        original(*args, **kwargs)
        if calls == 1:
            raise TransportFailure("lost acknowledgement")

    left.io.push_fast_forward = accept_then_lose_ack
    claim = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))

    assert calls == 1
    assert left.list()[0].claim_id == claim.claim_id


@pytest.mark.parametrize("remove_run", (False, True))
def test_accepted_release_with_lost_push_ack_is_idempotent(two_backends, remove_run):
    _, (left, _) = two_backends
    left.bootstrap()
    claim = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    original = left.io.push_fast_forward
    calls = 0

    def accept_then_lose_ack(*args, **kwargs):
        nonlocal calls
        calls += 1
        original(*args, **kwargs)
        if calls == 1:
            raise TransportFailure("lost acknowledgement")

    left.io.push_fast_forward = accept_then_lose_ack
    left.release(
        run_id=RUN_A,
        claim_id=claim.claim_id,
        reason="done",
        remove_run=remove_run,
    )

    assert calls == 1
    assert left.list() == []
    if remove_run:
        with pytest.raises(ClaimLost):
            left.get_run(RUN_A)


def test_accepted_finalize_with_lost_push_ack_is_idempotent(two_backends):
    _, (left, _) = two_backends
    left.bootstrap()
    claim = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    current = left.get_run(RUN_A)
    terminal = replace(
        current,
        outcome=READY_FOR_HUMAN,
        milestones=current.milestones
        + (
            Milestone(
                READY_FOR_HUMAN,
                current.updated_at,
                current.evidence_head_sha,
                None,
            ),
        ),
    )
    original = left.io.push_fast_forward
    calls = 0

    def accept_then_lose_ack(*args, **kwargs):
        nonlocal calls
        calls += 1
        original(*args, **kwargs)
        if calls == 1:
            raise TransportFailure("lost acknowledgement")

    left.io.push_fast_forward = accept_then_lose_ack
    left.finalize(terminal, claim_id=claim.claim_id, release_claim=True)

    assert calls == 1
    assert left.list() == []
    assert left.get_run(RUN_A) == terminal

    with pytest.raises(ClaimLost):
        left.release(
            run_id=RUN_A,
            claim_id=claim.claim_id,
            reason="late-cleanup",
            remove_run=True,
        )
    assert left.get_run(RUN_A) == terminal


def test_remove_run_cannot_delete_terminal_projection_with_retained_claim(
    two_backends,
):
    _, (left, _) = two_backends
    left.bootstrap()
    claim = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    current = left.get_run(RUN_A)
    terminal = replace(
        current,
        outcome=READY_FOR_HUMAN,
        milestones=current.milestones
        + (
            Milestone(
                READY_FOR_HUMAN,
                current.updated_at,
                current.evidence_head_sha,
                None,
            ),
        ),
    )
    left.finalize(terminal, claim_id=claim.claim_id, release_claim=False)

    with pytest.raises(ClaimLost):
        left.release(
            run_id=RUN_A,
            claim_id=claim.claim_id,
            reason="late-cleanup",
            remove_run=True,
        )
    assert left.get_run(RUN_A) == terminal
    assert left.list()[0].claim_id == claim.claim_id


def test_real_interleaved_disjoint_claims_are_both_preserved(two_backends):
    _, (left, right) = two_backends
    left.bootstrap()
    barrier = __import__("threading").Barrier(2)

    def synchronized(original):
        first = True

        def synchronize(*args, **kwargs):
            nonlocal first
            if first:
                first = False
                barrier.wait(timeout=5)
            return original(*args, **kwargs)

        return synchronize

    for backend in (left, right):
        backend.io.push_fast_forward = synchronized(backend.io.push_fast_forward)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (
            executor.submit(
                left.claim, **claim_kwargs(RUN_A, "mac", "fix/a", "streaming")
            ),
            executor.submit(
                right.claim,
                **claim_kwargs(RUN_B, "linux", "fix/b", "retrieval", ("y.py",)),
            ),
        )
        for future in futures:
            future.result()

    assert {claim.run_id for claim in left.list()} == {RUN_A, RUN_B}


def test_expired_run_requires_prior_token_and_rotates_fence(two_backends):
    _, (left, _) = two_backends
    now = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)
    left.clock = lambda: now
    left.bootstrap()
    first = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    now += timedelta(hours=4)

    with pytest.raises(ClaimLost):
        left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    reacquired = left.claim(
        **claim_kwargs(RUN_A, "mac", "fix/a", "streaming"),
        claim_id=first.claim_id,
    )

    assert reacquired.claim_id != first.claim_id
    assert left.get_run(RUN_A).claim_id == reacquired.claim_id
    with pytest.raises(ClaimLost):
        left.renew(run_id=RUN_A, claim_id=first.claim_id, ttl_seconds=10_800)


def test_run_updates_cannot_rewrite_fence_or_owner_and_orphans_must_be_terminal(
    two_backends,
):
    _, (left, _) = two_backends
    left.bootstrap()
    claim = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    current = left.get_run(RUN_A)

    with pytest.raises(ClaimLost):
        left.put_run(
            replace(current, claim_id="c-000000000000"), claim_id=claim.claim_id
        )
    with pytest.raises(ClaimLost):
        left.finalize(
            replace(current, branch="fix/other", outcome=READY_FOR_HUMAN),
            claim_id=claim.claim_id,
            release_claim=True,
        )

    left.release(run_id=RUN_A, claim_id=claim.claim_id, reason="orphan")
    orphan = left.get_run(RUN_A)
    with pytest.raises(ClaimLost):
        left.finalize_orphan(
            replace(orphan, state=FIXED, outcome=None),
            expected_claim_id=orphan.claim_id,
            expected_updated_at=orphan.updated_at,
        )
    terminal = replace(
        orphan,
        outcome=READY_FOR_HUMAN,
        milestones=orphan.milestones
        + (
            Milestone(
                READY_FOR_HUMAN,
                orphan.updated_at,
                orphan.evidence_head_sha,
                None,
            ),
        ),
    )
    left.finalize_orphan(
        terminal,
        expected_claim_id=orphan.claim_id,
        expected_updated_at=orphan.updated_at,
    )
    assert left.get_run(RUN_A).outcome == READY_FOR_HUMAN


@pytest.mark.parametrize("mutation", ("duplicate", "token-mismatch"))
def test_snapshot_decode_rejects_ambiguous_claim_fences(two_backends, mutation):
    _, (left, _) = two_backends
    left.bootstrap()
    left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    repo = left.io.repo_root
    git(repo, "fetch", "origin", "nous-coordination")
    tip = git(repo, "rev-parse", "FETCH_HEAD")
    claims = json.loads(git(repo, "show", f"{tip}:claims.json"))
    if mutation == "duplicate":
        claims["claims"].append(dict(claims["claims"][0]))
    else:
        claims["claims"][0]["claim_id"] = "c-000000000000"
    files = {
        "claims.json": (json.dumps(claims) + "\n").encode(),
        f"runs/{RUN_A}.json": git(repo, "show", f"{tip}:runs/{RUN_A}.json").encode(),
    }
    corrupt = left.io.commit_snapshot(files, parent=tip, message="corrupt peer")
    left.io.push_fast_forward("origin", corrupt, "nous-coordination")

    with pytest.raises(ValidationError):
        left.list()


def test_remote_schema_rejects_unknown_fields_and_mode_mismatch():
    raw = json.dumps(
        {
            "schema": 1,
            "mode": "remote-required",
            "updated_at": "2026-08-27T04:00:00+00:00",
            "claims": [],
            "unknown": True,
        }
    ).encode()
    with pytest.raises(ValidationError):
        decode_claims_document(raw)

    snapshot = CoordinationSnapshot(
        mode="local",
        updated_at="2026-08-27T04:00:00+00:00",
        claims=(),
        runs={},
    )
    with pytest.raises(ValidationError):
        GitBackend.assert_snapshot_mode(snapshot, "remote-required")
