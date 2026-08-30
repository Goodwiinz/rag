# mypy: disable-error-code=no-untyped-def

import subprocess
from pathlib import Path

import pytest

from scripts.nous.coordination import BackendUnavailable, ValidationError
from scripts.nous.gitio import (
    CommandResult,
    GitIO,
    NonFastForward,
    SubprocessRunner,
    TransportFailure,
)


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path, dict[str, str] | None, str | None]] = []

    def run(self, argv, *, cwd, env=None, input_text=None):
        self.calls.append((list(argv), cwd, env, input_text))
        object_commands = {"rev-parse", "hash-object", "mktree", "commit-tree"}
        stdout = (
            "23c3551a30ac5d230f68a01b76650c27144571f5\n"
            if argv[1] in object_commands
            else ""
        )
        return CommandResult(0, stdout, "")


def test_push_force_and_deletion_forms_are_rejected_before_execution():
    runner = RecordingRunner()
    io = GitIO(Path("/repo"), runner=runner)

    for args in (
        ("push", "origin", "--force", "x:refs/heads/y"),
        ("push", "origin", "--force-with-lease", "x:refs/heads/y"),
        ("push", "origin", "-f", "x:refs/heads/y"),
        ("push", "origin", "--delete", "refs/heads/y"),
        ("push", "origin", "--delete=refs/heads/y"),
        ("push", "origin", "-d", "refs/heads/y"),
        ("push", "origin", "-vf", "x:refs/heads/y"),
        ("push", "origin", "-fd", "refs/heads/y"),
        ("push", "--mirror", "origin"),
        ("push", "--mir", "origin"),
        ("push", "--prune", "origin"),
        ("push", "--pru", "origin"),
        ("push", "--for", "origin", "x:refs/heads/y"),
        ("push", "origin", ":refs/heads/y"),
        ("push", "origin", "+x:refs/heads/y"),
    ):
        with pytest.raises(ValidationError):
            io.run_git(args)

    assert runner.calls == []


@pytest.mark.parametrize(
    ("stderr", "error"),
    (
        ("! [rejected] x -> y (non-fast-forward)", NonFastForward),
        ("! [remote rejected] x -> y (reference already exists)", NonFastForward),
        (
            "! [remote rejected] x -> y (protected branch hook declined)",
            TransportFailure,
        ),
        ("remote: permission denied; push rejected", TransportFailure),
    ),
)
def test_push_classifies_only_actual_cas_races_as_non_fast_forward(stderr, error):
    class RejectingRunner(RecordingRunner):
        def run(self, argv, *, cwd, env=None, input_text=None):
            return CommandResult(1, "", stderr)

    io = GitIO(Path("/repo"), runner=RejectingRunner())

    with pytest.raises(error):
        io.push_fast_forward(
            "origin",
            "23c3551a30ac5d230f68a01b76650c27144571f5",
            "nous-coordination",
        )


def test_only_private_coordination_fetch_may_use_plus_refspec_without_shallowing_repo():
    runner = RecordingRunner()
    io = GitIO(Path("/repo"), runner=runner)
    temp_ref = "refs/nous/tmp/20260827T040000Z-agent-9f3a1c-abcdef123456"

    io.fetch_branch("origin", "nous-coordination", temp_ref)

    assert runner.calls[0][0] == [
        "git",
        "fetch",
        "--no-write-fetch-head",
        "origin",
        f"+refs/heads/nous-coordination:{temp_ref}",
    ]


def test_git_commands_disable_terminal_prompts():
    runner = RecordingRunner()
    io = GitIO(Path("/repo"), runner=runner)

    io.run_git(("status", "--porcelain"))

    env = runner.calls[0][2]
    assert env is not None
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_subprocess_runner_maps_timeout_to_retryable_transport_failure(monkeypatch):
    def stall(*_args, **kwargs):
        assert kwargs["timeout"] == 60
        raise subprocess.TimeoutExpired(cmd="git fetch", timeout=60)

    monkeypatch.setattr(subprocess, "run", stall)

    with pytest.raises(TransportFailure, match="git transport timed out"):
        SubprocessRunner().run(["git", "fetch"], cwd=Path("/repo"))


def test_commit_snapshot_uses_dedicated_identity():
    runner = RecordingRunner()
    io = GitIO(Path("/repo"), runner=runner)

    io.commit_snapshot({"claims.json": b"{}\n"}, parent=None, message="bootstrap")

    env = runner.calls[0][2]
    assert env is not None
    assert env["GIT_COMMITTER_NAME"] == "NOUS Coordination"
    assert env["GIT_COMMITTER_EMAIL"] == "nous-coordination@invalid"


def test_blob_reference_rejects_a_tree_object(tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    empty_tree = (
        subprocess.run(
            ["git", "mktree"], cwd=repo, input=b"", capture_output=True, check=True
        )
        .stdout.decode()
        .strip()
    )
    root_tree = (
        subprocess.run(
            ["git", "mktree"],
            cwd=repo,
            input=f"040000 tree {empty_tree}\truns\n".encode(),
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )
    commit = (
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=NOUS Coordination",
                "-c",
                "user.email=nous-coordination@invalid",
                "commit-tree",
                root_tree,
            ],
            cwd=repo,
            input=b"tree fixture\n",
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )

    with pytest.raises(ValidationError, match="regular blob"):
        GitIO(repo).blob_reference(commit, "runs")
