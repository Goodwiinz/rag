"""Behavioural tests for trajectory evaluator functions."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MODULE_DIR))
ev = importlib.import_module("langsmith_trajectory_evaluators")


def _run(outputs: dict, inputs: dict | None = None) -> dict:
    return {"outputs": outputs, "inputs": inputs or {"messages": []}}


def test_destructive_tool_confirmed_passes_when_user_confirmed() -> None:
    run = _run(
        outputs={
            "user_confirmed": True,
            "messages": [
                {"id": "h1", "type": "human", "content": "ingest these papers"},
                {
                    "id": "a1",
                    "type": "ai",
                    "tool_calls": [
                        {"id": "t1", "name": "ingest_arxiv_papers", "args": {"ids": ["2605.10286"]}}
                    ],
                },
                {"id": "t1", "type": "tool", "tool_call_id": "t1", "content": "ingested"},
            ],
        }
    )
    result = ev.destructive_tool_confirmed(run)
    assert result["score"] == 1


def test_destructive_tool_confirmed_fails_when_no_confirmation() -> None:
    run = _run(
        outputs={
            "user_confirmed": False,
            "pending_confirmation": {},
            "messages": [
                {"id": "h1", "type": "human", "content": "ingest"},
                {
                    "id": "a1",
                    "type": "ai",
                    "tool_calls": [
                        {"id": "t1", "name": "create_note", "args": {"title": "x"}}
                    ],
                },
            ],
        }
    )
    result = ev.destructive_tool_confirmed(run)
    assert result["score"] == 0


def test_destructive_tool_confirmed_vacuous_when_no_destructive_calls() -> None:
    run = _run(
        outputs={
            "messages": [
                {"id": "h1", "type": "human", "content": "list"},
                {
                    "id": "a1",
                    "type": "ai",
                    "tool_calls": [
                        {"id": "t1", "name": "list_project_documents", "args": {}}
                    ],
                },
                {"id": "t1", "type": "tool", "tool_call_id": "t1", "content": "ok"},
            ],
        }
    )
    result = ev.destructive_tool_confirmed(run)
    assert result["score"] == 1
