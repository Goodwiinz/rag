"""Assert that the new system-prompt rules from PR-D-2 ship in the
assembled llm_node prompt across the intents that hit it.

Pattern mirrors ``_assert_shared_rules_present`` in
``test_agent_graph_partial.py`` — we capture the system prompt by
patching ``_build_llm`` with a stub that records what messages were
sent. The actual LLM is never invoked.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from langchain_core.messages import AIMessage, HumanMessage

pytestmark = pytest.mark.asyncio


# A real request, NOT a greeting. The general-intent greeting fast-path in
# ``llm_node`` (``_greeting_reply``) returns a templated reply with ZERO LLM
# round-trip for bare greetings like "hi"/"hello", so those never assemble or
# send a system prompt. To capture the prompt we must send a message that
# actually reaches the model. See _nodes_llm.py:_is_greeting.
_NON_GREETING_MSG = "What documents do I have in my library?"


def _make_initial_state(
    user_msg: str = _NON_GREETING_MSG, *, intent: str = "general"
) -> dict:
    return {
        "messages": [HumanMessage(content=user_msg)],
        "page_context": {"type": "unknown"},
        "retrieved_contexts": [],
        "tool_executions": [],
        "thread_id": "",
        "tool_loop_count": 0,
        "error_count": 0,
        "last_error": "",
        "pending_confirmation": {},
        "user_confirmed": False,
        "intent": intent,
        "user_memories": [],
        "plan": [],
        "reflection_count": 0,
        "compaction_count": 0,
        "intent_confidence": 0.0,
        "last_error_info": {},
        "user_id": str(uuid4()),
        "model": "",
    }


def _make_config() -> dict:
    user = Mock(id=uuid4(), organization_id=uuid4())
    return {
        "configurable": {
            "thread_id": str(uuid4()),
            "db": AsyncMock(),
            "current_user": user,
            "page_context": {"type": "unknown"},
        }
    }


async def _capture_system_prompt(intent: str) -> str:
    """Run llm_node with a stub LLM and return its system prompt content."""
    from src.services.agent.graph import llm_node

    captured: dict = {"messages": None}

    async def fake_ainvoke(messages, config=None):
        captured["messages"] = messages
        return AIMessage(content="ok")

    fake_with_tools = MagicMock()
    fake_with_tools.ainvoke = fake_ainvoke
    fake_llm = MagicMock()
    fake_llm.bind_tools.return_value = fake_with_tools

    # For intent="general", llm_node routes to llm_factory.build_synthesis_llm
    # (see _nodes_llm.py:191 — the lightweight-synthesis optimisation). For
    # other intents it uses graph._build_llm. Patch both so the fake LLM is
    # returned regardless of intent.
    with (
        patch("src.services.agent.graph._build_llm", return_value=fake_llm),
        patch(
            "src.services.agent.llm_factory.build_synthesis_llm",
            return_value=fake_llm,
        ),
    ):
        await llm_node(_make_initial_state(intent=intent), _make_config())

    assert captured["messages"], "llm_node did not call the LLM"
    return captured["messages"][0].content


HONEST_REPORTING_RULE = "Honest result reporting"
HONEST_REPORTING_BODY = "documents_ingested=0"
DISAMBIGUATION_RULE = "Project-name disambiguation"
DISAMBIGUATION_BODY = "ask which one they mean"
CLEAR_RULE = "/clear is a CLI primitive"
CLEAR_BODY = "type /clear at the prompt"


class TestPromptRulesPresent:
    @pytest.mark.parametrize("intent", ["general", "research"])
    async def test_honest_result_reporting_rule_present(self, intent: str) -> None:
        prompt = await _capture_system_prompt(intent)
        assert HONEST_REPORTING_RULE in prompt
        assert HONEST_REPORTING_BODY in prompt

    @pytest.mark.parametrize("intent", ["general", "research"])
    async def test_project_disambiguation_rule_present(self, intent: str) -> None:
        prompt = await _capture_system_prompt(intent)
        assert DISAMBIGUATION_RULE in prompt
        assert DISAMBIGUATION_BODY in prompt

    @pytest.mark.parametrize("intent", ["general", "research"])
    async def test_clear_rule_present(self, intent: str) -> None:
        prompt = await _capture_system_prompt(intent)
        assert CLEAR_RULE in prompt
        assert CLEAR_BODY in prompt

    async def test_existing_workflow_block_still_present(self) -> None:
        """Sanity: we appended, didn't replace. The workflow block from
        before this PR still anchors the prompt. Strings were renamed
        (not removed) — see _prompts.py:205/217."""
        prompt = await _capture_system_prompt("general")
        assert "Workflow for adding papers to a project" in prompt
        assert "Never invent IDs like 'proj_12345'" in prompt
