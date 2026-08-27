"""Typed coordination contracts shared by the NOUS backends.

The module intentionally contains no storage or network code.  It defines the
validated values that may cross the remote coordination boundary, separates
the remote claim protocol from the legacy branch-keyed mutex, and provides the
small compensation sequence used when both leases are acquired together.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .schema import (
    BLOCKER_KINDS,
    CANDIDATE_SOURCES,
    SchemaError,
    reject_secret_text,
    validate_agent,
    validate_area,
    validate_branch,
    validate_files,
    validate_machine_id,
    validate_pr,
    validate_run_id,
    validate_sha,
    validate_timestamp,
)


STARTED = "started"
CLAIMED = "claimed"
REPRODUCED = "reproduced"
FIXED = "fixed"
REVIEWED = "reviewed"
LOCALLY_VERIFIED = "locally_verified"
PUBLISHED = "published"
HOSTED_VERIFIED = "hosted_verified"
MERGED_VERIFIED = "merged_verified"

INVALIDATED = "invalidated"

MERGED = "merged"
READY_FOR_HUMAN = "ready-for-human"
DRY = "dry"
CANCELLED = "cancelled"

ACTIVE = "active"
LOCAL = "local"
REMOTE = "remote"

STAGE_STATES = (
    STARTED,
    CLAIMED,
    REPRODUCED,
    FIXED,
    REVIEWED,
    LOCALLY_VERIFIED,
    PUBLISHED,
    HOSTED_VERIFIED,
    MERGED_VERIFIED,
)
BACKEND_STATES = STAGE_STATES
OUTCOMES = (MERGED, READY_FOR_HUMAN, DRY, CANCELLED)
MILESTONE_STATES = STAGE_STATES + (INVALIDATED,) + OUTCOMES
MILESTONE_TIERS = (LOCAL, REMOTE)
MAX_MILESTONES = 40

_CLAIM_ID = re.compile(r"c-[0-9a-f]{12}")


class CoordinationError(Exception):
    """Base class for expected coordination failures."""


class Conflict(CoordinationError):
    """The requested area or file set overlaps an existing lease."""


class ClaimLost(CoordinationError):
    """The caller's fencing token is absent, stale, or expired."""


class BackendUnavailable(CoordinationError):
    """A coordination backend could not complete a transport operation."""


class ValidationError(CoordinationError):
    """A model value failed a schema check.

    ``schema_error`` retains the structured cause for callers that need to
    classify it.  The public exception text is deliberately generic: rejected
    free text (including credential-shaped values) must never be echoed.
    """

    def __init__(self, schema_error: SchemaError):
        if not isinstance(schema_error, SchemaError):
            schema_error = SchemaError("invalid coordination value")
        self.schema_error = schema_error
        # ``error`` is a convenient compatibility alias for callers that use
        # the shorter name while ``schema_error`` documents the contract.
        self.error = schema_error
        super().__init__("coordination validation failed")


