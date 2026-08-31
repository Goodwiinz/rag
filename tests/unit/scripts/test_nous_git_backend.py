# mypy: disable-error-code=no-untyped-def

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.nous.backend_git import (
    CURRENT_COORDINATION_SCHEMA,
    LEGACY_COORDINATION_SCHEMA,
    VERCEL_DEPLOYMENT_GUARD,
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


def git_bytes(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, check=True
    ).stdout


def git_with_input(repo: Path, *args: str, input_bytes: bytes) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        input=input_bytes,
        capture_output=True,
        check=True,
    ).stdout


def commit_adversarial_tree(repo: Path, parent: str, entries: bytes) -> str:
    tree = git_with_input(repo, "mktree", input_bytes=entries).decode().strip()
    return (
        git_with_input(
            repo,
            "-c",
            "user.name=NOUS Coordination",
            "-c",
            "user.email=nous-coordination@invalid",
            "commit-tree",
            tree,
            "-p",
            parent,
            input_bytes=b"adversarial tree\n",
        )
        .decode()
        .strip()
    )


def empty_tree(repo: Path) -> str:
    return git_with_input(repo, "mktree", input_bytes=b"").decode().strip()


def downgrade_tip_to_schema1(
    backend: GitBackend, *, claims_bytes: bytes | None = None
) -> str:
    repo = backend.io.repo_root
    git(repo, "fetch", "origin", "nous-coordination")
    tip = git(repo, "rev-parse", "FETCH_HEAD")
    paths = git(repo, "ls-tree", "-r", "--name-only", tip).splitlines()
    if claims_bytes is None:
        claims = json.loads(git(repo, "show", f"{tip}:claims.json"))
        claims["schema"] = LEGACY_COORDINATION_SCHEMA
        claims_bytes = (json.dumps(claims, indent=2, sort_keys=True) + "\n").encode()
    files = {"claims.json": claims_bytes}
    for path in paths:
        if path.startswith("runs/"):
            files[path] = git_bytes(repo, "show", f"{tip}:{path}")
    legacy = backend.io.commit_snapshot(files, parent=tip, message="legacy fixture")
    backend.io.push_fast_forward("origin", legacy, "nous-coordination")
    return legacy


def replace_tip_run_blob(backend: GitBackend, run_id: str, content: bytes) -> str:
    repo = backend.io.repo_root
    git(repo, "fetch", "origin", "nous-coordination")
    tip = git(repo, "rev-parse", "FETCH_HEAD")
    replacement = backend.io.commit_snapshot(
        {
            "claims.json": git_bytes(repo, "show", f"{tip}:claims.json"),
            f"runs/{run_id}.json": content,
            "vercel.json": git_bytes(repo, "show", f"{tip}:vercel.json"),
        },
        parent=tip,
        message="noncanonical run fixture",
    )
    backend.io.push_fast_forward("origin", replacement, "nous-coordination")
    return replacement


def crlf_json(raw: bytes) -> bytes:
    return (json.dumps(json.loads(raw), indent=2) + "\n").replace("\n", "\r\n").encode()


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
        "vercel.json",
    ]
    claims = json.loads(git(probe, "show", f"{tip}:claims.json"))
    run = json.loads(git(probe, "show", f"{tip}:runs/{RUN_A}.json"))
    assert claims["claims"][0]["claim_id"] == claim.claim_id
    assert run["claim_id"] == claim.claim_id
    assert git(left.io.repo_root, "rev-parse", "--is-shallow-repository") == "false"


def test_bootstrap_writes_schema2_and_exact_vercel_guard(two_backends):
    _, (left, _) = two_backends
    root = left.bootstrap()
    assert git(left.io.repo_root, "rev-list", "--max-parents=0", root) == root
    assert git(
        left.io.repo_root, "ls-tree", "-r", "--name-only", root
    ).splitlines() == ["claims.json", "vercel.json"]
    claims = json.loads(git(left.io.repo_root, "show", f"{root}:claims.json"))
    assert claims["schema"] == CURRENT_COORDINATION_SCHEMA
    assert git_bytes(left.io.repo_root, "show", f"{root}:vercel.json") == (
        VERCEL_DEPLOYMENT_GUARD
    )


