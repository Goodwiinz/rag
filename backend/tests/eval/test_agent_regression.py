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

from src.services.agent.graph import compile_agent_graph

from tests.eval.golden_examples import ALL_CASES, GoldenCase

pytestmark = [pytest.mark.langsmith]


# ---------------------------------------------------------------------------
# Target — runs the compiled graph against a single dataset example
# ---------------------------------------------------------------------------


def _build_initial_state(inputs: dict[str, Any]) -> dict[str, Any]:
    """Convert a LangSmith example's inputs into agent initial state."""
    if "messages" in inputs and inputs["messages"]:
        messages = inputs["messages"]
    else:
        question = inputs.get("question") or ""
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
                final_state.update(update)

    tool_calls = _extract_tool_calls(final_state.get("messages", []))
    for name in interrupted_tool_calls:
        if name not in tool_calls:
            tool_calls.append(name)

    return {
        "intent": final_state.get("intent", ""),
        "tool_calls": tool_calls,
        "answer": _extract_final_answer(final_state.get("messages", [])),
        "retrieved_contexts": final_state.get("retrieved_contexts", []) or [],
    }


def _extract_final_answer(messages: list[Any]) -> str:
    """Return content of last AIMessage without tool_calls (the final reply)."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in content
                ]
                return "".join(parts)
    return ""


def _target(inputs: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(_run_agent(inputs))


# ---------------------------------------------------------------------------
# Evaluators — pure functions over (run_outputs, example_outputs)
# ---------------------------------------------------------------------------


def intent_match(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
    """Score 1 if intent matches expected OR any accept_intents fallback."""
    ref = reference_outputs or {}
    accepted = {ref.get("intent", "")} | set(ref.get("accept_intents", []) or [])
    actual = (outputs or {}).get("intent", "")
    return {"key": "intent_match", "score": int(actual in accepted)}


def tool_subset_match(
    outputs: dict[str, Any], reference_outputs: dict[str, Any]
) -> dict[str, Any]:
    """Score 1 iff expected tools satisfied per the case's match strategy.

    Strategies (read from ``reference_outputs.tool_match``):
      - ``subset_in_order`` (default): every expected tool appears in order
      - ``any``: at least one expected tool was invoked (recovery-path cases)
    """
    expected = list((reference_outputs or {}).get("expected_tools", ()))
    actual = list((outputs or {}).get("tool_calls", ()))
    strategy = (reference_outputs or {}).get("tool_match") or "subset_in_order"

    if not expected:
        # No tools expected → pass iff agent invoked none.
        return {"key": "tool_subset_match", "score": int(not actual)}

    if strategy == "any":
        score = int(any(t in actual for t in expected))
        return {"key": "tool_subset_match", "score": score, "comment": "strategy=any"}

    idx = 0
    for tool_name in actual:
        if idx < len(expected) and tool_name == expected[idx]:
            idx += 1
    score = int(idx == len(expected))
    return {"key": "tool_subset_match", "score": score, "comment": "strategy=subset_in_order"}


_GROUNDEDNESS_PROMPT = """You are a strict factuality judge.

Decide if every factual claim in ANSWER is directly supported by CONTEXTS.
- Score 1 if all factual claims are supported (verbatim or paraphrase).
- Score 0 if any claim is unsupported, contradicted, or fabricated.
- Ignore stylistic/opinion content. Judge only factual substance.

QUESTION:
{question}

CONTEXTS:
{contexts}

ANSWER:
{answer}

Respond with a single character: 1 or 0.
"""


def answer_groundedness(
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
) -> dict[str, Any]:
    """LLM-as-judge: answer's factual claims supported by retrieved_contexts.

    Returns score=None when there are no retrieved contexts or no answer —
    LangSmith treats None as "not applicable" and excludes from aggregates.
    Skipping conversational cases (greetings, capability questions) avoids
    penalising the agent for grounded-by-vacuity replies.
    """
    del reference_outputs  # LangSmith passes it; we only judge against contexts
    answer = (outputs or {}).get("answer") or ""
    contexts = (outputs or {}).get("retrieved_contexts") or []
    question = (inputs or {}).get("question") or ""

    if not answer.strip() or not contexts:
        return {"key": "groundedness", "score": None, "comment": "no answer or contexts"}

    context_text = "\n\n".join(
        f"[{i}] {c.get('content', '') if isinstance(c, dict) else str(c)}"[:1500]
        for i, c in enumerate(contexts[:6])
    )

    from src.services.agent.llm_factory import build_lightweight_llm

    judge = build_lightweight_llm(
        temperature=0,
        max_tokens=128,  # gpt-5 family reasons internally; max_tokens<~16 returns empty
        use_responses_api=False,  # judge uses single-shot Chat Completions; avoid Responses API ver requirement
    )
    prompt = _GROUNDEDNESS_PROMPT.format(
        question=question, contexts=context_text, answer=answer[:4000]
    )
    try:
        resp = judge.invoke(prompt)
    except Exception as exc:  # noqa: BLE001 — judge fail must not fail suite
        return {"key": "groundedness", "score": None, "comment": f"judge error: {exc}"}

    raw = (resp.content if isinstance(resp.content, str) else str(resp.content)).strip()
    score = 1 if raw.startswith("1") else 0
    return {"key": "groundedness", "score": score, "comment": f"judge=\"{raw[:32]}\""}


_CORRECTNESS_PROMPT = """You are a lenient intent-coverage judge.

