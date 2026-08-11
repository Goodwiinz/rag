#!/usr/bin/env python3
"""Run the frozen project-skill/HITL benchmark on the production graph."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

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

BENCHMARK_ID = "agent-project-skill-runtime-v1"
SOURCE_REVISION = "ba71044eb99019c1813cd7593838c6f98d35639c"
EXPECTED_INSTRUCTION = (
    "Use the active evidence-note project skill and the document in this project "
    "to create a source-grounded project note about sparse transformer attention."
)
APPROVAL_TEXT = "Yes, create the note."
MAX_APPROVALS = 3

ORG_ID = UUID("00000000-0000-4000-8000-000000003000")
USER_ID = UUID("00000000-0000-4000-8000-000000003001")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000003002")
CONVERSATION_ID = UUID("00000000-0000-4000-8000-000000003003")
THREAD_ID = "00000000-0000-4000-8000-000000003004"
PROJECT_ID = UUID("00000000-0000-4000-8000-000000003010")
DOCUMENT_ID = UUID("00000000-0000-4000-8000-000000003011")
SKILL_ID = UUID("00000000-0000-4000-8000-000000003012")
VERSION_1_ID = UUID("00000000-0000-4000-8000-000000003013")
VERSION_2_ID = UUID("00000000-0000-4000-8000-000000003014")
SCAN_1_ID = UUID("00000000-0000-4000-8000-000000003015")
SCAN_2_ID = UUID("00000000-0000-4000-8000-000000003016")

SOURCE_TEXT = (
    "A controlled sparse-window transformer experiment reduced peak memory by "
    "38 percent while preserving validation accuracy within 0.4 percentage "
    "points. The measurement used 16k-token scientific abstracts. Dense "
    "cross-token reasoning workloads were not evaluated, so the result must not "
    "be generalized to those workloads."
)
VERSION_1 = """---
name: evidence-note
description: Create a source-grounded note with finding, evidence, and uncertainty.
---
Before writing, read the source document in the current project.
Structure the note with exactly these Markdown headings: ## Finding, ## Evidence, and ## Uncertainty.
Under Finding, state the measured benefit without adding outside claims.
Under Evidence, preserve the source's numeric result and measurement context.
Under Uncertainty, state the source's explicit limitation.
"""
VERSION_2 = """---
name: evidence-note
description: Create an executive brief with recommendations and next steps.
---
Write an Executive Brief with headings ## Context, ## Recommendation, and ## Next Steps.
Do not use Finding, Evidence, or Uncertainty headings.
Add a recommendation for production adoption.
"""

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"


async def seed_database() -> None:
    from src.core.database import AsyncSessionLocal
    from src.models import (
        Collection,
        CollectionDocument,
        Conversation,
        Document,
        ProjectSkill,
        ProjectSkillVersion,
        ProjectSkillVersionScan,
        Thread,
    )
    from src.models.document import DocumentType, ProcessingStatus
    from src.models.thread import ThreadStatus

    await seed_tenant(
        ORG_ID,
        USER_ID,
        WORKSPACE_ID,
        name_prefix="Skill Runtime Benchmark",
        email="skill-runtime@example.invalid",
    )
    async with AsyncSessionLocal() as session:
        session.add(
            Collection(
                id=PROJECT_ID,
                workspace_id=WORKSPACE_ID,
                name="Sparse Attention Study",
                description="Synthetic project for frozen skill runtime evaluation.",
                project_type="research",
                research_status="active",
                tags=[],
                is_private=True,
            )
        )
        session.add(
            Document(
                id=DOCUMENT_ID,
                title="Sparse Transformer Attention Evidence",
                filename="sparse-attention.txt",
                file_path=f"/synthetic/{DOCUMENT_ID}.txt",
                file_size_bytes=len(SOURCE_TEXT),
                mime_type="text/plain",
                document_type=DocumentType.TEXT,
                storage_path=f"documents/{ORG_ID}/{DOCUMENT_ID}.txt",
                storage_backend="local",
                processing_status=ProcessingStatus.COMPLETED,
                processing_retry_count=0,
                content_text=SOURCE_TEXT,
                is_embedded=True,
                is_indexed=True,
                is_public=False,
                is_deleted=False,
                organization_id=ORG_ID,
                uploaded_by_user_id=USER_ID,
            )
        )
        session.add(
            CollectionDocument(
                collection_id=PROJECT_ID,
                document_id=DOCUMENT_ID,
                sort_order=0,
            )
        )
        session.add(
            Conversation(
                id=CONVERSATION_ID,
                workspace_id=WORKSPACE_ID,
                title="Frozen skill runtime",
                description="Synthetic benchmark conversation.",
                is_archived=False,
                is_pinned=False,
                created_by_id=USER_ID,
            )
        )
        session.add(
            Thread(
                id=UUID(THREAD_ID),
                conversation_id=CONVERSATION_ID,
                title="Use evidence-note",
                status=ThreadStatus.ACTIVE,
                created_by_id=USER_ID,
                source_project_id=PROJECT_ID,
                message_count=0,
                token_count=0,
            )
        )
        skill = ProjectSkill(
            id=SKILL_ID,
            project_id=PROJECT_ID,
            normalized_name="evidence-note",
            active_version_id=None,
            is_archived=False,
            created_by_id=USER_ID,
        )
        session.add(skill)
        await session.flush()
        session.add_all(
            [
                ProjectSkillVersion(
                    id=VERSION_1_ID,
                    skill_id=SKILL_ID,
                    version=1,
                    instructions=VERSION_1,
                    parsed_name="evidence-note",
                    description=(
                        "Create a source-grounded note with finding, evidence, "
                        "and uncertainty."
                    ),
                    content_hash=sha256(VERSION_1.encode()).hexdigest(),
                    author_id=USER_ID,
                ),
                ProjectSkillVersion(
                    id=VERSION_2_ID,
                    skill_id=SKILL_ID,
                    version=2,
                    instructions=VERSION_2,
                    parsed_name="evidence-note",
                    description=(
                        "Create an executive brief with recommendations and next steps."
                    ),
                    content_hash=sha256(VERSION_2.encode()).hexdigest(),
                    author_id=USER_ID,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                ProjectSkillVersionScan(
                    id=SCAN_1_ID,
                    version_id=VERSION_1_ID,
                    scan_state="passed",
                    findings=[],
                    scanner_version="benchmark-v1",
                    scanned_by_id=USER_ID,
                ),
                ProjectSkillVersionScan(
                    id=SCAN_2_ID,
                    version_id=VERSION_2_ID,
                    scan_state="passed",
                    findings=[],
                    scanner_version="benchmark-v1",
                    scanned_by_id=USER_ID,
                ),
            ]
        )
        skill.active_version_id = VERSION_1_ID
        await session.commit()


async def database_state() -> dict[str, Any]:
    from src.core.database import AsyncSessionLocal
    from src.models import (
        AgentRuntimeSnapshot,
        Document,
        ProjectNote,
        ProjectSkill,
        ProjectSkillVersion,
    )

    async with AsyncSessionLocal() as session:
        skill = await session.get(ProjectSkill, SKILL_ID)
        versions = list(
            (
                await session.scalars(
                    select(ProjectSkillVersion)
                    .where(ProjectSkillVersion.skill_id == SKILL_ID)
                    .order_by(ProjectSkillVersion.version)
                )
            ).all()
        )
        snapshots = list(
            (
                await session.scalars(
                    select(AgentRuntimeSnapshot)
                    .where(AgentRuntimeSnapshot.project_id == PROJECT_ID)
                    .order_by(AgentRuntimeSnapshot.created_at)
                )
            ).all()
        )
        notes = list(
            (
                await session.scalars(
                    select(ProjectNote)
                    .where(ProjectNote.project_id == PROJECT_ID)
                    .order_by(ProjectNote.created_at)
                )
            ).all()
        )
        document = await session.get(Document, DOCUMENT_ID)
    return {
        "skill": {
            "id": str(skill.id),
            "project_id": str(skill.project_id),
            "name": skill.normalized_name,
            "active_version_id": str(skill.active_version_id),
            "is_archived": bool(skill.is_archived),
        },
        "versions": [
            {
                "id": str(row.id),
                "version": row.version,
                "parsed_name": row.parsed_name,
                "description": row.description,
                "instructions": row.instructions,
                "content_hash": row.content_hash,
            }
            for row in versions
        ],
        "snapshots": [
            {
                "id": str(row.id),
                "project_id": str(row.project_id),
                "user_id": str(row.user_id),
                "thread_id": str(row.thread_id),
                "skill_catalog": json_safe(row.skill_catalog),
                "loaded_skill_versions": json_safe(row.loaded_skill_versions),
                "tool_metadata": json_safe(row.tool_metadata),
            }
            for row in snapshots
        ],
        "notes": [
            {
                "id": str(row.id),
                "project_id": str(row.project_id),
                "user_id": str(row.user_id),
                "title": row.title,
                "content": row.content,
                "tags": json_safe(row.tags),
            }
            for row in notes
        ],
        "document": {
            "id": str(document.id),
            "title": document.title,
            "content_text": document.content_text,
            "is_deleted": bool(document.is_deleted),
        },
    }


async def activate_version_2() -> None:
    from src.core.database import AsyncSessionLocal
    from src.models import ProjectSkill

    async with AsyncSessionLocal() as session:
        skill = await session.get(ProjectSkill, SKILL_ID)
        skill.active_version_id = VERSION_2_ID
        await session.commit()


def extract_interrupt(snapshot: Any) -> dict[str, Any] | None:
    for task in getattr(snapshot, "tasks", ()) or ():
        for item in getattr(task, "interrupts", ()) or ():
            if isinstance(getattr(item, "value", None), dict):
                return json_safe(item.value)
    return None


async def collect_updates(
    graph: Any,
    graph_input: Any,
    config: dict[str, Any],
    phase: str,
    updates: list[dict[str, Any]],
) -> None:
    async for event in graph.astream(graph_input, config=config, stream_mode="updates"):
        updates.append(
            {"phase": phase, "observed_at": utc_now(), "update": json_safe(event)}
        )


def hitl_steps(
    steps: list[dict[str, Any]], _evidence: dict[str, Any]
) -> list[dict[str, Any]]:
    if not steps or steps[-1].get("source") != "agent":
        return steps
    if any((step.get("extra") or {}).get("hitl_resume") for step in steps):
        return steps
    if any(
        call.get("function_name") == "create_project_note"
        for call in steps[-1].get("tool_calls") or []
    ):
        return [
            *steps,
            {
                "source": "user",
                "message": APPROVAL_TEXT,
                "extra": {"hitl_resume": {"confirmed": True}},
            },
        ]
    return steps


async def run_benchmark() -> dict[str, Any]:
    started = time.monotonic()
    instruction = os.environ.get("HARBOR_INSTRUCTION", "").strip()
    if instruction != EXPECTED_INSTRUCTION:
        raise InfrastructureFailure("instruction contract drift")

    network_boundary = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", "")
    )
    await bootstrap_schema()
    await seed_database()
    initial_db = await database_state()

    from src.core.database import AsyncSessionLocal
    from src.services.agent._builders import RECURSION_LIMIT
    from src.services.agent.checkpointer import get_checkpointer
    from src.services.agent.graph import compile_agent_graph
    from src.services.agent.memory import get_memory_store
    from src.services.agent.runtime_snapshot import (
        create_runtime_snapshot,
        render_project_skill_catalog,
        runtime_config_fields,
        runtime_state_fields,
    )

    async with AsyncSessionLocal() as session:
        runtime = await create_runtime_snapshot(
            session,
            user_id=USER_ID,
            project_id=PROJECT_ID,
            thread_id=THREAD_ID,
        )
    if not runtime.id or len(runtime.project_skill_catalog) != 1:
        raise InfrastructureFailure("production runtime snapshot was not created")
    snapshot_db = await database_state()
    await activate_version_2()
    activated_db = await database_state()

    checkpointer = await get_checkpointer()
    store = await get_memory_store()
    graph = compile_agent_graph(checkpointer=checkpointer, store=store)
    runtime_config = runtime_config_fields(runtime.id, PROJECT_ID)
    config = {
        "recursion_limit": RECURSION_LIMIT,
        "configurable": {
            "thread_id": THREAD_ID,
            "user_id": str(USER_ID),
            "organization_id": str(ORG_ID),
            "page_context": {
                "type": "project",
                "project_id": str(PROJECT_ID),
                "project_name": "Sparse Attention Study",
            },
            "current_project_id": str(PROJECT_ID),
            **runtime_config,
        },
        "metadata": {
            "benchmark_id": BENCHMARK_ID,
            "source_revision": SOURCE_REVISION,
            "thread_id": THREAD_ID,
        },
    }
    state = initial_agent_state(
        instruction,
        THREAD_ID,
        user_id=str(USER_ID),
        page_context={
            "type": "project",
            "project_id": str(PROJECT_ID),
            "project_name": "Sparse Attention Study",
        },
        **runtime_state_fields(runtime, PROJECT_ID),
    )

    updates: list[dict[str, Any]] = []
    interrupts: list[dict[str, Any]] = []
    before_approval: dict[str, Any] | None = None
    snapshot_id_before_resume = ""
    graph_input: Any = state
    phase = "initial"
    for _ in range(MAX_APPROVALS + 1):
        await collect_updates(graph, graph_input, config, phase, updates)
        checkpoint = await graph.aget_state(config)
        payload = extract_interrupt(checkpoint)
        if payload is None:
            break
        tools = [item for item in payload.get("tools") or [] if isinstance(item, dict)]
        if len(tools) != 1 or tools[0].get("name") != "create_project_note":
            raise InfrastructureFailure(f"unexpected HITL payload: {payload}")
        if len(interrupts) >= MAX_APPROVALS:
            raise InfrastructureFailure(
                f"graph still interrupting after {MAX_APPROVALS} approvals"
            )
        before_approval = await database_state()
        snapshot_id_before_resume = str(
            (getattr(checkpoint, "values", {}) or {}).get("runtime_snapshot_id") or ""
        )
        interrupts.append(
            {
                "tool": "create_project_note",
                "args": json_safe(tools[0].get("args") or {}),
                "approved_at": utc_now(),
            }
        )
        graph_input = Command(resume={"confirmed": True})
        phase = "resume"
    else:
        raise InfrastructureFailure("graph did not settle after HITL resume")

    final_checkpoint = await graph.aget_state(config)
    final_values = dict(getattr(final_checkpoint, "values", {}) or {})
    messages = list(final_values.get("messages") or [])
    tool_executions = list(final_values.get("tool_executions") or [])
    final_db = await database_state()
    final_snapshots = final_db.get("snapshots") or []
    if len(final_snapshots) != 1:
        raise InfrastructureFailure(
            f"expected one final runtime snapshot, observed {len(final_snapshots)}"
        )
    loaded_skill_versions = list(final_snapshots[0].get("loaded_skill_versions") or [])
    pending = extract_interrupt(final_checkpoint)
    termination_reason = (
        "awaiting_confirmation"
        if pending
        else "completed" if not getattr(final_checkpoint, "next", ()) else "incomplete"
    )
    return {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "source_revision": SOURCE_REVISION,
        "agent_revision": SOURCE_REVISION,
        "instruction": instruction,
        "network_boundary": network_boundary,
        "runtime": {
            "snapshot_id": runtime.id,
            "snapshot_id_before_resume": snapshot_id_before_resume,
            "snapshot_id_after_resume": str(
                final_values.get("runtime_snapshot_id") or ""
            ),
            "project_id_before_resume": str(
                final_values.get("current_project_id") or ""
            ),
            "catalog": json_safe(runtime.project_skill_catalog),
            "prompt_catalog": render_project_skill_catalog(
                runtime.project_skill_catalog
            ),
            "tool_names": list(runtime.tool_names),
            "loaded_skill_versions": json_safe(loaded_skill_versions),
        },
        "interrupts": interrupts,
        "interrupt": {
            "count": len(interrupts),
            "tools": [item["tool"] for item in interrupts],
        },
        "approval": {"count": len(interrupts), "text": APPROVAL_TEXT},
        "pending_interrupt_after_resume": pending,
        "database": {
            "initial": initial_db,
            "after_snapshot": snapshot_db,
            "after_activation": activated_db,
            "before_approval": before_approval,
            "final": final_db,
        },
        "updates": updates,
        "raw_tool_executions": json_safe(tool_executions),
        "messages": json_safe(messages),
        "final_assistant_message": final_assistant_message(messages),
        "termination_reason": termination_reason,
        "model_usage": collect_model_usage(messages),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "suppress_observation_for": ["create_project_note"],
        "notes": "Production frozen skill catalog, loader, graph, and HITL over isolated PostgreSQL.",
    }


async def async_main() -> int:
    AGENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        evidence = await run_benchmark()
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True))
        TRAJECTORY_PATH.write_text(
            json.dumps(
                build_atif_trajectory(
                    evidence,
                    BENCHMARK_ID,
                    THREAD_ID,
                    extra_steps_hook=hitl_steps,
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
