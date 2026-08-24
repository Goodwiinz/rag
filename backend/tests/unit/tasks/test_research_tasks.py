"""Tests for the research workflow Celery task."""

import importlib
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def research_task_module():
    """Import research_tasks with mocked heavy dependencies.

    We inject mocks for celery's current_app, the SessionLocal from
    processing_tasks, and the connector/engine classes so that we can
    test the task function in isolation without Celery or a real DB.
    """
    # Create mock for celery.current_app.task decorator
    mock_current_app = MagicMock()
    mock_current_app.task = lambda *a, **kw: lambda fn: fn

    # Create mock SessionLocal
    mock_session_local = MagicMock

    # Patch modules before import
    saved = {}
    patches = {
        "celery": MagicMock(current_app=mock_current_app),
        "celery.current_app": mock_current_app,
    }

    # We must also ensure src.tasks.processing_tasks is importable and
    # exposes SessionLocal without actually running its heavy init code.
    mock_processing_tasks = MagicMock()
    mock_processing_tasks.SessionLocal = MagicMock
    mock_processing_tasks.celery_app = MagicMock()

    for mod_name, mock_obj in patches.items():
        saved[mod_name] = sys.modules.get(mod_name)
        sys.modules[mod_name] = mock_obj

    # Ensure src.tasks.processing_tasks is mocked
    saved["src.tasks.processing_tasks"] = sys.modules.get("src.tasks.processing_tasks")
    sys.modules["src.tasks.processing_tasks"] = mock_processing_tasks

    # Remove cached research_tasks module so it re-imports with our mocks
    mod_key = "src.tasks.research_tasks"
    saved[mod_key] = sys.modules.pop(mod_key, None)

    try:
        import src.tasks.research_tasks as mod

        importlib.reload(mod)
        yield mod
    finally:
        # Restore original modules
        for mod_name, orig in saved.items():
            if orig is None:
                sys.modules.pop(mod_name, None)
            else:
                sys.modules[mod_name] = orig


def _make_run(run_id, blueprint_id, status="pending"):
    """Create a mock ResearchRun."""
    run = MagicMock()
    run.id = run_id
    run.blueprint_id = blueprint_id
    run.blueprint_version = 1
    run.status = status
    run.started_at = None
    run.completed_at = None
    run.reproducibility_manifest = None
    run.total_tokens = 0
    return run


def _make_blueprint(blueprint_id):
    """Create a mock ResearchBlueprint."""
    bp = MagicMock()
    bp.id = blueprint_id
    bp.version = 1
    bp.steps = [
        {
            "id": "search_step",
            "type": "search",
            "params": {
                "sources": ["arxiv"],
                "query_template": "{query}",
            },
        },
        {
            "id": "synthesize_step",
            "type": "synthesize",
            "params": {
                "model_id": "gpt-4",
                "system_prompt_template": "Summarize: {query}",
            },
        },
    ]
    bp.parameters = {"query": "machine learning"}
    return bp


def _make_step_complete_event(run_id, step_index, step_id, token_count=10):
    """Create a step_complete event dict."""
    return {
        "event": "step_complete",
        "run_id": str(run_id),
        "step_index": step_index,
        "step_id": step_id,
        "output": {"content": f"result from {step_id}"},
        "quality_marks": [],
        "token_count": token_count,
    }


def _setup_db_queries(db, mock_run, mock_blueprint, mod):
    """Wire up db.query(...).filter(...).first() for ResearchRun and ResearchBlueprint."""
    run_chain = MagicMock()
    run_chain.filter.return_value.first.return_value = mock_run

    bp_chain = MagicMock()
    bp_chain.filter.return_value.first.return_value = mock_blueprint

    def query_side_effect(model):
        if model is mod.ResearchRun:
            return run_chain
        elif model is mod.ResearchBlueprint:
            return bp_chain
        return MagicMock()

    db.query.side_effect = query_side_effect


async def _engine_events_completed(run_id, events):
    """Async generator that yields a run_start, the given events, and run_complete."""
    yield {"event": "run_start", "run_id": str(run_id), "total_steps": len(events)}
    for ev in events:
        yield ev
    yield {"event": "run_complete", "run_id": str(run_id), "context": {}}
