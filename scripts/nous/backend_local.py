"""The branch-keyed local coordination backend.

This module keeps the legacy ``claims.json`` board deliberately small and
compatible with :mod:`scripts.loop_bridge`.  It owns only the local mutex;
remote run projections and claim-id fencing belong to other backends.
"""

from __future__ import annotations

import datetime as _dt
import fcntl
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .coordination import (
    BackendUnavailable,
    ClaimLost,
    Conflict,
    LocalMutex,
    ValidationError,
)
from .schema import SchemaError, decode_legacy_claims

DEFAULT_TTL_SECONDS = 45 * 60


def _now() -> datetime:
    """Return the timezone-aware UTC clock used by legacy board operations."""

    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def resolve_bridge_dir(configured: str | None, default_dir: Path) -> Path:
    """Resolve the configured board directory without creating storage."""

    if configured:
        return Path(configured)
    error: str | None = None
    try:
        established = default_dir.exists()
    except OSError as exc:
        error = f"unable to inspect the default bridge directory {default_dir}: {exc}"
    if error is not None:
        raise BackendUnavailable(error)
    if established:
        return default_dir
    raise BackendUnavailable(
        "LOOP_BRIDGE_DIR is not configured and no established legacy bridge "
        "directory exists; select a shared writable directory first"
    )


@contextmanager
def locked(bridge_dir: Path) -> Iterator[Path]:
    """Create and exclusively lock a board directory for mutation."""

    error: str | None = None
    try:
        bridge_dir.mkdir(parents=True, exist_ok=True)
        lock_path = bridge_dir / ".lock"
        lock_fh = open(lock_path, "w")
    except OSError as exc:
        error = f"unable to lock bridge directory {bridge_dir}: {exc}"
    if error is not None:
        raise BackendUnavailable(error)

    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
    except OSError as exc:
        error = f"unable to lock bridge directory {bridge_dir}: {exc}"
    if error is not None:
        lock_fh.close()
        raise BackendUnavailable(error)
    try:
        yield bridge_dir
    finally:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        finally:
            lock_fh.close()


def decode_state(raw: str) -> dict[str, object]:
    """Decode the complete legacy claims-board schema unchanged."""

    return decode_legacy_claims(raw)


def read_mutating(bridge_dir: Path) -> dict[str, object]:
    """Read state for a mutation, failing closed on corrupt or unreadable data."""

    claims_path = bridge_dir / "claims.json"
    read_error: str | None = None
    try:
        if not claims_path.exists():
            return {"claims": []}
        raw = claims_path.read_text()
    except (OSError, ValueError) as exc:
        read_error = f"unable to read claims state in {claims_path}: {exc}"
    if read_error is not None:
        raise BackendUnavailable(read_error)

    schema_reason: str | None = None
    try:
        state = decode_state(raw)
    except SchemaError as exc:
        # The original bytes remain untouched; a caller must repair the board
        # explicitly before mutations can proceed.  Keep only the safe
        # validation message and raise after leaving the parser's handler.
        schema_reason = str(exc)
        state = None
    if schema_reason is not None:
        detail = f"invalid claims state in {claims_path}: {schema_reason}"
        raise ValidationError(SchemaError(detail), message=detail)
    assert state is not None
    return state


def read_observational(bridge_dir: Path) -> tuple[dict[str, object], str | None]:
    """Read claims without creating, locking, renaming, or repairing storage."""

    claims_path = bridge_dir / "claims.json"
    try:
        if not claims_path.exists():
            return {"claims": []}, None
        raw = claims_path.read_text()
    except (OSError, ValueError) as exc:
        return {}, f"invalid claims state in {claims_path}: {exc}"

    try:
        return decode_state(raw), None
    except SchemaError as exc:
        return {}, f"invalid claims state in {claims_path}: {exc}"


def write_state(bridge_dir: Path, state: Mapping[str, object]) -> None:
    """Publish legacy state through the historical same-filesystem rename."""

    claims_path = bridge_dir / "claims.json"
    tmp_path = bridge_dir / "claims.json.tmp"
    write_error: str | None = None
    try:
        tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True))
        tmp_path.replace(claims_path)
    except OSError as exc:
        write_error = f"unable to write claims state in {claims_path}: {exc}"
    if write_error is not None:
        raise BackendUnavailable(write_error)


def audit(
    bridge_dir: Path,
    action: str,
    entry: Mapping[str, object],
    *,
    now: Callable[[], datetime] | None = None,
) -> None:
    """Append one legacy audit record using the existing JSONL shape."""

    clock = _now if now is None else now
    record = {"ts": _iso(clock()), "action": action, **entry}
    audit_error: str | None = None
    try:
        with open(bridge_dir / "log.jsonl", "a") as log_fh:
            log_fh.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError as exc:
        audit_error = (
            f"unable to append bridge audit in {bridge_dir / 'log.jsonl'}: {exc}"
        )
    if audit_error is not None:
        raise BackendUnavailable(audit_error)


