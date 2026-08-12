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


@pytest.mark.unit
@pytest.mark.parametrize(
    "content",
    [
        "Search arXiv for papers from the last five years",
        "search arxiv for transformer papers since 2015",
        "find arxiv papers on RAG over the past decade",
        "search arxiv for the earliest work on neural nets",
        "look up arxiv papers 2015-2020",
    ],
)
def test_explicit_time_window_skips_fast_path(content: str) -> None:
    """Turns that state their own window must fall through to the LLM.

    The fast path hard-codes search_arxiv's 365-day default, so a declared
    multi-year window would otherwise silently return only the last year.
    """
    from src.services.agent.subgraphs.research_agent import _direct_arxiv_search_query

    assert _direct_arxiv_search_query(content) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "content",
    [
        "find arxiv papers on RAG",
        "search arxiv for recent RAG papers",
        "show me the latest arxiv papers on diffusion",
    ],
)
def test_recency_words_still_take_fast_path(content: str) -> None:
    """ "recent"/"latest" keep the deterministic path — 365 days is right there."""
    from src.services.agent.subgraphs.research_agent import _direct_arxiv_search_query

    assert _direct_arxiv_search_query(content) is not None
