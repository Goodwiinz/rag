"""Git-backed, remote-authoritative NOUS claim board."""

from __future__ import annotations

import builtins
import json
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import TypeVar, cast

from .coordination import (
    ACTIVE,
    CLAIMED,
    MAX_MILESTONES,
    OUTCOMES,
    Blocker,
    Candidate,
    Claim,
    ClaimLost,
    Conflict,
    CoordinationBackend,
    Milestone,
    RunProjection,
    ValidationError,
)
from .gitio import (
    COORDINATION_EMAIL,
    COORDINATION_NAME,
    BlobReference,
    GitIO,
    NonFastForward,
    RemoteRefMissing,
    TransportFailure,
    TreeEntry,
)
from .schema import (
    CLAIMS_MAX_BYTES,
    RUN_MAX_BYTES,
    SKEW_SECONDS,
    SchemaError,
    validate_agent,
    validate_area,
    validate_branch_syntax,
    validate_files,
    validate_machine_id,
    validate_pr,
    validate_run_id,
    validate_sha,
    validate_timestamp,
)

LEGACY_COORDINATION_SCHEMA = 1
CURRENT_COORDINATION_SCHEMA = 2
VERCEL_DEPLOYMENT_GUARD = (
    b"{\n"
    b'  "$schema": "https://openapi.vercel.sh/vercel.json",\n'
    b'  "git": {\n'
    b'    "deploymentEnabled": false\n'
    b"  }\n"
    b"}\n"
)


def _validation(message: str) -> ValidationError:
    return ValidationError(SchemaError(message), message=message)


_F = TypeVar("_F", bound=Callable[..., object])


def _schema_boundary(method: _F) -> _F:
    """Translate schema rejections at every public backend boundary."""

    @wraps(method)
    def wrapped(*args: object, **kwargs: object) -> object:
        try:
            return method(*args, **kwargs)
        except SchemaError as exc:
            raise ValidationError(exc) from None

    return cast(_F, wrapped)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse(value: str) -> datetime:
    validate_timestamp(value)
    return datetime.fromisoformat(value)


