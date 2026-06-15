"""Unit tests for the zero-LLM greeting template fast-path in llm_node.

A bare greeting ("hi", "hello") gets a templated on-brand reply with NO LLM
round-trip. Critically, acknowledgements ("yes", "no", "thanks", "ok") are
NOT greetings — they may answer a prior question (e.g. a HITL confirmation)
and must still flow to the real model.
"""

import pytest
from langchain_core.messages import HumanMessage


@pytest.mark.unit
class TestIsGreeting:
    def test_true_for_greetings(self):
        from src.services.agent._nodes_llm import _is_greeting

        for q in ("hi", "Hello", "hey!", "hi there", "good morning", "  HEY  "):
            assert _is_greeting(q) is True, q

    def test_false_for_acks_and_queries(self):
        from src.services.agent._nodes_llm import _is_greeting

        for q in (
            "yes",
            "no",
            "thanks",
            "ok",
            "sure",
            "find papers",
            "hi, can you search arxiv",
            "",
        ):
            assert _is_greeting(q) is False, q


@pytest.mark.unit
class TestGreetingReply:
    def test_returns_text_for_greeting(self):
        from src.services.agent._nodes_llm import _greeting_reply

        r = _greeting_reply("hi", {}, [HumanMessage(content="hi")])
        assert isinstance(r, str) and r.strip()

    def test_none_for_non_greeting(self):
        from src.services.agent._nodes_llm import _greeting_reply

        assert _greeting_reply("find papers", {}, [HumanMessage(content="find papers")]) is None
        assert _greeting_reply("yes", {}, [HumanMessage(content="yes")]) is None

    def test_project_aware(self):
        from src.services.agent._nodes_llm import _greeting_reply

        r = _greeting_reply(
            "hi",
            {"type": "project", "project_name": "Transformers 2024"},
            [HumanMessage(content="hi")],
        )
        assert "Transformers 2024" in r


@pytest.mark.unit
@pytest.mark.asyncio
class TestLlmNodeGreetingShortCircuit:
    async def test_greeting_returns_template_without_calling_llm(self, monkeypatch):
        import src.services.agent.graph as graphmod
        import src.services.agent.llm_factory as factory
        from src.services.agent._nodes_llm import llm_node

        def _boom(*a, **k):
            raise AssertionError("LLM must not be built for a greeting")

        monkeypatch.setattr(graphmod, "_build_llm", _boom, raising=False)
        monkeypatch.setattr(factory, "build_synthesis_llm", _boom, raising=False)

        state = {
            "messages": [HumanMessage(content="hi")],
            "intent": "general",
            "retrieved_contexts": [],
            "page_context": {},
        }
        result = await llm_node(state, {})
        content = result["messages"][0].content
        assert isinstance(content, str) and content.strip()
        assert result["messages"][0].tool_calls == []

    async def test_real_query_still_reaches_llm(self, monkeypatch):
        import src.services.agent.graph as graphmod
        from src.services.agent._nodes_llm import llm_node

        called = {"built": False}

        def _spy(*a, **k):
            called["built"] = True
            raise RuntimeError("stop after build")

        monkeypatch.setattr(graphmod, "_build_llm", _spy, raising=False)
        import src.services.agent.llm_factory as factory

        monkeypatch.setattr(factory, "build_synthesis_llm", _spy, raising=False)

        state = {
            "messages": [HumanMessage(content="find papers about transformers")],
            "intent": "general",
            "retrieved_contexts": [],
            "page_context": {},
        }
        with pytest.raises(RuntimeError):
            await llm_node(state, {})
        assert called["built"] is True
