"""Unit tests for per-turn tool binding in llm_node.

A conversational general turn ("hi") calls no tool, so binding the 10
``GENERAL_TOOLS_NAMES`` schemas just inflates the prompt (~thousands of input
tokens, slower TTFT). ``_tools_for_turn`` binds nothing for those turns while
leaving every retrieval/specialised turn untouched.
"""

import pytest


@pytest.mark.unit
class TestToolsForTurn:
    def test_conversational_general_binds_no_tools(self):
        from src.services.agent._nodes_llm import _tools_for_turn

        for q in ("hi", "thanks", "ok cool", "hello"):
            assert _tools_for_turn("general", last_user_msg=q, retrieved=[]) == [], q

    def test_real_general_query_keeps_general_tools(self):
        from src.services.agent._nodes_llm import (
            GENERAL_TOOLS_NAMES,
            _tools_for_turn,
        )

        tools = _tools_for_turn(
            "general", last_user_msg="find papers about transformers", retrieved=[]
        )
        assert {t.name for t in tools} == set(GENERAL_TOOLS_NAMES)

    def test_general_with_retrieved_context_keeps_tools(self):
        # Context present → likely a grounded follow-up that may still tool;
        # do not strip even if the message text looks short/conversational.
        from src.services.agent._nodes_llm import _tools_for_turn

        tools = _tools_for_turn(
            "general", last_user_msg="thanks", retrieved=[{"title": "Doc", "content": "x"}]
        )
        assert len(tools) > 0

    def test_research_intent_unaffected(self):
        from src.services.agent._nodes_llm import (
            RESEARCH_TOOLS_NAMES,
            _tools_for_turn,
        )

        tools = _tools_for_turn("research", last_user_msg="hi", retrieved=[])
        assert {t.name for t in tools} == set(RESEARCH_TOOLS_NAMES)
