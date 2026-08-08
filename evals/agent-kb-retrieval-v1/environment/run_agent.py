#!/usr/bin/env python3
"""Run the KB-retrieval benchmark against the production LangGraph graph.

The instruction asks for a single research-subgraph turn covering two
RESEARCH-bound tools in order: ``search_documents`` (title/filename search
over Postgres) then ``do_kb_retrieve`` (semantic retrieval against the mock
DO Knowledge Base). Both tools are bound to the RESEARCH subgraph -- see the
routing spike recorded in ``evals/specs/agent-kb-retrieval-v1/harness.md``:
``do_kb_retrieve`` is research-subgraph-only with empty intents and
``exposed_in_all_tools=False`` (never reachable from WRITING/GENERAL, where
``summarize_document`` lives), so this task deliberately scopes to the
research-reachable pair and leaves ``summarize_document`` for a later task.

Neither tool is destructive, so there is no HITL interrupt to drive here
(unlike ``agent-writing-flow-v1``'s ``create_draft``).
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

import httpx

from evals.harbor_common.db import bootstrap_schema, initial_agent_state, seed_tenant
from evals.harbor_common.envelope import InfrastructureFailure
from evals.harbor_common.network import validate_network_boundary
from evals.harbor_common.serialization import json_safe, utc_now
from evals.harbor_common.trajectory import (
    build_atif_trajectory,
    collect_model_usage,
    final_assistant_message,
)

BENCHMARK_ID = "agent-kb-retrieval-v1"
SOURCE_REVISION = "b67ebbf1b067d5f5b1e74299535244e58df41a68"
AGENT_REVISION = "b67ebbf1b067d5f5b1e74299535244e58df41a68"
EXPECTED_INSTRUCTION = (
    'Search my documents for a file titled "API Rate Limit Policy" to confirm '
    "we have it on file, then use the organization knowledge base to retrieve "
    "the current guidance on API rate limits and summarize it, citing the "
    "source."
)
DOC1_TITLE = "API Rate Limit Policy"
DOC2_TITLE = "Webhook Retry Policy"
SUCCESS_MILESTONE_TOOLS = ("search_documents", "do_kb_retrieve")

ORG_ID = UUID("00000000-0000-4000-8000-000000000701")
USER_ID = UUID("00000000-0000-4000-8000-000000000702")
WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000703")
DOC1_ID = UUID("00000000-0000-4000-8000-000000000704")
DOC2_ID = UUID("00000000-0000-4000-8000-000000000705")
THREAD_ID = "00000000-0000-4000-8000-000000000706"
KB_UUID = "benchmark-kb-0701"

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"
KB_FIXTURE_PATH = Path("/benchmark/kb-fixtures.json")

DOC1_TEXT = (
    "API Rate Limit Policy. Effective 2026, API requests are limited to 120 "
    "requests per minute per API key. Requests beyond the limit receive HTTP "
    "429 with a Retry-After header. Limits are enforced per organization, "
    "not per user."
)
DOC2_TEXT = (
    "Webhook Retry Policy. Webhook deliveries are retried up to 3 times with "
    "exponential backoff starting at 30 seconds. This policy governs "
    "delivery retries only and does not define API request rate limits."
)


async def seed_database() -> None:
    """Seed the tenant triple, KB-provisioned org, and the two seeded documents."""
    from src.core.database import AsyncSessionLocal
    from src.models.document import Document, DocumentType, ProcessingStatus
    from src.models.organization import Organization

    await seed_tenant(
        org_id=ORG_ID,
        user_id=USER_ID,
        workspace_id=WORKSPACE_ID,
        name_prefix="Benchmark KB Retrieval",
        email="benchmark-kb-retrieval@example.invalid",
    )
    async with AsyncSessionLocal() as session:
        organization = await session.get(Organization, ORG_ID)
        if organization is None:
            raise InfrastructureFailure("seed_tenant did not create the organization")
        organization.do_kb_uuid = KB_UUID
        for doc_id, title, text in (
            (DOC1_ID, DOC1_TITLE, DOC1_TEXT),
            (DOC2_ID, DOC2_TITLE, DOC2_TEXT),
        ):
            session.add(
                Document(
                    id=doc_id,
                    title=title,
                    filename=f"{title}.txt",
                    file_path=f"/synthetic/{doc_id}.txt",
                    file_size_bytes=len(text),
                    mime_type="text/plain",
                    document_type=DocumentType.TEXT,
                    storage_path=f"documents/{ORG_ID}/{doc_id}.txt",
                    storage_backend="local",
                    processing_status=ProcessingStatus.COMPLETED,
                    processing_retry_count=0,
                    content_text=text,
                    is_embedded=True,
                    is_indexed=True,
                    is_public=False,
                    is_deleted=False,
                    organization_id=ORG_ID,
                    uploaded_by_user_id=USER_ID,
                )
            )
        await session.commit()


async def database_state() -> dict[str, Any]:
    """Raw org / document rows for the synthetic tenant."""
    from sqlalchemy import select

    from src.core.database import AsyncSessionLocal
    from src.models.document import Document
    from src.models.organization import Organization

    async with AsyncSessionLocal() as session:
        organization = await session.get(Organization, ORG_ID)
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
        "documents": [
            {
                "id": str(row.id),
                "title": row.title,
                "organization_id": str(row.organization_id),
                "is_deleted": bool(row.is_deleted),
            }
            for row in documents
        ],
        "counts": {"documents": len(documents)},
    }


async def mock_service_reachable() -> bool:
    """Direct (non-proxied) reachability probe -- the private-network gate.

    ``trust_env=False`` bypasses HTTPS_PROXY/HTTP_PROXY: the mock host is on
    ``benchmark-internal`` only (no ``egress-public`` attachment), so this
    connects directly rather than through Squid.
    """
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get("http://mock-services:8080/health")
            return response.status_code == 200
    except httpx.HTTPError as exc:
        raise InfrastructureFailure(
            f"mock-service preflight failed: {type(exc).__name__}"
        ) from exc


async def environment_events() -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get("http://mock-services:8080/events")
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise InfrastructureFailure(
            f"mock-service evidence unavailable: {type(exc).__name__}"
        ) from exc
    events = payload.get("events")
    if not isinstance(events, list):
        raise InfrastructureFailure("mock-service evidence has invalid shape")
    return events


def record_milestone(
    milestones: list[dict[str, Any]], sequence: list[int], name: str
) -> None:
    sequence[0] += 1
    milestones.append(
        {"milestone": name, "sequence": sequence[0], "observed_at": utc_now()}
    )


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


async def run_benchmark() -> dict[str, Any]:
    started_at = utc_now()
    started = time.monotonic()
    instruction = os.environ.get("HARBOR_INSTRUCTION", "").strip()
    if instruction != EXPECTED_INSTRUCTION:
        raise InfrastructureFailure(
            f"instruction contract drift: expected {EXPECTED_INSTRUCTION!r}"
        )

    network_boundary = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", ""),
        extra_probes={"private_mock_service_reachable": mock_service_reachable},
    )
    await bootstrap_schema()
    await seed_database()
    before = await database_state()
    if before["kb_uuid"] != KB_UUID:
        raise InfrastructureFailure("database reset failed: org KB uuid is missing")
    seeded_titles = sorted(row["title"] for row in before["documents"])
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

    graph_input = initial_agent_state(instruction, THREAD_ID, user_id=str(USER_ID))
    async for event in graph.astream(graph_input, config=config, stream_mode="updates"):
        sequence[0] += 1
        events.append(
            {
                "sequence": sequence[0],
                "observed_at": utc_now(),
                "update": json_safe(event),
            }
        )

    final_snapshot = await graph.aget_state(config)
    final_values = dict(getattr(final_snapshot, "values", {}) or {})
    pending_interrupt = None
    for task in getattr(final_snapshot, "tasks", ()) or ():
        for item in getattr(task, "interrupts", ()) or ():
            payload = getattr(item, "value", None)
            if isinstance(payload, dict):
                pending_interrupt = json_safe(payload)

    messages = list(final_values.get("messages") or [])
    tool_executions = list(final_values.get("tool_executions") or [])
    for tool_name in SUCCESS_MILESTONE_TOOLS:
        if tool_succeeded(tool_executions, tool_name):
            record_milestone(milestones, sequence, f"{tool_name}_success")

    after = await database_state()
    service_events = await environment_events()
    final_message = final_assistant_message(messages)
    if final_message:
        record_milestone(milestones, sequence, "final_assistant_message")

    termination_reason = (
        "awaiting_confirmation"
        if pending_interrupt is not None
        else "completed" if not getattr(final_snapshot, "next", ()) else "incomplete"
    )

    kb_fixture = json.loads(KB_FIXTURE_PATH.read_text())
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
            "doc1_id": str(DOC1_ID),
            "doc1_title": DOC1_TITLE,
            "doc2_id": str(DOC2_ID),
            "doc2_title": DOC2_TITLE,
            "kb_uuid": KB_UUID,
        },
        "network_boundary": network_boundary,
        "classification": {
            "intent": final_values.get("intent"),
            "confidence": final_values.get("intent_confidence"),
            "source_probe": getattr(classification_probe, "source", None),
            "probe_reasoning": getattr(classification_probe, "reasoning", None),
        },
        "plan": json_safe(final_values.get("plan") or []),
        "pending_interrupt": pending_interrupt,
        "database": {
            "bootstrap": "src.models.Base.metadata.create_all",
            "initial": before,
            "after": after,
        },
        "kb_fixture": kb_fixture,
        "tool_executions": summarize_tool_executions(tool_executions),
        "raw_tool_executions": json_safe(tool_executions),
        "messages": json_safe(messages),
        "events": events,
        "environment_events": service_events,
        "milestones": milestones,
        "notes": (
            "Production graph with an isolated database and a mock DO "
            "Knowledge Base retrieve endpoint; no destructive tool is in "
            "scope, so no HITL interrupt is expected."
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
            from src.services.do_kb import get_do_kb_client

            await get_do_kb_client().aclose()
        except Exception:
            pass
        try:
            from src.services.agent._pool_utils import close_shared_langgraph_pool

            await close_shared_langgraph_pool()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
