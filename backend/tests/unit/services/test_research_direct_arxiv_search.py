"""Regression tests for deterministic arXiv search routing."""

import pytest
from langchain_core.messages import HumanMessage


@pytest.mark.unit
@pytest.mark.asyncio
async def test_explicit_arxiv_search_emits_tool_call_without_llm(monkeypatch):
    """A direct arXiv search request should run search_arxiv, not prose-only."""
    import src.services.agent.llm_factory as factory
    from src.services.agent.subgraphs.research_agent import research_llm_node

    def _boom(*_args, **_kwargs):
        raise AssertionError("LLM must not be built before direct arXiv search")

    monkeypatch.setattr(factory, "build_lightweight_llm", _boom)
    monkeypatch.setattr(factory, "build_synthesis_llm", _boom)

    result = await research_llm_node(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "Search arXiv for recent retrieval-augmented "
                        "generation papers"
                    )
                )
            ],
            "plan": [],
            "tool_loop_count": 0,
        },
        {},
    )

    message = result["messages"][0]

    assert message.content == ""
    assert len(message.tool_calls) == 1
    tool_call = message.tool_calls[0]
    assert tool_call["name"] == "search_arxiv"
    assert tool_call["args"] == {
        "query": "recent retrieval-augmented generation papers",
        "max_results": 5,
    }
    assert tool_call["id"].startswith("direct_search_arxiv_")
    assert tool_call["type"] == "tool_call"
