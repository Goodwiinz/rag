"""LangSmith-traced performance harness for the NOUS agent.

Drives the compiled LangGraph agent through a fixed set of representative
scenarios with LangSmith tracing ON, each turn carrying a stable
``run_name`` + tags (``scenario:<x>``, ``perf-harness``) + metadata so a
perf audit can:

- measure per-scenario latency over time (saved views by ``scenario:*``),
- diff latency across deploys (filter by the ``deploy`` / ``commit`` metadata),
- correlate with the production intent dashboards (``intent:*`` tags emitted
  by the graph itself via ``tag_trace_intent``).

This is the repeatable version of the manual SDK audit: same scenarios, same
tags, run on demand in dev/CI instead of by hand.

Running modes
-------------
1. **Unit lane (default):** every test SKIPS cleanly. There is no Azure LLM,
   no Postgres checkpointer, and no LangSmith key, so nothing to measure.
   Imports stay lazy so collection never touches libpq / langchain / azure.

2. **Dev / CI perf run:** set the gate and provide credentials::

       RUN_PERF_HARNESS=1 \
       LANGSMITH_API_KEY=ls-... \
       AZURE_OPENAI_CHAT_ENDPOINT=... AZURE_OPENAI_CHAT_API_KEY=... \
       AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-5-mini \
       pytest -m performance backend/tests/perf/

   With the gate on, soft latency-budget assertions are enforced so the
   harness catches regressions; without it they are skipped.

3. **Script mode (dev):** ``python -m tests.perf.test_agent_langsmith_tracing``
   drives every scenario sequentially, prints per-scenario wall-clock, and
   relies on ``configure_langsmith()`` for project routing. Useful for a quick
   local sweep without pytest.

Markers
-------
Every scenario test is tagged ``@pytest.mark.performance`` (registered in
``pytest.ini``) and ``@pytest.mark.integration`` so the unit lane (which has
no infra) never tries to run it, while dev/CI can select it explicitly with
``-m performance``.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

# ---------------------------------------------------------------------------
# Scenario catalogue
# ---------------------------------------------------------------------------
#
# Each scenario maps to one intent that showed a distinct latency profile in
# the manual audit: a bare greeting takes the conversational fast-path (no
# tools), general Q&A does a single RAG + LLM round-trip, research/writing/KG
# fan out into tool loops, and the HITL turn pauses on an interrupt (so its
# wall-clock measures time-to-interrupt, not a full tool execution).
#
# ``budget_s`` is a SOFT per-scenario latency ceiling. It only asserts when
# ``RUN_PERF_HARNESS=1`` so the harness can catch regressions but never fails
# the normal suite. The numbers are generous upper bounds, not SLOs — tighten
# them once a dev/CI baseline exists.


@dataclass(frozen=True)
class Scenario:
    """One representative agent turn driven by the harness."""

    key: str  # stable id, used in run_name + tags + skip reasons
    prompt: str  # the user message for this turn
    budget_s: float  # soft latency ceiling (asserted only under the gate)
    expect_interrupt: bool = False  # HITL turn: measure time-to-interrupt
    page_context: Dict[str, Any] = field(default_factory=dict)


SCENARIOS: List[Scenario] = [
    Scenario(
        key="greeting",
        prompt="hi",
        budget_s=3.0,
    ),
    Scenario(
        key="general_qa",
        prompt="What is retrieval-augmented generation, in two sentences?",
        budget_s=15.0,
    ),
    Scenario(
        key="research_arxiv",
        prompt="Search arXiv for recent papers on retrieval-augmented generation.",
        budget_s=45.0,
    ),
    Scenario(
        key="writing_draft",
        prompt="Draft a short note summarizing the key ideas behind RAG.",
        budget_s=45.0,
    ),
    Scenario(
        key="kg_query",
        prompt="What entities and relationships are in the knowledge graph for transformers?",
        budget_s=45.0,
    ),
    Scenario(
        # Destructive tool (ingest) -> interrupt() for HITL confirmation.
        # We measure time-to-interrupt: the graph pauses awaiting a
        # Command(resume=...) it never receives here.
        key="hitl_destructive",
        prompt="Ingest the arXiv paper 1706.03762 into my library.",
        budget_s=30.0,
        expect_interrupt=True,
    ),
]

SCENARIOS_BY_KEY: Dict[str, Scenario] = {s.key: s for s in SCENARIOS}


# ---------------------------------------------------------------------------
# Gating — keep import + collection infra-free; decide skips at call time
# ---------------------------------------------------------------------------


def _perf_gate_enabled() -> bool:
    """True when the operator explicitly opted into the perf harness."""
    return os.environ.get("RUN_PERF_HARNESS", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _has_langsmith() -> bool:
    return bool(
        os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    )


def _has_azure_chat() -> bool:
    """True when an Azure/OpenAI chat endpoint + key + deployment are set.

    Mirrors the requirement in ``graph._build_llm``: an endpoint, an API key,
    and a deployment name (CHAT-prefixed names win, non-CHAT are the fallback).
    """
    endpoint = os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT") or os.environ.get(
        "AZURE_OPENAI_ENDPOINT"
    )
    api_key = os.environ.get("AZURE_OPENAI_CHAT_API_KEY") or os.environ.get(
        "AZURE_OPENAI_API_KEY"
    )
    deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME") or os.environ.get(
        "AZURE_OPENAI_DEPLOYMENT_NAME"
    )
    return bool(endpoint and api_key and deployment)


def _skip_reason() -> Optional[str]:
    """Return a clear skip reason, or None when the harness can run.

    Order matters: report the gate first (the common unit-lane case) so the
    skip message reads "opt in" rather than "missing creds" when nobody asked
    for a perf run.
    """
    if not _perf_gate_enabled():
        return "perf harness disabled (set RUN_PERF_HARNESS=1 to enable)"
    if not _has_langsmith():
        return "LangSmith disabled (set LANGSMITH_API_KEY / LANGCHAIN_API_KEY)"
    if not _has_azure_chat():
        return (
            "Azure chat LLM not configured (set AZURE_OPENAI_CHAT_ENDPOINT + "
            "AZURE_OPENAI_CHAT_API_KEY + AZURE_OPENAI_CHAT_DEPLOYMENT_NAME)"
        )
    return None


# ---------------------------------------------------------------------------
# Driver — build initial state + config, run one traced turn
# ---------------------------------------------------------------------------


def _build_initial_state(scenario: Scenario, *, thread_id: str) -> Dict[str, Any]:
    """Construct the AgentState initial dict for one scenario turn.

    Mirrors the canonical shape built in ``jobs.run_agent_graph`` /
    ``tests.eval.test_agent_regression`` so the harness exercises the same
    state the production job path does. ``HumanMessage`` is imported lazily so
    importing this module never pulls langchain into the unit lane.
    """
    from langchain_core.messages import HumanMessage

    return {
        "messages": [HumanMessage(content=scenario.prompt)],
        "page_context": dict(scenario.page_context),
        "retrieved_contexts": [],
        "tool_executions": [],
        "thread_id": thread_id,
        "tool_loop_count": 0,
        "error_count": 0,
        "last_error": "",
        "pending_confirmation": {},
        "user_confirmed": False,
        "intent": "",
        "user_memories": [],
        "project_memories": [],
        "plan": [],
        "reflection_count": 0,
        "compaction_count": 0,
        "intent_confidence": 0.0,
        "last_error_info": {},
        "user_id": "",
        "current_project_id": "",
        "model": "",
        "_reflection_result": None,
        "_force_synthesis_fired": False,
    }


def _build_config(scenario: Scenario, *, thread_id: str) -> Dict[str, Any]:
    """Build the RunnableConfig: configurable + LangSmith run_name/tags/metadata.

    - ``configurable.thread_id`` keeps each scenario on its own checkpoint.
    - ``configurable.page_context`` mirrors the job path (classifier reads it).
    - ``db`` / ``current_user`` are intentionally absent: the memory/RAG/tool
      nodes guard those with ``.get()`` and degrade best-effort, so the harness
      can run against a MemorySaver checkpointer with no Postgres session.
    - ``run_name`` is stable per scenario so latency series line up over time.
    - ``tags`` carry ``scenario:<key>`` + ``perf-harness`` (plus a deploy tag)
      for saved views; the graph adds ``intent:<x>`` itself.
    - ``metadata`` records the diff dimensions: scenario, deploy env, git sha.
    - ``recursion_limit`` uses the production value so tool loops behave as
      they do in prod.
    """
    from src.services.agent._builders import RECURSION_LIMIT

    deploy_env = (
        os.environ.get("DEPLOY_ENV") or os.environ.get("ENVIRONMENT") or "local"
    )
    commit = (
        os.environ.get("GIT_COMMIT")
        or os.environ.get("GITHUB_SHA")
        or os.environ.get("COMMIT_SHA")
        or "unknown"
    )

    return {
        "recursion_limit": RECURSION_LIMIT,
        "run_name": f"perf:{scenario.key}",
        "tags": [
            "perf-harness",
            f"scenario:{scenario.key}",
            f"deploy:{deploy_env}",
        ],
        "metadata": {
            "perf_harness": True,
            "scenario": scenario.key,
            "expect_interrupt": scenario.expect_interrupt,
            "deploy_env": deploy_env,
            "commit": commit,
        },
        "configurable": {
            "thread_id": thread_id,
            "page_context": dict(scenario.page_context),
        },
    }


async def _build_graph() -> Any:
    """Compile the agent graph for the harness.

    Prefers the durable Postgres checkpointer + memory store (the production
    wiring) but falls back to a fresh ``MemorySaver`` when no infra is
    reachable, so the harness still produces latency numbers in a thin dev
    environment. All imports are lazy to keep collection infra-free.
    """
    from src.services.agent._builders import compile_agent_graph

    checkpointer = None
    store = None
    try:
        from src.services.agent.checkpointer import get_checkpointer
        from src.services.agent.memory import get_memory_store

        checkpointer = await get_checkpointer()
        store = await get_memory_store()
    except Exception:
        # No Postgres / store available — fall back to an in-memory saver so
        # the harness can still run and trace in a thin dev box.
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()
        store = None

    return compile_agent_graph(checkpointer=checkpointer, store=store)


@dataclass
class TurnResult:
    """Outcome of one traced scenario turn."""

    scenario: str
    wall_clock_s: float
    interrupted: bool
    intent: str
    assistant_preview: str
    error: Optional[str] = None


async def _run_scenario(scenario: Scenario) -> TurnResult:
    """Run one scenario turn through the compiled graph with tracing on.

    Returns a ``TurnResult`` carrying wall-clock and basic outcome signal.
    The HITL scenario is expected to ``interrupt()``; we catch ``GraphInterrupt``
    and record ``interrupted=True`` rather than treating the pause as a failure.
    Wall-clock is measured with ``time.perf_counter`` around a single
    ``graph.ainvoke`` (or until the interrupt fires).
    """
    from langgraph.errors import GraphInterrupt

    from src.services.agent.observability import configure_langsmith

    # Route traces to the right LangSmith project (rag-agent-{dev|staging|prod}).
    configure_langsmith()

    thread_id = f"perf-{scenario.key}-{int(time.time() * 1000)}"
    graph = await _build_graph()
    initial_state = _build_initial_state(scenario, thread_id=thread_id)
    config = _build_config(scenario, thread_id=thread_id)

    interrupted = False
    error: Optional[str] = None
    final_state: Dict[str, Any] = {}

    t0 = time.perf_counter()
    try:
        # Bound the turn so a hung LLM/tool can't wedge the whole sweep.
        async with asyncio.timeout(360):
            final_state = await graph.ainvoke(initial_state, config=config)
    except GraphInterrupt:
        interrupted = True
    except Exception as exc:  # noqa: BLE001 - record, never crash the sweep
        error = f"{type(exc).__name__}: {exc}"
    wall = time.perf_counter() - t0

    intent = ""
    assistant_preview = ""
    if final_state:
        intent = final_state.get("intent", "") or ""
        for msg in reversed(final_state.get("messages", []) or []):
            if getattr(msg, "type", None) == "ai" and getattr(msg, "content", None):
                assistant_preview = str(msg.content)[:160]
                break

    return TurnResult(
        scenario=scenario.key,
        wall_clock_s=wall,
        interrupted=interrupted,
        intent=intent,
        assistant_preview=assistant_preview,
        error=error,
    )


# ---------------------------------------------------------------------------
# pytest entry points
# ---------------------------------------------------------------------------


@pytest.mark.performance
@pytest.mark.integration
@pytest.mark.parametrize("scenario_key", [s.key for s in SCENARIOS])
def test_scenario_latency(scenario_key: str) -> None:
    """Drive one scenario through the traced graph and assert a soft budget.

    Skips cleanly when the perf gate is off or infra/creds are missing, so the
    unit lane never touches an LLM. Under the gate it records wall-clock to
    LangSmith (via the run_name/tags/metadata on the config) and asserts the
    soft per-scenario latency budget — a regression guard that is inert outside
    the gated run.
    """
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)

    scenario = SCENARIOS_BY_KEY[scenario_key]
    result = asyncio.run(_run_scenario(scenario))

    # A real error (not the expected HITL interrupt) fails the run.
    assert result.error is None, f"{scenario.key} raised: {result.error}"

    if scenario.expect_interrupt:
        assert result.interrupted, (
            f"{scenario.key} expected a HITL interrupt but the turn completed "
            f"normally (intent={result.intent!r})"
        )

    # Soft latency budget — only enforced under the gate (we are past the skip
    # above, so the gate is on here). Catches regressions without ever failing
    # the normal suite.
    assert result.wall_clock_s < scenario.budget_s, (
        f"{scenario.key} took {result.wall_clock_s:.2f}s, "
        f"over soft budget {scenario.budget_s:.1f}s"
    )


# ---------------------------------------------------------------------------
# Script mode — `python -m tests.perf.test_agent_langsmith_tracing`
# ---------------------------------------------------------------------------


async def _run_all() -> List[TurnResult]:
    """Drive every scenario sequentially and return the results."""
    results: List[TurnResult] = []
    for scenario in SCENARIOS:
        result = await _run_scenario(scenario)
        results.append(result)
        flag = "INTERRUPT" if result.interrupted else "ok"
        if result.error:
            flag = f"ERROR {result.error}"
        budget = SCENARIOS_BY_KEY[result.scenario].budget_s
        over = " OVER-BUDGET" if result.wall_clock_s >= budget else ""
        print(
            f"  {result.scenario:<18} {result.wall_clock_s:7.2f}s "
            f"(budget {budget:5.1f}s){over}  intent={result.intent or '-':<10} [{flag}]"
        )
    return results


def main() -> int:
    """Script entry point: sweep all scenarios, print per-scenario wall-clock.

    Relies on ``configure_langsmith()`` (called inside each run) for project
    routing. Returns a non-zero exit code if any scenario errored, so the
    script is CI-friendly; budgets are reported but not enforced here (the
    pytest path owns budget assertions).
    """
    reason = _skip_reason()
    if reason:
        print(f"[perf-harness] skipped: {reason}")
        return 0

    print("[perf-harness] driving agent scenarios (LangSmith tracing on)...")
    results = asyncio.run(_run_all())

    errored = [r for r in results if r.error]
    total = sum(r.wall_clock_s for r in results)
    print(f"[perf-harness] {len(results)} scenarios, {total:.2f}s total wall-clock")
    if errored:
        print(f"[perf-harness] {len(errored)} scenario(s) errored")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
