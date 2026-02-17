"""Tests for the workflow engine, step executor, and verification service."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.services.research_engine.connectors.base import SourceConnector, SourceDocument
from src.services.research_engine.providers.base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderConfig,
)
from src.services.research_engine.verification import QualityMark, run_source_grounding_check
from src.services.research_engine.step_executor import StepExecutor, StepResult
from src.services.research_engine.engine import WorkflowEngine


# ---------------------------------------------------------------------------
# TestStepResult
# ---------------------------------------------------------------------------

class TestStepResult:
    """Tests for StepResult dataclass."""

    def test_creation(self):
        result = StepResult(output={"summary": "hello"})
        assert result.output == {"summary": "hello"}
        assert result.sources_used == []
        assert result.quality_marks == []
        assert result.token_count == 0
        assert result.inputs_hash is None
        assert result.outputs_hash is None
        assert result.full_prompt is None

    def test_quality_marks(self):
        qm = QualityMark(check_type="source_grounding", passed=True, details="ok")
        result = StepResult(output={"x": 1}, quality_marks=[qm])
        assert len(result.quality_marks) == 1
        assert result.quality_marks[0].passed is True
        assert result.quality_marks[0].check_type == "source_grounding"


# ---------------------------------------------------------------------------
# TestVerificationService
# ---------------------------------------------------------------------------

class TestVerificationService:
    """Tests for run_source_grounding_check."""

    def test_source_grounding_pass_numbers(self):
        claim = "The accuracy was 95.5% in the experiment"
        source = "Results showed an accuracy of 95.5% across all trials"
        mark = run_source_grounding_check(claim, source)
        assert mark.check_type == "source_grounding"
        assert mark.passed is True

    def test_source_grounding_fail_numbers(self):
        claim = "The accuracy was 99.9% in the experiment"
        source = "Results showed an accuracy of 72.3% across all trials"
        mark = run_source_grounding_check(claim, source)
        assert mark.check_type == "source_grounding"
        assert mark.passed is False

    def test_source_grounding_no_numbers_pass(self):
        claim = "The model performed well on the benchmark dataset"
        source = "The model performed exceptionally well on the benchmark dataset used in evaluation"
        mark = run_source_grounding_check(claim, source)
        assert mark.passed is True

    def test_source_grounding_no_numbers_fail(self):
        claim = "quantum computing revolutionizes cryptography entirely"
        source = "The weather today is sunny and warm in California"
        mark = run_source_grounding_check(claim, source)
        assert mark.passed is False


# ---------------------------------------------------------------------------
# TestStepExecutor
# ---------------------------------------------------------------------------

class TestStepExecutor:
    """Tests for StepExecutor."""

    @pytest.mark.asyncio
    async def test_execute_search_step(self):
        mock_connector = AsyncMock(spec=SourceConnector)
        mock_connector.search.return_value = [
            SourceDocument(
                connector_type="arxiv",
                title="Test Paper",
                abstract="Abstract text",
                external_id="123",
            )
        ]

        executor = StepExecutor(
            connectors={"arxiv": mock_connector},
            providers={},
        )

        step_def = {
            "type": "search",
            "params": {"sources": ["arxiv"], "query_template": "{query}"},
        }
        context = {"query": "machine learning"}
        result = await executor.execute(step_def, context)

        assert len(result.sources_used) == 1
        assert result.sources_used[0].title == "Test Paper"
        assert "sources" in result.output
        mock_connector.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_synthesize_step(self):
        mock_provider = AsyncMock(spec=LLMProvider)
        mock_provider.complete.return_value = LLMResponse(
            content="Synthesized output text",
            model_id="test-model",
            input_tokens=100,
            output_tokens=50,
        )

        executor = StepExecutor(
            connectors={},
            providers={"test-model": mock_provider},
        )

        step_def = {
            "type": "synthesize",
            "params": {
                "model_id": "test-model",
                "system_prompt_template": "Synthesize: {query}",
                "temperature": 0.3,
                "seed": 42,
            },
        }
        context = {"query": "summarize findings"}
        result = await executor.execute(step_def, context)

        assert "content" in result.output
        assert result.output["content"] == "Synthesized output text"
        assert result.token_count == 150
        assert result.inputs_hash is not None
        assert result.outputs_hash is not None
        mock_provider.complete.assert_awaited_once()


# ---------------------------------------------------------------------------
# TestWorkflowEngine
# ---------------------------------------------------------------------------

class TestWorkflowEngine:
    """Tests for WorkflowEngine."""

    @pytest.mark.asyncio
    async def test_run_blueprint(self):
        mock_executor = AsyncMock(spec=StepExecutor)
        mock_executor.execute.return_value = StepResult(
            output={"result": "done"},
            quality_marks=[QualityMark(check_type="source_grounding", passed=True)],
        )

        engine = WorkflowEngine(step_executor=mock_executor)

        blueprint = {
            "steps": [
                {"id": "step_1", "type": "search", "params": {}},
                {"id": "step_2", "type": "synthesize", "params": {}},
            ]
        }
        run_id = uuid4()

        events = []
        async for event in engine.run(blueprint, run_id):
            events.append(event)

        event_types = [e["event"] for e in events]
        assert "run_start" in event_types
        assert "step_start" in event_types
        assert "step_complete" in event_types
        assert "run_complete" in event_types

    @pytest.mark.asyncio
    async def test_run_pauses_on_quality_failure(self):
        mock_executor = AsyncMock(spec=StepExecutor)
        mock_executor.execute.return_value = StepResult(
            output={"result": "bad"},
            quality_marks=[
                QualityMark(check_type="source_grounding", passed=False, details="mismatch")
            ],
        )

        engine = WorkflowEngine(step_executor=mock_executor, pause_on_quality_failure=True)

        blueprint = {
            "steps": [
                {"id": "step_1", "type": "search", "params": {}},
                {"id": "step_2", "type": "synthesize", "params": {}},
            ]
        }
        run_id = uuid4()

        events = []
        async for event in engine.run(blueprint, run_id):
            events.append(event)

        event_types = [e["event"] for e in events]
        assert "run_paused" in event_types
        # Should NOT reach run_complete since it paused after step 1
        assert "run_complete" not in event_types
        # Only the first step should have been executed
        assert mock_executor.execute.await_count == 1
