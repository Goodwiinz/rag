"""Regression tests for registry-owned agent execution policy."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage


@pytest.mark.unit
def test_main_llm_binding_queries_registry_for_intent(monkeypatch):
    from src.services.agent import _nodes_llm

    expected = [Mock(name="registry_tool")]
    registry = Mock()
    registry.descriptors_for_intent.return_value = [Mock(tool=expected[0])]
    monkeypatch.setattr(_nodes_llm, "TOOL_REGISTRY", registry)

    assert _nodes_llm._get_tools_for_intent("research") == expected
    registry.descriptors_for_intent.assert_called_once_with("research")


@pytest.mark.unit
async def test_disabled_registry_tool_is_rejected_without_dispatch(monkeypatch):
    from src.services.agent import tools, tools_impl
    from src.services.agent.tool_registry import ToolRegistry

    disabled = tuple(
        (
            replace(descriptor, enabled=False)
            if descriptor.name == "search_arxiv"
            else descriptor
        )
        for descriptor in tools.TOOL_REGISTRY.descriptors
    )
    monkeypatch.setattr(tools, "TOOL_REGISTRY", ToolRegistry(disabled))
    handler = AsyncMock(return_value={"unexpected": True})
    monkeypatch.setattr(tools_impl, "_tool_search_arxiv", handler)

    result = await tools_impl.execute_tool("search_arxiv", {"query": "test"})

    assert result == {"error": "Unknown tool: search_arxiv"}
    handler.assert_not_awaited()


@pytest.mark.unit
async def test_filtered_node_rejects_registered_name_when_disabled(monkeypatch):
    from src.services.agent import _nodes_tools, tools
    from src.services.agent.tool_registry import ToolRegistry

    disabled = tuple(
        (
            replace(descriptor, enabled=False)
            if descriptor.name == "search_arxiv"
            else descriptor
        )
        for descriptor in tools.TOOL_REGISTRY.descriptors
    )
    monkeypatch.setattr(_nodes_tools, "TOOL_REGISTRY", ToolRegistry(disabled))
    execute = AsyncMock()
    monkeypatch.setattr(_nodes_tools, "_execute_single_tool", execute)

    node = _nodes_tools.make_filtered_tool_node({"search_arxiv"})
    result = await node(
        {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{"id": "call-1", "name": "search_arxiv", "args": {}}],
                )
            ],
            "tool_executions": [],
            "error_count": 0,
            "last_error": "",
        },
        {},
    )

    execute.assert_not_awaited()
    assert "not available" in result["messages"][0].content
