"""Validation primitives for local and remote NOUS coordination state.

The remote coordination schema treats all data crossing a process or machine
boundary as untrusted.  The legacy claims board intentionally has a separate,
backwards-compatible decoder below: it validates the shape accepted by the
existing bridge without normalizing or removing unknown keys.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from typing import Final

CLAIMS_MAX_BYTES: Final = 64 * 1024
RUN_MAX_BYTES: Final = 16 * 1024
MAX_FILES: Final = 50
MAX_AREA_CHARS: Final = 200
MAX_PATH_CHARS: Final = 200
MAX_BRANCH_CHARS: Final = 120
MAX_AGENT_CHARS: Final = 64
MAX_MACHINE_ID_CHARS: Final = 64
MAX_PR: Final = 10**7
SKEW_SECONDS: Final = 120
CANDIDATE_SOURCES: Final = (
    "trace",
    "audit-ledger",
    "backlog",
    "fresh-hunt",
)
BLOCKER_KINDS: Final = (
    "permission",
    "review-unavailable",
    "gate-unavailable",
    "red-check",
    "human-decision",
    "publication-unavailable",
    "other",
)


class SchemaError(ValueError):
    """A schema or untrusted-input validation rejection."""


_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s")
_RUN_ID = re.compile(r"[0-9]{8}T[0-9]{6}Z-[a-z0-9-]{1,32}-[a-f0-9]{6}")
_AGENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9@._-]{0,63}")
_MACHINE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_SHA = re.compile(r"[0-9a-f]{40}")
_BRANCH_FORBIDDEN = re.compile(r"[~^:?*\\\[\]]")

# Keep these patterns separate and compiled: they are applied to short,
# operator-authored free text and must never be interpolated into an error.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_"),
    re.compile(r"gho_"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(password|secret|token|api[_-]?key)\s*[:=]\s*\S",
        re.IGNORECASE,
    ),
    re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{40,}(?![A-Za-z0-9+/])"),
)


def _ensure_text(value: object, field: str) -> str:
    """Validate a remote string's UTF-8 and Unicode printability."""

    if not isinstance(value, str):
        raise SchemaError(f"{field} must be text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        invalid_encoding = True
    else:
        invalid_encoding = False
    if (
        invalid_encoding
        or _CONTROL.search(value) is not None
        or not value.isprintable()
    ):
        raise SchemaError(f"{field} contains invalid text")
    return value


def _require_length(value: str, field: str, maximum: int) -> None:
    if len(value) > maximum:
        raise SchemaError(f"{field} exceeds the maximum length of {maximum} characters")


def validate_run_id(value: str) -> str:
    """Validate the path-safe run identifier used by remote projections."""

    value = _ensure_text(value, "run_id")
    if _RUN_ID.fullmatch(value) is None:
        raise SchemaError("run_id has an invalid format")
    return value


def validate_agent(value: str) -> str:
    """Validate an agent slug."""

    value = _ensure_text(value, "agent")
    if _AGENT.fullmatch(value) is None:
        raise SchemaError("agent has an invalid format")
    return value


def validate_machine_id(value: str) -> str:
    """Validate a stable, explicitly configured machine identifier."""

    value = _ensure_text(value, "machine_id")
    if _MACHINE_ID.fullmatch(value) is None:
        raise SchemaError("machine_id has an invalid format")
    return value


def _validate_branch_local(value: str, *, conservative: bool = True) -> None:
    """Apply invariant branch checks and optionally the local subset."""

    if not value:
        raise SchemaError("branch must be non-empty")
    _require_length(value, "branch", MAX_BRANCH_CHARS)
    if value.startswith("-"):
        raise SchemaError("branch must not begin with '-'")
    if _WHITESPACE.search(value) is not None:
        raise SchemaError("branch must not contain whitespace")
    if ".." in value:
        raise SchemaError("branch must not contain '..'")
    if "@{" in value:
        raise SchemaError("branch must not contain '@{'")

    if not conservative:
        return

    if _BRANCH_FORBIDDEN.search(value) is not None:
        raise SchemaError("branch contains a character forbidden by Git")
    if value == "@":
        raise SchemaError("branch must not be '@'")
    if value.startswith("/") or value.endswith("/") or "//" in value:
        raise SchemaError("branch has invalid slash placement")

    # Git disallows components that begin or end with a dot, and components
    # ending in the lockfile suffix.  Checking these locally keeps unsafe
    # values out of a subprocess even when no checker is available.
    for component in value.split("/"):
        if not component or component.startswith(".") or component.endswith("."):
            raise SchemaError("branch has an invalid component")
        if component.lower().endswith(".lock"):
            raise SchemaError("branch component must not end with '.lock'")


def validate_branch_syntax(
    value: str, checker: Callable[[str], bool] | None = None
) -> str:
    """Validate a branch locally and, optionally, with Git's exact checker.

    ``checker`` is injected by callers that can run ``git check-ref-format
    --branch``.  No process is started here; without it the conservative local
    subset above is the complete check.
    """

    value = _ensure_text(value, "branch")
    _validate_branch_local(value, conservative=checker is None)
    if checker is not None:
        if not callable(checker):
            raise SchemaError("branch checker must be callable")
        try:
            valid = checker(value)
        except Exception:
            checker_failed = True
        else:
            checker_failed = False
        if checker_failed:
            raise SchemaError("branch could not be checked by Git")
        if not valid:
            raise SchemaError("branch does not satisfy Git branch syntax")
    return value


def validate_branch(value: str) -> str:
    """Validate a branch using only the conservative local subset."""

    return validate_branch_syntax(value)


def validate_area(value: str) -> str:
    """Validate the short free-text area used for overlap checks."""

    value = reject_secret_text(value, field="area")
    if not value:
        raise SchemaError("area must be non-empty")
    _require_length(value, "area", MAX_AREA_CHARS)
    return value


def validate_files(values: Sequence[str]) -> tuple[str, ...]:
    """Validate and preserve a bounded sequence of repo-relative paths."""

    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise SchemaError("files must be a sequence of paths")
    if len(values) > MAX_FILES:
        raise SchemaError(f"files must contain at most {MAX_FILES} paths")

    result: list[str] = []
    for index, value in enumerate(values):
        field = f"files[{index}]"
        value = _ensure_text(value, field)
        if not value:
            raise SchemaError(f"{field} must be non-empty")
        _require_length(value, field, MAX_PATH_CHARS)
        if value.startswith("/"):
            raise SchemaError(f"{field} must be repo-relative")
        if value.startswith("-"):
            raise SchemaError(f"{field} must not begin with '-'")
        if "\\" in value:
            raise SchemaError(f"{field} must not contain backslashes")
        if ".." in value.split("/"):
            raise SchemaError(f"{field} must not contain a '..' segment")
        result.append(value)
    return tuple(result)


def validate_sha(value: str) -> str:
    """Validate a lowercase Git object ID without generic secret heuristics."""

    if not isinstance(value, str):
        raise SchemaError("sha must be exactly 40 lowercase hexadecimal characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        invalid_encoding = True
    else:
        invalid_encoding = False
    if invalid_encoding:
        raise SchemaError("sha must be exactly 40 lowercase hexadecimal characters")
    if _SHA.fullmatch(value) is None:
        raise SchemaError("sha must be exactly 40 lowercase hexadecimal characters")
    return value


def validate_pr(value: int | None) -> int | None:
    """Validate an optional positive pull-request number."""

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError("pr must be a positive integer or null")
    if value < 1 or value > MAX_PR:
        raise SchemaError(f"pr must be between 1 and {MAX_PR}")
    return value


def validate_timestamp(value: str) -> str:
    """Validate an ISO-8601 timestamp carrying an explicit UTC offset."""

    value = _ensure_text(value, "timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is None:
        raise SchemaError("timestamp must be an ISO-8601 timestamp")
    offset = parsed.utcoffset()
    if parsed.tzinfo is None or offset is None:
        raise SchemaError("timestamp must include a timezone")
    if offset != timedelta(0):
        raise SchemaError("timestamp must be in UTC")
    return value


def reject_secret_text(value: str, *, field: str) -> str:
    """Reject control characters and known credential-shaped free text."""

    value = _ensure_text(value, field)
    if any(pattern.search(value) is not None for pattern in _SECRET_PATTERNS):
        raise SchemaError(f"{field} matches a prohibited secret pattern")
    return value


def _legacy_error(index: int, field: str, message: str) -> SchemaError:
    return SchemaError(f"claims[{index}].{field} {message}")


def validate_legacy_claim(claim: Mapping[str, object], *, index: int) -> None:
    """Validate exactly the shape accepted by the historical local bridge.

    Unknown fields are deliberately ignored.  The decoder returns the parsed
    object unchanged so bridge extensions survive a read/write cycle.
    """

    if not isinstance(claim, Mapping):
        raise _legacy_error(index, "claim", "must be an object")

    required_fields = ("agent", "branch", "area", "status", "claimed_at", "expires_at")
    for field in required_fields:
        value = claim.get(field)
        if not isinstance(value, str) or not value:
            raise _legacy_error(index, field, "must be a non-empty string")

    if claim["status"] != "active":
        raise _legacy_error(index, "status", "must be active")

    files = claim.get("files")
    if not isinstance(files, list) or not all(
        isinstance(path, str) and bool(path) for path in files
    ):
        raise _legacy_error(index, "files", "must be a list of non-empty strings")

    pr = claim.get("pr")
    if pr is not None and (isinstance(pr, bool) or not isinstance(pr, (str, int))):
        raise _legacy_error(index, "pr", "must be a string, integer, or null")

    for field in ("claimed_at", "expires_at"):
        timestamp = claim[field]
        try:
            parsed = datetime.fromisoformat(timestamp)
        except (TypeError, ValueError, OverflowError):
            parsed = None
        if parsed is None:
            raise _legacy_error(index, field, "must be an ISO timestamp")
        if parsed.tzinfo is None:
            raise _legacy_error(index, field, "must include a timezone")


def decode_legacy_claims(raw: str) -> dict[str, object]:
    """Decode and validate a legacy ``claims.json`` document unchanged."""

    if not isinstance(raw, str):
        raise SchemaError("claims state must be JSON text")
    if not raw.strip():
        raise SchemaError("claims state is empty")
    parser_detail: str | None = None
    try:
        state = json.loads(raw)
    except (TypeError, ValueError) as exc:
        parser_detail = str(exc)
        state = None
    if parser_detail is not None:
        raise SchemaError(f"claims state is not valid JSON: {parser_detail}")
    if not isinstance(state, dict):
        raise SchemaError("claims state root must be an object")

    claims = state.get("claims")
    if not isinstance(claims, list):
        raise SchemaError("claims state must contain a claims list")
    for index, claim in enumerate(claims):
        validate_legacy_claim(claim, index=index)
    return state


__all__ = [
    "BLOCKER_KINDS",
    "CANDIDATE_SOURCES",
    "CLAIMS_MAX_BYTES",
    "MAX_AGENT_CHARS",
    "MAX_AREA_CHARS",
    "MAX_BRANCH_CHARS",
    "MAX_FILES",
    "MAX_MACHINE_ID_CHARS",
    "MAX_PATH_CHARS",
    "MAX_PR",
    "RUN_MAX_BYTES",
    "SKEW_SECONDS",
    "SchemaError",
    "decode_legacy_claims",
    "reject_secret_text",
    "validate_agent",
    "validate_area",
    "validate_branch",
    "validate_branch_syntax",
    "validate_files",
    "validate_legacy_claim",
    "validate_machine_id",
    "validate_pr",
    "validate_run_id",
    "validate_sha",
    "validate_timestamp",
]
