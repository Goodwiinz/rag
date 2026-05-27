"""Tests for the iteration-ledger replay diff."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.eval.replay_ledger import diff_runs


def _write_run(root: Path, thread_id: str, iterations: list[dict], final: dict | None = None) -> Path:
    """Build a synthetic ledger directory."""
    run_dir = root / thread_id
    iter_dir = run_dir / "iterations"
    iter_dir.mkdir(parents=True, exist_ok=True)
    for i, payload in enumerate(iterations, start=1):
        (iter_dir / f"{i:04d}.json").write_text(json.dumps(payload))
    if final is not None:
        (run_dir / "final.json").write_text(json.dumps(final))
    return run_dir


def _iter(turn: int, intent: str = "research", tools: list[str] | None = None) -> dict:
    return {
        "turn": turn,
        "timestamp": "2026-05-12T00:00:00",
        "summary": {
            "user_query": "find papers",
            "intent": intent,
            "intent_confidence": 0.95,
            "tool_loop_count": 1,
            "error_count": 0,
            "tools_used": tools or ["search_arxiv"],
            "ai_response_chars": 500,
        },
        "state_snapshot": {
            "page_context": {"type": "project", "project_id": "p1"},
            "current_project_id": "p1",
            "model": "gpt-5",
            "plan": [],
            "tool_executions": [],
            "retrieved_contexts": [],
            "user_memories_keys": [],
            "reflection_result": {"passed": True, "issues": [], "severity": "none"},
            "last_error": None,
            "last_error_info": None,
            "compaction_count": 0,
            "reflection_count": 0,
        },
    }


def _final(latest_turn: int = 1, intent: str = "research") -> dict:
    return {
        "thread_id": "t1",
        "latest_turn": latest_turn,
        "updated_at": "2026-05-12T00:00:00",
        "summary": {
            "intent": intent,
            "tools_used": ["search_arxiv"],
            "tool_loop_count": 1,
            "error_count": 0,
        },
    }


@pytest.mark.unit
def test_identical_runs_have_no_drift(tmp_path: Path):
    g = _write_run(tmp_path / "g", "t1", [_iter(1)], final=_final())
    c = _write_run(tmp_path / "c", "t1", [_iter(1)], final=_final())
    diff = diff_runs(g, c)
    assert not diff.has_drift
    assert diff.turn_count_match


@pytest.mark.unit
def test_intent_drift_flagged(tmp_path: Path):
    g = _write_run(tmp_path / "g", "t1", [_iter(1, intent="research")])
    c = _write_run(tmp_path / "c", "t1", [_iter(1, intent="general")])
    diff = diff_runs(g, c)
    assert diff.has_drift
    assert diff.turn_diffs[0].summary_diff.get("intent") == ("research", "general")


@pytest.mark.unit
def test_tools_used_order_matters(tmp_path: Path):
    g = _write_run(
        tmp_path / "g", "t1",
        [_iter(1, tools=["search_arxiv", "ingest_arxiv_papers"])],
    )
    c = _write_run(
        tmp_path / "c", "t1",
        [_iter(1, tools=["ingest_arxiv_papers", "search_arxiv"])],
    )
    diff = diff_runs(g, c)
    assert diff.has_drift
    assert "tools_used" in diff.turn_diffs[0].summary_diff


@pytest.mark.unit
def test_turn_count_mismatch_flagged(tmp_path: Path):
    g = _write_run(tmp_path / "g", "t1", [_iter(1), _iter(2)])
    c = _write_run(tmp_path / "c", "t1", [_iter(1)])
    diff = diff_runs(g, c)
    assert diff.has_drift
    assert not diff.turn_count_match
    assert diff.golden_turn_count == 2
    assert diff.candidate_turn_count == 1


@pytest.mark.unit
def test_format_includes_drift_details(tmp_path: Path):
    g = _write_run(tmp_path / "g", "t1", [_iter(1, intent="research")])
    c = _write_run(tmp_path / "c", "t1", [_iter(1, intent="general")])
    diff = diff_runs(g, c)
    text = diff.format()
    assert "Turn 1" in text
    assert "intent" in text
    assert "research" in text
    assert "general" in text


@pytest.mark.unit
def test_format_silent_when_clean(tmp_path: Path):
    g = _write_run(tmp_path / "g", "t1", [_iter(1)], final=_final())
    c = _write_run(tmp_path / "c", "t1", [_iter(1)], final=_final())
    text = diff_runs(g, c).format()
    assert "No behavioral drift detected" in text


@pytest.mark.unit
def test_missing_iterations_dir_returns_empty(tmp_path: Path):
    """Run dir without iterations/ subdir → 0 turns, not crash."""
    g = tmp_path / "empty_g"
    c = tmp_path / "empty_c"
    g.mkdir()
    c.mkdir()
    diff = diff_runs(g, c)
    assert diff.golden_turn_count == 0
    assert diff.candidate_turn_count == 0
    assert not diff.has_drift


@pytest.mark.unit
def test_corrupt_iteration_json_skipped(tmp_path: Path):
    g_dir = tmp_path / "g"
    g_iter = g_dir / "iterations"
    g_iter.mkdir(parents=True)
    (g_iter / "0001.json").write_text("not valid json {")
    (g_iter / "0002.json").write_text(json.dumps(_iter(2)))
    c = _write_run(tmp_path / "c", "t1", [_iter(2)])
    diff = diff_runs(g_dir, c)
    # Corrupt file skipped → only 1 turn loaded from golden
    assert diff.golden_turn_count == 1
    assert diff.candidate_turn_count == 1