The REFERENCE_ANSWER describes the *shape* of an acceptable reply — not the
exact wording. The CANDIDATE_ANSWER is acceptable if it addresses the user's
QUESTION in a way that matches the reference's intent and constraints.

Score 1 (acceptable) if ALL of:
- Candidate addresses the question directly (no refusal, no error message,
  no "I can't help with that" dead-end)
- Candidate's overall shape matches the reference (e.g. reference says
  "friendly greeting" → any friendly greeting qualifies)
- Candidate doesn't claim to have done something it didn't (e.g. doesn't
  fabricate retrieval results)

Score 0 (unacceptable) if ANY of:
- Candidate refuses, errors out, or claims inability to respond
- Candidate's content contradicts a hard constraint in the reference
- Candidate fabricates facts clearly outside scope (hallucination)

Wording, length, tone, structure may differ freely — judge intent, not text.

QUESTION:
{question}

REFERENCE_ANSWER (describes acceptable shape):
{reference}

CANDIDATE_ANSWER:
{candidate}

Respond with a single character: 1 or 0.
"""


def answer_correctness(
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    reference_outputs: dict[str, Any],
) -> dict[str, Any]:
    """LLM-as-judge: candidate answer semantically equivalent to reference.

    Skips (score=None) when no reference_answer present — retrieval-driven
    cases whose exact wording depends on indexed content shouldn't be
    graded against a static string.
    """
    reference = (reference_outputs or {}).get("expected_answer") or ""
    candidate = (outputs or {}).get("answer") or ""
    question = (inputs or {}).get("question") or ""

    if not reference.strip():
        return {"key": "correctness", "score": None, "comment": "no reference answer"}
    if not candidate.strip():
        return {"key": "correctness", "score": 0, "comment": "empty candidate"}

    from src.services.agent.llm_factory import build_lightweight_llm

    judge = build_lightweight_llm(
        temperature=0,
        max_tokens=128,  # gpt-5 family reasons internally; max_tokens<~16 returns empty
        use_responses_api=False,  # judge uses single-shot Chat Completions; avoid Responses API ver requirement
    )
    prompt = _CORRECTNESS_PROMPT.format(
        question=question, reference=reference[:2000], candidate=candidate[:4000]
    )
    try:
        resp = judge.invoke(prompt)
    except Exception as exc:  # noqa: BLE001
        return {"key": "correctness", "score": None, "comment": f"judge error: {exc}"}

    raw = (resp.content if isinstance(resp.content, str) else str(resp.content)).strip()
    score = 1 if raw.startswith("1") else 0
    return {"key": "correctness", "score": score, "comment": f"judge=\"{raw[:32]}\""}


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
        evaluators=[
            intent_match,
            tool_subset_match,
            answer_groundedness,
            answer_correctness,
        ],
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
            score = getattr(eval_result, "score", None)
            if score is None:
                continue  # evaluator opted out (e.g. groundedness on no-context cases)
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

    accepted_intents = (case.expected_intent, *case.accept_intents)
    actual_intent = outputs.get("intent", "")
    assert actual_intent in accepted_intents, (
        f"intent mismatch: expected one of {accepted_intents} "
        f"actual={actual_intent}"
    )

    actual_tools = outputs.get("tool_calls", [])
    if case.tool_match == "any":
        assert any(t in actual_tools for t in case.expected_tools), (
            f"no expected tool fired: expected any of {case.expected_tools} "
            f"actual={actual_tools}"
        )
    else:
        tool_result = tool_subset_match(
            outputs, {"expected_tools": case.expected_tools}
        )
        assert tool_result["score"] == 1, (
            f"tool sequence mismatch: expected={case.expected_tools} "
            f"actual={actual_tools}"
        )
