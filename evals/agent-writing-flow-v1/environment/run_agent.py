#!/usr/bin/env python3
"""Run the writing-flow benchmark against the production LangGraph graph.

The instruction asks for a single writing-subgraph turn covering three
WRITING-bound tools in order: ``compare_documents`` (read-only), ``create_draft``
(DESTRUCTIVE -> one HITL interrupt+approval), and ``export_bibliography``
(read-only). All three tools are bound to the WRITING subgraph, so a
writing-routed turn reaches every one of them -- there is no routing risk here
(unlike a task that spans subgraphs).

``create_draft`` is asynchronous: ``DraftGenerationService.generate_draft``
fires a background task and returns a ``task_id`` immediately, it does not
return a completed draft. The adapter records a database snapshot *before*
sending the HITL approval so the verifier can prove no ``generated_drafts`` row
existed prior to approval, without asserting a synchronous completed draft.
"""

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

BENCHMARK_ID = "agent-writing-flow-v1"
SOURCE_REVISION = "ecc30ede203061b9440cbab1d2cfad23fa9abf1c"
AGENT_REVISION = "ecc30ede203061b9440cbab1d2cfad23fa9abf1c"
APPROVAL_TEXT = "Yes, go ahead."
EXPECTED_INSTRUCTION = (
    "In the currently open project, compare the two documents titled "
    '"Graph Neural Networks for Molecular Property Prediction" and '
    '"Attention Mechanisms in Transformer Architectures", then create a '
    'literature review draft on the theme "neural architectures for '
    'scientific discovery", and finally export the bibliography for both '
    "documents in IEEE format."
)
EXPECTED_PROJECT_NAME = "Tool Coverage Writing Study"
DOC1_TITLE = "Graph Neural Networks for Molecular Property Prediction"
DOC2_TITLE = "Attention Mechanisms in Transformer Architectures"

# The one write the graph must pause on.
EXPECTED_DESTRUCTIVE_TOOLS = ("create_draft",)
# Non-destructive tools whose successful execution is recorded as a
# `<tool>_success` milestone alongside the destructive one.
SUCCESS_MILESTONE_TOOLS = (
    ("compare_documents",) + EXPECTED_DESTRUCTIVE_TOOLS + ("export_bibliography",)
)
# One resume per expected interrupt, plus headroom for a re-fired interrupt on
# resume; the loop is bounded so a graph that never settles cannot hang here.
MAX_RESUMES = 4

ORG_ID = UUID("00000000-0000-4000-8000-000000000601")
USER_ID = UUID("00000000-0000-4000-8000-000000000602")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000603")
PROJECT_ID = UUID("00000000-0000-4000-8000-000000000604")
DOC1_ID = UUID("00000000-0000-4000-8000-000000000605")
DOC2_ID = UUID("00000000-0000-4000-8000-000000000606")
THREAD_ID = "00000000-0000-4000-8000-000000000607"

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"

DOC1_TEXT = (
    "Graph Neural Networks for Molecular Property Prediction. This survey "
    "reviews message-passing graph neural networks applied to molecular "
    "property prediction, covering atom/bond featurization, permutation-"
    "invariant aggregation, and benchmark results on quantum-chemistry "
    "datasets. Key theme: structured relational inductive bias improves "
    "sample efficiency over sequence-based encodings for molecules."
)
DOC2_TEXT = (
    "Attention Mechanisms in Transformer Architectures. This survey reviews "
    "scaled dot-product self-attention and multi-head attention in "
    "transformer architectures, covering positional encoding schemes and "
    "the quadratic cost of full sequence attention. Key theme: learned, "
    "content-dependent weighting outperforms fixed convolutional receptive "
    "fields for long-range dependencies in sequences."
)


