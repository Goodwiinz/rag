"""LangSmith regression evaluation for the LangGraph agent.

Runs the compiled agent against a LangSmith dataset and scores:

- ``intent_match`` — final classified intent equals expected
- ``tool_subset_match`` — every expected tool was invoked, in order

Activate with:

    LANGCHAIN_API_KEY=... pytest -m langsmith backend/tests/eval/

The suite is auto-skipped when ``LANGCHAIN_API_KEY`` is unset (see
``conftest.py``).
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import add_messages

from src.services.agent.graph import compile_agent_graph

from tests.eval.golden_examples import ALL_CASES, GoldenCase

pytestmark = [pytest.mark.langsmith]


# ---------------------------------------------------------------------------
# Target — runs the compiled graph against a single dataset example
# ---------------------------------------------------------------------------


def _build_initial_state(inputs: dict[str, Any]) -> dict[str, Any]:
    """Convert a LangSmith example's inputs into agent initial state.

    Raises ``ValueError`` if the row carries neither ``messages`` nor a
    non-empty ``question`` — a loud contract-drift guard. The remote dataset
    previously accumulated malformed rows (pytest-langsmith captured test
    parametrize args: a fixture-arg-leak row and ``{"case": {...}}``-nested
    rows), which silently produced empty messages and scored every example 0.
    Fail loudly so drift surfaces as an error, not 48 silent zeros.
    """
    # Unwrap a nested ``{"case": {...}}`` row (pytest-langsmith parametrize
    # capture) so a polluted dataset is still interpretable.
    if (
        isinstance(inputs.get("case"), dict)
        and "question" not in inputs
        and "messages" not in inputs
    ):
        inputs = inputs["case"]

    if "messages" in inputs and inputs["messages"]:
        messages = inputs["messages"]
    else:
        question = inputs.get("question") or ""
        if not question:
            raise ValueError(
                "eval example has neither 'messages' nor a non-empty 'question' "
                f"(keys={sorted(inputs)}); dataset/harness contract drift — "
                "regenerate the dataset with `python -m tests.eval.upload_golden --clean`"
            )
        messages = [HumanMessage(content=question)]

    return {
        "messages": messages,
        "page_context": inputs.get("page_context", {}) or {},
        "retrieved_contexts": [],
        "tool_executions": [],
        "thread_id": inputs.get("thread_id", ""),
        "tool_loop_count": 0,
        "error_count": 0,
        "last_error": "",
        "pending_confirmation": {},
        "user_confirmed": False,
        "intent": inputs.get("intent", ""),
        "user_memories": [],
        "plan": [],
        "reflection_count": 0,
        "compaction_count": 0,
        "intent_confidence": 0.0,
        "last_error_info": {},
        "user_id": inputs.get("user_id", ""),
        "current_project_id": "",
        "model": "",
        "_reflection_result": None,
    }


def _extract_tool_calls(messages: list[Any]) -> list[str]:
    """Extract tool-call names in invocation order from message history."""
    names: list[str] = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            for call in getattr(msg, "tool_calls", []) or []:
                name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                if name:
                    names.append(name)
    return names


async def _run_agent(inputs: dict[str, Any]) -> dict[str, Any]:
    """Run the compiled graph and collect intent + intended tool calls.

    Destructive tools (``ingest_arxiv_papers``, ``add_document_to_project``,
    ``create_project``) trigger ``interrupt()`` for HITL confirmation. The
    blocked tool calls don't reach the top-level message history, so we
    also harvest tool names from interrupt payloads observed via streaming.
    """
    graph = compile_agent_graph()
    initial_state = _build_initial_state(inputs)

    final_state: dict[str, Any] = {}
    interrupted_tool_calls: list[str] = []

    async for event in graph.astream(initial_state, stream_mode="updates"):
        for node, update in event.items():
            if node == "__interrupt__" and isinstance(update, tuple):
                for item in update:
                    payload = getattr(item, "value", None) or {}
                    for tool in payload.get("tools") or []:
                        name = tool.get("name") if isinstance(tool, dict) else None
                        if name:
                            interrupted_tool_calls.append(name)
                continue
            if isinstance(update, dict):
                # The messages channel uses the ``add_messages`` reducer in
                # AgentState. Under ``stream_mode="updates"`` each node emits
                # only its OWN message delta, so a plain ``dict.update`` REPLACES
                # the accumulated history and drops every general-path tool call
                # (AIMessage with tool_calls clobbered by the next node's delta).
                # Merge messages through the real reducer (dedups by id, so
                # re-merging a subgraph's accumulated list is idempotent) and
                # only ``update`` the scalar keys.
                if "messages" in update:
                    final_state["messages"] = add_messages(
                        final_state.get("messages", []), update["messages"]
                    )
                final_state.update(
                    {k: v for k, v in update.items() if k != "messages"}
                )

    tool_calls = _extract_tool_calls(final_state.get("messages", []))
    for name in interrupted_tool_calls:
        if name not in tool_calls:
            tool_calls.append(name)

    return {
        "intent": final_state.get("intent", ""),
        "tool_calls": tool_calls,
    }


def _target(inputs: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_run_agent(inputs))


# ---------------------------------------------------------------------------
# Evaluators — pure functions over (run_outputs, example_outputs)
# ---------------------------------------------------------------------------


def intent_match(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    ref = reference_outputs or {}
    # Null-reference guard: a row with no reference intent (e.g. outputs=null
    # in a polluted dataset) must FAIL, not vacuously pass on ""=="".
    if "intent" not in ref:
        return {
            "key": "intent_match",
            "score": 0,
            "comment": "missing reference intent (null/polluted dataset row)",
        }
    actual = (outputs or {}).get("intent", "")
    # Output-side guard: "" is never a valid classified intent. A run that
    # produced no intent must FAIL, not vacuously pass when the reference is
    # also "" (which a polluted dataset row could be).
    if not actual:
        return {
            "key": "intent_match",
            "score": 0,
            "comment": "run produced no intent",
        }
    return {"key": "intent_match", "score": int(ref["intent"] == actual)}


def tool_subset_match(
    outputs: dict[str, Any], reference_outputs: dict[str, Any]
) -> dict[str, Any]:
    """Score 1 iff every expected tool call appears in order in actual calls.

    A *legitimately empty* ``expected_tools=()`` (key present) passes — that is
    a valid "no tools expected" case. A *missing* key (null/polluted reference)
    FAILS, instead of the old vacuous pass that made the suite green-but-blind.
    """
    ref = reference_outputs or {}
    if "expected_tools" not in ref:
        return {
            "key": "tool_subset_match",
            "score": 0,
            "comment": "missing reference expected_tools (null/polluted dataset row)",
        }
    expected = list(ref.get("expected_tools", ()))
    actual = list((outputs or {}).get("tool_calls", ()))
    idx = 0
    for tool_name in actual:
        if idx < len(expected) and tool_name == expected[idx]:
            idx += 1
    score = int(idx == len(expected))
    return {"key": "tool_subset_match", "score": score}


# ---------------------------------------------------------------------------
# LangSmith dataset experiment — full regression sweep
# ---------------------------------------------------------------------------


def test_agent_regression_against_dataset(
    langsmith_dataset_name: str, experiment_prefix: str
) -> None:
    """Run the agent against the LangSmith golden dataset.

    Fails the suite if any evaluator scores < 1 across the dataset, which
    catches intent or tool-routing regressions before they ship.
    """
    from langsmith import evaluate  # local import — heavy dependency

    results = evaluate(
        _target,
        data=langsmith_dataset_name,
        evaluators=[intent_match, tool_subset_match],
        experiment_prefix=experiment_prefix,
        max_concurrency=2,
    )

    failures: list[str] = []
    for result in results:
        # ``ExperimentResults`` items expose ``evaluation_results`` as either
        # a dict (older SDK) or an attribute (newer SDK). Be defensive.
        eval_block = (
            result.get("evaluation_results")
            if isinstance(result, dict)
            else getattr(result, "evaluation_results", None)
        )
        if eval_block is None:
            continue
        eval_list = (
            eval_block.get("results")
            if isinstance(eval_block, dict)
            else getattr(eval_block, "results", [])
        )
        example = (
            result.get("example")
            if isinstance(result, dict)
            else getattr(result, "example", None)
        )
        example_id = (
            (example.get("id") if isinstance(example, dict) else getattr(example, "id", "?"))
            if example is not None
            else "?"
        )
        for eval_result in eval_list or []:
            score = getattr(eval_result, "score", None) or 0
            if score < 1:
                key = getattr(eval_result, "key", "?")
                failures.append(f"{example_id}: {key}={score}")

    assert not failures, "Agent regression failures:\n  " + "\n  ".join(failures)


# ---------------------------------------------------------------------------
# Local golden cases — fast feedback without LangSmith dataset round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.name)
async def test_local_golden_case(case: GoldenCase) -> None:
    """Smoke-test golden cases locally; complements the dataset sweep."""
    inputs = {
        "question": case.question,
        "page_context": case.page_context,
    }
    outputs = await _run_agent(inputs)

    intent_result = intent_match(
        outputs, {"intent": case.expected_intent}
    )
    tool_result = tool_subset_match(
        outputs, {"expected_tools": case.expected_tools}
    )

    assert intent_result["score"] == 1, (
        f"intent mismatch: expected={case.expected_intent} "
        f"actual={outputs['intent']}"
    )
    assert tool_result["score"] == 1, (
        f"tool sequence mismatch: expected={case.expected_tools} "
        f"actual={outputs['tool_calls']}"
    )
