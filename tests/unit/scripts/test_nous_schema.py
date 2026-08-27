"""Focused tests for the shared NOUS coordination schema primitives."""

from __future__ import annotations

import pytest


def test_run_id_and_remote_scalars_reject_traversal_and_secrets():
    from scripts.nous import schema
    from scripts.nous.schema import SchemaError
    import pytest

    assert schema.validate_run_id("20260827T040000Z-agent-9f3a1c")
    with pytest.raises(SchemaError):
        schema.validate_run_id("../runs/evil")
    with pytest.raises(SchemaError):
        schema.validate_branch("-delete-me")
    with pytest.raises(SchemaError):
        schema.reject_secret_text("token=ghp_abcdefghijklmnopqrstuvwxyz", field="area")


def test_legacy_decoder_keeps_old_claim_shape():
    from scripts.nous.schema import decode_legacy_claims

    raw = (
        '{"claims": [{"agent": "a", "branch": "b", "area": "x", '
        '"files": [], "pr": null, "status": "active", '
        '"claimed_at": "2026-01-01T00:00:00+00:00", '
        '"expires_at": "2026-01-01T01:00:00+00:00"}]}'
    )
    assert decode_legacy_claims(raw)["claims"][0]["branch"] == "b"


def test_legacy_decoder_rejects_missing_expiry():
    from scripts.nous.schema import SchemaError, decode_legacy_claims
    import pytest

    with pytest.raises(SchemaError):
        decode_legacy_claims('{"claims": [{"agent": "a"}]}')


def test_scalar_validators_enforce_declared_shapes_and_limits():
    from scripts.nous import schema
    from scripts.nous.schema import SchemaError

    assert schema.validate_agent("agent_1@example") == "agent_1@example"
    assert schema.validate_machine_id("linux-box_1") == "linux-box_1"
    assert schema.validate_branch("fix/streaming-null-guard") == (
        "fix/streaming-null-guard"
    )
    assert schema.validate_area("an area") == "an area"
    assert schema.validate_files(["backend/src/app.py", "tests/test_app.py"]) == (
        "backend/src/app.py",
        "tests/test_app.py",
    )
    assert schema.validate_sha("a" * 40) == "a" * 40
    assert schema.validate_pr(None) is None
    assert schema.validate_pr(123) == 123
    assert schema.validate_timestamp("2026-01-01T00:00:00+00:00") == (
        "2026-01-01T00:00:00+00:00"
    )

    invalid_values = (
        (schema.validate_agent, "-agent"),
        (schema.validate_machine_id, "machine id"),
        (schema.validate_branch, "topic..name"),
        (schema.validate_area, ""),
        (schema.validate_files, ["../outside.py"]),
        (schema.validate_sha, "A" * 40),
        (schema.validate_pr, 0),
        (schema.validate_timestamp, "2026-01-01T00:00:00"),
    )
    for validator, value in invalid_values:
        with pytest.raises(SchemaError):
            validator(value)


def test_branch_syntax_uses_exact_checker_when_supplied():
    from scripts.nous.schema import validate_branch_syntax

    calls: list[str] = []

    def checker(value: str) -> bool:
        calls.append(value)
        return value == "feature/valid"

    assert validate_branch_syntax("feature/valid", checker=checker) == "feature/valid"
    assert calls == ["feature/valid"]


def test_branch_syntax_checker_can_accept_a_git_valid_branch_outside_local_subset():
    from scripts.nous.schema import validate_branch_syntax

    assert validate_branch_syntax("foo/bar.LOCK", checker=lambda _: True) == (
        "foo/bar.LOCK"
    )


@pytest.mark.parametrize(
    "value",
    [
        "AKIA" + "A" * 16,
        "ghp_" + "a" * 20,
        "github_pat_abc",
        "gho_abc",
        "sk-" + "a" * 20,
        "xoxb-abc",
        "-----BEGIN RSA PRIVATE KEY-----",
        "password: secret-value",
        "a" * 40,
    ],
)
def test_secret_patterns_are_rejected_without_echoing_text(value):
    from scripts.nous.schema import SchemaError, reject_secret_text

    with pytest.raises(SchemaError) as caught:
        reject_secret_text(value, field="area")
    assert value not in str(caught.value)


def test_sha_is_structured_and_not_rejected_by_generic_secret_heuristic():
    from scripts.nous.schema import validate_sha

    value = "abcdef0123456789abcdef0123456789abcdef01"
    assert validate_sha(value) == value


def test_files_reject_limits_traversal_and_backslashes():
    from scripts.nous.schema import (
        MAX_FILES,
        MAX_PATH_CHARS,
        SchemaError,
        validate_files,
    )

    assert (
        len(validate_files([f"file-{index}.py" for index in range(MAX_FILES)]))
        == MAX_FILES
    )
    with pytest.raises(SchemaError):
        validate_files(["a.py"] * (MAX_FILES + 1))
    with pytest.raises(SchemaError):
        validate_files(["a" * (MAX_PATH_CHARS + 1)])
    for path in ("/absolute.py", "-option.py", "foo/../bar.py", "foo\\bar.py"):
        with pytest.raises(SchemaError):
            validate_files([path])


def test_legacy_decoder_preserves_unknown_root_and_claim_keys():
    from scripts.nous.schema import decode_legacy_claims

    raw = (
        '{"legacy": {"keep": true}, "claims": [{"agent": "a", '
        '"branch": "b", "area": "x", "files": [], "pr": "42", '
        '"status": "active", "claimed_at": "2026-01-01T00:00:00+00:00", '
        '"expires_at": "2026-01-01T01:00:00+00:00", '
        '"future_key": {"untouched": [1, 2]}}]}'
    )
    decoded = decode_legacy_claims(raw)
    assert decoded["legacy"] == {"keep": True}
    assert decoded["claims"][0]["future_key"] == {"untouched": [1, 2]}
