"""Unit tests for StepExecutor deterministic behavior."""

import pytest

from src.services.research_engine.step_executor import StepExecutor


class TestStepExecutor:
    @pytest.mark.asyncio
    async def test_export_step_does_not_require_llm_provider(self):
        executor = StepExecutor(connectors={}, providers={})

        result = await executor.execute(
            {"type": "export", "parameters": {"format": "json", "fields": ["query"]}},
            {"query": "rag", "ignored": "value"},
        )

        assert result.output["format"] == "json"
        assert result.output["exported"] == {"query": "rag"}

    @pytest.mark.asyncio
    async def test_verify_step_emits_quality_mark(self):
        executor = StepExecutor(connectors={}, providers={})

        result = await executor.execute(
            {"type": "verify", "parameters": {}},
            {
                "claim": "Accuracy improved by 20%",
                "source_text": "Results show accuracy improved by 20% in evaluation.",
            },
        )

        assert result.output["verified"] is True
        assert len(result.quality_marks) == 1
        assert result.quality_marks[0].check_type == "source_grounding"
        assert result.quality_marks[0].passed is True