def _enum(value: object, field: str, allowed: Sequence[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise SchemaError(f"{field} has an invalid value")
    return value


def _printable(value: object, field: str, maximum: int) -> str:
    value = reject_secret_text(value, field=field)
    if not value:
        raise SchemaError(f"{field} must be non-empty")
    if not value.isprintable():
        raise SchemaError(f"{field} must contain printable characters")
    if len(value) > maximum:
        raise SchemaError(f"{field} exceeds the maximum length of {maximum} characters")
    return value


def _claim_id(value: object, field: str = "claim_id") -> str:
    if not isinstance(value, str) or _CLAIM_ID.fullmatch(value) is None:
        raise SchemaError(f"{field} has an invalid format")
    return value


def _optional_claim_id(value: object, field: str = "claim_id") -> str | None:
    if value is None:
        return None
    return _claim_id(value, field)


def _candidate(value: object, field: str = "candidate") -> Candidate | None:
    if value is None:
        return None
    if not isinstance(value, Candidate):
        raise SchemaError(f"{field} must be a Candidate or null")
    return value


def _repo_relative_lead_ref(value: object) -> str:
    value = _printable(value, "lead_ref", 200)
    path, separator, fragment = value.partition("#")
    if not path:
        raise SchemaError("lead_ref must be repo-relative")
    if separator and not fragment:
        raise SchemaError("lead_ref fragment must be non-empty")
    if path.startswith("/") or path.startswith("-"):
        raise SchemaError("lead_ref must be repo-relative")
    if "\\" in path:
        raise SchemaError("lead_ref must not contain backslashes")
    if ".." in path.split("/"):
        raise SchemaError("lead_ref must not contain a '..' segment")
    return value


def _positive_ttl(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SchemaError("ttl_seconds must be a positive integer")
    return value


def _wrap_schema_error(function: Callable[[], object]) -> object:
    """Run a model validator and expose only a typed, safe error boundary."""

    try:
        return function()
    except SchemaError as exc:
        raise ValidationError(exc) from exc


@dataclass(frozen=True)
class Candidate:
    source: str
    summary: str
    lead_ref: str | None

    def __post_init__(self) -> None:
        def validate() -> None:
            source = _enum(self.source, "source", CANDIDATE_SOURCES)
            summary = _printable(self.summary, "summary", 200)
            lead_ref = (
                None
                if self.lead_ref is None
                else _repo_relative_lead_ref(self.lead_ref)
            )
            object.__setattr__(self, "source", source)
            object.__setattr__(self, "summary", summary)
            object.__setattr__(self, "lead_ref", lead_ref)

        _wrap_schema_error(validate)


@dataclass(frozen=True)
class Claim:
    claim_id: str
    run_id: str
    agent: str
    machine_id: str
    branch: str
    area: str
    files: tuple[str, ...]
    pr: int | None
    status: str
    claimed_at: str
    expires_at: str
    renewed_at: str | None
    candidate: Candidate | None

    def __post_init__(self) -> None:
        def validate() -> None:
            object.__setattr__(self, "claim_id", _claim_id(self.claim_id))
            object.__setattr__(self, "run_id", validate_run_id(self.run_id))
            object.__setattr__(self, "agent", validate_agent(self.agent))
            object.__setattr__(self, "machine_id", validate_machine_id(self.machine_id))
            object.__setattr__(self, "branch", validate_branch(self.branch))
            object.__setattr__(self, "area", validate_area(self.area))
            object.__setattr__(self, "files", validate_files(self.files))
            object.__setattr__(self, "pr", validate_pr(self.pr))
            object.__setattr__(self, "status", _enum(self.status, "status", (ACTIVE,)))
            object.__setattr__(self, "claimed_at", validate_timestamp(self.claimed_at))
            object.__setattr__(self, "expires_at", validate_timestamp(self.expires_at))
            renewed_at = (
                None if self.renewed_at is None else validate_timestamp(self.renewed_at)
            )
            object.__setattr__(self, "renewed_at", renewed_at)
            object.__setattr__(self, "candidate", _candidate(self.candidate))

        _wrap_schema_error(validate)


@dataclass(frozen=True)
class Milestone:
    state: str
    at: str
    evidence_head_sha: str
    tier: str | None

    def __post_init__(self) -> None:
        def validate() -> None:
            object.__setattr__(
                self, "state", _enum(self.state, "state", MILESTONE_STATES)
            )
            object.__setattr__(self, "at", validate_timestamp(self.at))
            object.__setattr__(
                self, "evidence_head_sha", validate_sha(self.evidence_head_sha)
            )
            tier = (
                None if self.tier is None else _enum(self.tier, "tier", MILESTONE_TIERS)
            )
            object.__setattr__(self, "tier", tier)

        _wrap_schema_error(validate)


@dataclass(frozen=True)
class Blocker:
    kind: str
    detail: str

    def __post_init__(self) -> None:
        def validate() -> None:
            object.__setattr__(self, "kind", _enum(self.kind, "kind", BLOCKER_KINDS))
            object.__setattr__(self, "detail", _printable(self.detail, "detail", 300))

        _wrap_schema_error(validate)


@dataclass(frozen=True)
class RunProjection:
    schema: int
    run_id: str
    agent: str
    machine_id: str
    claim_id: str
    state: str
    outcome: str | None
    branch: str
    area: str
    files: tuple[str, ...]
    candidate: Candidate | None
    base_sha: str
    evidence_head_sha: str
    pr: int | None
    parent_run_id: str | None
    blocker: Blocker | None
    claim_expires_at: str
    milestones: tuple[Milestone, ...]
    milestones_truncated: bool
    updated_at: str

    def __post_init__(self) -> None:
        def validate() -> None:
            if (
                isinstance(self.schema, bool)
                or not isinstance(self.schema, int)
                or self.schema != 1
            ):
                raise SchemaError("schema must be 1")
            object.__setattr__(self, "schema", 1)
            object.__setattr__(self, "run_id", validate_run_id(self.run_id))
            object.__setattr__(self, "agent", validate_agent(self.agent))
            object.__setattr__(self, "machine_id", validate_machine_id(self.machine_id))
            object.__setattr__(self, "claim_id", _claim_id(self.claim_id))
            object.__setattr__(self, "state", _enum(self.state, "state", STAGE_STATES))
            outcome = (
                None
                if self.outcome is None
                else _enum(self.outcome, "outcome", OUTCOMES)
            )
            object.__setattr__(self, "outcome", outcome)
            object.__setattr__(self, "branch", validate_branch(self.branch))
            object.__setattr__(self, "area", validate_area(self.area))
            object.__setattr__(self, "files", validate_files(self.files))
            object.__setattr__(self, "candidate", _candidate(self.candidate))
            object.__setattr__(self, "base_sha", validate_sha(self.base_sha))
            object.__setattr__(
                self, "evidence_head_sha", validate_sha(self.evidence_head_sha)
            )
            object.__setattr__(self, "pr", validate_pr(self.pr))
            parent_run_id = (
                None
                if self.parent_run_id is None
                else validate_run_id(self.parent_run_id)
            )
            object.__setattr__(self, "parent_run_id", parent_run_id)
            if self.blocker is not None and not isinstance(self.blocker, Blocker):
                raise SchemaError("blocker must be a Blocker or null")
            if self.blocker is not None and outcome != READY_FOR_HUMAN:
                raise SchemaError("blocker is only valid for ready-for-human")
            object.__setattr__(
                self, "claim_expires_at", validate_timestamp(self.claim_expires_at)
            )
            if isinstance(self.milestones, (str, bytes, bytearray)) or not isinstance(
                self.milestones, Sequence
            ):
                raise SchemaError("milestones must be a sequence")
            milestones = tuple(self.milestones)
            if len(milestones) > MAX_MILESTONES:
                raise SchemaError(
                    f"milestones must contain at most {MAX_MILESTONES} entries"
                )
            if not all(isinstance(milestone, Milestone) for milestone in milestones):
                raise SchemaError("milestones must contain Milestone values")
            object.__setattr__(self, "milestones", milestones)
            if not isinstance(self.milestones_truncated, bool):
                raise SchemaError("milestones_truncated must be boolean")
            object.__setattr__(self, "updated_at", validate_timestamp(self.updated_at))

        _wrap_schema_error(validate)


@runtime_checkable
class CoordinationBackend(Protocol):
    """Remote coordination backend with run and claim-id fencing."""

    def claim(
        self,
        *,
        run_id: str,
        agent: str,
        machine_id: str,
        branch: str,
        area: str,
        files: Sequence[str],
        candidate: Candidate | None,
        pr: int | None,
        ttl_seconds: int,
        claim_id: str | None = None,
        base_sha: str | None = None,
        evidence_head_sha: str | None = None,
    ) -> Claim: ...

    def assert_claim(self, *, run_id: str, claim_id: str) -> Claim: ...

    def renew(self, *, run_id: str, claim_id: str, ttl_seconds: int) -> Claim: ...

    def release(
        self, *, run_id: str, claim_id: str, reason: str, remove_run: bool = False
    ) -> None: ...

    def list(self) -> list[Claim]: ...

    def list_runs(self) -> tuple[RunProjection, ...]: ...

    def check(self, *, area: str, files: Sequence[str]) -> list[Claim]: ...

    def put_run(self, projection: RunProjection, *, claim_id: str) -> None: ...

    def get_run(self, run_id: str) -> RunProjection: ...

    def finalize(
        self, projection: RunProjection, *, claim_id: str, release_claim: bool
    ) -> None: ...

    def finalize_orphan(
        self,
        projection: RunProjection,
        *,
        expected_claim_id: str,
        expected_updated_at: str,
    ) -> None: ...


@runtime_checkable
class LocalMutex(Protocol):
    """Legacy same-host mutex keyed only by branch and overlap inputs."""

    def claim_legacy(
        self,
        agent: str,
        branch: str,
        area: str,
        files: Sequence[str],
        pr: str | int | None,
        ttl_seconds: int,
    ) -> dict[str, object]: ...

    def heartbeat_legacy(self, branch: str, ttl_seconds: int) -> None: ...

    def release_legacy(self, branch: str, reason: str) -> None: ...

    def list_legacy(self) -> list[dict[str, object]]: ...

    def check_legacy(
        self, area: str, files: Sequence[str]
    ) -> list[dict[str, object]]: ...


@dataclass(frozen=True)
class ClaimRequest:
    run_id: str
    agent: str
    machine_id: str
    branch: str
    area: str
    files: tuple[str, ...]
    candidate: Candidate | None
    pr: int | None
    ttl_seconds: int
    claim_id: str | None = None
    base_sha: str | None = None
    evidence_head_sha: str | None = None

    def __post_init__(self) -> None:
        def validate() -> None:
            object.__setattr__(self, "run_id", validate_run_id(self.run_id))
            object.__setattr__(self, "agent", validate_agent(self.agent))
            object.__setattr__(self, "machine_id", validate_machine_id(self.machine_id))
            object.__setattr__(self, "branch", validate_branch(self.branch))
            object.__setattr__(self, "area", validate_area(self.area))
            object.__setattr__(self, "files", validate_files(self.files))
            object.__setattr__(self, "candidate", _candidate(self.candidate))
            object.__setattr__(self, "pr", validate_pr(self.pr))
            object.__setattr__(self, "ttl_seconds", _positive_ttl(self.ttl_seconds))
            object.__setattr__(self, "claim_id", _optional_claim_id(self.claim_id))
            base_sha = None if self.base_sha is None else validate_sha(self.base_sha)
            evidence_head_sha = (
                None
                if self.evidence_head_sha is None
                else validate_sha(self.evidence_head_sha)
            )
            object.__setattr__(self, "base_sha", base_sha)
            object.__setattr__(self, "evidence_head_sha", evidence_head_sha)

        _wrap_schema_error(validate)

    def as_kwargs(self) -> dict[str, object]:
        """Return all arguments accepted by ``CoordinationBackend.claim``."""

        return {
            "run_id": self.run_id,
            "agent": self.agent,
            "machine_id": self.machine_id,
            "branch": self.branch,
            "area": self.area,
            "files": self.files,
            "candidate": self.candidate,
            "pr": self.pr,
            "ttl_seconds": self.ttl_seconds,
            "claim_id": self.claim_id,
            "base_sha": self.base_sha,
            "evidence_head_sha": self.evidence_head_sha,
        }

    def as_local_kwargs(self) -> dict[str, object]:
        """Return only the branch-keyed legacy mutex arguments."""

        return {
            "agent": self.agent,
            "branch": self.branch,
            "area": self.area,
            "files": self.files,
            "pr": self.pr,
            "ttl_seconds": self.ttl_seconds,
        }


def acquire_remote_then_local(
    *,
    remote: CoordinationBackend,
    local: LocalMutex,
    request: ClaimRequest,
    on_compensation_pending: Callable[[Claim], None] | None = None,
) -> Claim:
    """Acquire the remote lease first and compensate it on local conflict."""

    remote_claim = remote.claim(**request.as_kwargs())
    try:
        local.claim_legacy(**request.as_local_kwargs())
    except Conflict:
        try:
            remote.release(
                run_id=request.run_id,
                claim_id=remote_claim.claim_id,
                reason="local-conflict",
                remove_run=True,
            )
        except BackendUnavailable:
            if on_compensation_pending is not None:
                on_compensation_pending(remote_claim)
            raise
        raise
    return remote_claim


__all__ = [
    "ACTIVE",
    "BACKEND_STATES",
    "BLOCKER_KINDS",
    "CANCELLED",
    "CANDIDATE_SOURCES",
    "CLAIMED",
    "Claim",
    "ClaimLost",
    "ClaimRequest",
    "Conflict",
    "CoordinationBackend",
    "CoordinationError",
    "DRY",
    "FIXED",
    "HOSTED_VERIFIED",
    "INVALIDATED",
    "LOCAL",
    "LOCALLY_VERIFIED",
    "LocalMutex",
    "MERGED",
    "MERGED_VERIFIED",
    "Milestone",
    "MILESTONE_STATES",
    "MILESTONE_TIERS",
    "MAX_MILESTONES",
    "OUTCOMES",
    "PUBLISHED",
    "READY_FOR_HUMAN",
    "REMOTE",
    "REPRODUCED",
    "REVIEWED",
    "RunProjection",
    "STARTED",
    "STAGE_STATES",
    "ValidationError",
    "BackendUnavailable",
    "Blocker",
    "Candidate",
    "acquire_remote_then_local",
]
