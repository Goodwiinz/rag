"""Unit tests for the rag_node short-conversational query skip path."""

import pytest


@pytest.mark.unit
class TestIsRetrievalQuery:
    def test_empty_string(self):
        from src.services.agent.graph import _is_retrieval_query

        assert _is_retrieval_query("") is False
        assert _is_retrieval_query("   ") is False

    def test_short_conversational_returns_false(self):
        from src.services.agent.graph import _is_retrieval_query

        for q in ("hi", "thanks!", "yes", "ok cool", "sure"):
            assert _is_retrieval_query(q) is False, q

    def test_retrieval_verb_short_query_returns_true(self):
        from src.services.agent.graph import _is_retrieval_query

        for q in (
            "find papers",
            "search for GANs",
            "show docs",
            "summarize this",
            "compare them",
            "what is RAG?",
            "tell me about it",
        ):
            assert _is_retrieval_query(q) is True, q

    def test_long_query_without_verb_still_routes_to_retrieval(self):
        from src.services.agent.graph import _is_retrieval_query

        q = "the conference deadline next quarter is going to be very tight"
        assert len(q.split()) >= 8
        assert _is_retrieval_query(q) is True

    def test_tool_name_prefix_returns_true(self):
        from src.services.agent.graph import _is_retrieval_query

        for q in (
            "list_projects",
            "search_arxiv",
            "summarize_document abc",
            "ingest_arxiv_papers 1234.5678",
            "extract_entities",
        ):
            assert _is_retrieval_query(q) is True, q


@pytest.mark.unit
@pytest.mark.asyncio
class TestRagNodeFastPath:
    async def test_rag_node_skips_search_for_trivial_query(self):
        from unittest.mock import AsyncMock, patch

        from langchain_core.messages import HumanMessage

        from src.services.agent.graph import rag_node

        state = {
            "messages": [HumanMessage(content="hi")],
            "page_context": {},
            "retrieved_contexts": [],
            "thread_id": "t-1",
        }
        config = {"configurable": {}}

        with patch(
            "src.services.agent.graph.hybrid_search",
            new_callable=AsyncMock,
        ) as mock_search:
            result = await rag_node(state, config)

        assert mock_search.called is False
        assert result.get("retrieved_contexts", []) == []

    async def test_rag_node_runs_search_for_retrieval_query(self):
        from unittest.mock import AsyncMock, patch

        from langchain_core.messages import HumanMessage

        from src.services.agent.graph import rag_node

        state = {
            "messages": [HumanMessage(content="find papers about transformers")],
            "page_context": {},
            "retrieved_contexts": [],
            "thread_id": "t-2",
        }
        config = {"configurable": {}}

        with patch(
            "src.services.agent.graph.hybrid_search",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search:
            await rag_node(state, config)

        assert mock_search.called is True
