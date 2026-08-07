"""Model-usage accounting and ATIF-v1.7 trajectory construction.

Consumed only by Harbor eval tasks added after 2026-08-07; the three original
tasks are digest-pinned and keep their inline copies. Ported from
`evals/agent-direct-project-action-v1/environment/run_agent.py`.

`langchain_core` is imported lazily inside the message helpers so this module
imports cleanly without the agent runtime installed.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Optional

from .serialization import json_safe

__all__ = [
    "final_assistant_message",
    "collect_model_usage",
    "build_atif_trajectory",
]

ExtraStepsHook = Callable[[list, dict], list]


def final_assistant_message(messages: list[Any]) -> dict[str, Any]:
    """Return the last non-empty AI message as JSON-safe evidence ({} if none)."""
    from langchain_core.messages import AIMessage

    for message in reversed(messages):
        if isinstance(message, AIMessage) and str(message.content or "").strip():
            return json_safe(message)
    return {}


def collect_model_usage(messages: list[Any]) -> dict[str, int]:
    """Sum prompt/completion/cache-read tokens over de-duplicated AI messages."""
    from langchain_core.messages import AIMessage

    totals = {"input_tokens": 0, "output_tokens": 0, "cache_tokens": 0}
    seen: set[str] = set()
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        key = str(message.id or id(message))
        if key in seen:
            continue
        seen.add(key)
        usage = message.usage_metadata or {}
        totals["input_tokens"] += int(usage.get("input_tokens") or 0)
        totals["output_tokens"] += int(usage.get("output_tokens") or 0)
        details = usage.get("input_token_details") or {}
        totals["cache_tokens"] += int(details.get("cache_read") or 0)
    return totals


def build_atif_trajectory(
    evidence: dict[str, Any],
    benchmark_id: str,
    thread_id: str,
    extra_steps_hook: Optional[ExtraStepsHook] = None,
) -> dict[str, Any]:
    """Render captured evidence as an ATIF-v1.7 trajectory document.

    `evidence` is the JSON-safe run record produced by an adapter. Keys read:

    - ``messages``      — JSON-safe message dicts (``type``/``content``/
      ``tool_calls``/``tool_call_id``); the sole source of steps.
    - ``model_usage``   — output of :func:`collect_model_usage`.
    - ``interrupt``, ``termination_reason`` — copied into ``extra``.
    - ``agent_name``, ``agent_revision``, ``source_revision``, ``notes``,
      ``suppress_observation_for`` — optional metadata (see below).

    Tool results are attached to the emitting agent step as ``observation``.
    Results for tool names listed in ``evidence["suppress_observation_for"]``
    are omitted — the direct-project task uses this to keep the destructive
    ``create_project`` result out of the trajectory, since replaying it would
    re-execute the very action under test.

    ``extra_steps_hook(steps, evidence) -> list`` lets a task splice in steps
    the message log does not contain — most importantly the synthetic
    human-in-the-loop approval turn, which is injected by the harness rather
    than the model and therefore has no message of its own. Contract:

    - It is called **after every agent step is appended** (exactly where the
      source task injected its HITL approval turn), and **once more after the
      loop finishes** so a hook can append trailing/fallback steps such as a
      "no approval was observed" marker.
    - It receives the steps built so far and must **return the amended list**;
      the return value replaces the working list. Returning the argument
      unchanged is a no-op. Returning ``None`` is an error.
    - It may append, insert, or drop steps. ``step_id`` is renumbered from 1
      after the hook runs, so a hook need not maintain it.
    - Hooks are responsible for their own idempotence: seeing the same steps
      list repeatedly is expected, so guard against duplicate injection (e.g.
      by checking whether the approval step is already present).
    """
    messages = evidence.get("messages") or []
    suppressed = set(evidence.get("suppress_observation_for") or ())
    tool_results = {
        str(message.get("tool_call_id")): message
        for message in messages
        if message.get("type") == "tool" and message.get("tool_call_id")
    }
    steps: list[dict[str, Any]] = []
    for message in messages:
        msg_type = message.get("type")
        if msg_type == "human":
            steps.append(
                {
                    "step_id": len(steps) + 1,
                    "source": "user",
                    "message": str(message.get("content") or ""),
                }
            )
            continue
        if msg_type != "ai":
            continue
        calls = message.get("tool_calls") or []
        tool_calls = [
            {
                "tool_call_id": str(call.get("id") or "unknown"),
                "function_name": str(call.get("name") or "unknown"),
                "arguments": call.get("args") or {},
            }
            for call in calls
        ]
        step: dict[str, Any] = {
            "step_id": len(steps) + 1,
            "source": "agent",
            "model_name": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
            "message": str(message.get("content") or "[tool call]"),
            "llm_call_count": 1,
        }
        if tool_calls:
            step["tool_calls"] = tool_calls
            reportable_results = []
            for call in tool_calls:
                if call["function_name"] in suppressed:
                    continue
                result = tool_results.get(call["tool_call_id"])
                if result:
                    reportable_results.append(
                        {
                            "source_call_id": call["tool_call_id"],
                            "content": str(result.get("content") or ""),
                        }
                    )
            if reportable_results:
                step["observation"] = {"results": reportable_results}
        steps.append(step)
        if extra_steps_hook is not None:
            steps = extra_steps_hook(steps, evidence)

    if extra_steps_hook is not None:
        steps = extra_steps_hook(steps, evidence)
    for index, step in enumerate(steps, start=1):
        step["step_id"] = index

    usage = evidence.get("model_usage") or {}
    agent_revision = str(evidence.get("agent_revision") or "")
    return {
        "schema_version": "ATIF-v1.7",
        "session_id": thread_id,
        "trajectory_id": f"{benchmark_id}:{thread_id}",
        "agent": {
            "name": evidence.get("agent_name") or "nous-production-agent",
            "version": agent_revision[:12],
            "model_name": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        },
        "steps": steps,
        "notes": evidence.get("notes")
        or "Production graph with an isolated database.",
        "final_metrics": {
            "total_prompt_tokens": usage.get("input_tokens", 0),
            "total_completion_tokens": usage.get("output_tokens", 0),
            "total_cached_tokens": usage.get("cache_tokens", 0),
            "total_steps": len(steps),
        },
        "extra": {
            "benchmark_id": benchmark_id,
            "source_revision": evidence.get("source_revision"),
            "interrupt": evidence.get("interrupt"),
            "termination_reason": evidence.get("termination_reason"),
        },
    }
