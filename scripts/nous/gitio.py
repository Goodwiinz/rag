"""Guarded Git subprocess boundary for NOUS coordination metadata."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .coordination import BackendUnavailable, Conflict, ValidationError
from .schema import SchemaError, validate_branch, validate_files, validate_sha

COORDINATION_NAME = "NOUS Coordination"
COORDINATION_EMAIL = "nous-coordination@invalid"


def _validation(message: str) -> ValidationError:
    return ValidationError(SchemaError(message), message=message)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class Runner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
    ) -> CommandResult: ...


class SubprocessRunner:
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        try:
            result = subprocess.run(
                list(argv),
                cwd=cwd,
                env=None if env is None else dict(env),
                input=input_text,
                shell=False,
                capture_output=True,
                text=True,
                errors="surrogateescape",
                check=False,
            )
        except OSError:
            raise BackendUnavailable("git transport unavailable") from None
        return CommandResult(result.returncode, result.stdout, result.stderr)


class NonFastForward(Conflict):
    """A peer updated the remote coordination ref first."""


class RemoteRefMissing(BackendUnavailable):
    """The configured coordination branch does not exist."""


class TransportFailure(BackendUnavailable):
    """Git could not complete an operation."""


@dataclass(frozen=True)
class CommitIdentity:
    committer_name: str
    committer_email: str


def validate_git_args(args: Sequence[str]) -> None:
    if not args:
        raise _validation("git command must not be empty")
    command = args[0]
    if command == "push":
        if any(token.startswith("-") and token != "--porcelain" for token in args[1:]):
            raise _validation("only the porcelain push option is permitted")
        if any(token.startswith("+") or token.startswith(":") for token in args[1:]):
            raise _validation("force push refspecs are prohibited")
    elif command == "fetch":
        for token in args[1:]:
            if not token.startswith("+"):
                continue
            _, separator, destination = token.partition(":")
            if not separator or not destination.startswith("refs/nous/tmp/"):
                raise _validation("forced fetch is limited to private NOUS refs")


class GitIO:
    def __init__(
        self,
        repo_root: Path,
        *,
        runner: Runner | None = None,
        sleep: Callable[[float], None] | None = None,
        jitter: Callable[[float, float], float] | None = None,
    ) -> None:
        import random
        import time

        self.repo_root = repo_root
        self.runner = runner or SubprocessRunner()
        self.sleep = sleep or time.sleep
        self.jitter = jitter or random.uniform

    def run_git(
        self,
        args: Sequence[str],
        *,
        check: bool = True,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        validate_git_args(args)
        result = self.runner.run(
            ["git", *args],
            cwd=self.repo_root,
            env=env,
            input_text=input_text,
        )
        if check and result.returncode:
            raise TransportFailure("git operation failed")
        return result

    def check_branch_format(self, branch: str) -> bool:
        branch = validate_branch(branch)
        return not self.run_git(
            ("check-ref-format", "--branch", branch), check=False
        ).returncode

    def fetch_branch(
        self,
        remote: str,
        branch: str,
        temp_ref: str,
        *,
        allow_missing: bool = False,
    ) -> str | None:
        branch = validate_branch(branch)
        if not temp_ref.startswith("refs/nous/tmp/"):
            raise _validation("temporary ref must be private to NOUS")
        result = self.run_git(
            (
                "fetch",
                "--depth",
                "1",
                remote,
                f"+refs/heads/{branch}:{temp_ref}",
            ),
            check=False,
        )
        if result.returncode:
            missing = "couldn't find remote ref" in result.stderr.lower()
            if allow_missing and missing:
                return None
            if missing:
                raise RemoteRefMissing("coordination branch is absent")
            raise TransportFailure("coordination fetch failed")
        resolved = self.run_git(("rev-parse", temp_ref)).stdout.strip()
        try:
            return validate_sha(resolved)
        except SchemaError:
            raise TransportFailure(
                "coordination fetch returned an invalid tip"
            ) from None

    def delete_local_ref(self, temp_ref: str) -> None:
        if not temp_ref.startswith("refs/nous/tmp/"):
            raise _validation("only private NOUS refs may be deleted")
        self.run_git(("update-ref", "-d", temp_ref), check=False)

    def commit_identity(self, commit: str) -> CommitIdentity:
        commit = validate_sha(commit)
        value = self.run_git(("show", "-s", "--format=%cn%x00%ce", commit)).stdout
        parts = value.rstrip("\n").split("\x00")
        if len(parts) != 2:
            raise _validation("coordination commit identity is malformed")
        return CommitIdentity(*parts)

    def list_tree(self, commit: str) -> tuple[str, ...]:
        commit = validate_sha(commit)
        raw = self.run_git(("ls-tree", "-r", "--name-only", "-z", commit)).stdout
        paths = tuple(item for item in raw.split("\x00") if item)
        if len(paths) > 10_000:
            raise _validation("coordination snapshot contains too many files")
        try:
            for path in paths:
                validate_files((path,))
        except SchemaError as exc:
            raise ValidationError(exc) from None
        return paths

    def cat_file(self, commit: str, path: str) -> bytes:
        commit = validate_sha(commit)
        validate_files((path,))
        result = self.run_git(("show", f"{commit}:{path}"))
        try:
            return result.stdout.encode("utf-8")
        except UnicodeError:
            raise _validation("coordination metadata is not valid UTF-8") from None

    def commit_snapshot(
        self,
        files: Mapping[str, bytes],
        *,
        parent: str | None,
        message: str,
    ) -> str:
        if not files:
            raise _validation("coordination snapshot must contain files")
        if len(files) > 10_000:
            raise _validation("coordination snapshot contains too many files")
        try:
            for path in files:
                validate_files((path,))
        except SchemaError as exc:
            raise ValidationError(exc) from None
        identity_env = dict(os.environ)
        identity_env.update(
            {
                "GIT_AUTHOR_NAME": COORDINATION_NAME,
                "GIT_AUTHOR_EMAIL": COORDINATION_EMAIL,
                "GIT_COMMITTER_NAME": COORDINATION_NAME,
                "GIT_COMMITTER_EMAIL": COORDINATION_EMAIL,
            }
        )

        trie: dict[str, object] = {}
        for path, content in files.items():
            cursor = trie
            parts = path.split("/")
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})  # type: ignore[assignment]
            blob = self.run_git(
                ("hash-object", "-w", "--stdin"),
                env=identity_env,
                input_text=content.decode("utf-8"),
            ).stdout.strip()
            cursor[parts[-1]] = ("blob", validate_sha(blob))

        def build_tree(node: Mapping[str, object]) -> str:
            lines: list[str] = []
            for name in sorted(node):
                child = node[name]
                if isinstance(child, dict):
                    object_id = build_tree(child)
                    lines.append(f"040000 tree {object_id}\t{name}\n")
                else:
                    _, object_id = child  # type: ignore[misc]
                    lines.append(f"100644 blob {object_id}\t{name}\n")
            tree = self.run_git(
                ("mktree",),
                env=identity_env,
                input_text="".join(lines),
            ).stdout.strip()
            return validate_sha(tree)

        tree = build_tree(trie)
        args = ["commit-tree", tree]
        if parent is not None:
            args.extend(("-p", validate_sha(parent)))
        commit = self.run_git(
            args,
            env=identity_env,
            input_text=message + "\n",
        ).stdout.strip()
        return validate_sha(commit)

    def push_fast_forward(self, remote: str, commit: str, branch: str) -> None:
        commit = validate_sha(commit)
        branch = validate_branch(branch)
        result = self.run_git(
            ("push", "--porcelain", remote, f"{commit}:refs/heads/{branch}"),
            check=False,
        )
        if not result.returncode:
            return
        text = f"{result.stdout}\n{result.stderr}".lower()
        if (
            "non-fast-forward" in text
            or "fetch first" in text
            or "reference already exists" in text
        ):
            raise NonFastForward("coordination push lost a race")
        raise TransportFailure("coordination push failed")


__all__ = [
    "COORDINATION_EMAIL",
    "COORDINATION_NAME",
    "CommandResult",
    "CommitIdentity",
    "GitIO",
    "NonFastForward",
    "RemoteRefMissing",
    "Runner",
    "SubprocessRunner",
    "TransportFailure",
    "validate_git_args",
]
