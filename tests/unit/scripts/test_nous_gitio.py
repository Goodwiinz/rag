# mypy: disable-error-code=no-untyped-def

from pathlib import Path

import pytest

from scripts.nous.coordination import ValidationError
from scripts.nous.gitio import CommandResult, GitIO, NonFastForward, TransportFailure


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


def test_only_private_coordination_fetch_may_use_plus_refspec():
    runner = RecordingRunner()
    io = GitIO(Path("/repo"), runner=runner)
    temp_ref = "refs/nous/tmp/20260827T040000Z-agent-9f3a1c-abcdef123456"

    io.fetch_branch("origin", "nous-coordination", temp_ref)

    assert runner.calls[0][0] == [
        "git",
        "fetch",
        "--depth",
        "1",
        "origin",
        f"+refs/heads/nous-coordination:{temp_ref}",
    ]


def test_commit_snapshot_uses_dedicated_identity():
    runner = RecordingRunner()
    io = GitIO(Path("/repo"), runner=runner)

    io.commit_snapshot({"claims.json": b"{}\n"}, parent=None, message="bootstrap")

    env = runner.calls[0][2]
    assert env is not None
    assert env["GIT_COMMITTER_NAME"] == "NOUS Coordination"
    assert env["GIT_COMMITTER_EMAIL"] == "nous-coordination@invalid"