def _object(value: object, fields: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise _validation(f"{label} has incompatible fields")
    return value


def _candidate_from_json(value: object) -> Candidate | None:
    if value is None:
        return None
    item = _object(value, {"source", "summary", "lead_ref"}, "candidate")
    return Candidate(
        source=item["source"],  # type: ignore[arg-type]
        summary=item["summary"],  # type: ignore[arg-type]
        lead_ref=item["lead_ref"],  # type: ignore[arg-type]
    )


def _candidate_to_json(value: Candidate | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "source": value.source,
        "summary": value.summary,
        "lead_ref": value.lead_ref,
    }


_CLAIM_FIELDS = {
    "claim_id",
    "run_id",
    "agent",
    "machine_id",
    "branch",
    "area",
    "files",
    "pr",
    "status",
    "claimed_at",
    "expires_at",
    "renewed_at",
    "candidate",
}


def _claim_from_json(value: object) -> Claim:
    item = _object(value, _CLAIM_FIELDS, "claim")
    files = item["files"]
    if not isinstance(files, list):
        raise _validation("claim files must be a list")
    return Claim(
        claim_id=item["claim_id"],  # type: ignore[arg-type]
        run_id=item["run_id"],  # type: ignore[arg-type]
        agent=item["agent"],  # type: ignore[arg-type]
        machine_id=item["machine_id"],  # type: ignore[arg-type]
        branch=item["branch"],  # type: ignore[arg-type]
        area=item["area"],  # type: ignore[arg-type]
        files=tuple(files),  # type: ignore[arg-type]
        pr=item["pr"],  # type: ignore[arg-type]
        status=item["status"],  # type: ignore[arg-type]
        claimed_at=item["claimed_at"],  # type: ignore[arg-type]
        expires_at=item["expires_at"],  # type: ignore[arg-type]
        renewed_at=item["renewed_at"],  # type: ignore[arg-type]
        candidate=_candidate_from_json(item["candidate"]),
    )


def _claim_to_json(value: Claim) -> dict[str, object]:
    return {
        "claim_id": value.claim_id,
        "run_id": value.run_id,
        "agent": value.agent,
        "machine_id": value.machine_id,
        "branch": value.branch,
        "area": value.area,
        "files": list(value.files),
        "pr": value.pr,
        "status": value.status,
        "claimed_at": value.claimed_at,
        "expires_at": value.expires_at,
        "renewed_at": value.renewed_at,
        "candidate": _candidate_to_json(value.candidate),
    }


_MILESTONE_FIELDS = {"state", "at", "evidence_head_sha", "tier"}
_RUN_FIELDS = {
    "schema",
    "run_id",
    "agent",
    "machine_id",
    "claim_id",
    "state",
    "outcome",
    "branch",
    "area",
    "files",
    "candidate",
    "base_sha",
    "evidence_head_sha",
    "pr",
    "parent_run_id",
    "blocker",
    "claim_expires_at",
    "milestones",
    "milestones_truncated",
    "updated_at",
}


def _run_from_json(value: object) -> RunProjection:
    item = _object(value, _RUN_FIELDS, "run")
    files = item["files"]
    milestones = item["milestones"]
    if not isinstance(files, list) or not isinstance(milestones, list):
        raise _validation("run arrays are incompatible")
    blocker = None
    if item["blocker"] is not None:
        raw_blocker = _object(item["blocker"], {"kind", "detail"}, "blocker")
        blocker = Blocker(
            kind=raw_blocker["kind"],  # type: ignore[arg-type]
            detail=raw_blocker["detail"],  # type: ignore[arg-type]
        )
    decoded = []
    for raw in milestones:
        milestone = _object(raw, _MILESTONE_FIELDS, "milestone")
        decoded.append(
            Milestone(
                state=milestone["state"],  # type: ignore[arg-type]
                at=milestone["at"],  # type: ignore[arg-type]
                evidence_head_sha=milestone["evidence_head_sha"],  # type: ignore[arg-type]
                tier=milestone["tier"],  # type: ignore[arg-type]
            )
        )
    return RunProjection(
        schema=item["schema"],  # type: ignore[arg-type]
        run_id=item["run_id"],  # type: ignore[arg-type]
        agent=item["agent"],  # type: ignore[arg-type]
        machine_id=item["machine_id"],  # type: ignore[arg-type]
        claim_id=item["claim_id"],  # type: ignore[arg-type]
        state=item["state"],  # type: ignore[arg-type]
        outcome=item["outcome"],  # type: ignore[arg-type]
        branch=item["branch"],  # type: ignore[arg-type]
        area=item["area"],  # type: ignore[arg-type]
        files=tuple(files),  # type: ignore[arg-type]
        candidate=_candidate_from_json(item["candidate"]),
        base_sha=item["base_sha"],  # type: ignore[arg-type]
        evidence_head_sha=item["evidence_head_sha"],  # type: ignore[arg-type]
        pr=item["pr"],  # type: ignore[arg-type]
        parent_run_id=item["parent_run_id"],  # type: ignore[arg-type]
        blocker=blocker,
        claim_expires_at=item["claim_expires_at"],  # type: ignore[arg-type]
        milestones=tuple(decoded),
        milestones_truncated=item["milestones_truncated"],  # type: ignore[arg-type]
        updated_at=item["updated_at"],  # type: ignore[arg-type]
    )


def _run_to_json(value: RunProjection) -> dict[str, object]:
    blocker = None
    if value.blocker is not None:
        blocker = {"kind": value.blocker.kind, "detail": value.blocker.detail}
    return {
        "schema": value.schema,
        "run_id": value.run_id,
        "agent": value.agent,
        "machine_id": value.machine_id,
        "claim_id": value.claim_id,
        "state": value.state,
        "outcome": value.outcome,
        "branch": value.branch,
        "area": value.area,
        "files": list(value.files),
        "candidate": _candidate_to_json(value.candidate),
        "base_sha": value.base_sha,
        "evidence_head_sha": value.evidence_head_sha,
        "pr": value.pr,
        "parent_run_id": value.parent_run_id,
        "blocker": blocker,
        "claim_expires_at": value.claim_expires_at,
        "milestones": [
            {
                "state": item.state,
                "at": item.at,
                "evidence_head_sha": item.evidence_head_sha,
                "tier": item.tier,
            }
            for item in value.milestones
        ],
        "milestones_truncated": value.milestones_truncated,
        "updated_at": value.updated_at,
    }


def _load_json(raw: bytes, maximum: int, label: str) -> object:
    if len(raw) > maximum:
        raise _validation(f"{label} exceeds its schema size limit")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise _validation(f"{label} is not valid UTF-8 JSON") from None


def decode_claims_document(raw: bytes) -> tuple[int, str, str, tuple[Claim, ...]]:
    value = _load_json(raw, CLAIMS_MAX_BYTES, "claims.json")
    item = _object(value, {"schema", "mode", "updated_at", "claims"}, "claims.json")
    schema = item["schema"]
    if (
        isinstance(schema, bool)
        or not isinstance(schema, int)
        or schema not in {LEGACY_COORDINATION_SCHEMA, CURRENT_COORDINATION_SCHEMA}
    ):
        raise _validation("claims.json schema is incompatible")
    if item["mode"] not in {"local", "remote-required"}:
        raise _validation("claims.json mode is incompatible")
    try:
        updated_at = validate_timestamp(item["updated_at"])  # type: ignore[arg-type]
    except SchemaError as exc:
        raise ValidationError(exc) from None
    raw_claims = item["claims"]
    if not isinstance(raw_claims, list):
        raise _validation("claims must be a list")
    claims = tuple(_claim_from_json(value) for value in raw_claims)
    return schema, item["mode"], updated_at, claims  # type: ignore[return-value]


def serialize_claims(snapshot: "CoordinationSnapshot") -> bytes:
    value = {
        "schema": snapshot.schema,
        "mode": snapshot.mode,
        "updated_at": snapshot.updated_at,
        "claims": [_claim_to_json(item) for item in snapshot.claims],
    }
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if len(raw) > CLAIMS_MAX_BYTES:
        raise _validation("claims.json exceeds its schema size limit")
    return raw


def serialize_run(value: RunProjection) -> bytes:
    raw = (json.dumps(_run_to_json(value), indent=2, sort_keys=True) + "\n").encode()
    if len(raw) > RUN_MAX_BYTES:
        raise _validation("run projection exceeds its schema size limit")
    return raw


@dataclass(frozen=True)
class GitBackendConfig:
    remote: str
    branch: str
    mode: str
    machine_id: str
    repo_slug: str | None = None
    ttl_seconds: int = 10_800
    skew_seconds: int = SKEW_SECONDS
    max_attempts: int = 5

    def __post_init__(self) -> None:
        try:
            validate_branch_syntax(self.branch)
            validate_machine_id(self.machine_id)
        except SchemaError as exc:
            raise ValidationError(exc) from None
        if self.mode not in {"local", "remote-required"}:
            raise _validation("coordination mode is invalid")
        if self.max_attempts < 1 or self.max_attempts > 5:
            raise _validation("max_attempts must be between 1 and 5")


@dataclass(frozen=True)
class CoordinationSnapshot:
    mode: str
    updated_at: str
    claims: tuple[Claim, ...]
    runs: Mapping[str, RunProjection]
    schema: int = CURRENT_COORDINATION_SCHEMA


@dataclass(frozen=True)
class SchemaMigration:
    previous_schema: int
    current_schema: int
    tip: str
    changed: bool


def _assert_snapshot_invariants(snapshot: CoordinationSnapshot) -> None:
    try:
        validate_timestamp(snapshot.updated_at)
    except SchemaError as exc:
        raise ValidationError(exc) from None
    claim_ids = [claim.claim_id for claim in snapshot.claims]
    run_ids = [claim.run_id for claim in snapshot.claims]
    if len(claim_ids) != len(set(claim_ids)) or len(run_ids) != len(set(run_ids)):
        raise _validation("coordination snapshot contains duplicate claim fences")
    for claim in snapshot.claims:
        projection = snapshot.runs.get(claim.run_id)
        if projection is None:
            raise _validation("active claim has no matching run projection")
        claim_identity = (
            claim.claim_id,
            claim.agent,
            claim.machine_id,
            claim.branch,
            claim.area,
            claim.files,
            claim.candidate,
            claim.pr,
            claim.expires_at,
        )
        projection_identity = (
            projection.claim_id,
            projection.agent,
            projection.machine_id,
            projection.branch,
            projection.area,
            projection.files,
            projection.candidate,
            projection.pr,
            projection.claim_expires_at,
        )
        if claim_identity != projection_identity:
            raise _validation("claim fence does not match its run projection")


def _assert_projection_update(
    current: RunProjection, replacement: RunProjection, claim_id: str
) -> None:
    if current.claim_id != claim_id or replacement.claim_id != claim_id:
        raise ClaimLost("run projection claim token changed")
    immutable = (
        "schema",
        "run_id",
        "agent",
        "machine_id",
        "branch",
        "area",
        "files",
        "candidate",
        "base_sha",
        "parent_run_id",
    )
    if any(
        getattr(current, field) != getattr(replacement, field) for field in immutable
    ):
        raise ClaimLost("run projection ownership changed")


class ForeignMetadata(ValidationError):
    pass


class GitBackend(CoordinationBackend):
    def __init__(
        self,
        config: GitBackendConfig,
        io: GitIO,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config
        self.io = io
        self.clock = clock or _utc_now

    @staticmethod
    def assert_snapshot_mode(snapshot: CoordinationSnapshot, expected: str) -> None:
        if snapshot.mode != expected:
            raise _validation("coordination mode does not match the remote board")

    def _temp_ref(self, hint: str) -> str:
        safe_hint = "bootstrap" if hint == "bootstrap" else validate_run_id(hint)
        return f"refs/nous/tmp/{safe_hint}-{secrets.token_hex(6)}"

    def _files(self, snapshot: CoordinationSnapshot) -> dict[str, bytes]:
        _assert_snapshot_invariants(snapshot)
        files = {"claims.json": serialize_claims(snapshot)}
        if snapshot.schema == CURRENT_COORDINATION_SCHEMA:
            files["vercel.json"] = VERCEL_DEPLOYMENT_GUARD
        for run_id, projection in sorted(snapshot.runs.items()):
            validate_run_id(run_id)
            if projection.run_id != run_id:
                raise _validation("run filename and embedded run_id differ")
            files[f"runs/{run_id}.json"] = serialize_run(projection)
        return files

    def _migration_files(
        self, parent: str, snapshot: CoordinationSnapshot
    ) -> dict[str, bytes | BlobReference]:
        _assert_snapshot_invariants(snapshot)
        files: dict[str, bytes | BlobReference] = {
            "claims.json": serialize_claims(snapshot),
            "vercel.json": VERCEL_DEPLOYMENT_GUARD,
        }
        for run_id in sorted(snapshot.runs):
            files[f"runs/{run_id}.json"] = self.io.blob_reference(
                parent, f"runs/{run_id}.json"
            )
        return files

    @staticmethod
    def _validate_snapshot_tree(entries: Sequence[TreeEntry]) -> tuple[str, ...]:
        paths: list[str] = []
        run_paths: list[str] = []
        has_runs_tree = False
        for entry in entries:
            paths.append(entry.path)
            if entry.path in {"claims.json", "vercel.json"}:
                if entry.mode != "100644" or entry.object_type != "blob":
                    raise _validation("coordination snapshot has an invalid tree entry")
                continue
            if entry.path == "runs":
                if entry.mode != "040000" or entry.object_type != "tree":
                    raise _validation("coordination snapshot has an invalid tree entry")
                has_runs_tree = True
                continue
            if not entry.path.startswith("runs/"):
                raise _validation("coordination snapshot has an invalid tree entry")
            run_id = entry.path.removeprefix("runs/").removesuffix(".json")
            if (
                not entry.path.endswith(".json")
                or "/" in run_id
                or entry.mode != "100644"
                or entry.object_type != "blob"
            ):
                raise _validation("coordination snapshot has an invalid tree entry")
            try:
                validate_run_id(run_id)
            except SchemaError as exc:
                raise _validation(
                    "coordination snapshot has an invalid tree entry"
                ) from exc
            run_paths.append(entry.path)
        if has_runs_tree != bool(run_paths):
            raise _validation("coordination snapshot has an invalid tree entry")
        return tuple(paths)

    def _decode_snapshot(self, commit: str) -> CoordinationSnapshot:
        identity = self.io.commit_identity(commit)
        if (
            identity.committer_name != COORDINATION_NAME
            or identity.committer_email != COORDINATION_EMAIL
        ):
            raise ForeignMetadata(
                SchemaError("foreign coordination commit"),
                message="coordination branch contains foreign metadata",
            )
        paths = self._validate_snapshot_tree(self.io.list_tree_entries(commit))
        if "claims.json" not in paths:
            raise _validation("coordination snapshot is missing claims.json")
        schema, mode, updated_at, claims = decode_claims_document(
            self.io.cat_file(commit, "claims.json")
        )
        if schema == LEGACY_COORDINATION_SCHEMA:
            if "vercel.json" in paths:
                raise _validation(
                    "schema 1 snapshot contains a partial deployment guard"
                )
        else:
            if "vercel.json" not in paths:
                raise _validation("schema 2 snapshot is missing the deployment guard")
            if self.io.cat_file(commit, "vercel.json") != VERCEL_DEPLOYMENT_GUARD:
                raise _validation("schema 2 deployment guard is invalid")
        runs: dict[str, RunProjection] = {}
        for path in paths:
            if path in {"claims.json", "vercel.json", "runs"}:
                continue
            if not path.startswith("runs/") or not path.endswith(".json"):
                raise _validation("coordination snapshot contains an unknown file")
            run_id = path.removeprefix("runs/").removesuffix(".json")
            validate_run_id(run_id)
            projection = _run_from_json(
                _load_json(self.io.cat_file(commit, path), RUN_MAX_BYTES, path)
            )
            if projection.run_id != run_id:
                raise _validation("run filename and embedded run_id differ")
            runs[run_id] = projection
        snapshot = CoordinationSnapshot(mode, updated_at, claims, runs, schema)
        _assert_snapshot_invariants(snapshot)
        return snapshot

    def _read_with_tip(
        self, *, allow_missing: bool = False
    ) -> tuple[str, CoordinationSnapshot] | None:
        temp_ref = self._temp_ref("bootstrap")
        try:
            commit = self.io.fetch_branch(
                self.config.remote,
                self.config.branch,
                temp_ref,
                allow_missing=allow_missing,
            )
            if commit is None:
                return None
            snapshot = self._decode_snapshot(commit)
            self.assert_snapshot_mode(snapshot, self.config.mode)
            return commit, snapshot
        finally:
            self.io.delete_local_ref(temp_ref)

    def _read(self, *, allow_missing: bool = False) -> CoordinationSnapshot | None:
        current = self._read_with_tip(allow_missing=allow_missing)
        if current is None:
            return None
        _, snapshot = current
        return snapshot

    @_schema_boundary
    def bootstrap(self, *, mode: str | None = None) -> str:
        selected_mode = mode or self.config.mode
        if selected_mode not in {"local", "remote-required"}:
            raise _validation("bootstrap mode is invalid")
        existing = self._read(allow_missing=True)
        if existing is not None:
            self.assert_snapshot_mode(existing, selected_mode)
            # Return the fetched remote tip through a fresh private ref.
            temp_ref = self._temp_ref("bootstrap")
            try:
                tip = self.io.fetch_branch(
                    self.config.remote, self.config.branch, temp_ref
                )
                assert tip is not None
                return tip
            finally:
                self.io.delete_local_ref(temp_ref)
        snapshot = CoordinationSnapshot(selected_mode, _iso(self.clock()), (), {})
        commit = self.io.commit_snapshot(
            self._files(snapshot), parent=None, message="nous coordination bootstrap"
        )
        try:
            self.io.push_fast_forward(self.config.remote, commit, self.config.branch)
            return commit
        except NonFastForward:
            temp_ref = self._temp_ref("bootstrap")
            try:
                tip = self.io.fetch_branch(
                    self.config.remote, self.config.branch, temp_ref
                )
                assert tip is not None
                self.assert_snapshot_mode(self._decode_snapshot(tip), selected_mode)
                return tip
            finally:
                self.io.delete_local_ref(temp_ref)

    def _cas(
        self,
        run_id: str,
        operation: Callable[
            [CoordinationSnapshot], tuple[CoordinationSnapshot, object]
        ],
        *,
        files: (
            Callable[[str, CoordinationSnapshot], dict[str, bytes | BlobReference]]
            | None
        ) = None,
    ) -> object:
        last_error: Exception | None = None
        for attempt in range(self.config.max_attempts):
            temp_ref = self._temp_ref(run_id)
            try:
                parent = self.io.fetch_branch(
                    self.config.remote, self.config.branch, temp_ref
                )
                assert parent is not None
                before = self._decode_snapshot(parent)
                self.assert_snapshot_mode(before, self.config.mode)
                after, result = operation(before)
                if after.schema != CURRENT_COORDINATION_SCHEMA:
                    after = replace(after, schema=CURRENT_COORDINATION_SCHEMA)
                if after == before:
                    return result
                commit = self.io.commit_snapshot(
                    self._files(after) if files is None else files(parent, after),
                    parent=parent,
                    message="nous coordination update",
                )
                self.io.push_fast_forward(
                    self.config.remote, commit, self.config.branch
                )
                return result
            except (NonFastForward, TransportFailure, RemoteRefMissing) as exc:
                last_error = exc
                if attempt + 1 < self.config.max_attempts:
                    base = min(30.0, 1.5 ** (attempt + 1))
                    self.io.sleep(base * self.io.jitter(0.5, 1.5))
            finally:
                self.io.delete_local_ref(temp_ref)
        raise TransportFailure("coordination CAS retry limit reached") from last_error

    @_schema_boundary
    def migrate_schema(self, *, target: int) -> SchemaMigration:
        if type(target) is not int or target != CURRENT_COORDINATION_SCHEMA:
            raise _validation("only coordination schema 2 is supported")

        def apply(snapshot: CoordinationSnapshot):
            if snapshot.claims:
                raise Conflict(
                    "coordination schema migration requires an empty claim board"
                )
            if snapshot.schema == target:
                return snapshot, (snapshot.schema, False)
            if snapshot.schema != LEGACY_COORDINATION_SCHEMA:
                raise _validation("coordination schema cannot be migrated")
            return replace(snapshot, schema=target, updated_at=_iso(self.clock())), (
                snapshot.schema,
                True,
            )

        previous_schema, changed = self._cas(
            "bootstrap", apply, files=self._migration_files
        )
        current = self._read_with_tip()
        assert current is not None
        tip, snapshot = current
        if snapshot.schema != target:
            raise TransportFailure("coordination schema migration was not observable")
        return SchemaMigration(previous_schema, snapshot.schema, tip, changed)

    def _live(self, snapshot: CoordinationSnapshot, now: datetime) -> tuple[Claim, ...]:
        return tuple(
            claim for claim in snapshot.claims if _parse(claim.expires_at) > now
        )

    def _prune(
        self, snapshot: CoordinationSnapshot, now: datetime
    ) -> tuple[Claim, ...]:
        cutoff = now - timedelta(seconds=self.config.skew_seconds)
        return tuple(
            claim for claim in snapshot.claims if _parse(claim.expires_at) >= cutoff
        )

    @_schema_boundary
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
    ) -> Claim:
        run_id = validate_run_id(run_id)
        agent = validate_agent(agent)
        machine_id = validate_machine_id(machine_id)
        if machine_id != self.config.machine_id:
            raise _validation("machine_id does not match runtime configuration")
        branch = validate_branch_syntax(branch, checker=self.io.check_branch_format)
        area = validate_area(area)
        paths = validate_files(files)
        pr = validate_pr(pr)
        if base_sha is None or evidence_head_sha is None:
            raise _validation("new remote claims require base and evidence SHAs")
        base_sha = validate_sha(base_sha)
        evidence_head_sha = validate_sha(evidence_head_sha)
        if ttl_seconds <= 0:
            raise _validation("ttl_seconds must be positive")
        next_claim_id = "c-" + secrets.token_hex(6)

        def apply(snapshot: CoordinationSnapshot) -> tuple[CoordinationSnapshot, Claim]:
            now = self.clock()
            claims = self._prune(snapshot, now)
            active_for_run = next(
                (item for item in self._live(snapshot, now) if item.run_id == run_id),
                None,
            )
            if active_for_run is not None:
                if (
                    active_for_run.claim_id in {claim_id, next_claim_id}
                    and active_for_run.agent == agent
                    and active_for_run.machine_id == machine_id
                    and active_for_run.branch == branch
                ):
                    return snapshot, active_for_run
                raise ClaimLost("active run is fenced by another claim token")
            existing_run = snapshot.runs.get(run_id)
            if existing_run is None:
                if claim_id is not None:
                    raise ClaimLost("a new run cannot present a prior claim token")
            else:
                if existing_run.outcome is not None:
                    raise ClaimLost("terminal runs cannot be re-acquired")
                if claim_id != existing_run.claim_id:
                    raise ClaimLost("expired run requires its prior claim token")
                if (
                    existing_run.agent != agent
                    or existing_run.machine_id != machine_id
                    or existing_run.branch != branch
                ):
                    raise Conflict("expired run ownership does not match the claimant")
            for existing in self._live(snapshot, now):
                if existing.area.strip().lower() == area.strip().lower() or set(
                    existing.files
                ) & set(paths):
                    raise Conflict("remote coordination claim overlaps active work")
            claimed_at = _iso(now)
            expires_at = _iso(now + timedelta(seconds=ttl_seconds))
            acquired = Claim(
                claim_id=next_claim_id,
                run_id=run_id,
                agent=agent,
                machine_id=machine_id,
                branch=branch,
                area=area,
                files=paths,
                pr=pr,
                status=ACTIVE,
                claimed_at=claimed_at,
                expires_at=expires_at,
                renewed_at=None,
                candidate=candidate,
            )
            milestones = (() if existing_run is None else existing_run.milestones) + (
                Milestone(CLAIMED, claimed_at, evidence_head_sha, None),
            )
            milestones_truncated = (
                False if existing_run is None else existing_run.milestones_truncated
            )
            if len(milestones) > MAX_MILESTONES:
                milestones = milestones[-MAX_MILESTONES:]
                milestones_truncated = True
            projection = RunProjection(
                schema=1,
                run_id=run_id,
                agent=agent,
                machine_id=machine_id,
                claim_id=acquired.claim_id,
                state=CLAIMED,
                outcome=None,
                branch=branch,
                area=area,
                files=paths,
                candidate=candidate,
                base_sha=base_sha,
                evidence_head_sha=evidence_head_sha,
                pr=pr,
                parent_run_id=(
                    None if existing_run is None else existing_run.parent_run_id
                ),
                blocker=None,
                claim_expires_at=expires_at,
                milestones=milestones,
                milestones_truncated=milestones_truncated,
                updated_at=claimed_at,
            )
            claims = tuple(item for item in claims if item.run_id != run_id)
            next_runs = dict(snapshot.runs)
            next_runs[run_id] = projection
            return (
                CoordinationSnapshot(
                    snapshot.mode,
                    claimed_at,
                    claims + (acquired,),
                    next_runs,
                ),
                acquired,
            )

        try:
            return self._cas(run_id, apply)  # type: ignore[return-value]
        except TransportFailure as exc:
            detail = (
                f"claim outcome indeterminate for run_id={run_id}; "
                f"possible_claim_id={next_claim_id}"
            )
            if claim_id is not None:
                detail += f"; prior_claim_id={claim_id}"
            detail += "; inspect the remote board before retrying"
            raise TransportFailure(detail) from exc

    def _owned(
        self, snapshot: CoordinationSnapshot, run_id: str, claim_id: str
    ) -> Claim:
        now = self.clock()
        claim = next((item for item in snapshot.claims if item.run_id == run_id), None)
        if (
            claim is None
            or claim.claim_id != claim_id
            or _parse(claim.expires_at) <= now
        ):
            raise ClaimLost("claim is missing, expired, or fenced")
        return claim

    @_schema_boundary
    def assert_claim(self, *, run_id: str, claim_id: str) -> Claim:
        snapshot = self._read()
        assert snapshot is not None
        return self._owned(snapshot, validate_run_id(run_id), claim_id)

    @_schema_boundary
    def renew(self, *, run_id: str, claim_id: str, ttl_seconds: int) -> Claim:
        run_id = validate_run_id(run_id)
        if ttl_seconds <= 0:
            raise _validation("ttl_seconds must be positive")

        def apply(snapshot: CoordinationSnapshot) -> tuple[CoordinationSnapshot, Claim]:
            current = self._owned(snapshot, run_id, claim_id)
            now = self.clock()
            renewed = replace(
                current,
                expires_at=_iso(now + timedelta(seconds=ttl_seconds)),
                renewed_at=_iso(now),
            )
            claims = tuple(
                renewed if item.run_id == run_id else item for item in snapshot.claims
            )
            runs = dict(snapshot.runs)
            runs[run_id] = replace(
                runs[run_id],
                claim_expires_at=renewed.expires_at,
                updated_at=_iso(now),
            )
            return CoordinationSnapshot(snapshot.mode, _iso(now), claims, runs), renewed

        return self._cas(run_id, apply)  # type: ignore[return-value]

    @_schema_boundary
    def release(
        self, *, run_id: str, claim_id: str, reason: str, remove_run: bool = False
    ) -> None:
        run_id = validate_run_id(run_id)
        attempted = False

        def apply(snapshot: CoordinationSnapshot) -> tuple[CoordinationSnapshot, None]:
            nonlocal attempted
            active = next(
                (item for item in snapshot.claims if item.run_id == run_id), None
            )
            retained = snapshot.runs.get(run_id)
            if active is None:
                if retained is not None and retained.claim_id == claim_id:
                    if not remove_run:
                        return snapshot, None
                    if retained.state != CLAIMED or retained.outcome is not None:
                        raise ClaimLost("only an unstarted claimed run may be removed")
                    runs = dict(snapshot.runs)
                    runs.pop(run_id)
                    attempted = True
                    return (
                        replace(snapshot, updated_at=_iso(self.clock()), runs=runs),
                        None,
                    )
                if remove_run and attempted and retained is None:
                    return snapshot, None
                raise ClaimLost("claim is missing, expired, or fenced")
            self._owned(snapshot, run_id, claim_id)
            claims = tuple(item for item in snapshot.claims if item.run_id != run_id)
            runs = dict(snapshot.runs)
            if remove_run:
                removable = runs.get(run_id)
                if (
                    removable is None
                    or removable.state != CLAIMED
                    or removable.outcome is not None
                ):
                    raise ClaimLost("only an unstarted claimed run may be removed")
                runs.pop(run_id, None)
            now = _iso(self.clock())
            attempted = True
            return CoordinationSnapshot(snapshot.mode, now, claims, runs), None

        self._cas(run_id, apply)

    @_schema_boundary
    def list(self) -> list[Claim]:
        snapshot = self._read()
        assert snapshot is not None
        return list(self._live(snapshot, self.clock()))

    @_schema_boundary
    def check(self, *, area: str, files: Sequence[str]) -> builtins.list[Claim]:
        area = validate_area(area)
        paths = validate_files(files)
        return [
            claim
            for claim in self.list()
            if claim.area.strip().lower() == area.strip().lower()
            or bool(set(claim.files) & set(paths))
        ]

    @_schema_boundary
    def get_run(self, run_id: str) -> RunProjection:
        snapshot = self._read()
        assert snapshot is not None
        try:
            return snapshot.runs[validate_run_id(run_id)]
        except KeyError:
            raise ClaimLost("remote run projection is absent") from None

    @_schema_boundary
    def list_runs(self) -> tuple[RunProjection, ...]:
        snapshot = self._read()
        assert snapshot is not None
        return tuple(snapshot.runs[key] for key in sorted(snapshot.runs))

    @_schema_boundary
    def put_run(self, projection: RunProjection, *, claim_id: str) -> None:
        def apply(snapshot: CoordinationSnapshot) -> tuple[CoordinationSnapshot, None]:
            self._owned(snapshot, projection.run_id, claim_id)
            current = snapshot.runs.get(projection.run_id)
            if current is None:
                raise ClaimLost("remote run projection is absent")
            _assert_projection_update(current, projection, claim_id)
            if current == projection:
                return snapshot, None
            runs = dict(snapshot.runs)
            runs[projection.run_id] = projection
            return replace(snapshot, updated_at=_iso(self.clock()), runs=runs), None

        self._cas(projection.run_id, apply)

    @_schema_boundary
    def finalize(
        self, projection: RunProjection, *, claim_id: str, release_claim: bool
    ) -> None:
        def apply(snapshot: CoordinationSnapshot) -> tuple[CoordinationSnapshot, None]:
            current = snapshot.runs.get(projection.run_id)
            active = next(
                (item for item in snapshot.claims if item.run_id == projection.run_id),
                None,
            )
            if (
                release_claim
                and active is None
                and current == projection
                and projection.claim_id == claim_id
                and projection.outcome in OUTCOMES
            ):
                return snapshot, None
            self._owned(snapshot, projection.run_id, claim_id)
            if current is None:
                raise ClaimLost("remote run projection is absent")
            _assert_projection_update(current, projection, claim_id)
            if projection.outcome not in OUTCOMES:
                raise ClaimLost("final projection requires a terminal outcome")
            if not release_claim and current == projection:
                return snapshot, None
            claims = snapshot.claims
            if release_claim:
                claims = tuple(
                    item for item in claims if item.run_id != projection.run_id
                )
            runs = dict(snapshot.runs)
            runs[projection.run_id] = projection
            return (
                CoordinationSnapshot(snapshot.mode, _iso(self.clock()), claims, runs),
                None,
            )

        self._cas(projection.run_id, apply)

    @_schema_boundary
    def finalize_orphan(
        self,
        projection: RunProjection,
        *,
        expected_claim_id: str,
        expected_updated_at: str,
    ) -> None:
        def apply(snapshot: CoordinationSnapshot) -> tuple[CoordinationSnapshot, None]:
            active = any(
                item.run_id == projection.run_id
                for item in self._live(snapshot, self.clock())
            )
            if active:
                raise ClaimLost("run still has an active claim")
            current = snapshot.runs.get(projection.run_id)
            if (
                current == projection
                and projection.claim_id == expected_claim_id
                and projection.outcome in OUTCOMES
            ):
                return snapshot, None
            if (
                current is None
                or current.claim_id != expected_claim_id
                or current.updated_at != expected_updated_at
            ):
                raise ClaimLost("orphan projection fence changed")
            _assert_projection_update(current, projection, expected_claim_id)
            if projection.outcome not in OUTCOMES:
                raise ClaimLost("orphan finalization requires a terminal outcome")
            runs = dict(snapshot.runs)
            runs[projection.run_id] = projection
            return replace(snapshot, updated_at=_iso(self.clock()), runs=runs), None

        self._cas(projection.run_id, apply)

    @_schema_boundary
    def prune_expired(self, *, now: datetime | None = None) -> tuple[str, ...]:
        instant = now or self.clock()
        run_hint = "20260827T000000Z-prune-000000"

        def apply(
            snapshot: CoordinationSnapshot,
        ) -> tuple[CoordinationSnapshot, tuple[str, ...]]:
            kept = self._prune(snapshot, instant)
            removed = tuple(
                sorted(
                    {item.run_id for item in snapshot.claims}
                    - {item.run_id for item in kept}
                )
            )
            if kept == snapshot.claims:
                return snapshot, removed
            return replace(snapshot, updated_at=_iso(instant), claims=kept), removed

        return self._cas(run_hint, apply)  # type: ignore[return-value]


__all__ = [
    "CURRENT_COORDINATION_SCHEMA",
    "LEGACY_COORDINATION_SCHEMA",
    "VERCEL_DEPLOYMENT_GUARD",
    "CoordinationSnapshot",
    "SchemaMigration",
    "ForeignMetadata",
    "GitBackend",
    "GitBackendConfig",
    "decode_claims_document",
    "serialize_claims",
    "serialize_run",
]
