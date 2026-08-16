"""Unit contracts for the targeted evidence migration probe."""

import signal
from collections.abc import Callable, Iterable
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.engine import make_url

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


def _require_api(probe: Any, *names: str) -> None:
    for name in names:
        assert hasattr(probe, name), f"probe module is missing required API: {name}"


def _stub_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    probe: Any,
    events: list[tuple[str, Any]],
    run_alembic: Callable[..., Any],
) -> str:
    _require_api(probe, "run_probe", "_create_database")
    scratch_name = "ci_evidence_delta_123_test_12345678"
    monkeypatch.setattr(probe, "scratch_database_name", lambda: scratch_name)

    class FakeConnection:
        def __init__(self, role: str) -> None:
            self.role = role

        def close(self) -> None:
            events.append(("close", self.role))

    connections = iter(
        [
            FakeConnection("admin"),
            FakeConnection("prior"),
            FakeConnection("upgrade"),
            FakeConnection("downgrade"),
        ]
    )

    def connect(database_url: str) -> Any:
        events.append(("connect", database_url))
        return next(connections)

    monkeypatch.setattr(
        probe,
        "_connect",
        connect,
    )
    monkeypatch.setattr(
        probe,
        "_create_database",
        lambda connection, database_name: events.append(("create", database_name)),
    )
    monkeypatch.setattr(
        probe,
        "_create_prior_state",
        lambda connection: events.append(("prior-state", connection.role)),
    )
    versions = iter(
        [probe.PARENT_REVISION, probe.TARGET_REVISION, probe.PARENT_REVISION]
    )
    monkeypatch.setattr(probe, "_version", lambda connection: next(versions))
    monkeypatch.setattr(probe, "_all_target_column_names", lambda connection: [])
    monkeypatch.setattr(
        probe,
        "_column_rows",
        lambda connection: [
            ("claim_text", "text", None, "YES"),
            ("source_content_hash", "character varying", 64, "YES"),
        ],
    )
    monkeypatch.setattr(probe, "_run_alembic", run_alembic)
    monkeypatch.setattr(
        probe,
        "_drop_database",
        lambda connection, database_name: events.append(("drop", database_name)),
    )
    return scratch_name


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
    rows: Iterable[tuple[str, str, int | None, str]] = (
        ("claim_text", "text", None, "YES"),
        ("source_content_hash", "character varying", 64, "YES"),
    )

    probe.verify_added_columns(rows)


