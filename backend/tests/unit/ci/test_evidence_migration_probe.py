"""Unit contracts for the targeted evidence migration probe."""

from collections.abc import Iterable
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest

# The backend pytest configuration adds ``backend/`` to ``sys.path``. The
# probe lives at repository scope under ``scripts/``, so make that boundary
# explicit for this contract test.
REPO_ROOT = Path(__file__).resolve().parents[4]
PROBE_PATH = REPO_ROOT / "scripts" / "ci" / "probe_evidence_migration.py"


def _load_probe() -> Any:
    """Load the probe directly so the RED state is a normal test failure."""
    assert PROBE_PATH.is_file(), f"missing targeted probe: {PROBE_PATH}"
    spec = spec_from_file_location("probe_evidence_migration", PROBE_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_targets_exact_parent_and_revision() -> None:
    probe = _load_probe()
    assert probe.PARENT_REVISION == "i9j0k1l2m3n4"
    assert probe.TARGET_REVISION == "evidence_prov_20260816"
    assert probe.TABLE_NAME == "stance_classifications"
    assert probe.EXPECTED_COLUMNS == {
        "claim_text": ("text", None),
        "source_content_hash": ("character varying", 64),
    }


def test_verify_added_columns_requires_nullable_text_and_varchar_64() -> None:
    probe = _load_probe()
    rows: Iterable[probe.ColumnRow] = (
        ("claim_text", "text", None, "YES"),
        ("source_content_hash", "character varying", 64, "YES"),
    )

    probe.verify_added_columns(rows)


def test_verify_added_columns_rejects_wrong_type_or_nullability() -> None:
    probe = _load_probe()
    rows: Iterable[probe.ColumnRow] = (
        ("claim_text", "character varying", 64, "NO"),
        ("source_content_hash", "character varying", 32, "YES"),
    )

    with pytest.raises(probe.ProbeError, match="claim_text"):
        probe.verify_added_columns(rows)


def test_verify_columns_absent_rejects_any_target_column() -> None:
    probe = _load_probe()
    with pytest.raises(probe.ProbeError, match="source_content_hash"):
        probe.verify_columns_absent(("source_content_hash",))


def test_scratch_database_name_is_generated_and_guarded() -> None:
    probe = _load_probe()
    name = probe.scratch_database_name("unit-test")

    assert name.startswith(probe.SCRATCH_DATABASE_PREFIX)
    assert probe.is_safe_scratch_database_name(name)
    assert not probe.is_safe_scratch_database_name("postgres")
    assert not probe.is_safe_scratch_database_name("ci_evidence_delta_../../oops")


def test_alembic_environment_clears_managed_database_override() -> None:
    probe = _load_probe()
    env = probe.alembic_environment(
        "postgresql://postgres:postgres@127.0.0.1:5432/scratch",
        {"SUPABASE_DB_URL": "postgresql://managed.example/db", "KEEP": "yes"},
    )

    assert env["DATABASE_URL"].endswith("/scratch")
    assert env["SUPABASE_DB_URL"] == ""
    assert env["KEEP"] == "yes"
