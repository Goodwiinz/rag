#!/usr/bin/env python3
"""Run the long-run controls task through the unchanged production graph."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from evals.harbor_common.db import bootstrap_schema, initial_agent_state, seed_tenant
from evals.harbor_common.envelope import InfrastructureFailure
from evals.harbor_common.network import validate_network_boundary
from evals.harbor_common.serialization import json_safe
from evals.harbor_common.trajectory import (
    build_atif_trajectory,
    collect_model_usage,
    final_assistant_message,
)

BENCHMARK_ID = "agent-long-run-controls-v1"
SOURCE_REVISION = "fa3858d79baeb9dba79f0a44a077856418933898"
EXPECTED_INSTRUCTION = (
    "Search the project knowledge base beginning with NOUS-LONG-1. Complete "
    "stages 1 through 5, and do not execute stage 6. Then explain the first "
    "and final verified findings. You may synthesize voluntarily after stage 5; "
    "if an execution limit stops an attempted next call, give the best grounded "
    "partial answer and clearly identify the last verified stage instead of "
    "inventing later findings."
)

ORG_ID = UUID("00000000-0000-4000-8000-000000002000")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000002010")
USER_ID = UUID("00000000-0000-4000-8000-000000002011")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000002012")
DOC_IDS = (
    UUID("00000000-0000-4000-8000-000000002001"),
    UUID("00000000-0000-4000-8000-000000002002"),
)
THREAD_ID = "00000000-0000-4000-8000-000000002013"
KB_UUID = "benchmark-kb-long-001"

LOG_DIR = Path("/logs/agent")
LEDGER_DIR = LOG_DIR / "ledger"
EVIDENCE_PATH = LOG_DIR / "evidence.json"
TRAJECTORY_PATH = LOG_DIR / "trajectory.json"


async def seed_database() -> None:
    from src.core.database import AsyncSessionLocal
    from src.models.collection import Collection, CollectionDocument
    from src.models.document import Document, DocumentType, ProcessingStatus
    from src.models.organization import Organization

    await seed_tenant(
        ORG_ID,
        USER_ID,
        WORKSPACE_ID,
        name_prefix="Benchmark Long Run",
        email="benchmark-long-run@example.invalid",
    )
    async with AsyncSessionLocal() as session:
        organization = await session.get(Organization, ORG_ID)
        if organization is None:
            raise InfrastructureFailure("seed_tenant did not create organization")
        organization.do_kb_uuid = KB_UUID
        session.add(
            Collection(
                id=PROJECT_ID,
                workspace_id=WORKSPACE_ID,
                name="Atlas Long-Run Study",
                description="Synthetic sequential-retrieval project.",
                project_type="research",
                research_status="active",
                is_deleted=False,
            )
        )
        for index, doc_id in enumerate(DOC_IDS, start=1):
            session.add(
                Document(
                    id=doc_id,
                    title=f"Atlas Evidence {index}",
                    filename=f"{doc_id}.txt",
                    file_path=f"/synthetic/{doc_id}.txt",
                    file_size_bytes=1,
                    mime_type="text/plain",
                    document_type=DocumentType.TEXT,
                    storage_path=f"documents/{ORG_ID}/{doc_id}.txt",
                    storage_backend="local",
                    processing_status=ProcessingStatus.COMPLETED,
                    processing_retry_count=0,
                    content_text="Synthetic KB source marker.",
                    is_embedded=True,
                    is_indexed=True,
                    is_public=False,
                    is_deleted=False,
                    organization_id=ORG_ID,
                    uploaded_by_user_id=USER_ID,
                )
            )
        await session.flush()
        session.add_all(
            [
                CollectionDocument(
                    collection_id=PROJECT_ID,
                    document_id=doc_id,
                    sort_order=index,
                )
                for index, doc_id in enumerate(DOC_IDS)
            ]
        )
        await session.commit()


async def database_state() -> dict[str, Any]:
    from src.core.database import AsyncSessionLocal
    from src.models.collection import Collection
    from src.models.document import Document
    from src.models.organization import Organization

    async with AsyncSessionLocal() as session:
        organization = await session.get(Organization, ORG_ID)
        project = await session.get(Collection, PROJECT_ID)
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
    return {
        "kb_uuid": getattr(organization, "do_kb_uuid", None),
        "project": {
            "id": str(project.id),
            "is_deleted": bool(project.is_deleted),
        },
        "documents": [
            {"id": str(doc.id), "title": doc.title, "is_deleted": bool(doc.is_deleted)}
            for doc in documents
        ],
    }


async def mock_reachable() -> bool:
    async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
        return (await client.get("http://mock-services:8080/health")).status_code == 200


async def mock_events() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
        response = await client.get("http://mock-services:8080/events")
        response.raise_for_status()
        return list(response.json().get("events") or [])


def read_ledger() -> dict[str, Any]:
    path = LEDGER_DIR / THREAD_ID / "iterations" / "0001.json"
    if not path.exists():
        raise InfrastructureFailure("production iteration ledger was not written")
    return {"path": str(path), "record": json.loads(path.read_text())}


async def run_benchmark() -> dict[str, Any]:
    instruction = os.environ.get("HARBOR_INSTRUCTION", "").strip()
    if instruction != EXPECTED_INSTRUCTION:
        raise InfrastructureFailure("Harbor instruction does not match approved task")

    started = time.monotonic()
    network = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", ""),
        extra_probes={"private_mock_service_reachable": mock_reachable},
    )
    await bootstrap_schema()
    await seed_database()
    initial_db = await database_state()

    from src.services.agent._builders import RECURSION_LIMIT
    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.memory import get_memory_store

    page_context = {
        "type": "project",
        "project_id": str(PROJECT_ID),
        "project_name": "Atlas Long-Run Study",
    }
    state = initial_agent_state(
        instruction,
        THREAD_ID,
        page_context=page_context,
        user_id=str(USER_ID),
        current_project_id=str(PROJECT_ID),
    )
    config = {
        "recursion_limit": RECURSION_LIMIT,
        "configurable": {
            "thread_id": THREAD_ID,
            "user_id": str(USER_ID),
            "organization_id": str(ORG_ID),
            "page_context": page_context,
        },
    }
    graph = compile_agent_graph(
        checkpointer=await get_checkpointer(),
        store=await get_memory_store(),
    )
    update_nodes: list[list[str]] = []

    async def invoke() -> dict[str, Any]:
        async for update in graph.astream(state, config=config, stream_mode="updates"):
            if isinstance(update, dict):
                update_nodes.append(sorted(str(key) for key in update))
        snapshot = await graph.aget_state(config)
        return dict(getattr(snapshot, "values", {}) or {})

    final_state = await asyncio.wait_for(invoke(), timeout=420)
    messages = list(final_state.get("messages") or [])
    final_message = final_assistant_message(messages)
    completed = bool(final_message.get("content")) and not final_message.get(
        "tool_calls"
    )
    compacted = [
        json_safe(message)
        for message in messages
        if getattr(message, "type", None) == "tool"
        and str(getattr(message, "content", "")).startswith("[Compacted]")
    ]

    return {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "source_revision": SOURCE_REVISION,
        "agent_revision": SOURCE_REVISION,
        "instruction": instruction,
        "network_boundary": network,
        "messages": json_safe(messages),
        "raw_tool_executions": json_safe(final_state.get("tool_executions") or []),
        "environment_events": await mock_events(),
        "update_nodes": update_nodes,
        "intent": final_state.get("intent"),
        "intent_confidence": final_state.get("intent_confidence"),
        "tool_loop_count": final_state.get("tool_loop_count"),
        "error_count": final_state.get("error_count"),
        "compaction_count": final_state.get("compaction_count"),
        "compacted_messages": compacted,
        "forced_synthesis_fired": final_state.get("_force_synthesis_fired"),
        "reflection_count": final_state.get("reflection_count"),
        "reflection_result": json_safe(final_state.get("_reflection_result")),
        "pending_confirmation": json_safe(
            final_state.get("pending_confirmation") or {}
        ),
        "iteration_ledger": read_ledger(),
        "final_assistant_message": final_message,
        "termination_reason": "completed" if completed else "incomplete",
        "database": {"initial": initial_db, "final": await database_state()},
        "model_usage": collect_model_usage(messages),
        "notes": "Production research subgraph with a sequential synthetic KB.",
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }


async def async_main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        evidence = await run_benchmark()
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        TRAJECTORY_PATH.write_text(
            json.dumps(
                build_atif_trajectory(evidence, BENCHMARK_ID, THREAD_ID),
                indent=2,
                sort_keys=True,
            )
        )
        print(
            json.dumps(
                {
                    "benchmark_id": BENCHMARK_ID,
                    "termination_reason": evidence["termination_reason"],
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
        (LOG_DIR / "infrastructure-error.json").write_text(json.dumps(error, indent=2))
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