def test_verify_added_columns_rejects_wrong_type_or_nullability() -> None:
    probe = _load_probe()
    rows: Iterable[tuple[str, str, int | None, str]] = (
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


def test_postgres_url_from_environment_preserves_special_credentials() -> None:
    probe = _load_probe()
    _require_api(probe, "postgres_url_from_environment")

    username = "ci@operator/name"
    password = "p@ss/w:rd%with?chars#"
    environment = {
        "PGHOST": "db.example.internal",
        "PGPORT": "55432",
        "PGUSER": username,
        "PGPASSWORD": password,
        "PGDATABASE": "scratch/postgres",
    }

    rendered = probe.postgres_url_from_environment(environment)
    parsed = make_url(rendered)

    assert parsed.username == username
    assert parsed.password == password
    assert parsed.host == "db.example.internal"
    assert parsed.port == 55432
    assert parsed.database == "scratch/postgres"
    assert password not in rendered


def test_run_probe_success_cleans_up_the_generated_scratch_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = _load_probe()
    events: list[tuple[str, Any]] = []

    def run_alembic(database_url: str, *arguments: str) -> None:
        events.append(("alembic", arguments))

    scratch_name = _stub_lifecycle(monkeypatch, probe, events, run_alembic)

    probe.run_probe("postgresql://admin@127.0.0.1/postgres")

    assert ("create", scratch_name) in events
    assert ("alembic", ("upgrade", probe.TARGET_REVISION)) in events
    assert ("alembic", ("downgrade", probe.PARENT_REVISION)) in events
    assert ("drop", scratch_name) in events
    assert events.index(("drop", scratch_name)) > events.index(
        ("alembic", ("downgrade", probe.PARENT_REVISION))
    )


def test_run_probe_migration_failure_still_drops_scratch_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = _load_probe()
    events: list[tuple[str, Any]] = []

    def run_alembic(database_url: str, *arguments: str) -> None:
        events.append(("alembic", arguments))
        if arguments == ("upgrade", probe.TARGET_REVISION):
            raise probe.ProbeError("injected migration failure")

    scratch_name = _stub_lifecycle(monkeypatch, probe, events, run_alembic)

    with pytest.raises(probe.ProbeError, match="injected migration failure"):
        probe.run_probe("postgresql://admin@127.0.0.1/postgres")

    assert ("drop", scratch_name) in events


def test_run_probe_sigterm_restores_handlers_and_drops_scratch_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = _load_probe()
    _require_api(probe, "signal")
    events: list[tuple[str, Any]] = []
    installed: dict[signal.Signals, Any] = {}
    previous = {signal.SIGTERM: "previous-term", signal.SIGINT: "previous-int"}
    calls: list[tuple[signal.Signals, Any]] = []

    def fake_getsignal(signum: signal.Signals) -> Any:
        return previous[signum]

    def fake_signal(signum: signal.Signals, handler: Any) -> Any:
        calls.append((signum, handler))
        if callable(handler):
            installed[signum] = handler
        return previous[signum]

    monkeypatch.setattr(probe.signal, "getsignal", fake_getsignal)
    monkeypatch.setattr(probe.signal, "signal", fake_signal)

    def run_alembic(database_url: str, *arguments: str) -> None:
        events.append(("alembic", arguments))
        if arguments == ("upgrade", probe.TARGET_REVISION):
            installed[signal.SIGTERM](signal.SIGTERM, None)

    scratch_name = _stub_lifecycle(monkeypatch, probe, events, run_alembic)

    with pytest.raises(probe.ProbeError, match="SIGTERM"):
        probe.run_probe("postgresql://admin@127.0.0.1/postgres")

    assert ("drop", scratch_name) in events
    assert (signal.SIGTERM, previous[signal.SIGTERM]) in calls
    assert (signal.SIGINT, previous[signal.SIGINT]) in calls


def test_run_probe_fails_closed_before_connecting_for_an_unsafe_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = _load_probe()
    connected = False
    monkeypatch.setattr(probe, "scratch_database_name", lambda: "postgres")

    def connect(database_url: str) -> Any:
        nonlocal connected
        connected = True
        return SimpleNamespace(close=lambda: None)

    monkeypatch.setattr(probe, "_connect", connect)

    with pytest.raises(probe.ProbeError, match="scratch"):
        probe.run_probe("postgresql://admin@127.0.0.1/postgres")

    assert not connected


def test_run_alembic_environment_overrides_managed_process_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = _load_probe()
    captured: dict[str, Any] = {}

    def fake_run(command: Any, **kwargs: Any) -> Any:
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(probe.subprocess, "run", fake_run)
    monkeypatch.setenv("DATABASE_URL", "postgresql://old-target")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://managed-target")

    probe._run_alembic("postgresql://scratch-target", "upgrade", probe.TARGET_REVISION)

    assert captured["env"]["DATABASE_URL"] == "postgresql://scratch-target"
    assert captured["env"]["SUPABASE_DB_URL"] == ""


def test_main_reports_probe_failure_without_leaking_admin_password(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    probe = _load_probe()
    secret = "p@ss/w:rd%with?chars#"

    def fail_probe(database_url: str) -> None:
        raise probe.ProbeError("injected failure")

    monkeypatch.setattr(probe, "run_probe", fail_probe)

    result = probe.main(
        ["--admin-database-url", f"postgresql://operator:{secret}@127.0.0.1/postgres"]
    )

    captured = capsys.readouterr()
    assert result == 1
    assert "injected failure" in captured.err
    assert secret not in captured.out
    assert secret not in captured.err
