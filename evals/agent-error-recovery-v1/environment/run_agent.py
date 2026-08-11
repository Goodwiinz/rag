#!/usr/bin/env python3
"""Run the error-recovery task through the unchanged production graph."""

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

BENCHMARK_ID = "agent-error-recovery-v1"
SOURCE_REVISION = "85c3cc19dbb1c73b19cbb486690c768aa5bd4df0"
EXPECTED_INSTRUCTION = (
    "In the currently open project, summarize both identifiers. First try "
    "00000000-0000-4000-8000-000000001001; if the tool says that is a project "
    "rather than a document, follow its recovery guidance to locate and summarize "
    "the project document. Then try 00000000-0000-4000-8000-0000000010ff; if it "
    "is unavailable, retry that same identifier twice before giving up. Report the "
    "failure honestly and do not invent either summary."
)

ORG_ID = UUID("00000000-0000-4000-8000-000000001000")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000001001")
DOC_ID = UUID("00000000-0000-4000-8000-000000001002")
USER_ID = UUID("00000000-0000-4000-8000-000000001003")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000001004")
MISSING_ID = UUID("00000000-0000-4000-8000-0000000010ff")
THREAD_ID = "00000000-0000-4000-8000-000000001005"
PROJECT_NAME = "Error Recovery Study"
DOC_TITLE = "Sparse Attention Tradeoffs"
DOC_TEXT = (
    "Sparse Attention Tradeoffs. In a controlled 64k-token benchmark, block-sparse "
    "attention reduced peak memory use by 37 percent and improved throughput by 22 "
    "percent compared with full attention. Accuracy on long-range retrieval fell by "
    "2 percentage points. The study used one synthetic scientific corpus, so the "
    "authors caution that the efficiency gains may not generalize to other domains."
)

LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = LOG_DIR / "evidence.json"
TRAJECTORY_PATH = LOG_DIR / "trajectory.json"


async def seed_database() -> None:
    from src.core.database import AsyncSessionLocal
    from src.models.collection import Collection, CollectionDocument
    from src.models.document import Document, DocumentType, ProcessingStatus

    await seed_tenant(
        ORG_ID,
        USER_ID,
        WORKSPACE_ID,
        name_prefix="Benchmark Error Recovery",
        email="benchmark-error-recovery@example.invalid",
    )
    async with AsyncSessionLocal() as session:
        session.add(
            Collection(
                id=PROJECT_ID,
                workspace_id=WORKSPACE_ID,
                name=PROJECT_NAME,
                description="Synthetic project for structured error recovery.",
                project_type="research",
                research_status="active",
                is_deleted=False,
            )
        )
        session.add(
            Document(
                id=DOC_ID,
                title=DOC_TITLE,
                filename="sparse-attention-tradeoffs.txt",
                file_path="/synthetic/sparse-attention-tradeoffs.txt",
                file_size_bytes=len(DOC_TEXT),
                mime_type="text/plain",
                document_type=DocumentType.TEXT,
                storage_path=f"documents/{ORG_ID}/{DOC_ID}.txt",
                storage_backend="local",
                processing_status=ProcessingStatus.COMPLETED,
                processing_retry_count=0,
                content_text=DOC_TEXT,
                document_metadata={"title": DOC_TITLE, "authors": ["Benchmark Team"]},
                is_embedded=True,
                is_indexed=True,
                is_public=False,
                is_deleted=False,
                organization_id=ORG_ID,
                uploaded_by_user_id=USER_ID,
            )
        )
        await session.flush()
        session.add(
            CollectionDocument(
                collection_id=PROJECT_ID,
                document_id=DOC_ID,
                sort_order=0,
            )
        )
        await session.commit()


async def database_state() -> dict[str, Any]:
    from src.core.database import AsyncSessionLocal
    from src.models.collection import Collection
    from src.models.document import Document

    async with AsyncSessionLocal() as session:
        project = await session.scalar(
            select(Collection).where(Collection.id == PROJECT_ID)
        )
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
        "project": (
            {
                "id": str(project.id),
                "workspace_id": str(project.workspace_id),
                "name": project.name,
                "is_deleted": bool(project.is_deleted),
            }
            if project
            else None
        ),
        "documents": [
            {
                "id": str(doc.id),
                "title": doc.title,
                "organization_id": str(doc.organization_id),
                "is_deleted": bool(doc.is_deleted),
            }
            for doc in documents
        ],
        "counts": {"documents": len(documents)},
    }


async def run_benchmark() -> dict[str, Any]:
    instruction = os.environ.get("HARBOR_INSTRUCTION", "").strip()
    if instruction != EXPECTED_INSTRUCTION:
        raise InfrastructureFailure("Harbor instruction does not match approved task")

    started = time.monotonic()
    await bootstrap_schema()
    await seed_database()
    initial_db = await database_state()
    network = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", "")
    )

    from src.services.agent.graph import compile_agent_graph

    page_context = {
        "type": "project",
        "project_id": str(PROJECT_ID),
        "project_name": PROJECT_NAME,
    }
    state = initial_agent_state(
        instruction,
        THREAD_ID,
        page_context=page_context,
        user_id=str(USER_ID),
        current_project_id=str(PROJECT_ID),
    )
    config = {
        "recursion_limit": 50,
        "configurable": {
            "thread_id": THREAD_ID,
            "user_id": str(USER_ID),
            "organization_id": str(ORG_ID),
            "page_context": page_context,
        },
    }
    graph = compile_agent_graph()
    final_state = await asyncio.wait_for(
        graph.ainvoke(state, config=config), timeout=330
    )
    messages = list(final_state.get("messages") or [])
    final_message = final_assistant_message(messages)
    completed = bool(final_message.get("content")) and not final_message.get(
        "tool_calls"
    )

    return {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "source_revision": SOURCE_REVISION,
        "agent_revision": SOURCE_REVISION,
        "instruction": instruction,
        "synthetic_actor": {
            "organization_id": str(ORG_ID),
            "user_id": str(USER_ID),
            "workspace_id": str(WORKSPACE_ID),
            "project_id": str(PROJECT_ID),
            "document_id": str(DOC_ID),
            "missing_document_id": str(MISSING_ID),
            "thread_id": THREAD_ID,
        },
        "network_boundary": network,
        "messages": json_safe(messages),
        "raw_tool_executions": json_safe(final_state.get("tool_executions") or []),
        "intent": final_state.get("intent"),
        "intent_confidence": final_state.get("intent_confidence"),
        "error_count": final_state.get("error_count"),
        "last_error": final_state.get("last_error"),
        "last_error_info": json_safe(final_state.get("last_error_info") or {}),
        "tool_loop_count": final_state.get("tool_loop_count"),
        "final_assistant_message": final_message,
        "termination_reason": "completed" if completed else "incomplete",
        "database": {"initial": initial_db, "final": await database_state()},
        "model_usage": collect_model_usage(messages),
        "notes": "Unchanged production graph with isolated synthetic document state.",
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