def live_claims(
    state: Mapping[str, object], *, now: datetime
) -> list[dict[str, object]]:
    """Return active claims whose expiry is strictly after ``now``."""

    claims = state.get("claims", [])
    out: list[dict[str, object]] = []
    for claim in claims:  # type: ignore[union-attr]
        try:
            if _parse(claim["expires_at"]) > now and claim.get("status") == "active":  # type: ignore[index, union-attr]
                out.append(claim)  # type: ignore[arg-type]
        except (KeyError, ValueError):
            continue
    return out


def overlap(claim: Mapping[str, object], area: str, files: Sequence[str]) -> str | None:
    """Return the historical human-readable overlap reason, if any."""

    claim_area = claim.get("area", "")
    if area and claim_area.strip().lower() == area.strip().lower():  # type: ignore[union-attr]
        return f"same area '{claim['area']}'"
    shared = set(claim.get("files", [])) & set(files)  # type: ignore[arg-type]
    if shared:
        return f"shared files {sorted(shared)}"
    return None


class LocalBackend(LocalMutex):
    """Legacy branch-keyed local mutex backed by a shared filesystem path."""

    def __init__(self, bridge_dir: Path) -> None:
        self.bridge_dir = bridge_dir

    def claim_legacy(
        self,
        agent: str,
        branch: str,
        area: str,
        files: Sequence[str],
        pr: str | int | None,
        ttl_seconds: int,
    ) -> dict[str, object]:
        with locked(self.bridge_dir) as bridge_dir:
            state = read_mutating(bridge_dir)
            for existing in live_claims(state, now=_now()):
                # A same-agent reclaim of the same branch is an idempotent
                # update, matching the old command-line bridge.
                if existing.get("branch") == branch and existing.get("agent") == agent:
                    continue
                why = overlap(existing, area, files)
                if why:
                    raise Conflict(
                        f"CONFLICT: {existing.get('agent')} already holds "
                        f"'{existing.get('area')}' (branch {existing.get('branch')}, "
                        f"{why}). Pick something else."
                    )

            now = _now()
            claim: dict[str, object] = {
                "agent": agent,
                "branch": branch,
                "area": area,
                "files": list(files),
                "pr": pr,
                "status": "active",
                "claimed_at": _iso(now),
                "expires_at": _iso(now + _dt.timedelta(seconds=ttl_seconds)),
            }
            state["claims"] = [
                existing
                for existing in state.get("claims", [])  # type: ignore[union-attr]
                if existing.get("branch") != branch  # type: ignore[union-attr]
            ]
            state["claims"].append(claim)  # type: ignore[union-attr]
            write_state(bridge_dir, state)
            audit(bridge_dir, "claim", claim)
        return claim

    def heartbeat_legacy(self, branch: str, ttl_seconds: int) -> None:
        with locked(self.bridge_dir) as bridge_dir:
            state = read_mutating(bridge_dir)
            live_branches = {
                claim.get("branch") for claim in live_claims(state, now=_now())
            }
            if branch not in live_branches:
                raise ClaimLost(
                    f"no live claim for branch {branch} "
                    "(expired or released — re-run `claim`)"
                )
            for claim in state.get("claims", []):  # type: ignore[union-attr]
                if claim.get("branch") == branch and claim.get("status") == "active":  # type: ignore[union-attr]
                    claim["expires_at"] = _iso(  # type: ignore[index, union-attr]
                        _now() + _dt.timedelta(seconds=ttl_seconds)
                    )
            write_state(bridge_dir, state)
            audit(bridge_dir, "heartbeat", {"branch": branch})

    def release_legacy(self, branch: str, reason: str) -> bool:
        with locked(self.bridge_dir) as bridge_dir:
            state = read_mutating(bridge_dir)
            before = len(state.get("claims", []))  # type: ignore[arg-type]
            state["claims"] = [
                claim
                for claim in state.get("claims", [])  # type: ignore[union-attr]
                if claim.get("branch") != branch  # type: ignore[union-attr]
            ]
            write_state(bridge_dir, state)
            audit(bridge_dir, "release", {"branch": branch, "reason": reason})
        return bool(before)

    def list_legacy(self) -> list[dict[str, object]]:
        state, error = read_observational(self.bridge_dir)
        if error is not None:
            raise ValidationError(SchemaError(error), message=error)
        return live_claims(state, now=_now())

    def check_legacy(self, area: str, files: Sequence[str]) -> list[dict[str, object]]:
        with locked(self.bridge_dir) as bridge_dir:
            state = read_mutating(bridge_dir)
            conflicts: list[dict[str, object]] = []
            for claim in live_claims(state, now=_now()):
                if overlap(claim, area, files):
                    conflicts.append(claim)
            return conflicts


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "LocalBackend",
    "audit",
    "decode_state",
    "live_claims",
    "locked",
    "overlap",
    "read_mutating",
    "read_observational",
    "resolve_bridge_dir",
    "write_state",
]
