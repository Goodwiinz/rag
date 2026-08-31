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
GIT_COMMAND_TIMEOUT_SECONDS = 60
MAX_SNAPSHOT_FILES = 10_000
MAX_SNAPSHOT_TREE_RECORDS = MAX_SNAPSHOT_FILES + 1


def _validation(message: str) -> ValidationError:
    return ValidationError(SchemaError(message), message=message)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class BytesCommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


class Runner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
    ) -> CommandResult: ...

    def run_bytes(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
        input_bytes: bytes | None = None,
    ) -> BytesCommandResult: ...


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
                timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise TransportFailure("git transport timed out") from None
        except OSError:
            raise BackendUnavailable("git transport unavailable") from None
        return CommandResult(result.returncode, result.stdout, result.stderr)

    def run_bytes(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str] | None = None,
        input_bytes: bytes | None = None,
    ) -> BytesCommandResult:
        try:
            result = subprocess.run(
                list(argv),
                cwd=cwd,
                env=None if env is None else dict(env),
                input=input_bytes,
                shell=False,
                capture_output=True,
                check=False,
                timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise TransportFailure("git transport timed out") from None
        except OSError:
            raise BackendUnavailable("git transport unavailable") from None
        return BytesCommandResult(result.returncode, result.stdout, result.stderr)


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


@dataclass(frozen=True)
class BlobReference:
    object_id: str


@dataclass(frozen=True)
class TreeEntry:
    mode: str
    object_type: str
    object_id: str
    path: str


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
        git_env = dict(os.environ)
        if env is not None:
            git_env.update(env)
        git_env["GIT_TERMINAL_PROMPT"] = "0"
        result = self.runner.run(
            ["git", *args],
            cwd=self.repo_root,
            env=git_env,
            input_text=input_text,
        )
        if check and result.returncode:
            raise TransportFailure("git operation failed")
        return result

    def run_git_bytes(
        self,
        args: Sequence[str],
        *,
        check: bool = True,
        env: Mapping[str, str] | None = None,
        input_bytes: bytes | None = None,
    ) -> BytesCommandResult:
        validate_git_args(args)
        git_env = dict(os.environ)
        if env is not None:
            git_env.update(env)
        git_env["GIT_TERMINAL_PROMPT"] = "0"
        result = self.runner.run_bytes(
            ["git", *args],
            cwd=self.repo_root,
            env=git_env,
            input_bytes=input_bytes,
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
                "--no-write-fetch-head",
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
        return tuple(
            entry.path
            for entry in self.list_tree_entries(commit)
            if entry.object_type != "tree"
        )

    def list_tree_entries(self, commit: str) -> tuple[TreeEntry, ...]:
        commit = validate_sha(commit)
        raw = self.run_git_bytes(("ls-tree", "-r", "-t", "-z", commit)).stdout
        records = tuple(item for item in raw.split(b"\x00") if item)
        if len(records) > MAX_SNAPSHOT_TREE_RECORDS:
            raise _validation("coordination snapshot contains too many files")
        entries: list[TreeEntry] = []
        try:
            for record in records:
                header, separator, raw_path = record.partition(b"\t")
                mode, object_type, raw_object_id = header.split(b" ")
                if not separator:
                    raise ValueError
                path = raw_path.decode("utf-8")
                validate_files((path,))
                entries.append(
                    TreeEntry(
                        mode=mode.decode("ascii"),
                        object_type=object_type.decode("ascii"),
                        object_id=validate_sha(raw_object_id.decode("ascii")),
                        path=path,
                    )
                )
        except (UnicodeError, ValueError, SchemaError) as exc:
            raise _validation("coordination tree entry is invalid") from exc
        if len({entry.path for entry in entries}) != len(entries):
            raise _validation("coordination tree contains duplicate paths")
        if sum(entry.object_type != "tree" for entry in entries) > MAX_SNAPSHOT_FILES:
            raise _validation("coordination snapshot contains too many files")
        return tuple(entries)

    def cat_file(self, commit: str, path: str) -> bytes:
        commit = validate_sha(commit)
        validate_files((path,))
        return self.run_git_bytes(("cat-file", "blob", f"{commit}:{path}")).stdout

    def blob_reference(self, commit: str, path: str) -> BlobReference:
        return self.blob_references(commit, (path,))[path]

    def blob_references(
        self, commit: str, paths: Sequence[str]
    ) -> dict[str, BlobReference]:
        commit = validate_sha(commit)
        if (
            isinstance(paths, (str, bytes, bytearray))
            or len(paths) > MAX_SNAPSHOT_FILES
        ):
            raise _validation("coordination blob reference paths are invalid")
        requested = tuple(validate_files((path,))[0] for path in paths)
        if len(set(requested)) != len(requested):
            raise _validation("coordination blob reference paths are not unique")
        entries = {entry.path: entry for entry in self.list_tree_entries(commit)}
        references: dict[str, BlobReference] = {}
        for path in requested:
            entry = entries.get(path)
            if entry is None:
                raise _validation("coordination blob reference is absent")
            if entry.mode != "100644" or entry.object_type != "blob":
                raise _validation("coordination blob reference is not a regular blob")
            references[path] = BlobReference(entry.object_id)
        return references

    def commit_snapshot(
        self,
        files: Mapping[str, bytes | BlobReference],
        *,
        parent: str | None,
        message: str,
    ) -> str:
        if not files:
            raise _validation("coordination snapshot must contain files")
        if len(files) > MAX_SNAPSHOT_FILES:
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
            if isinstance(content, BlobReference):
                blob = content.object_id
            else:
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
    "BlobReference",
    "BytesCommandResult",
    "CommandResult",
    "CommitIdentity",
    "GitIO",
    "NonFastForward",
    "RemoteRefMissing",
    "Runner",
    "SubprocessRunner",
    "TransportFailure",
    "TreeEntry",
    "validate_git_args",
]
