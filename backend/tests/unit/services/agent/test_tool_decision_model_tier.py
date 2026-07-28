"""Tool-decision turns must run on the main deployment, not the cheap tier.

The subgraphs originally built their tool-decision LLM with
``build_lightweight_llm`` — a workaround from when the main deployment was
``model-router`` and hit the 30s timeout cap (trace 019e1da5). When the
deployment changed, the workaround left the *cheapest* model making the
*hardest* decision: which tool to call, with what arguments, over an 8-loop
path. Multi-step function calling is precisely where small tiers collapse.

Observed on dev: the research subgraph answered "shall I ingest it?" in prose
instead of calling ``ingest_arxiv_papers`` on ~96% of runs (1 of 23).

This is the whole invariant — it fails if anyone re-routes a tool-calling turn
back to the cheap tier. The synthesis branch (post-``ToolMessage``) is
deliberately *not* covered: prose after a tool result is where cheap belongs.
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

pytestmark = pytest.mark.unit


class _FakeLLM:
    """Minimal stand-in: records nothing, returns a tool-free AIMessage."""

    def bind_tools(self, *_args: Any, **_kwargs: Any) -> "_FakeLLM":
        return self

    async def ainvoke(self, *_args: Any, **_kwargs: Any) -> AIMessage:
        return AIMessage(content="ok")


def _install_spies(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Count which builder each node reaches for."""
    calls = {"lightweight": 0, "synthesis": 0, "main": 0}

    from src.services.agent import graph as graph_mod
    from src.services.agent import llm_factory

    def _lightweight(*_a: Any, **_k: Any) -> _FakeLLM:
        calls["lightweight"] += 1
        return _FakeLLM()

    def _synthesis(*_a: Any, **_k: Any) -> _FakeLLM:
        calls["synthesis"] += 1
        return _FakeLLM()

    def _main(*_a: Any, **_k: Any) -> _FakeLLM:
        calls["main"] += 1
        return _FakeLLM()

    monkeypatch.setattr(llm_factory, "build_lightweight_llm", _lightweight)
    monkeypatch.setattr(llm_factory, "build_synthesis_llm", _synthesis)
    monkeypatch.setattr(llm_factory, "_build_llm", _main)
    return calls


def _state(messages: list) -> dict:
    return {"messages": messages, "intent": "research", "tool_loop_count": 0}


@pytest.mark.parametrize(
    ("module_path", "node_name"),
    [
        ("src.services.agent.subgraphs.research_agent", "research_llm_node"),
        ("src.services.agent.subgraphs.writing_agent", "writing_llm_node"),
        ("src.services.agent.subgraphs.data_agent", "data_llm_node"),
    ],
)
async def test_tool_decision_turn_uses_the_main_model(
    monkeypatch: pytest.MonkeyPatch, module_path: str, node_name: str
) -> None:
    """Non-ToolMessage tail == a tool decision == the main deployment."""
    import importlib

    calls = _install_spies(monkeypatch)
    module = importlib.import_module(module_path)
    node = getattr(module, node_name)

    # A plain user turn: the model still has to decide what to call.
    await node(_state([HumanMessage(content="ingest arXiv 1706.03762")]), {})

    assert calls["main"] == 1, f"{node_name} should build the main LLM"
    assert calls["lightweight"] == 0, (
        f"{node_name} routed a tool-calling turn to the cheap tier — this is the "
        "inversion that made the agent answer in prose instead of calling tools"
    )


@pytest.mark.parametrize(
    ("module_path", "node_name"),
    [
        ("src.services.agent.subgraphs.research_agent", "research_llm_node"),
        ("src.services.agent.subgraphs.writing_agent", "writing_llm_node"),
        ("src.services.agent.subgraphs.data_agent", "data_llm_node"),
    ],
)
async def test_post_tool_synthesis_stays_on_the_cheap_tier(
    monkeypatch: pytest.MonkeyPatch, module_path: str, node_name: str
) -> None:
    """The other half of the split: prose after a tool result stays cheap."""
    import importlib

    from src.core.config import get_settings

    monkeypatch.setattr(get_settings(), "AGENT_LIGHTWEIGHT_SYNTHESIS", True)
    calls = _install_spies(monkeypatch)
    module = importlib.import_module(module_path)
    node = getattr(module, node_name)

    # The AIMessage must carry the matching tool_call: _sanitize_messages
    # drops an orphan ToolMessage, which would put a non-tool message at the
    # tail and silently send this turn down the tool-decision path instead.
    await node(
        _state(
            [
                HumanMessage(content="ingest arXiv 1706.03762"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {"id": "t1", "name": "list_projects", "args": {}},
                    ],
                ),
                ToolMessage(content="{}", tool_call_id="t1"),
            ]
        ),
        {},
    )

    assert calls["synthesis"] == 1, f"{node_name} should use the synthesis tier"
    assert calls["main"] == 0, f"{node_name} spent the main model on prose"


def test_main_graph_cheap_path_is_derived_from_bound_tools() -> None:
    """``llm_node`` picks the tier from whether tools are bound, not intent.

    The old condition was ``intent == "general"``, a proxy that sent general
    turns carrying the full tool set to the cheap tier and then asked it to
    choose among them.

    Bare greetings keep the fast path (trace 019e19f2: "hi" took 13s on
    gpt-5) because ``_tools_for_turn`` strips tools for them. Acks like
    "thanks" deliberately keep their tools — ``_is_greeting`` is narrower
    than ``is_conversational`` precisely so an ack that accepts a proposed
    action can still call it — so they now reach the main model. That is the
    intended trade, and the cost of it lands on a frequent turn type.
    """
    from src.services.agent._nodes_llm import _tools_for_turn

    assert _tools_for_turn("general", last_user_msg="hi", retrieved=[]) == []
    assert _tools_for_turn("general", last_user_msg="thanks", retrieved=[])
    assert _tools_for_turn("research", last_user_msg="find papers", retrieved=[])
