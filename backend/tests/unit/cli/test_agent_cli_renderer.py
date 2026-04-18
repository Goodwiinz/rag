from __future__ import annotations

from src.cli.agent_cli_renderer import (
    render_confirmation,
    render_error,
    render_event,
    render_plan,
    render_reflection,
    render_tool_end,
    render_tool_start,
    render_trace,
)
from src.cli.types import CLIEvent


def test_render_plan_formats_steps_compactly() -> None:
    event = CLIEvent(
        type="plan",
        data={
            "steps": [
                {"step": 1, "description": "Search arXiv"},
                {"step": 2, "description": "Read the top paper"},
            ],
            "reasoning": "Complex request",
        },
    )

    text = render_event(event, debug=False)

    assert "plan>" in text
    assert "1. Search arXiv" in text
    assert "2. Read the top paper" in text
    assert "Complex request" not in text


def test_render_plan_includes_reasoning_when_debug_enabled() -> None:
    text = render_plan(
        {
            "steps": [{"step": 1, "description": "Search arXiv"}],
            "reasoning": "Complex request",
        },
        debug=True,
    )

    assert "plan>" in text
    assert "Search arXiv" in text
    assert "reasoning:" in text
    assert "Complex request" in text


def test_render_tool_events_and_trace_and_confirmation_and_reflection() -> None:
    assert "tool>" in render_tool_start({"tool": "search_arxiv"})
    assert "search_arxiv" in render_tool_start({"tool": "search_arxiv"})

    tool_end_text = render_tool_end(
        {"tool": "search_arxiv", "result": '{"count": 1, "title": "Paper"}'}
    )
    assert "tool>" in tool_end_text
    assert "search_arxiv" in tool_end_text
    assert "Paper" in tool_end_text

    trace_text = render_trace(
        {
            "thread_id": "thread-1",
            "cli_session_id": "cli-1",
            "langsmith_run_id": "run-1",
            "langsmith_url": "https://smith.langchain.com/public/run-1",
        }
    )
    assert "trace>" in trace_text
    assert "thread-1" in trace_text
    assert "run-1" in trace_text
    assert "https://smith.langchain.com/public/run-1" in trace_text

    confirmation_text = render_confirmation(
        {
            "thread_id": "thread-1",
            "confirmation": {"message": "Proceed with delete_document?"},
        }
    )
    assert "confirmation>" in confirmation_text
    assert "Proceed with delete_document?" in confirmation_text
    assert "y/n" in confirmation_text

    reflection_text = render_reflection(
        {"passed": False, "issues": ["Needs citations"], "round": 2}
    )
    assert "reflection>" in reflection_text
    assert "round 2" in reflection_text
    assert "Needs citations" in reflection_text

    error_text = render_error({"error": "boom"})
    assert "error>" in error_text
    assert "boom" in error_text
