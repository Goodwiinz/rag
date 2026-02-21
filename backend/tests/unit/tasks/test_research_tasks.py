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


class TestExecuteResearchWorkflow:
    """Tests for execute_research_workflow task."""

    def test_loads_run_and_blueprint_from_db(self, research_task_module):
        """Task should load both ResearchRun and ResearchBlueprint from DB."""
        mod = research_task_module
        run_id = uuid.uuid4()
        blueprint_id = uuid.uuid4()
        mock_run = _make_run(run_id, blueprint_id)
        mock_blueprint = _make_blueprint(blueprint_id)

        db = MagicMock()
        _setup_db_queries(db, mock_run, mock_blueprint, mod)

        async def mock_engine_run(blueprint, run_id, start_from_step=0):
            yield {"event": "run_start", "run_id": str(run_id), "total_steps": 0}
            yield {"event": "run_complete", "run_id": str(run_id), "context": {}}

        with patch.object(mod, "SessionLocal", return_value=db):
            with patch.object(mod, "WorkflowEngine") as mock_engine_cls:
                engine_instance = MagicMock()
                engine_instance.run = mock_engine_run
                mock_engine_cls.return_value = engine_instance

                with patch.object(mod, "StepExecutor"):
                    with patch.object(mod, "ArxivConnector"):
                        with patch.object(mod, "SemanticScholarConnector"):
                            result = mod.execute_research_workflow(str(run_id))

        assert db.query.call_count >= 2
        assert result["status"] == "completed"

    def test_raises_if_run_not_found(self, research_task_module):
        """Task should raise ValueError when run_id not found in DB."""
        mod = research_task_module
        run_id = uuid.uuid4()
        db = MagicMock()

        run_chain = MagicMock()
        run_chain.filter.return_value.first.return_value = None
        db.query.return_value = run_chain

        with patch.object(mod, "SessionLocal", return_value=db):
            with pytest.raises(ValueError, match="not found"):
                mod.execute_research_workflow(str(run_id))

        db.close.assert_called_once()

    def test_updates_status_to_running_then_completed(self, research_task_module):
        """Task should set status to RUNNING at start and COMPLETED on success."""
        mod = research_task_module
        run_id = uuid.uuid4()
        blueprint_id = uuid.uuid4()
        mock_run = _make_run(run_id, blueprint_id)
        mock_blueprint = _make_blueprint(blueprint_id)

        db = MagicMock()
        _setup_db_queries(db, mock_run, mock_blueprint, mod)

        status_changes = []

        class StatusTracker:
            """Track status changes on mock_run."""

            def __init__(self):
                self._status = "pending"

            @property
            def status(self):
                return self._status

            @status.setter
            def status(self, value):
                status_changes.append(value)
                self._status = value

        tracker = StatusTracker()
        # Use property descriptor to track status
        type(mock_run).status = property(
            lambda self: tracker.status,
            lambda self, v: setattr(tracker, 'status', v),
        )

        async def mock_engine_run(blueprint, run_id, start_from_step=0):
            yield {"event": "run_start", "run_id": str(run_id), "total_steps": 0}
            yield {"event": "run_complete", "run_id": str(run_id), "context": {}}

        with patch.object(mod, "SessionLocal", return_value=db):
            with patch.object(mod, "WorkflowEngine") as mock_engine_cls:
                engine_instance = MagicMock()
                engine_instance.run = mock_engine_run
                mock_engine_cls.return_value = engine_instance

                with patch.object(mod, "StepExecutor"):
                    with patch.object(mod, "ArxivConnector"):
                        with patch.object(mod, "SemanticScholarConnector"):
                            mod.execute_research_workflow(str(run_id))

        assert "running" in status_changes
        assert "completed" in status_changes

    def test_creates_step_records_on_step_complete(self, research_task_module):
        """Task should create ResearchStep records for each step_complete event."""
        mod = research_task_module
        run_id = uuid.uuid4()
        blueprint_id = uuid.uuid4()
        mock_run = _make_run(run_id, blueprint_id)
        mock_blueprint = _make_blueprint(blueprint_id)

        db = MagicMock()
        _setup_db_queries(db, mock_run, mock_blueprint, mod)

        async def mock_engine_run(blueprint, run_id, start_from_step=0):
            yield {"event": "run_start", "run_id": str(run_id), "total_steps": 2}
            yield _make_step_complete_event(run_id, 0, "search_step", token_count=5)
            yield _make_step_complete_event(run_id, 1, "synthesize_step", token_count=15)
            yield {"event": "run_complete", "run_id": str(run_id), "context": {}}

        with patch.object(mod, "SessionLocal", return_value=db):
            with patch.object(mod, "WorkflowEngine") as mock_engine_cls:
                engine_instance = MagicMock()
                engine_instance.run = mock_engine_run
                mock_engine_cls.return_value = engine_instance

                with patch.object(mod, "StepExecutor"):
                    with patch.object(mod, "ArxivConnector"):
                        with patch.object(mod, "SemanticScholarConnector"):
                            with patch.object(mod, "ResearchStep") as mock_step_cls:
                                mock_step_cls.return_value = MagicMock()
                                mod.execute_research_workflow(str(run_id))

        # Two step_complete events -> two ResearchStep records added
        assert db.add.call_count >= 2

    def test_sets_failed_on_run_failed_event(self, research_task_module):
        """Task should set status to FAILED when engine emits run_failed."""
        mod = research_task_module
        run_id = uuid.uuid4()
        blueprint_id = uuid.uuid4()
        mock_run = _make_run(run_id, blueprint_id)
        mock_blueprint = _make_blueprint(blueprint_id)

        db = MagicMock()
        _setup_db_queries(db, mock_run, mock_blueprint, mod)

        async def mock_engine_run(blueprint, run_id, start_from_step=0):
            yield {"event": "run_start", "run_id": str(run_id), "total_steps": 1}
            yield {
                "event": "run_failed",
                "run_id": str(run_id),
                "error": "Something broke",
            }

        with patch.object(mod, "SessionLocal", return_value=db):
            with patch.object(mod, "WorkflowEngine") as mock_engine_cls:
                engine_instance = MagicMock()
                engine_instance.run = mock_engine_run
                mock_engine_cls.return_value = engine_instance

                with patch.object(mod, "StepExecutor"):
                    with patch.object(mod, "ArxivConnector"):
                        with patch.object(mod, "SemanticScholarConnector"):
                            result = mod.execute_research_workflow(str(run_id))

        assert mock_run.status == "failed"
        assert result["status"] == "failed"

    def test_sets_paused_on_run_paused_event(self, research_task_module):
        """Task should set status to PAUSED when engine emits run_paused."""
        mod = research_task_module
        run_id = uuid.uuid4()
        blueprint_id = uuid.uuid4()
        mock_run = _make_run(run_id, blueprint_id)
        mock_blueprint = _make_blueprint(blueprint_id)

        db = MagicMock()
        _setup_db_queries(db, mock_run, mock_blueprint, mod)

        async def mock_engine_run(blueprint, run_id, start_from_step=0):
            yield {"event": "run_start", "run_id": str(run_id), "total_steps": 1}
            yield _make_step_complete_event(run_id, 0, "search_step")
            yield {
                "event": "run_paused",
                "run_id": str(run_id),
                "step_index": 0,
                "step_id": "search_step",
                "reason": "Quality check failed",
                "quality_marks": [],
            }

        with patch.object(mod, "SessionLocal", return_value=db):
            with patch.object(mod, "WorkflowEngine") as mock_engine_cls:
                engine_instance = MagicMock()
                engine_instance.run = mock_engine_run
                mock_engine_cls.return_value = engine_instance

                with patch.object(mod, "StepExecutor"):
                    with patch.object(mod, "ArxivConnector"):
                        with patch.object(mod, "SemanticScholarConnector"):
                            result = mod.execute_research_workflow(str(run_id))

        assert mock_run.status == "paused"
        assert result["status"] == "paused"

    def test_sets_failed_on_exception(self, research_task_module):
        """Task should set status to FAILED when an exception is raised."""
        mod = research_task_module
        run_id = uuid.uuid4()
        blueprint_id = uuid.uuid4()
        mock_run = _make_run(run_id, blueprint_id)
        mock_blueprint = _make_blueprint(blueprint_id)

        db = MagicMock()
        _setup_db_queries(db, mock_run, mock_blueprint, mod)

        with patch.object(mod, "SessionLocal", return_value=db):
            with patch.object(mod, "WorkflowEngine") as mock_engine_cls:
                mock_engine_cls.side_effect = RuntimeError("Engine init failed")

                with patch.object(mod, "StepExecutor"):
                    with patch.object(mod, "ArxivConnector"):
                        with patch.object(mod, "SemanticScholarConnector"):
                            with pytest.raises(RuntimeError, match="Engine init failed"):
                                mod.execute_research_workflow(str(run_id))

        assert mock_run.status == "failed"
        db.close.assert_called_once()

    def test_accumulates_total_tokens(self, research_task_module):
        """Task should accumulate token counts from step_complete events."""
        mod = research_task_module
        run_id = uuid.uuid4()
        blueprint_id = uuid.uuid4()
        mock_run = _make_run(run_id, blueprint_id)
        mock_blueprint = _make_blueprint(blueprint_id)

        db = MagicMock()
        _setup_db_queries(db, mock_run, mock_blueprint, mod)

        async def mock_engine_run(blueprint, run_id, start_from_step=0):
            yield {"event": "run_start", "run_id": str(run_id), "total_steps": 2}
            yield _make_step_complete_event(run_id, 0, "search_step", token_count=100)
            yield _make_step_complete_event(run_id, 1, "synthesize_step", token_count=250)
            yield {"event": "run_complete", "run_id": str(run_id), "context": {}}

        with patch.object(mod, "SessionLocal", return_value=db):
            with patch.object(mod, "WorkflowEngine") as mock_engine_cls:
                engine_instance = MagicMock()
                engine_instance.run = mock_engine_run
                mock_engine_cls.return_value = engine_instance

                with patch.object(mod, "StepExecutor"):
                    with patch.object(mod, "ArxivConnector"):
                        with patch.object(mod, "SemanticScholarConnector"):
                            with patch.object(mod, "ResearchStep") as mock_step_cls:
                                mock_step_cls.return_value = MagicMock()
                                mod.execute_research_workflow(str(run_id))

        assert mock_run.total_tokens == 350