async def seed_database() -> None:
    """Seed the tenant triple, one project, and the two seeded documents."""
    from src.core.database import AsyncSessionLocal
    from src.models.collection import Collection, CollectionDocument
    from src.models.document import Document, DocumentType, ProcessingStatus

    await seed_tenant(
        org_id=ORG_ID,
        user_id=USER_ID,
        workspace_id=WORKSPACE_ID,
        name_prefix="Benchmark Writing",
        email="benchmark-writing@example.invalid",
    )
    async with AsyncSessionLocal() as session:
        session.add(
            Collection(
                id=PROJECT_ID,
                workspace_id=WORKSPACE_ID,
                name=EXPECTED_PROJECT_NAME,
                description="Synthetic project for the writing-flow benchmark.",
                project_type="research",
                research_status="active",
                is_deleted=False,
            )
        )
        for doc_id, title, text, year, doi in (
            (
                DOC1_ID,
                DOC1_TITLE,
                DOC1_TEXT,
                2021,
                "10.1000/benchmark-gnn",
            ),
            (
                DOC2_ID,
                DOC2_TITLE,
                DOC2_TEXT,
                2022,
                "10.1000/benchmark-attn",
            ),
        ):
            session.add(
                Document(
                    id=doc_id,
                    title=title,
                    filename=f"{doc_id}.txt",
                    file_path=f"/synthetic/{doc_id}.txt",
                    file_size_bytes=len(text),
                    mime_type="text/plain",
                    document_type=DocumentType.TEXT,
                    storage_path=f"documents/{ORG_ID}/{doc_id}.txt",
                    storage_backend="local",
                    processing_status=ProcessingStatus.COMPLETED,
                    processing_retry_count=0,
                    content_text=text,
                    document_metadata={
                        "title": title,
                        "authors": ["Benchmark Author"],
                        "publication_date": f"{year}-01-01",
                        "doi": doi,
                    },
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
                    collection_id=PROJECT_ID, document_id=DOC1_ID, sort_order=0
                ),
                CollectionDocument(
                    collection_id=PROJECT_ID, document_id=DOC2_ID, sort_order=1
                ),
            ]
        )
        await session.commit()


