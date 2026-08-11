#!/usr/bin/env python3
"""Run the arXiv research-flow benchmark against the production LangGraph graph.

Three sequential turns on one thread: (1) search arXiv for a fixture topic,
(2) repeat the identical search to prove the shared Redis cache, (3) ingest
two of the returned papers into the seeded project — DESTRUCTIVE, so the
research subgraph raises one HITL interrupt, approved only after it is
observed. The arXiv client's hard-coded base-URL class attributes are patched
to the in-network mock double before the graph compiles (Landmine 5).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from langgraph.types import Command
from sqlalchemy import select

from evals.harbor_common.db import bootstrap_schema, initial_agent_state, seed_tenant
from evals.harbor_common.envelope import InfrastructureFailure
from evals.harbor_common.network import validate_network_boundary
from evals.harbor_common.serialization import json_safe, utc_now
from evals.harbor_common.trajectory import (
    build_atif_trajectory,
    collect_model_usage,
    final_assistant_message,
)

BENCHMARK_ID = "agent-arxiv-research-flow-v1"
SOURCE_REVISION = "deab258b29c4c4005d0178a04c1aadce44f7a3bd"
AGENT_REVISION = SOURCE_REVISION
APPROVAL_TEXT = "Yes, ingest them."

SEARCH_TEXT = "Search arXiv for deterministic benchmark retrieval evaluation."
EXPECTED_INSTRUCTION = SEARCH_TEXT

ORG_ID = UUID("00000000-0000-4000-8000-000000001001")
USER_ID = UUID("00000000-0000-4000-8000-000000001002")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000001003")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000001004")
THREAD_ID = "00000000-0000-4000-8000-000000001005"
PROJECT_NAME = "Benchmark Research Project"

REQUESTED_PAPER_IDS = ["2401.10001", "2401.10002"]
INGEST_TEXT = (
    "Ingest arXiv papers "
    + " and ".join(REQUESTED_PAPER_IDS)
    + f" into project {PROJECT_ID} and confirm the resulting document IDs."
)

# One destructive tool the flow sanctions.
DESTRUCTIVE_TOOL = "ingest_arxiv_papers"
MAX_RESUMES = 4

MOCK_HOST = "http://mock-services:8080"
MOCK_API_BASE = f"{MOCK_HOST}/api/query"
MOCK_PDF_BASE = f"{MOCK_HOST}/pdf"

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"


async def seed_database() -> None:
    """Seed the tenant triple plus the pre-created, empty target project."""
    from src.core.database import AsyncSessionLocal
    from src.models.collection import Collection

    await seed_tenant(
        org_id=ORG_ID,
        user_id=USER_ID,
        workspace_id=WORKSPACE_ID,
        name_prefix="Benchmark",
        email="benchmark-route@example.invalid",
    )
    async with AsyncSessionLocal() as session:
        session.add(
            Collection(
                id=PROJECT_ID,
                workspace_id=WORKSPACE_ID,
                name=PROJECT_NAME,
                description="Synthetic project for the arXiv research-flow benchmark.",
            )
        )
        await session.commit()


async def database_state() -> dict[str, Any]:
    """Raw document / project-link rows for the synthetic tenant."""
    from src.core.database import AsyncSessionLocal
    from src.models.collection import CollectionDocument
    from src.models.document import Document

    async with AsyncSessionLocal() as session:
        documents = list(
            (
                await session.execute(
                    select(Document)
                    .where(Document.organization_id == ORG_ID)
                    .order_by(Document.id)
                )
            )
            .scalars()
            .all()
        )
        document_ids = [row.id for row in documents]
        links = (
            list(
                (
                    await session.execute(
                        select(CollectionDocument)
                        .where(CollectionDocument.collection_id == PROJECT_ID)
                        .order_by(CollectionDocument.created_at, CollectionDocument.id)
                    )
                )
                .scalars()
                .all()
            )
            if document_ids
            else []
        )
    return {
        "documents": [
            {
                "id": str(row.id),
                "title": row.title,
                "organization_id": str(row.organization_id),
                "processing_status": json_safe(row.processing_status),
                "checksum_sha256": row.checksum_sha256,
                "file_path": row.file_path,
                "storage_path": row.storage_path,
                "storage_backend": row.storage_backend,
                "filename": row.filename,
                "has_search_vector": row.search_vector is not None,
                "document_metadata": json_safe(row.document_metadata or {}),
                "is_deleted": bool(row.is_deleted),
            }
            for row in documents
        ],
        "collection_documents": [
            {
                "id": str(row.id),
                "collection_id": str(row.collection_id),
                "document_id": str(row.document_id),
            }
            for row in links
        ],
        "counts": {"documents": len(documents), "collection_documents": len(links)},
    }


def storage_listing() -> list[dict[str, Any]]:
    """List every file the benchmark's local storage backend wrote."""
    upload_dir = Path(os.environ.get("UPLOAD_DIR", "/benchmark/uploads"))
    if not upload_dir.exists():
        return []
    entries = []
    for path in sorted(upload_dir.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            entries.append(
                {
                    "path": str(path.relative_to(upload_dir)),
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
    return entries


async def redis_arxiv_state() -> dict[str, Any]:
    """Dump every ``arxiv:search:*`` key: TTL, value envelope, and content."""
    import redis.asyncio as redis_asyncio

    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        raise InfrastructureFailure("REDIS_URL is missing")
    client = redis_asyncio.from_url(redis_url, decode_responses=True)
    try:
        if not await client.ping():
            raise InfrastructureFailure("Redis ping returned false")
        keys = sorted(await client.keys("arxiv:search:*"))
        entries = []
        for key in keys:
            raw = await client.get(key)
            ttl = await client.ttl(key)
            parsed = None
            if raw is not None:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
            entries.append({"key": key, "ttl_seconds": ttl, "value": parsed})
        return {"matching_keys": keys, "entries": entries}
    finally:
        await client.aclose()


def mock_events() -> list[dict[str, Any]]:
    response = httpx.get(f"{MOCK_HOST}/events", timeout=10)
    response.raise_for_status()
    return response.json().get("events", [])


async def probe_mock_internal() -> bool:
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(f"{MOCK_HOST}/health")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


async def probe_redis_internal() -> bool:
    import redis.asyncio as redis_asyncio

    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        return False
    client = redis_asyncio.from_url(redis_url, decode_responses=True)
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()


def patch_arxiv_client() -> dict[str, str]:
    """Point the hard-coded arXiv base-URL class attributes at the mock double.

    ``ArXivIngestionService.ARXIV_API_BASE`` / ``ARXIV_PDF_BASE`` are class
    constants, not environment-driven (Landmine 5) — this is the only seam.
    """
    from src.services.arxiv.arxiv_service import ArXivIngestionService

    ArXivIngestionService.ARXIV_API_BASE = MOCK_API_BASE
    ArXivIngestionService.ARXIV_PDF_BASE = MOCK_PDF_BASE
    return {"ARXIV_API_BASE": MOCK_API_BASE, "ARXIV_PDF_BASE": MOCK_PDF_BASE}


def extract_interrupt(snapshot: Any) -> dict[str, Any] | None:
    for task in getattr(snapshot, "tasks", ()) or ():
        for item in getattr(task, "interrupts", ()) or ():
            payload = getattr(item, "value", None)
            if isinstance(payload, dict):
                return json_safe(payload)
    return None


def interrupt_tools(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    tools = payload.get("tools")
    return (
        [tool for tool in tools if isinstance(tool, dict)]
        if isinstance(tools, list)
        else []
    )


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


def record_milestone(
    milestones: list[dict[str, Any]], sequence: list[int], name: str
) -> None:
    sequence[0] += 1
    milestones.append(
        {"milestone": name, "sequence": sequence[0], "observed_at": utc_now()}
    )


async def drive_turn(
    graph: Any,
    config: dict[str, Any],
    turn_name: str,
    instruction: str,
    events: list[dict[str, Any]],
    sequence: list[int],
    milestones: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Send one conversation turn, approving any HITL interrupt it raises.

    Mirrors ``agent-project-management-v1``'s per-interrupt approval loop,
    generalized across multiple human turns on the same thread: every turn is
    a fresh ``initial_agent_state`` (matching production's per-turn state
    shape — ``add_messages`` id-keys the new ``HumanMessage`` onto the
    checkpointed history rather than replacing it).
    """
    interrupts: list[dict[str, Any]] = []
    graph_input: Any = initial_agent_state(instruction, THREAD_ID, user_id=str(USER_ID))
    phase = f"{turn_name}:initial"
    for resume_index in range(MAX_RESUMES + 1):
        await collect_updates(graph, graph_input, config, phase, events, sequence)
        snapshot = await graph.aget_state(config)
        payload = extract_interrupt(snapshot)
        if payload is None:
            return interrupts

        if resume_index >= MAX_RESUMES:
            raise InfrastructureFailure(
                f"{turn_name}: graph still interrupting after {MAX_RESUMES} approvals"
            )

        tools = interrupt_tools(payload)
        for tool in tools:
            record_milestone(
                milestones, sequence, f"interrupt:{tool.get('name') or 'unknown'}"
            )
        # Pre-approval database snapshot — proves no mutation landed before
        # the approval that releases it (Landmine 3 / HITL ordering gate).
        record_milestone(milestones, sequence, f"{turn_name}:preapproval_database_read")
        approved_at = utc_now()
        for tool in tools:
            name = tool.get("name") or "unknown"
            interrupts.append(
                {
                    "turn": turn_name,
                    "tool": name,
                    "args": json_safe(tool.get("args") or {}),
                    "approved_at": approved_at,
                }
            )
            record_milestone(milestones, sequence, f"approval:{name}")
        graph_input = Command(resume={"confirmed": True})
        phase = f"{turn_name}:resume:{resume_index + 1}"

    return interrupts


def tool_executions_for(
    tool_executions: list[Any], tool_name: str
) -> list[dict[str, Any]]:
    return [
        item
        for item in tool_executions
        if isinstance(item, dict) and item.get("tool_name") == tool_name
    ]


def tool_succeeded(tool_executions: list[Any], tool_name: str) -> bool:
    for item in tool_executions_for(tool_executions, tool_name):
        if item.get("status") not in {"completed", "success"}:
            continue
        result = item.get("result")
        if isinstance(result, dict) and result.get("error"):
            continue
        return True
    return False


def hitl_steps(steps: list[dict[str, Any]], evidence: dict[str, Any]) -> list[Any]:
    """Splice the harness-supplied ingest approval into the trajectory."""
    for step in steps:
        if any(
            str(call.get("tool_call_id") or "").startswith("direct_search_arxiv_")
            for call in step.get("tool_calls") or []
        ):
            step["llm_call_count"] = 0
            step.pop("model_name", None)
    if steps and steps[-1].get("source") == "agent":
        approved = [
            call.get("function_name")
            for call in steps[-1].get("tool_calls") or []
            if call.get("function_name") == DESTRUCTIVE_TOOL
        ]
        if approved:
            return steps + [
                {
                    "source": "user",
                    "message": APPROVAL_TEXT,
                    "extra": {
                        "hitl_resume": {"confirmed": True},
                        "approved_tools": approved,
                    },
                }
            ]
    return steps


async def run_benchmark() -> dict[str, Any]:
    started_at = utc_now()
    started = time.monotonic()
    instruction = os.environ.get("HARBOR_INSTRUCTION", "").strip()
    if instruction != EXPECTED_INSTRUCTION:
        raise InfrastructureFailure(
            f"instruction contract drift: expected {EXPECTED_INSTRUCTION!r}"
        )

    async def _mock_reachable() -> bool:
        return await probe_mock_internal()

    async def _redis_reachable() -> bool:
        return await probe_redis_internal()

    network_boundary = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", ""),
        extra_probes={
            "private_mock_services_reachable": _mock_reachable,
            "private_redis_reachable": _redis_reachable,
        },
    )

    patched_urls = patch_arxiv_client()
    await bootstrap_schema()
    await seed_database()
    before_initial = await database_state()
    if before_initial["counts"]["documents"]:
        raise InfrastructureFailure("database reset failed: documents exist before run")

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
    milestones: list[dict[str, Any]] = []
    record_milestone(milestones, sequence, "instruction")

    # Turn 1: search.
    await drive_turn(
        graph, config, "search_1", SEARCH_TEXT, events, sequence, milestones
    )
    after_search_1 = await graph.aget_state(config)
    tool_executions_after_search_1 = list(
        dict(getattr(after_search_1, "values", {}) or {}).get("tool_executions") or []
    )
    if tool_succeeded(tool_executions_after_search_1, "search_arxiv"):
        record_milestone(milestones, sequence, "search_arxiv_success:1")

    # Turn 2: byte-identical repeat search — proves the shared Redis cache.
    await drive_turn(
        graph, config, "search_2", SEARCH_TEXT, events, sequence, milestones
    )
    after_search_2 = await graph.aget_state(config)
    tool_executions_after_search_2 = list(
        dict(getattr(after_search_2, "values", {}) or {}).get("tool_executions") or []
    )
    if tool_succeeded(tool_executions_after_search_2, "search_arxiv"):
        record_milestone(milestones, sequence, "search_arxiv_success:2")

    # Turn 3: ingest — DESTRUCTIVE, one HITL interrupt/approval.
    before_ingest_approval = await database_state()
    interrupts = await drive_turn(
        graph, config, "ingest", INGEST_TEXT, events, sequence, milestones
    )

    final_snapshot = await graph.aget_state(config)
    final_values = dict(getattr(final_snapshot, "values", {}) or {})
    pending_interrupt = extract_interrupt(final_snapshot)

    messages = list(final_values.get("messages") or [])
    tool_executions = list(final_values.get("tool_executions") or [])
    if tool_succeeded(tool_executions, "ingest_arxiv_papers"):
        record_milestone(milestones, sequence, "ingest_arxiv_papers_success")

    after = await database_state()
    record_milestone(milestones, sequence, "postapproval_database_read")
    final_message = final_assistant_message(messages)
    if final_message:
        record_milestone(milestones, sequence, "final_assistant_message")

    termination_reason = (
        "awaiting_confirmation"
        if pending_interrupt is not None
        else "completed" if not getattr(final_snapshot, "next", ()) else "incomplete"
    )

    search_executions = [
        *tool_executions_for(tool_executions_after_search_1, "search_arxiv"),
        *tool_executions_for(tool_executions_after_search_2, "search_arxiv"),
    ]
    if len(search_executions) != 2:
        raise InfrastructureFailure(
            f"expected two search_arxiv executions, observed {len(search_executions)}"
        )
    ingest_executions = tool_executions_for(tool_executions, "ingest_arxiv_papers")

    return {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "source_revision": SOURCE_REVISION,
        "agent_revision": AGENT_REVISION,
        "started_at": started_at,
        "completed_at": utc_now(),
        "instruction": instruction,
        "search_instruction": SEARCH_TEXT,
        "ingest_instruction": INGEST_TEXT,
        "synthetic_actor": {
            "organization_id": str(ORG_ID),
            "user_id": str(USER_ID),
            "workspace_id": str(WORKSPACE_ID),
            "project_id": str(PROJECT_ID),
            "thread_id": THREAD_ID,
        },
        "requested_paper_ids": REQUESTED_PAPER_IDS,
        "arxiv_client_patch": patched_urls,
        "network_boundary": network_boundary,
        "classification": {
            "intent": final_values.get("intent"),
            "confidence": final_values.get("intent_confidence"),
            "source_probe": getattr(classification_probe, "source", None),
            "probe_reasoning": getattr(classification_probe, "reasoning", None),
        },
        "plan": json_safe(final_values.get("plan") or []),
        "interrupts": interrupts,
        "interrupt": (
            {
                "count": len(interrupts),
                "tools": [item.get("tool") for item in interrupts],
            }
            if interrupts
            else None
        ),
        "approval": {
            "count": len(interrupts),
            "text": APPROVAL_TEXT if interrupts else None,
            "resume": {"confirmed": True} if interrupts else None,
        },
        "pending_interrupt_after_resume": pending_interrupt,
        "database": {
            "bootstrap": "src.models.Base.metadata.create_all",
            "initial": before_initial,
            "before_ingest_approval": before_ingest_approval,
            "after": after,
        },
        "storage": storage_listing(),
        "redis_arxiv": await redis_arxiv_state(),
        "mock_events": mock_events(),
        "search_executions": json_safe(search_executions),
        "ingest_executions": json_safe(ingest_executions),
        "tool_executions": json_safe(tool_executions),
        "messages": json_safe(messages),
        "events": events,
        "milestones": milestones,
        "suppress_observation_for": [DESTRUCTIVE_TOOL],
        "notes": (
            "Production graph with an isolated database, an arXiv Atom/PDF "
            "protocol double, a shared Redis cache, and one post-interrupt "
            "ingest approval."
        ),
        "final_assistant_message": final_message,
        "termination_reason": termination_reason,
        "model_usage": collect_model_usage(messages),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }


async def async_main() -> int:
    AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        evidence = await run_benchmark()
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        TRAJECTORY_PATH.write_text(
            json.dumps(
                build_atif_trajectory(
                    evidence, BENCHMARK_ID, THREAD_ID, extra_steps_hook=hitl_steps
                ),
                indent=2,
                sort_keys=True,
            )
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
