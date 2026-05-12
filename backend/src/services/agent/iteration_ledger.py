"""Per-turn append-only iteration ledger.

Inspired by K-Dense's `rowan-autosearch`: capture every agent turn as a
versioned JSON record on disk so the full reasoning trail (intent, plan,
tool executions, RAG context, response, reflection verdict, tokens) is
auditable, replayable, and post-hoc evaluable.

Layout::

    <AGENT_LEDGER_DIR>/
        <thread_id>/
            iterations/
                0001.json
                0002.json
                ...

Each turn appends one numbered JSON file. The format mirrors the K-Dense
shape: `turn`, `timestamp`, plus a `state_snapshot` of the meaningful
agent state and a compact `summary` for quick scans.

Disabled when ``settings.AGENT_LEDGER_DIR`` is empty/None — zero-cost
when the user doesn't want it.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.core.config import get_settings

logger = logging.getLogger(__name__)


def _ledger_root() -> Path | None:
    settings = get_settings()
    base = settings.AGENT_LEDGER_DIR
    if not base:
        return None
    return Path(base).expanduser()


def _next_turn_number(thread_dir: Path) -> int:
    """Scan iterations/ for the highest existing turn N and return N+1.

    Robust against missing dir (returns 1) and non-numeric filenames
    (skipped silently).
    """
    iter_dir = thread_dir / "iterations"
    if not iter_dir.exists():
        return 1
    existing = []
    for p in iter_dir.iterdir():
        if p.suffix != ".json":
            continue
        try:
            existing.append(int(p.stem))
        except ValueError:
            continue
    return (max(existing) + 1) if existing else 1


def _serialize_message(msg: Any) -> dict:
    """Compact dict for one LangChain message — drops bulky fields."""
    if isinstance(msg, HumanMessage):
        return {"role": "human", "content": str(msg.content)[:2000]}
    if isinstance(msg, AIMessage):
        out: dict[str, Any] = {
            "role": "ai",
            "content": str(msg.content)[:4000],
        }
        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            out["tool_calls"] = [
                {"name": tc.get("name"), "args": tc.get("args"), "id": tc.get("id")}
                for tc in tool_calls
            ]
        meta = getattr(msg, "response_metadata", None) or {}
        if meta.get("model_name"):
            out["model"] = meta["model_name"]
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            out["usage"] = {
                "input": usage.get("input_tokens"),
                "output": usage.get("output_tokens"),
                "reasoning": (usage.get("output_token_details") or {}).get("reasoning"),
                "cache_read": (usage.get("input_token_details") or {}).get("cache_read"),
            }
        return out
    if isinstance(msg, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": getattr(msg, "tool_call_id", None),
            "content": str(msg.content)[:2000],
        }
    return {"role": getattr(msg, "type", "unknown"), "content": str(msg)[:500]}


def _build_record(state: dict, turn: int) -> dict:
    """Build the JSON-serializable record for one turn."""
    messages = state.get("messages") or []
    # Slice to current turn: walk back to most recent HumanMessage and keep
    # everything from there to the end. Same boundary the dedupe + sanitizer
    # use — keeps the ledger record focused on this turn's exchange.
    boundary = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            boundary = i
            break
    in_turn_msgs = messages[boundary:] if boundary >= 0 else list(messages)

    user_msg = ""
    ai_content = ""
    for m in in_turn_msgs:
        if isinstance(m, HumanMessage) and not user_msg:
            user_msg = str(m.content)[:1000]
        if isinstance(m, AIMessage) and m.content:
            ai_content = str(m.content)[:4000]

    tool_executions = list(state.get("tool_executions") or [])

    # Compact retrieved_contexts: titles + scores only, drop full chunk text.
    retrieved = state.get("retrieved_contexts") or []
    retrieved_summary = [
        {
            "document_id": ctx.get("document_id"),
            "title": ctx.get("title"),
            "score": ctx.get("score"),
        }
        for ctx in retrieved[:10]
        if isinstance(ctx, dict)
    ]

    reflection = state.get("_reflection_result")
    if reflection is not None and not isinstance(reflection, dict):
        reflection = {
            "passed": getattr(reflection, "passed", None),
            "issues": getattr(reflection, "issues", None),
            "severity": getattr(reflection, "severity", None),
        }

    return {
        "turn": turn,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "user_query": user_msg,
            "intent": state.get("intent"),
            "intent_confidence": state.get("intent_confidence"),
            "tool_loop_count": state.get("tool_loop_count"),
            "error_count": state.get("error_count"),
            "tools_used": [te.get("tool_name") for te in tool_executions[-5:]],
            "ai_response_chars": len(ai_content),
        },
        "state_snapshot": {
            "messages": [_serialize_message(m) for m in in_turn_msgs],
            "page_context": state.get("page_context"),
            "current_project_id": state.get("current_project_id"),
            "model": state.get("model"),
            "plan": state.get("plan") or [],
            "tool_executions": tool_executions,
            "retrieved_contexts": retrieved_summary,
            "user_memories_keys": [
                m.get("key") for m in (state.get("user_memories") or [])
            ],
            "reflection_result": reflection,
            "last_error": state.get("last_error") or None,
            "last_error_info": state.get("last_error_info") or None,
            "compaction_count": state.get("compaction_count"),
            "reflection_count": state.get("reflection_count"),
        },
    }


def _atomic_write_json(path: Path, payload: dict) -> None:
    """tmp+rename atomic write so partial writes don't poison the ledger."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _maybe_write_config(thread_dir: Path, state: dict) -> None:
    """Write runs/<thread_id>/config.json on the first turn only.

    Captures the immutable run setup: thread_id, user_id, page_context
    (project/paper/chat type at first turn), model override, and the
    initial user query. Subsequent turns leave it alone — the file is
    a record of how the run STARTED, not its current state.
    """
    config_path = thread_dir / "config.json"
    if config_path.exists():
        return
    messages = state.get("messages") or []
    first_user = ""
    for m in messages:
        if isinstance(m, HumanMessage) and m.content:
            first_user = str(m.content)[:1000]
            break
    config = {
        "thread_id": (state.get("thread_id") or thread_dir.name),
        "user_id": state.get("user_id"),
        "page_context": state.get("page_context"),
        "current_project_id": state.get("current_project_id"),
        "model": state.get("model"),
        "initial_query": first_user,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _atomic_write_json(config_path, config)
    except Exception as exc:  # noqa: BLE001 - observability only
        logger.debug("ledger config write skipped: %s", exc)


def write_iteration(thread_id: str, state: dict) -> Path | None:
    """Append one iteration record for *thread_id*. Returns the path
    written, or None if the ledger is disabled or write fails (never
    raises — agent flow must not break on observability errors).

    On first turn also writes ``config.json`` (immutable run setup) and
    on every turn rewrites ``final.json`` (latest summary; fast lookup
    without scanning iterations/).
    """
    root = _ledger_root()
    if not root or not thread_id:
        return None
    try:
        thread_dir = root / thread_id
        iter_dir = thread_dir / "iterations"
        iter_dir.mkdir(parents=True, exist_ok=True)

        # Write config.json on the first turn (idempotent — checks existence).
        _maybe_write_config(thread_dir, state)

        turn = _next_turn_number(thread_dir)
        record = _build_record(state, turn)

        path = iter_dir / f"{turn:04d}.json"
        _atomic_write_json(path, record)

        # Rewrite final.json with the latest summary on every turn so
        # consumers (HTML report, dashboard) can fetch the run's current
        # state in one read.
        final_path = thread_dir / "final.json"
        try:
            _atomic_write_json(
                final_path,
                {
                    "thread_id": thread_id,
                    "latest_turn": turn,
                    "updated_at": record["timestamp"],
                    "summary": record["summary"],
                    "page_context": record["state_snapshot"].get("page_context"),
                    "current_project_id": record["state_snapshot"].get(
                        "current_project_id"
                    ),
                    "tool_executions_count": len(
                        record["state_snapshot"].get("tool_executions") or []
                    ),
                    "reflection_result": record["state_snapshot"].get(
                        "reflection_result"
                    ),
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("ledger final.json write skipped: %s", exc)

        logger.debug("ledger: wrote %s (turn %d)", path, turn)
        return path
    except Exception as exc:  # noqa: BLE001 - never crash the agent
        logger.warning("ledger write failed for thread %s: %s", thread_id, exc)
        return None