async def database_state() -> dict[str, Any]:
    """Raw project / document / generated-draft rows for the synthetic tenant."""
    from src.core.database import AsyncSessionLocal
    from src.models.collection import Collection, CollectionDocument
    from src.models.document import Document
    from src.models.generated_draft import GeneratedDraft

    async with AsyncSessionLocal() as session:
        project_row = (
            await session.execute(select(Collection).where(Collection.id == PROJECT_ID))
        ).scalar_one_or_none()
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
        links = list(
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
        drafts = list(
            (
                await session.execute(
                    select(GeneratedDraft)
                    .where(GeneratedDraft.project_id == PROJECT_ID)
                    .order_by(GeneratedDraft.created_at, GeneratedDraft.id)
                )
            )
            .scalars()
            .all()
        )
    return {
        "workspace_id": str(WORKSPACE_ID),
        "project": (
            {
                "id": str(project_row.id),
                "workspace_id": str(project_row.workspace_id),
                "name": project_row.name,
                "is_deleted": bool(project_row.is_deleted),
            }
            if project_row is not None
            else None
        ),
        "documents": [
            {
                "id": str(row.id),
                "title": row.title,
                "organization_id": str(row.organization_id),
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
        "generated_drafts": [
            {
                "id": str(row.id),
                "project_id": str(row.project_id),
                "title": row.title,
                "is_current": bool(row.is_current),
            }
            for row in drafts
        ],
        "counts": {
            "documents": len(documents),
            "collection_documents": len(links),
            "generated_drafts": len(drafts),
        },
    }


def extract_interrupt(snapshot: Any) -> dict[str, Any] | None:
    for task in getattr(snapshot, "tasks", ()) or ():
        for item in getattr(task, "interrupts", ()) or ():
            payload = getattr(item, "value", None)
            if isinstance(payload, dict):
                return json_safe(payload)
    return None


def interrupt_tools(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return the ``[{"name": ..., "args": {...}}]`` block of an interrupt."""
    if not payload:
        return []
    tools = payload.get("tools")
    if isinstance(tools, list):
        return [tool for tool in tools if isinstance(tool, dict)]
    return []


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


def hitl_steps(steps: list[dict[str, Any]], evidence: dict[str, Any]) -> list[Any]:
    """Splice the harness-supplied HITL approval turn into the trajectory.

    The approval is sent by this adapter via ``Command(resume=...)`` and so has
    no message of its own. Called after every agent step and once after the
    loop; both passes must be idempotent, hence the "did this step already get
    its approval" guard and the terminal-pass detection below.
    """
    if steps and steps[-1].get("source") == "agent":
        approved = [
            call.get("function_name")
            for call in steps[-1].get("tool_calls") or []
            if call.get("function_name") in EXPECTED_DESTRUCTIVE_TOOLS
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

    injected = [step for step in steps if (step.get("extra") or {}).get("hitl_resume")]
    expected = sum(
        1
        for message in evidence.get("messages") or []
        if message.get("type") in {"human", "ai"}
    )
    derived = sum(
        1
        for step in steps
        if step.get("source") == "agent"
        or (
            step.get("source") == "user"
            and not (step.get("extra") or {}).get("hitl_resume")
        )
    )
    if derived >= expected and not injected:
        if not (steps and steps[-1].get("source") == "system"):
            return steps + [
                {"source": "system", "message": "No HITL approval was observed."}
            ]
    return steps


async def drive_graph(
    graph: Any,
    config: dict[str, Any],
    instruction: str,
    events: list[dict[str, Any]],
    sequence: list[int],
    milestones: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Stream the graph, approving the HITL interrupt as it is observed.

    Returns ``(interrupts, database_reads)`` where every interrupt records the
    tool and arguments the graph paused on plus the timestamp of its approval.
    """
    interrupts: list[dict[str, Any]] = []
    database_reads: list[dict[str, Any]] = []

    graph_input: Any = initial_agent_state(instruction, THREAD_ID, user_id=str(USER_ID))
    phase = "initial"
    for resume_index in range(MAX_RESUMES + 1):
        await collect_updates(graph, graph_input, config, phase, events, sequence)
        snapshot = await graph.aget_state(config)
        payload = extract_interrupt(snapshot)
        if payload is None:
            return interrupts, database_reads

        if resume_index >= MAX_RESUMES:
            raise InfrastructureFailure(
                f"graph still interrupting after {MAX_RESUMES} approvals"
            )

        tools = interrupt_tools(payload)
        for tool in tools:
            record_milestone(
                milestones, sequence, f"interrupt:{tool.get('name') or 'unknown'}"
            )
        # Read the database *before* approving so the verifier can prove no
        # draft was enqueued ahead of its own approval.
        database_reads.append(
            {
                "phase": f"before_approval:{resume_index + 1}",
                "observed_at": utc_now(),
                "state": await database_state(),
            }
        )
        approved_at = utc_now()
        for tool in tools:
            name = tool.get("name") or "unknown"
            interrupts.append(
                {
                    "tool": name,
                    "args": json_safe(tool.get("args") or {}),
                    "approved_at": approved_at,
                }
            )
            record_milestone(milestones, sequence, f"approval:{name}")
        if not tools:
            interrupts.append(
                {
                    "tool": None,
                    "args": {},
                    "approved_at": approved_at,
                    "payload": payload,
                }
            )
            record_milestone(milestones, sequence, "approval:unknown")

        graph_input = Command(resume={"confirmed": True})
        phase = f"resume:{resume_index + 1}"

    return interrupts, database_reads


def summarize_tool_executions(tool_executions: list[Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for item in tool_executions:
        if not isinstance(item, dict):
            continue
        result = item.get("result")
        summary.append(
            {
                "tool": item.get("tool_name"),
                "status": item.get("status"),
                "result_keys": (
                    sorted(result.keys()) if isinstance(result, dict) else []
                ),
            }
        )
    return summary


def tool_succeeded(tool_executions: list[Any], tool_name: str) -> bool:
    for item in tool_executions:
        if not isinstance(item, dict) or item.get("tool_name") != tool_name:
            continue
        if item.get("status") not in {"completed", "success"}:
            continue
        result = item.get("result")
        if isinstance(result, dict) and result.get("error"):
            continue
        return True
    return False


async def run_benchmark() -> dict[str, Any]:
    started_at = utc_now()
    started = time.monotonic()
    instruction = os.environ.get("HARBOR_INSTRUCTION", "").strip()
    if instruction != EXPECTED_INSTRUCTION:
        raise InfrastructureFailure(
            f"instruction contract drift: expected {EXPECTED_INSTRUCTION!r}"
        )

    # Dedicated preflight: the fixed probes block the event loop for up to
    # ~22s, so this never runs concurrently with the graph.
    network_boundary = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", "")
    )
    await bootstrap_schema()
    await seed_database()
    before_initial = await database_state()
    if before_initial["project"] is None:
        raise InfrastructureFailure("database reset failed: seeded project is missing")
    if before_initial["counts"]["generated_drafts"]:
        raise InfrastructureFailure(
            "database reset failed: generated_drafts rows exist before run"
        )
    seeded_titles = sorted(row["title"] for row in before_initial["documents"])
    if seeded_titles != sorted([DOC1_TITLE, DOC2_TITLE]):
        raise InfrastructureFailure(
            f"seed failed: expected exactly the two seed documents, got {seeded_titles}"
        )

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
            # The instruction says "the currently open project" -- mirror the
            # frontend's page-context contract so create_draft resolves
            # project_id without the model having to fabricate the UUID.
            "page_context": {"type": "project", "project_id": str(PROJECT_ID)},
            "runtime_snapshot_id": "",
            "current_project_id": str(PROJECT_ID),
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

    interrupts, database_reads = await drive_graph(
        graph, config, instruction, events, sequence, milestones
    )

    final_snapshot = await graph.aget_state(config)
    final_values = dict(getattr(final_snapshot, "values", {}) or {})
    pending_interrupt = extract_interrupt(final_snapshot)

    messages = list(final_values.get("messages") or [])
    tool_executions = list(final_values.get("tool_executions") or [])
    for tool_name in SUCCESS_MILESTONE_TOOLS:
        if tool_succeeded(tool_executions, tool_name):
            record_milestone(milestones, sequence, f"{tool_name}_success")

    after = await database_state()
    final_message = final_assistant_message(messages)
    if final_message:
        record_milestone(milestones, sequence, "final_assistant_message")

    termination_reason = (
        "awaiting_confirmation"
        if pending_interrupt is not None
        else "completed" if not getattr(final_snapshot, "next", ()) else "incomplete"
    )
    return {
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
            "project_id": str(PROJECT_ID),
            "expected_project_name": EXPECTED_PROJECT_NAME,
            "doc1_id": str(DOC1_ID),
            "doc1_title": DOC1_TITLE,
            "doc2_id": str(DOC2_ID),
            "doc2_title": DOC2_TITLE,
        },
        "network_boundary": network_boundary,
        "classification": {
            "intent": final_values.get("intent"),
            "confidence": final_values.get("intent_confidence"),
            "source_probe": getattr(classification_probe, "source", None),
            "probe_reasoning": getattr(classification_probe, "reasoning", None),
        },
        "plan": json_safe(final_values.get("plan") or []),
        "interrupts": interrupts,
        # ``harbor_common.trajectory`` copies the singular ``interrupt`` key
        # straight into ``extra``.  Publish a truthful summary alias of
        # ``interrupts`` so the shipped trajectory never records ``null`` for a
        # run that actually paused for human approval.
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
            "before_approvals": database_reads,
            "after": after,
        },
        "tool_executions": summarize_tool_executions(tool_executions),
        "raw_tool_executions": json_safe(tool_executions),
        "messages": json_safe(messages),
        "events": events,
        "milestones": milestones,
        "suppress_observation_for": list(EXPECTED_DESTRUCTIVE_TOOLS),
        "notes": (
            "Production graph with an isolated database and one post-interrupt "
            "approval for create_draft."
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
