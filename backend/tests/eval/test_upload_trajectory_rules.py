"""Unit tests for upload_trajectory_rules CLI surface and code extraction."""
from __future__ import annotations

import datetime as _dt
import importlib
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parent / "upload_trajectory_rules.py"
sys.path.insert(0, str(MODULE_PATH.parent))
uploader = importlib.import_module("upload_trajectory_rules")


def test_build_rule_body_includes_backfill_when_provided() -> None:
    body = uploader._build_rule_body(
        display_name="Tool Call Validity",
        session_id="00000000-0000-0000-0000-000000000000",
        code="def perform_check(run): return {'score': 1}",
        sampling_rate=1.0,
        backfill_from=_dt.datetime(2026, 5, 18, 0, 0, tzinfo=_dt.timezone.utc),
    )
    assert body["backfill_from"] == "2026-05-18T00:00:00+00:00"


def test_build_rule_body_omits_backfill_when_none() -> None:
    body = uploader._build_rule_body(
        display_name="Tool Call Validity",
        session_id="00000000-0000-0000-0000-000000000000",
        code="def perform_check(run): return {'score': 1}",
        sampling_rate=1.0,
        backfill_from=None,
    )
    assert "backfill_from" not in body


def test_build_rule_body_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        uploader._build_rule_body(
            display_name="x",
            session_id="00000000-0000-0000-0000-000000000000",
            code="def perform_check(run): return {'score': 1}",
            sampling_rate=1.0,
            backfill_from=_dt.datetime(2026, 5, 18, 0, 0),  # no tzinfo
        )


def test_summarize_results_returns_nonzero_when_any_failure() -> None:
    results = [
        ("Tool Call Validity", "ok", None),
        ("No Tool Loop", "failed", "HTTPError 500"),
    ]
    code = uploader._summarize_results(results)
    assert code == 1


def test_summarize_results_returns_zero_when_all_ok() -> None:
    results = [
        ("Tool Call Validity", "ok", None),
        ("No Tool Loop", "ok", None),
    ]
    code = uploader._summarize_results(results)
    assert code == 0


def test_summarize_results_returns_zero_for_empty() -> None:
    code = uploader._summarize_results([])
    assert code == 0


def test_extract_function_renames_target() -> None:
    source = (
        "def _extract_messages(run):\n    return []\n\n"
        "def _iter_tool_calls(messages):\n    yield from ()\n\n"
        "def my_metric(run):\n    return {'score': 1}\n"
    )
    code = uploader._extract_function(source, "my_metric")
    assert "def perform_eval(run):" in code
    assert "def my_metric(" not in code


def test_extract_function_includes_both_helpers() -> None:
    source = (
        "def _extract_messages(run):\n    return []\n\n"
        "def _iter_tool_calls(messages):\n    yield from ()\n\n"
        "def my_metric(run):\n    return {'score': 1}\n"
    )
    code = uploader._extract_function(source, "my_metric")
    assert "def _extract_messages(" in code
    assert "def _iter_tool_calls(" in code


def test_extract_function_raises_when_target_missing() -> None:
    source = (
        "def _extract_messages(run):\n    return []\n\n"
        "def _iter_tool_calls(messages):\n    yield from ()\n"
    )
    with pytest.raises(RuntimeError, match="not found"):
        uploader._extract_function(source, "does_not_exist")
