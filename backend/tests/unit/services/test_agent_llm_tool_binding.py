"""Unit tests for per-turn tool binding in llm_node.

A bare-greeting general turn ("hi") calls no tool, so binding the 10
``GENERAL_TOOLS_NAMES`` schemas just inflates the prompt (~thousands of input
tokens, slower TTFT). ``_tools_for_turn`` binds nothing for those turns while
leaving every other turn untouched.

Regression (LangSmith trace 019f33ca-fc58-7102-b3da-bb36370b1957): the skip
used to fire on ANY "conversational" message, including acks like "yes" —
but an ack routinely accepts an action the assistant just proposed
("Shall I run the arXiv search?" → "yes"). With tools=[] the model cannot
call the tool and fabricates a narrated tool call instead. Only bare
greetings — which cannot be answering a question — may skip binding.
"""

import pytest


@pytest.mark.unit
class TestToolsForTurn:
    def test_bare_greeting_general_binds_no_tools(self):
        from src.services.agent._nodes_llm import _tools_for_turn

        for q in ("hi", "hello", "hey there", "good morning"):
            assert _tools_for_turn("general", last_user_msg=q, retrieved=[]) == [], q

    def test_ack_binds_tools_regression_019f33ca(self):
        # "yes" may be accepting a proposed tool action — it must reach the
        # model WITH tools bound, else the model fabricates a tool call.
        from src.services.agent._nodes_llm import (
            GENERAL_TOOLS_NAMES,
            _tools_for_turn,
        )

        for q in ("yes", "no", "ok", "ok cool", "thanks", "go ahead", "proceed"):
            tools = _tools_for_turn("general", last_user_msg=q, retrieved=[])
            assert {t.name for t in tools} == set(GENERAL_TOOLS_NAMES), q

    def test_real_general_query_keeps_general_tools(self):
        from src.services.agent._nodes_llm import (
            GENERAL_TOOLS_NAMES,
            _tools_for_turn,
        )

        tools = _tools_for_turn(
            "general", last_user_msg="find papers about transformers", retrieved=[]
        )
        assert {t.name for t in tools} == set(GENERAL_TOOLS_NAMES)

    def test_greeting_with_request_keeps_tools(self):
        # A greeting carrying a real request must not match the skip.
        from src.services.agent._nodes_llm import _tools_for_turn

        tools = _tools_for_turn(
            "general", last_user_msg="hi, can you search arxiv", retrieved=[]
        )
        assert len(tools) > 0

    def test_general_with_retrieved_context_keeps_tools(self):
        # Context present → likely a grounded follow-up that may still tool;
        # do not strip even if the message text is a bare greeting.
        from src.services.agent._nodes_llm import _tools_for_turn

        tools = _tools_for_turn(
            "general", last_user_msg="hi", retrieved=[{"title": "Doc", "content": "x"}]
        )
        assert len(tools) > 0

    def test_research_intent_unaffected(self):
        from src.services.agent._nodes_llm import (
            RESEARCH_TOOLS_NAMES,
            _tools_for_turn,
        )

        tools = _tools_for_turn("research", last_user_msg="hi", retrieved=[])
        assert {t.name for t in tools} == set(RESEARCH_TOOLS_NAMES)
