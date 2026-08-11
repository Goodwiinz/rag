from __future__ import annotations

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "long_run_mock", Path(__file__).with_name("server.py")
)
assert SPEC and SPEC.loader
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


def test_duplicate_same_stage_markers_are_one_query() -> None:
    assert SERVER.query_stage("NOUS-LONG-1 then verify NOUS-LONG-1") == 1


def test_conflicting_stage_markers_are_ambiguous() -> None:
    assert SERVER.query_stage("NOUS-LONG-1 then NOUS-LONG-2") == 0
