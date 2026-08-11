#!/usr/bin/env python3
"""Run the direct-project benchmark against the production LangGraph graph."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import socket
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.types import Command
from sqlalchemy import func, select

BENCHMARK_ID = "agent-direct-project-action-v1"
SOURCE_REVISION = "b35524c80611d544749e109bd43a5a367798d62f"
AGENT_REVISION = "b35524c80611d544749e109bd43a5a367798d62f"
APPROVAL_TEXT = "Yes, create it."
EXPECTED_INSTRUCTION = "Create a project named The Discovery Note."
EXPECTED_PROJECT_NAME = "The Discovery Note"

ORG_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000102")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000103")
THREAD_ID = "00000000-0000-4000-8000-000000000104"

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"


class InfrastructureFailure(RuntimeError):
    """A trial setup/dependency failure that must not receive an agent score."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_safe(value: Any) -> Any:
    """Convert LangChain/LangGraph values into bounded JSON-safe evidence."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, BaseMessage):
        payload: dict[str, Any] = {
            "type": value.type,
            "id": getattr(value, "id", None),
            "content": json_safe(value.content),
        }
        if isinstance(value, AIMessage):
            payload["tool_calls"] = json_safe(value.tool_calls or [])
            payload["usage_metadata"] = json_safe(value.usage_metadata or {})
            payload["response_metadata"] = json_safe(value.response_metadata or {})
        if isinstance(value, ToolMessage):
            payload["tool_call_id"] = value.tool_call_id
            payload["status"] = getattr(value, "status", None)
        return payload
    if dataclasses.is_dataclass(value):
        return json_safe(dataclasses.asdict(value))
    if hasattr(value, "model_dump"):
        try:
            return json_safe(value.model_dump(mode="json"))
        except Exception:
            return json_safe(value.model_dump())
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if hasattr(value, "value"):
        try:
            return json_safe(value.value)
        except Exception:
            pass
    return str(value)


async def bootstrap_schema() -> None:
    """Provision the disposable benchmark DB from production ORM metadata.

    The repository's integration fixtures use this same path because the
    historical Alembic chain cannot bootstrap an empty database: its initial
    revision is a no-op and the next revision references tables that do not
    exist yet.  That migration defect is audit evidence, but it must not turn
    this agent capability benchmark into a migration benchmark.
    """
    try:
        from src.core.database import async_engine
        from src.models import Base

        async with async_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    except Exception as exc:
        raise InfrastructureFailure(
            f"SQLAlchemy metadata bootstrap failed: {type(exc).__name__}"
        ) from exc


def validate_network_boundary() -> dict[str, Any]:
    """Prove main has no direct egress and proxy permits only the model host."""
    direct_blocked = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect(("1.1.1.1", 443))
    except OSError:
        direct_blocked = True
    finally:
        sock.close()

    endpoint = os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", "").strip()
    if not endpoint:
        raise InfrastructureFailure("AZURE_OPENAI_CHAT_ENDPOINT is missing")

    allowed_reachable = False
    blocked_status: int | None = None
    allowed_status: int | None = None
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            allowed_response = client.get(endpoint.rstrip("/") + "/")
            allowed_status = allowed_response.status_code
            allowed_reachable = 100 <= allowed_status <= 599
    except httpx.HTTPError as exc:
        raise InfrastructureFailure(
            f"approved model-host proxy preflight failed: {type(exc).__name__}"
        ) from exc

    unrelated_blocked = False
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            blocked_response = client.get("https://example.com/")
            blocked_status = blocked_response.status_code
            unrelated_blocked = blocked_status == 403
    except httpx.ProxyError as exc:
        # For a denied HTTPS CONNECT, httpx surfaces Squid's 403 as a
        # ProxyError instead of an HTTP response.  That is the expected proof
        # that the proxy rejected an unapproved destination.
        unrelated_blocked = "403" in str(exc)
        blocked_status = 403 if unrelated_blocked else None
    except httpx.HTTPError as exc:
        raise InfrastructureFailure(
            f"blocked-host proxy preflight failed ambiguously: {type(exc).__name__}"
        ) from exc

    result = {
        "direct_public_socket_blocked": direct_blocked,
        "approved_model_host_reachable_via_proxy": allowed_reachable,
        "approved_model_probe_status": allowed_status,
        "unrelated_https_blocked_by_proxy": unrelated_blocked,
        "unrelated_probe_status": blocked_status,
    }
    if not all((direct_blocked, allowed_reachable, unrelated_blocked)):
        raise InfrastructureFailure(f"network boundary check failed: {result}")
    return result


async def seed_database() -> None:
    from src.core.database import AsyncSessionLocal
    from src.core.encryption import (
        EncryptionKeyType,
        get_key_manager,
        initialize_encryption,
    )
    from src.models.organization import Organization, StorageTier
    from src.models.user import User, UserRole
    from src.models.workspace import Workspace

    initialize_encryption()
    key_manager = get_key_manager()
    if key_manager.get_active_key(EncryptionKeyType.DATA) is None:
        key_manager.generate_key(EncryptionKeyType.DATA)
    async with AsyncSessionLocal() as session:
        session.add(
            Organization(
                id=ORG_ID,
                name="Benchmark Organization",
                storage_tier=StorageTier.FREE,
                storage_used_bytes=0,
                storage_limit_bytes=10 * 1024**3,
                is_active=True,
            )
        )
        session.add(
            User(
                id=USER_ID,
                email="benchmark-route@example.invalid",
                password_hash="benchmark-password-not-used",
                first_name="Benchmark",
                last_name="Route",
                role=UserRole.USER,
                is_active=True,
                organization_id=ORG_ID,
            )
        )
        session.add(
            Workspace(
                id=WORKSPACE_ID,
                name="Benchmark Workspace",
                description="Synthetic state for the Harbor benchmark.",
                owner_id=USER_ID,
                organization_id=ORG_ID,
                is_archived=False,
                is_public=False,
            )
        )
        await session.commit()


async def database_state() -> dict[str, Any]:
    from src.core.database import AsyncSessionLocal
    from src.models.collection import Collection, CollectionDocument
    from src.models.document import Document
    from src.models.project_note import ProjectNote

    async with AsyncSessionLocal() as session:
        rows = list(
            (
                await session.execute(
                    select(Collection)
                    .where(Collection.workspace_id == WORKSPACE_ID)
                    .order_by(Collection.created_at, Collection.id)
                )
            )
            .scalars()
            .all()
        )
        document_links = int(
            await session.scalar(select(func.count(CollectionDocument.id))) or 0
        )
        notes = int(await session.scalar(select(func.count(ProjectNote.id))) or 0)
        documents = int(await session.scalar(select(func.count(Document.id))) or 0)
        return {
            "workspace_id": str(WORKSPACE_ID),
            "projects": [
                {
                    "id": str(row.id),
                    "workspace_id": str(row.workspace_id),
                    "name": row.name,
                    "research_status": row.research_status,
                    "is_deleted": bool(row.is_deleted),
                }
                for row in rows
            ],
            "document_links": document_links,
            "project_notes": notes,
            "documents": documents,
        }


def initial_state(instruction: str) -> dict[str, Any]:
    return {
        "messages": [HumanMessage(content=instruction)],
        "page_context": {},
        "retrieved_contexts": [],
        "tool_executions": [],
        "thread_id": THREAD_ID,
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
        "user_id": str(USER_ID),
        "current_project_id": "",
        "model": "",
        "use_rag": False,
        "runtime_snapshot_id": "",
        "project_skill_catalog": [],
        "loaded_skill_versions": [],
        "_reflection_result": None,
        "_force_synthesis_fired": False,
        "tools_all_deduped": False,
    }


def extract_interrupt(snapshot: Any) -> dict[str, Any] | None:
    for task in getattr(snapshot, "tasks", ()) or ():
        for item in getattr(task, "interrupts", ()) or ():
            payload = getattr(item, "value", None)
            if isinstance(payload, dict):
                return json_safe(payload)
    return None


async def collect_updates(
    graph: Any,
    graph_input: Any,
    config: dict[str, Any],
    phase: str,
    events: list[dict[str, Any]],
    sequence: list[int],
) -> None:
    async for event in graph.astream(graph_input, config=config, stream_mode="updates"):
        sequence[0] += 1
        events.append(
            {
                "sequence": sequence[0],
                "phase": phase,
                "observed_at": utc_now(),
                "update": json_safe(event),
            }
        )


def final_assistant_message(messages: list[Any]) -> dict[str, Any]:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and str(message.content or "").strip():
            return json_safe(message)
    return {}


def collect_model_usage(messages: list[Any]) -> dict[str, int]:
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


def build_trajectory(evidence: dict[str, Any]) -> dict[str, Any]:
    messages = evidence.get("messages") or []
    tool_results = {
        str(message.get("tool_call_id")): message
        for message in messages
        if message.get("type") == "tool" and message.get("tool_call_id")
    }
    steps: list[dict[str, Any]] = []
    approval_inserted = False
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
            non_destructive_results = []
            for call in tool_calls:
                if call["function_name"] == "create_project":
                    continue
                result = tool_results.get(call["tool_call_id"])
                if result:
                    non_destructive_results.append(
                        {
                            "source_call_id": call["tool_call_id"],
                            "content": str(result.get("content") or ""),
                        }
                    )
            if non_destructive_results:
                step["observation"] = {"results": non_destructive_results}
        steps.append(step)
        if any(call["function_name"] == "create_project" for call in tool_calls):
            steps.append(
                {
                    "step_id": len(steps) + 1,
                    "source": "user",
                    "message": APPROVAL_TEXT,
                    "extra": {"hitl_resume": {"confirmed": True}},
                }
            )
            approval_inserted = True

    if not approval_inserted:
        steps.append(
            {
                "step_id": len(steps) + 1,
                "source": "system",
                "message": "No HITL approval was observed.",
            }
        )

    usage = evidence.get("model_usage") or {}
    return {
        "schema_version": "ATIF-v1.7",
        "session_id": THREAD_ID,
        "trajectory_id": f"{BENCHMARK_ID}:{THREAD_ID}",
        "agent": {
            "name": "nous-production-agent",
            "version": AGENT_REVISION[:12],
            "model_name": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        },
        "steps": steps,
        "notes": "Production graph with an isolated database and fixed post-interrupt approval.",
        "final_metrics": {
            "total_prompt_tokens": usage.get("input_tokens", 0),
            "total_completion_tokens": usage.get("output_tokens", 0),
            "total_cached_tokens": usage.get("cache_tokens", 0),
            "total_steps": len(steps),
        },
        "extra": {
            "benchmark_id": BENCHMARK_ID,
            "source_revision": SOURCE_REVISION,
            "interrupt": evidence.get("interrupt"),
            "termination_reason": evidence.get("termination_reason"),
        },
    }


async def run_benchmark() -> dict[str, Any]:
    started_at = utc_now()
    started = time.monotonic()
    instruction = os.environ.get("HARBOR_INSTRUCTION", "").strip()
    if instruction != EXPECTED_INSTRUCTION:
        raise InfrastructureFailure(
            f"instruction contract drift: expected {EXPECTED_INSTRUCTION!r}"
        )

    network_boundary = validate_network_boundary()
    await bootstrap_schema()
    await seed_database()
    before_initial = await database_state()
    if before_initial["projects"]:
        raise InfrastructureFailure("database reset failed: projects exist before run")

    from src.services.agent._builders import RECURSION_LIMIT
    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.classifier import classify_intent_with_fallback
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.memory import get_memory_store

    classification_probe = await classify_intent_with_fallback(instruction, {})
    checkpointer = await get_checkpointer()
    store = await get_memory_store()
    graph = compile_agent_graph(checkpointer=checkpointer, store=store)

    config = {
        "recursion_limit": RECURSION_LIMIT,
        "configurable": {
            "thread_id": THREAD_ID,
            "user_id": str(USER_ID),
            "organization_id": str(ORG_ID),
            "page_context": {},
            "runtime_snapshot_id": "",
            "current_project_id": "",
        },
        "metadata": {
            "benchmark_id": BENCHMARK_ID,
            "source_revision": SOURCE_REVISION,
            "thread_id": THREAD_ID,
            "user_id": str(USER_ID),
            "organization_id": str(ORG_ID),
        },
    }

    events: list[dict[str, Any]] = []
    sequence = [0]
    milestones = {"instruction": 1}
    await collect_updates(
        graph, initial_state(instruction), config, "initial", events, sequence
    )

    paused_snapshot = await graph.aget_state(config)
    interrupt_payload = extract_interrupt(paused_snapshot)
    sequence[0] += 1
    milestones["interrupt"] = sequence[0]
    before_approval = await database_state()
    sequence[0] += 1
    milestones["preapproval_database_read"] = sequence[0]

    approval_sent = interrupt_payload is not None
    if approval_sent:
        sequence[0] += 1
        milestones["approval"] = sequence[0]
        await collect_updates(
            graph,
            Command(resume={"confirmed": True}),
            config,
            "resume",
            events,
            sequence,
        )

    final_snapshot = await graph.aget_state(config)
    final_values = dict(getattr(final_snapshot, "values", {}) or {})
    pending_interrupt = extract_interrupt(final_snapshot)

    messages = list(final_values.get("messages") or [])
    tool_executions = list(final_values.get("tool_executions") or [])
    create_success = next(
        (
            item
            for item in tool_executions
            if item.get("tool_name") == "create_project"
            and item.get("status") in {"completed", "success"}
            and (item.get("result") or {}).get("status") == "success"
        ),
        None,
    )
    if create_success is not None:
        sequence[0] += 1
        milestones["create_project_success"] = sequence[0]
    after = await database_state()
    sequence[0] += 1
    milestones["postapproval_database_read"] = sequence[0]
    final_message = final_assistant_message(messages)
    if final_message:
        sequence[0] += 1
        milestones["final_assistant_message"] = sequence[0]

    termination_reason = (
        "awaiting_confirmation"
        if pending_interrupt is not None
        else "completed" if not getattr(final_snapshot, "next", ()) else "incomplete"
    )
    evidence = {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "source_revision": SOURCE_REVISION,
        "agent_revision": AGENT_REVISION,
        "started_at": started_at,
        "completed_at": utc_now(),
        "instruction": instruction,
        "synthetic_actor": {
            "organization_id": str(ORG_ID),
            "user_id": str(USER_ID),
            "workspace_id": str(WORKSPACE_ID),
            "thread_id": THREAD_ID,
        },
        "network_boundary": network_boundary,
        "classification": {
            "intent": final_values.get("intent"),
            "confidence": final_values.get("intent_confidence"),
            "source_probe": getattr(classification_probe, "source", None),
            "probe_reasoning": getattr(classification_probe, "reasoning", None),
        },
        "plan": json_safe(final_values.get("plan") or []),
        "interrupt": {
            "observed": interrupt_payload is not None,
            "payload": interrupt_payload,
        },
        "approval": {
            "sent": approval_sent,
            "text": APPROVAL_TEXT if approval_sent else None,
            "resume": {"confirmed": True} if approval_sent else None,
        },
        "pending_interrupt_after_resume": pending_interrupt,
        "database": {
            "bootstrap": "src.models.Base.metadata.create_all",
            "initial": before_initial,
            "before_approval": before_approval,
            "after": after,
        },
        "tool_executions": json_safe(tool_executions),
        "messages": json_safe(messages),
        "events": events,
        "milestones": milestones,
        "final_assistant_message": final_message,
        "termination_reason": termination_reason,
        "model_usage": collect_model_usage(messages),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }
    return evidence


async def async_main() -> int:
    AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        evidence = await run_benchmark()
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        TRAJECTORY_PATH.write_text(
            json.dumps(build_trajectory(evidence), indent=2, sort_keys=True)
        )
        print(
            json.dumps(
                {
                    "benchmark_id": BENCHMARK_ID,
                    "termination_reason": evidence["termination_reason"],
                    "elapsed_ms": evidence["elapsed_ms"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as exc:
        error = {
            "benchmark_id": BENCHMARK_ID,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        (AGENT_LOG_DIR / "infrastructure-error.json").write_text(
            json.dumps(error, indent=2, sort_keys=True)
        )
        print(
            f"benchmark infrastructure failure: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 70
    finally:
        try:
            from src.services.agent._pool_utils import close_shared_langgraph_pool

            await close_shared_langgraph_pool()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