def test_schema1_without_guard_remains_readable(two_backends):
    _, (left, _) = two_backends
    raw = (
        json.dumps(
            {
                "schema": LEGACY_COORDINATION_SCHEMA,
                "mode": "remote-required",
                "updated_at": "2026-08-27T04:00:00+00:00",
                "claims": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    root = left.io.commit_snapshot(
        {"claims.json": raw}, parent=None, message="legacy bootstrap"
    )
    left.io.push_fast_forward("origin", root, "nous-coordination")
    assert left.list() == []


def test_migration_preserves_runs_and_creates_one_fast_forward_child(two_backends):
    _, (left, _) = two_backends
    migrated_at = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)
    left.clock = lambda: migrated_at
    left.bootstrap()
    claim = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    left.release(run_id=RUN_A, claim_id=claim.claim_id, reason="fixture")
    repo = left.io.repo_root
    git(repo, "fetch", "origin", "nous-coordination")
    tip = git(repo, "rev-parse", "FETCH_HEAD")
    noncanonical_run = crlf_json(git_bytes(repo, "show", f"{tip}:runs/{RUN_A}.json"))
    assert noncanonical_run != git_bytes(repo, "show", f"{tip}:runs/{RUN_A}.json")
    assert b"\r\n" in noncanonical_run
    replace_tip_run_blob(left, RUN_A, noncanonical_run)
    legacy_claims = (
        b'{"updated_at":"2026-08-27T04:00:00+00:00","claims" : [ ],'
        b'"schema":1,"mode":"remote-required"}\n'
    )
    legacy = downgrade_tip_to_schema1(left, claims_bytes=legacy_claims)
    before_run = git_bytes(left.io.repo_root, "show", f"{legacy}:runs/{RUN_A}.json")
    before_run_blob = git(left.io.repo_root, "rev-parse", f"{legacy}:runs/{RUN_A}.json")
    assert before_run == noncanonical_run

    result = left.migrate_schema(target=CURRENT_COORDINATION_SCHEMA)

    assert (result.previous_schema, result.current_schema, result.changed) == (
        1,
        2,
        True,
    )
    assert git(left.io.repo_root, "rev-parse", f"{result.tip}^") == legacy
    expected_claims = (
        json.dumps(
            {
                "claims": [],
                "mode": "remote-required",
                "schema": CURRENT_COORDINATION_SCHEMA,
                "updated_at": migrated_at.isoformat(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    migrated_claims = git_bytes(left.io.repo_root, "show", f"{result.tip}:claims.json")
    assert migrated_claims == expected_claims
    assert json.loads(migrated_claims) == {
        "claims": [],
        "mode": "remote-required",
        "schema": CURRENT_COORDINATION_SCHEMA,
        "updated_at": migrated_at.isoformat(),
    }
    assert (
        git(left.io.repo_root, "rev-parse", f"{result.tip}:runs/{RUN_A}.json")
        == before_run_blob
    )
    assert (
        git_bytes(left.io.repo_root, "show", f"{result.tip}:runs/{RUN_A}.json")
        == before_run
    )
    repeated = left.migrate_schema(target=CURRENT_COORDINATION_SCHEMA)
    assert repeated.changed is False
    assert repeated.tip == result.tip


def test_migration_refetches_winning_schema1_child_after_nonfastforward(
    two_backends,
):
    _, (left, _) = two_backends
    left.bootstrap()
    claim = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    left.release(run_id=RUN_A, claim_id=claim.claim_id, reason="fixture")
    repo = left.io.repo_root
    git(repo, "fetch", "origin", "nous-coordination")
    tip = git(repo, "rev-parse", "FETCH_HEAD")
    crlf_run = crlf_json(git_bytes(repo, "show", f"{tip}:runs/{RUN_A}.json"))
    replace_tip_run_blob(left, RUN_A, crlf_run)
    legacy = downgrade_tip_to_schema1(left)
    legacy_blob = git(repo, "rev-parse", f"{legacy}:runs/{RUN_A}.json")
    competing_run = json.dumps(json.loads(crlf_run), separators=(",", ":")).encode()
    competing_claims = json.loads(git(repo, "show", f"{legacy}:claims.json"))
    competing_claims["updated_at"] = "2026-08-30T18:00:00+00:00"
    competing = left.io.commit_snapshot(
        {
            "claims.json": (
                json.dumps(competing_claims, indent=2, sort_keys=True) + "\n"
            ).encode(),
            f"runs/{RUN_A}.json": competing_run,
        },
        parent=legacy,
        message="winning schema1 child",
    )
    original = left.io.push_fast_forward
    calls = 0

    def publish_winner_then_race(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            original("origin", competing, "nous-coordination")
        return original(*args, **kwargs)

    left.io.push_fast_forward = publish_winner_then_race
    result = left.migrate_schema(target=CURRENT_COORDINATION_SCHEMA)

    assert calls == 2
    assert git(left.io.repo_root, "rev-parse", f"{result.tip}^") == competing
    assert git(
        left.io.repo_root, "rev-parse", f"{result.tip}:runs/{RUN_A}.json"
    ) == git(left.io.repo_root, "rev-parse", f"{competing}:runs/{RUN_A}.json")
    assert git(left.io.repo_root, "rev-parse", f"{result.tip}:runs/{RUN_A}.json") != (
        legacy_blob
    )
    assert git_bytes(left.io.repo_root, "show", f"{result.tip}:runs/{RUN_A}.json") == (
        competing_run
    )


def test_migration_reports_its_exact_commit_when_peer_writes_after_push(
    two_backends,
):
    _, (left, right) = two_backends
    left.bootstrap()
    legacy = downgrade_tip_to_schema1(left)
    original = left.io.push_fast_forward
    migration_tip: str | None = None
    later_tip: str | None = None

    def push_migration_then_publish_peer_child(remote, commit, branch):
        nonlocal migration_tip, later_tip
        original(remote, commit, branch)
        migration_tip = commit
        right.claim(**claim_kwargs(RUN_B, "linux", "fix/b", "retrieval"))
        git(right.io.repo_root, "fetch", "origin", "nous-coordination")
        later_tip = git(right.io.repo_root, "rev-parse", "FETCH_HEAD")

    left.io.push_fast_forward = push_migration_then_publish_peer_child

    result = left.migrate_schema(target=CURRENT_COORDINATION_SCHEMA)

    assert migration_tip is not None
    assert later_tip is not None
    assert result.tip == migration_tip
    assert later_tip != result.tip
    assert git(left.io.repo_root, "rev-parse", f"{later_tip}^") == result.tip
    assert git(left.io.repo_root, "rev-parse", f"{result.tip}^") == legacy
    assert (
        json.loads(git(left.io.repo_root, "show", f"{result.tip}:claims.json"))[
            "claims"
        ]
        == []
    )


def test_migration_lists_winning_tree_once_for_all_preserved_runs(two_backends):
    _, (left, _) = two_backends
    left.bootstrap()
    for run_id, branch, area in (
        (RUN_A, "fix/a", "streaming"),
        (RUN_B, "fix/b", "retrieval"),
    ):
        claim = left.claim(**claim_kwargs(run_id, "mac", branch, area))
        left.release(run_id=run_id, claim_id=claim.claim_id, reason="fixture")
    legacy = downgrade_tip_to_schema1(left)
    listed_commits: list[str] = []
    original = left.io.list_tree_entries

    def record_tree_listing(commit):
        listed_commits.append(commit)
        return original(commit)

    left.io.list_tree_entries = record_tree_listing

    result = left.migrate_schema(target=CURRENT_COORDINATION_SCHEMA)

    assert result.changed is True
    assert listed_commits.count(legacy) == 2


def test_migration_retry_refuses_claim_from_winning_peer_without_writing(
    two_backends,
):
    _, (left, right) = two_backends
    left.bootstrap()
    legacy = downgrade_tip_to_schema1(left)
    original = left.io.push_fast_forward
    calls = 0
    winning: str | None = None

    def publish_claim_then_race(*args, **kwargs):
        nonlocal calls, winning
        calls += 1
        if calls == 1:
            right.claim(**claim_kwargs(RUN_B, "linux", "fix/b", "retrieval"))
            git(right.io.repo_root, "fetch", "origin", "nous-coordination")
            winning = git(right.io.repo_root, "rev-parse", "FETCH_HEAD")
        return original(*args, **kwargs)

    left.io.push_fast_forward = publish_claim_then_race

    with pytest.raises(Conflict, match="empty claim board"):
        left.migrate_schema(target=CURRENT_COORDINATION_SCHEMA)

    assert calls == 1
    assert winning is not None
    git(left.io.repo_root, "fetch", "origin", "nous-coordination")
    assert git(left.io.repo_root, "rev-parse", "FETCH_HEAD") == winning
    assert git(left.io.repo_root, "rev-parse", f"{winning}^") == legacy
    assert json.loads(git(left.io.repo_root, "show", f"{winning}:claims.json"))[
        "claims"
    ]


# Mutation-verification record (2026-08-30):
# - Published-tip guard: scripts/nous/backend_git.py:716, `outcome.tip`.
#   Command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python -m pytest
#   tests/unit/scripts/test_nous_git_backend.py::test_migration_reports_its_exact_commit_when_peer_writes_after_push
#   --confcutdir=tests/unit/scripts -q -p no:cacheprovider --no-cov. Temporarily
#   returning the freshly fetched remote tip failed because a peer's child commit
#   replaced the migration commit in `SchemaMigration.tip`; restoring the guard
#   reproduced the source hash and the test passed.
# - Retry guard: scripts/nous/backend_git.py:678, `except (NonFastForward, ...)`.
#   Command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/pytest
#   tests/unit/scripts/test_nous_git_backend.py::test_migration_refetches_winning_schema1_child_after_nonfastforward
#   -q -p no:cacheprovider --no-cov --confcutdir=tests/unit/scripts. Temporarily
#   dropping NonFastForward failed with `coordination push lost a race`; restoring
#   the handler left the production source diff empty and the test passed.
# - Idempotency guard: scripts/nous/backend_git.py:697, `if snapshot.schema == target`.
#   Command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/pytest
#   tests/unit/scripts/test_nous_git_backend.py::test_migration_preserves_runs_and_creates_one_fast_forward_child
#   -q -p no:cacheprovider --no-cov --confcutdir=tests/unit/scripts. Temporarily
#   replacing the condition with False failed with `coordination schema cannot be
#   migrated`; restoring it left the production source diff empty and the test passed.


def test_migration_refuses_nonempty_claim_board_without_writing(two_backends):
    _, (left, _) = two_backends
    left.bootstrap()
    left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    legacy = downgrade_tip_to_schema1(left)

    with pytest.raises(Conflict, match="empty claim board"):
        left.migrate_schema(target=CURRENT_COORDINATION_SCHEMA)

    git(left.io.repo_root, "fetch", "origin", "nous-coordination")
    assert git(left.io.repo_root, "rev-parse", "FETCH_HEAD") == legacy


@pytest.mark.parametrize("target", (2.0, True, 1, 3))
def test_migration_rejects_noncanonical_targets_without_writing(two_backends, target):
    _, (left, _) = two_backends
    left.bootstrap()
    legacy = downgrade_tip_to_schema1(left)

    with pytest.raises(ValidationError, match="only coordination schema 2"):
        left.migrate_schema(target=target)

    git(left.io.repo_root, "fetch", "origin", "nous-coordination")
    assert git(left.io.repo_root, "rev-parse", "FETCH_HEAD") == legacy


def test_noop_cas_upgrades_legacy_snapshot_to_schema2(two_backends):
    _, (left, _) = two_backends
    raw = (
        json.dumps(
            {
                "schema": LEGACY_COORDINATION_SCHEMA,
                "mode": "remote-required",
                "updated_at": "2026-08-27T04:00:00+00:00",
                "claims": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    root = left.io.commit_snapshot(
        {"claims.json": raw}, parent=None, message="legacy bootstrap"
    )
    left.io.push_fast_forward("origin", root, "nous-coordination")

    assert left.prune_expired(now=datetime(2026, 8, 27, 4, tzinfo=timezone.utc)) == ()

    repo = left.io.repo_root
    git(repo, "fetch", "origin", "nous-coordination")
    tip = git(repo, "rev-parse", "FETCH_HEAD")
    assert git(repo, "rev-parse", f"{tip}^") == root
    assert json.loads(git(repo, "show", f"{tip}:claims.json"))["schema"] == (
        CURRENT_COORDINATION_SCHEMA
    )
    assert git_bytes(repo, "show", f"{tip}:vercel.json") == VERCEL_DEPLOYMENT_GUARD


def test_replace_cas_path_upgrades_legacy_snapshot_to_schema2(two_backends):
    _, (left, _) = two_backends
    left.bootstrap()
    claim = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    repo = left.io.repo_root
    git(repo, "fetch", "origin", "nous-coordination")
    tip = git(repo, "rev-parse", "FETCH_HEAD")
    claims = json.loads(git(repo, "show", f"{tip}:claims.json"))
    claims["schema"] = LEGACY_COORDINATION_SCHEMA
    legacy = left.io.commit_snapshot(
        {
            "claims.json": (json.dumps(claims) + "\n").encode(),
            f"runs/{RUN_A}.json": git_bytes(repo, "show", f"{tip}:runs/{RUN_A}.json"),
        },
        parent=tip,
        message="legacy snapshot",
    )
    left.io.push_fast_forward("origin", legacy, "nous-coordination")

    current = left.get_run(RUN_A)
    left.put_run(
        replace(current, updated_at="2026-08-27T04:00:01+00:00"),
        claim_id=claim.claim_id,
    )

    git(repo, "fetch", "origin", "nous-coordination")
    upgraded = git(repo, "rev-parse", "FETCH_HEAD")
    assert git(repo, "rev-parse", f"{upgraded}^") == legacy
    assert json.loads(git(repo, "show", f"{upgraded}:claims.json"))["schema"] == (
        CURRENT_COORDINATION_SCHEMA
    )
    assert git_bytes(repo, "show", f"{upgraded}:vercel.json") == VERCEL_DEPLOYMENT_GUARD


@pytest.mark.parametrize("guard", (None, b"{}\n"))
def test_schema2_requires_exact_vercel_guard(two_backends, guard):
    _, (left, _) = two_backends
    claims = (
        json.dumps(
            {
                "schema": CURRENT_COORDINATION_SCHEMA,
                "mode": "remote-required",
                "updated_at": "2026-08-27T04:00:00+00:00",
                "claims": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    files = {"claims.json": claims}
    if guard is not None:
        files["vercel.json"] = guard
    root = left.io.commit_snapshot(files, parent=None, message="invalid schema2")
    left.io.push_fast_forward("origin", root, "nous-coordination")
    with pytest.raises(ValidationError):
        left.list()


def test_schema1_rejects_partial_guard_migration(two_backends):
    _, (left, _) = two_backends
    claims = (
        json.dumps(
            {
                "schema": LEGACY_COORDINATION_SCHEMA,
                "mode": "remote-required",
                "updated_at": "2026-08-27T04:00:00+00:00",
                "claims": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    root = left.io.commit_snapshot(
        {"claims.json": claims, "vercel.json": VERCEL_DEPLOYMENT_GUARD},
        parent=None,
        message="partial migration",
    )
    left.io.push_fast_forward("origin", root, "nous-coordination")
    with pytest.raises(ValidationError):
        left.list()


@pytest.mark.parametrize(
    ("mutation", "error"),
    (
        ("crlf-guard", "deployment guard is invalid"),
        ("unknown-empty-tree", "invalid tree entry"),
        ("wrong-claims-mode", "invalid tree entry"),
        ("wrong-vercel-type", "invalid tree entry"),
    ),
)
def test_invalid_schema2_git_objects_fail_closed_without_writing(
    two_backends, mutation, error
):
    _, (left, _) = two_backends
    left.bootstrap()
    repo = left.io.repo_root
    git(repo, "fetch", "origin", "nous-coordination")
    tip = git(repo, "rev-parse", "FETCH_HEAD")
    root_entries = git_bytes(repo, "ls-tree", tip)
    if mutation == "crlf-guard":
        corrupt = left.io.commit_snapshot(
            {
                "claims.json": git_bytes(repo, "show", f"{tip}:claims.json"),
                "vercel.json": VERCEL_DEPLOYMENT_GUARD.replace(b"\n", b"\r\n"),
            },
            parent=tip,
            message="crlf guard",
        )
        assert b"\r\n" in git_bytes(repo, "show", f"{corrupt}:vercel.json")
    elif mutation == "unknown-empty-tree":
        corrupt = commit_adversarial_tree(
            repo,
            tip,
            root_entries + f"040000 tree {empty_tree(repo)}\tunknown\n".encode(),
        )
    elif mutation == "wrong-claims-mode":
        corrupt = commit_adversarial_tree(
            repo,
            tip,
            root_entries.replace(b"100644 blob ", b"100755 blob ", 1),
        )
    else:
        corrupt = commit_adversarial_tree(
            repo,
            tip,
            b"".join(
                entry
                for entry in root_entries.splitlines(keepends=True)
                if not entry.endswith(b"\tvercel.json\n")
            )
            + f"040000 tree {empty_tree(repo)}\tvercel.json\n".encode(),
        )
    left.io.push_fast_forward("origin", corrupt, "nous-coordination")

    with pytest.raises(ValidationError, match=error):
        left.list()
    with pytest.raises(ValidationError, match=error):
        left.prune_expired(now=datetime(2026, 8, 27, 4, tzinfo=timezone.utc))

    git(repo, "fetch", "origin", "nous-coordination")
    assert git(repo, "rev-parse", "FETCH_HEAD") == corrupt


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
        "vercel.json": git_bytes(repo, "show", f"{tip}:vercel.json"),
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


@pytest.mark.parametrize("schema", (True, 1.0, 2.0))
def test_claims_document_rejects_non_integer_schema(schema):
    raw = json.dumps(
        {
            "schema": schema,
            "mode": "remote-required",
            "updated_at": "2026-08-27T04:00:00+00:00",
            "claims": [],
        }
    ).encode()

    with pytest.raises(ValidationError):
        decode_claims_document(raw)


def test_public_backend_methods_translate_schema_errors(two_backends):
    _, (left, _) = two_backends
    left.bootstrap()

    with pytest.raises(ValidationError):
        left.renew(
            run_id="not-a-run-id",
            claim_id="c-a1b2c3d4e5f6",
            ttl_seconds=10_800,
        )

    repo = left.io.repo_root
    git(repo, "fetch", "origin", "nous-coordination")
    tip = git(repo, "rev-parse", "FETCH_HEAD")
    corrupt = left.io.commit_snapshot(
        {
            "claims.json": git(repo, "show", f"{tip}:claims.json").encode(),
            "runs/not-a-run-id.json": b"{}\n",
            "vercel.json": git_bytes(repo, "show", f"{tip}:vercel.json"),
        },
        parent=tip,
        message="invalid run filename",
    )
    left.io.push_fast_forward("origin", corrupt, "nous-coordination")

    with pytest.raises(ValidationError):
        left.list()
