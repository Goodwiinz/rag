#!/usr/bin/env python3
"""Drive the 12-probe tenant-isolation matrix against production read tools.

Seeds two disjoint organizations (org A holds fixture content, org B is the
attacking tenant), then for every declared read tool/node calls the
production implementation once as org A's own user (to prove there is
something to leak) and once as org B's user with the identical query
parameters (org A's real, just-seeded id where the tool takes an id). See
``evals/specs/agent-tenant-isolation-v1/{task.md,harness.md}`` for the full
probe-by-probe contract and the anti-false-pass rationale.

Two-org seeding follows the disjoint-second-org shape plan 3's
``agent-knowledge-graph-flow-v1`` established (``OTHER_ORG_ID``): org B gets
its own organization/user/workspace rows and zero content that shadows org
A's fixtures.
"""

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

from evals.harbor_common.db import bootstrap_schema, seed_tenant
from evals.harbor_common.envelope import InfrastructureFailure
from evals.harbor_common.network import validate_network_boundary
from evals.harbor_common.serialization import json_safe, utc_now

BENCHMARK_ID = "agent-tenant-isolation-v1"
SOURCE_REVISION = "deab258b29c4c4005d0178a04c1aadce44f7a3bd"
AGENT_REVISION = SOURCE_REVISION

# Org A -- the victim tenant.
ORG_A_ID = UUID("00000000-0000-4000-8000-000000000801")
USER_A_ID = UUID("00000000-0000-4000-8000-000000000802")
WORKSPACE_A_ID = UUID("00000000-0000-4000-8000-000000000803")

# Org B -- the attacking tenant. Disjoint ids, no shadow content, mirroring
# plan 3's agent-knowledge-graph-flow-v1 OTHER_ORG_ID pattern.
ORG_B_ID = UUID("00000000-0000-4000-8000-000000000810")
USER_B_ID = UUID("00000000-0000-4000-8000-000000000811")
WORKSPACE_B_ID = UUID("00000000-0000-4000-8000-000000000812")

DOCUMENT_TITLE = "Org A Confidential Report"
DOCUMENT_FILENAME = "org-a-confidential-report.pdf"
PROJECT_NAME = "Org A Research Project"
ENTITY_1_NAME = "Org A Principal Investigator"
ENTITY_2_NAME = "Org A Research Lab"
MEMORY_FRAGMENT = "org-a-eyes-only-budget-figure"
MEMORY_KEY = "tenant-isolation-benchmark-memory"
SKILL_NAME = "tenant-isolation-check"
SKILL_INSTRUCTIONS = "Return only tenant-scoped project information."
SKILL_ID = UUID("00000000-0000-4000-8000-0000000008a3")
SKILL_VERSION_ID = UUID("00000000-0000-4000-8000-0000000008a4")
SKILL_SCAN_ID = UUID("00000000-0000-4000-8000-0000000008a5")

AGENT_LOG_DIR = Path("/logs/agent")
EVIDENCE_PATH = AGENT_LOG_DIR / "evidence.json"
TRAJECTORY_PATH = AGENT_LOG_DIR / "trajectory.json"

# The 12-probe declared surface -- kept in exact 1:1 sync with the table in
# evals/specs/agent-tenant-isolation-v1/task.md. Order is the run order
# (the "same trial batch" gate).
DECLARED_PROBES = (
    "documents.search_documents",
    "documents.summarize_document",
    "documents.compare_documents",
    "projects.list_projects",
    "projects.list_project_documents",
    "knowledge_graph.search_knowledge_graph",
    "knowledge_graph.explore_entity_neighborhood",
    "knowledge_graph.find_entity_paths",
    "knowledge_graph.get_graph_stats",
    "memory.memory_retrieval_node",
    "suggestions.load_project_skill",
    "rag.rag_node",
)


class _FakeUser:
    """Minimal duck-typed stand-in for ``src.models.user.User``.

    The probed tool implementations only read ``.id`` and
    ``.organization_id`` off the passed ``current_user`` -- never ORM
    relationship attributes -- so a plain attribute holder is sufficient and
    keeps this harness independent of a second live session per probe.
    """

    def __init__(self, user_id: UUID, organization_id: UUID) -> None:
        self.id = user_id
        self.organization_id = organization_id


# ---------------------------------------------------------------------------
# seeding
# ---------------------------------------------------------------------------
async def seed_orgs() -> None:
    await seed_tenant(
        org_id=ORG_A_ID,
        user_id=USER_A_ID,
        workspace_id=WORKSPACE_A_ID,
        name_prefix="Tenant Isolation Org A",
        email="tenant-isolation-org-a@example.invalid",
    )
    await seed_tenant(
        org_id=ORG_B_ID,
        user_id=USER_B_ID,
        workspace_id=WORKSPACE_B_ID,
        name_prefix="Tenant Isolation Org B",
        email="tenant-isolation-org-b@example.invalid",
    )


async def seed_org_a_fixture() -> dict[str, str]:
    """Seed exactly one of each fixture kind under org A. Returns minted ids."""
    from src.core.database import AsyncSessionLocal
    from src.models.collection import Collection, CollectionDocument
    from src.models.document import Document, DocumentType, ProcessingStatus

    document_id = UUID("00000000-0000-4000-8000-0000000008a1")
    project_id = UUID("00000000-0000-4000-8000-0000000008a2")

    async with AsyncSessionLocal() as session:
        session.add(
            Document(
                id=document_id,
                title=DOCUMENT_TITLE,
                filename=DOCUMENT_FILENAME,
                file_path=f"/tmp/nous-benchmark-storage/{DOCUMENT_FILENAME}",
                file_size_bytes=1024,
                mime_type="application/pdf",
                document_type=DocumentType.PDF,
                processing_status=ProcessingStatus.COMPLETED,
                content_text=(
                    "This report tells readers about Org A confidential budget figures."
                ),
                organization_id=ORG_A_ID,
                uploaded_by_user_id=USER_A_ID,
            )
        )
        session.add(
            Collection(
                id=project_id,
                workspace_id=WORKSPACE_A_ID,
                name=PROJECT_NAME,
                description="Seeded fixture project for tenant-isolation probes.",
            )
        )
        await session.flush()
        from src.services.search.fulltext_search_service import fulltext_search_service

        await fulltext_search_service.async_update_document_search_vectors(
            [document_id], session
        )
        session.add(
            CollectionDocument(collection_id=project_id, document_id=document_id)
        )
        await session.commit()

    entity_ids = await seed_org_a_graph()

    from src.services.agent.memory import get_memory_store, save_memory

    store = await get_memory_store()
    if store is None:
        raise InfrastructureFailure("memory store unavailable during org-A seed")
    await save_memory(
        store,
        str(USER_A_ID),
        MEMORY_KEY,
        {
            "query": f"budget planning note: {MEMORY_FRAGMENT}",
            "intent": "general",
            "tools_used": [],
            "thread_id": "seed",
            "turn_index": 0,
        },
    )

    skill = await seed_org_a_skill(project_id)

    return {
        "document_id": str(document_id),
        "project_id": str(project_id),
        "entity_id": entity_ids["entity_1"],
        "entity_id_2": entity_ids["entity_2"],
        "memory_fragment": MEMORY_FRAGMENT,
        **skill,
    }


def leak_vocabulary() -> list[str]:
    """Every human-readable org-A identifier gate 2 must never see leaked.

    Kept separate from ``seed`` (which holds the *ids* probes use to build
    their queries) on purpose: this list exists only to feed
    ``tests/verify.py``'s cross-tenant-identifier check, so its shape can
    stay "flat list of literal strings" instead of tracking the id dict's
    per-fixture-kind keys. See ``task.md`` Gate 2 and
    ``tests/verify.py:seed_identifier_tokens`` for the matching rule (whole-
    value substring match, tokens under 6 characters ignored to avoid
    common-word false positives).
    """
    return [
        DOCUMENT_TITLE,
        DOCUMENT_FILENAME,
        PROJECT_NAME,
        ENTITY_1_NAME,
        ENTITY_2_NAME,
    ]


def _seed_org_a_graph_sync() -> dict[str, str]:
    from src.models.graph import (
        CreateEntityRequest,
        CreateRelationshipRequest,
        EntityType,
        ExtractionMethod,
        RelationshipType,
    )
    from src.services.knowledge_graph.knowledge_graph_service import (
        knowledge_graph_service,
    )

    entity_1 = knowledge_graph_service.create_entity(
        CreateEntityRequest(
            name=ENTITY_1_NAME,
            entity_type=EntityType.PERSON,
            confidence_score=0.95,
            extraction_method=ExtractionMethod.LLM_EXTRACTION,
            organization_id=str(ORG_A_ID),
        )
    )
    entity_2 = knowledge_graph_service.create_entity(
        CreateEntityRequest(
            name=ENTITY_2_NAME,
            entity_type=EntityType.ORGANIZATION,
            confidence_score=0.95,
            extraction_method=ExtractionMethod.LLM_EXTRACTION,
            organization_id=str(ORG_A_ID),
        )
    )
    knowledge_graph_service.create_relationship(
        CreateRelationshipRequest(
            source_entity_id=entity_1.id,
            target_entity_id=entity_2.id,
            relationship_type=RelationshipType.WORKS_FOR,
            strength=1.0,
            confidence_score=0.9,
            organization_id=str(ORG_A_ID),
        )
    )
    return {"entity_1": entity_1.id, "entity_2": entity_2.id}


def _verify_seed_queryable_sync(entity_id: str) -> bool:
    """Landmine-1 self-check (plan 3 pattern): the exact call
    ``_tool_search_knowledge_graph`` makes, against the same singleton the
    seed step just wrote through."""
    from src.services.knowledge_graph.knowledge_graph_service import (
        knowledge_graph_service,
    )

    found = knowledge_graph_service.search_entities(
        query=ENTITY_1_NAME, limit=10, organization_id=str(ORG_A_ID)
    )
    return any(entity.id == entity_id for entity in found)


async def seed_org_a_graph() -> dict[str, str]:
    try:
        ids = await asyncio.to_thread(_seed_org_a_graph_sync)
    except Exception as exc:
        raise InfrastructureFailure(
            f"neo4j org-A seed failed: {type(exc).__name__}: {exc}"
        ) from exc
    try:
        queryable = await asyncio.to_thread(
            _verify_seed_queryable_sync, ids["entity_1"]
        )
    except Exception as exc:
        raise InfrastructureFailure(
            f"landmine-1 seed-queryable self-check failed: {type(exc).__name__}: {exc}"
        ) from exc
    if not queryable:
        raise InfrastructureFailure(
            "seeded org-A entity is not visible through "
            "knowledge_graph_service.search_entities -- the seed step and the "
            "probed tool are hitting different Neo4j drivers/singletons"
        )
    return ids


async def seed_org_a_skill(project_id: UUID) -> dict[str, str]:
    """Seed one approved skill and freeze it in a production runtime snapshot."""
    from src.core.database import AsyncSessionLocal
    from src.models import ProjectSkill, ProjectSkillVersion, ProjectSkillVersionScan
    from src.services.agent.runtime_snapshot import create_runtime_snapshot

    async with AsyncSessionLocal() as session:
        skill = ProjectSkill(
            id=SKILL_ID,
            project_id=project_id,
            normalized_name=SKILL_NAME,
            active_version_id=None,
            is_archived=False,
            created_by_id=USER_A_ID,
        )
        session.add(skill)
        await session.flush()
        session.add(
            ProjectSkillVersion(
                id=SKILL_VERSION_ID,
                skill_id=SKILL_ID,
                version=1,
                instructions=SKILL_INSTRUCTIONS,
                parsed_name=SKILL_NAME,
                description="Verify tenant-scoped project reads.",
                content_hash=sha256(SKILL_INSTRUCTIONS.encode()).hexdigest(),
                author_id=USER_A_ID,
            )
        )
        await session.flush()
        session.add(
            ProjectSkillVersionScan(
                id=SKILL_SCAN_ID,
                version_id=SKILL_VERSION_ID,
                scan_state="passed",
                findings=[],
                scanner_version="benchmark-v1",
                scanned_by_id=USER_A_ID,
            )
        )
        skill.active_version_id = SKILL_VERSION_ID
        await session.commit()
        runtime = await create_runtime_snapshot(
            session, user_id=USER_A_ID, project_id=project_id
        )
    if not runtime.id or len(runtime.project_skill_catalog) != 1:
        raise InfrastructureFailure("org-A project skill snapshot was not created")
    return {"skill_id": str(SKILL_ID), "runtime_snapshot_id": runtime.id}


# ---------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------
def _rows_from_documents_payload(
    payload: dict[str, Any], seed: dict[str, str]
) -> list[str]:
    rows = []
    for doc in payload.get("documents") or []:
        if not isinstance(doc, dict):
            continue
        if doc.get("id") == seed["document_id"] or doc.get("title") == DOCUMENT_TITLE:
            rows.append(doc.get("id") or doc.get("title"))
    return rows


async def probe_search_documents(seed: dict[str, str]) -> dict[str, Any]:
    from src.services.agent.tools_impl import _tool_search_documents

    async def call(user: _FakeUser, db: Any) -> dict[str, Any]:
        return await _tool_search_documents({"query": DOCUMENT_TITLE[:12]}, db, user)

    return await _run_probe(
        "documents.search_documents",
        "documents",
        {"query": DOCUMENT_TITLE[:12]},
        seed,
        call,
        lambda payload: _rows_from_documents_payload(payload, seed),
    )


async def probe_summarize_document(seed: dict[str, str]) -> dict[str, Any]:
    from src.services.agent.tools_impl import _tool_summarize_document

    async def call(user: _FakeUser, db: Any) -> dict[str, Any]:
        return await _tool_summarize_document(
            {"document_id": seed["document_id"]}, db, user
        )

    def rows(payload: dict[str, Any]) -> list[str]:
        if payload.get("error"):
            return []
        return [seed["document_id"]] if payload.get("summary") else []

    return await _run_probe(
        "documents.summarize_document",
        "documents",
        {"document_id": seed["document_id"]},
        seed,
        call,
        rows,
    )


async def probe_compare_documents(seed: dict[str, str]) -> dict[str, Any]:
    from src.services.agent.tools_impl import _tool_compare_documents

    async def call(user: _FakeUser, db: Any) -> dict[str, Any]:
        return await _tool_compare_documents(
            {"document_ids": [seed["document_id"], seed["document_id"]]}, db, user
        )

    def rows(payload: dict[str, Any]) -> list[str]:
        if payload.get("error"):
            return []
        return [seed["document_id"]] if payload.get("comparison") else []

    return await _run_probe(
        "documents.compare_documents",
        "documents",
        {"document_ids": [seed["document_id"], seed["document_id"]]},
        seed,
        call,
        rows,
    )


async def probe_list_projects(seed: dict[str, str]) -> dict[str, Any]:
    from src.services.agent.tools_impl import _tool_list_projects

    async def call(user: _FakeUser, db: Any) -> dict[str, Any]:
        return await _tool_list_projects({}, db, user)

    def rows(payload: dict[str, Any]) -> list[str]:
        found = []
        for project in payload.get("projects") or []:
            if not isinstance(project, dict):
                continue
            if (
                project.get("id") == seed["project_id"]
                or project.get("name") == PROJECT_NAME
            ):
                found.append(project.get("id") or project.get("name"))
        return found

    return await _run_probe("projects.list_projects", "projects", {}, seed, call, rows)


async def probe_list_project_documents(seed: dict[str, str]) -> dict[str, Any]:
    from src.services.agent.tools_impl import _tool_list_project_documents

    async def call(user: _FakeUser, db: Any) -> dict[str, Any]:
        return await _tool_list_project_documents(
            {"project_id": seed["project_id"]}, db, user
        )

    def rows(payload: dict[str, Any]) -> list[str]:
        if payload.get("error"):
            return []
        return [
            d.get("id") for d in (payload.get("documents") or []) if isinstance(d, dict)
        ]

    return await _run_probe(
        "projects.list_project_documents",
        "projects",
        {"project_id": seed["project_id"]},
        seed,
        call,
        rows,
    )


async def probe_search_knowledge_graph(seed: dict[str, str]) -> dict[str, Any]:
    from src.services.agent.tools_impl import _tool_search_knowledge_graph

    async def call(user: _FakeUser, _db: Any) -> dict[str, Any]:
        return await _tool_search_knowledge_graph({"query": ENTITY_1_NAME}, user)

    def rows(payload: dict[str, Any]) -> list[str]:
        found = []
        for entity in payload.get("entities") or []:
            if not isinstance(entity, dict):
                continue
            if (
                entity.get("id") == seed["entity_id"]
                or entity.get("name") == ENTITY_1_NAME
            ):
                found.append(entity.get("id") or entity.get("name"))
        return found

    return await _run_probe(
        "knowledge_graph.search_knowledge_graph",
        "knowledge_graph",
        {"query": ENTITY_1_NAME},
        seed,
        call,
        rows,
        needs_db=False,
    )


async def probe_explore_entity_neighborhood(seed: dict[str, str]) -> dict[str, Any]:
    from src.services.agent.tools_impl import _tool_explore_entity_neighborhood

    async def call(user: _FakeUser, _db: Any) -> dict[str, Any]:
        return await _tool_explore_entity_neighborhood(
            {"entity_id": seed["entity_id"]}, user
        )

    def rows(payload: dict[str, Any]) -> list[str]:
        if payload.get("error"):
            return []
        neighbors = payload.get("connected_entities") or []
        return [seed["entity_id"]] if neighbors else []

    return await _run_probe(
        "knowledge_graph.explore_entity_neighborhood",
        "knowledge_graph",
        {"entity_id": seed["entity_id"]},
        seed,
        call,
        rows,
        needs_db=False,
    )


async def probe_find_entity_paths(seed: dict[str, str]) -> dict[str, Any]:
    from src.services.agent.tools_impl import _tool_find_entity_paths

    async def call(user: _FakeUser, _db: Any) -> dict[str, Any]:
        return await _tool_find_entity_paths(
            {
                "source_entity_id": seed["entity_id"],
                "target_entity_id": seed["entity_id_2"],
            },
            user,
        )

    def rows(payload: dict[str, Any]) -> list[str]:
        if payload.get("error"):
            return []
        return [seed["entity_id"]] if payload.get("paths") else []

    return await _run_probe(
        "knowledge_graph.find_entity_paths",
        "knowledge_graph",
        {
            "source_entity_id": seed["entity_id"],
            "target_entity_id": seed["entity_id_2"],
        },
        seed,
        call,
        rows,
        needs_db=False,
    )


async def probe_get_graph_stats(seed: dict[str, str]) -> dict[str, Any]:
    from src.services.agent.tools_impl import _tool_get_graph_stats

    async def call(user: _FakeUser, _db: Any) -> dict[str, Any]:
        return await _tool_get_graph_stats({}, user)

    def rows(payload: dict[str, Any]) -> list[str]:
        total = payload.get("total_entities") or 0
        return [f"total_entities={total}"] if total else []

    return await _run_probe(
        "knowledge_graph.get_graph_stats",
        "knowledge_graph",
        {},
        seed,
        call,
        rows,
        needs_db=False,
    )


async def probe_memory_retrieval(seed: dict[str, str]) -> dict[str, Any]:
    from src.services.agent.memory import get_memory_store, search_memories

    store = await get_memory_store()
    if store is None:
        raise InfrastructureFailure("memory store unavailable for memory probe")

    async def search(user_id: UUID) -> list[dict[str, Any]]:
        return await search_memories(store, str(user_id), MEMORY_FRAGMENT, limit=5)

    a_memories = await search(USER_A_ID)
    a_rows = [
        m["value"]["query"]
        for m in a_memories
        if MEMORY_FRAGMENT in str((m.get("value") or {}).get("query", ""))
    ]

    error = None
    try:
        b_memories = await search(USER_B_ID)
        b_rows = [
            m["value"]["query"]
            for m in b_memories
            if MEMORY_FRAGMENT in str((m.get("value") or {}).get("query", ""))
        ]
    except Exception as exc:  # noqa: BLE001 - captured as probe evidence, not raised
        b_rows = []
        error = f"{type(exc).__name__}: {exc}"

    if not a_rows:
        raise InfrastructureFailure(
            "memory.memory_retrieval_node: org-A's own memory search returned "
            "nothing -- cannot distinguish isolation from an empty store"
        )

    return {
        "probe_id": "memory.memory_retrieval_node",
        "category": "memory",
        "query": {"fragment": MEMORY_FRAGMENT},
        "org_a_rows": json_safe(a_rows),
        "org_b_rows": json_safe(b_rows),
        "org_b_error": error,
    }


async def probe_load_project_skill(seed: dict[str, str]) -> dict[str, Any]:
    from src.services.agent.tools_impl import _tool_load_project_skill

    async def call(user_id: UUID, db: Any) -> dict[str, Any]:
        return await _tool_load_project_skill(
            {"skill_name": SKILL_NAME},
            user_id=str(user_id),
            project_id=seed["project_id"],
            runtime_snapshot_id=seed["runtime_snapshot_id"],
            db=db,
        )

    from src.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db_a:
        a_result = await call(USER_A_ID, db_a)
    a_rows = (
        [seed["skill_id"]]
        if not a_result.get("error") and not a_result.get("error_type")
        else []
    )

    error = None
    try:
        async with AsyncSessionLocal() as db_b:
            b_result = await call(USER_B_ID, db_b)
        if b_result.get("error") or b_result.get("error_type"):
            error = str(b_result.get("error") or b_result.get("error_type"))
            b_rows: list[str] = []
        else:
            b_rows = [seed["skill_id"]]
    except Exception as exc:  # noqa: BLE001 - captured as probe evidence, not raised
        b_rows = []
        error = f"{type(exc).__name__}: {exc}"

    if not a_rows:
        raise InfrastructureFailure(
            "suggestions.load_project_skill: org-A's own call returned no "
            "skill for its own project -- cannot distinguish isolation from "
            "an empty catalog"
        )

    return {
        "probe_id": "suggestions.load_project_skill",
        "category": "suggestions",
        "query": {
            "project_id": seed["project_id"],
            "runtime_snapshot_id": seed["runtime_snapshot_id"],
            "skill_name": SKILL_NAME,
        },
        "org_a_rows": json_safe(a_rows),
        "org_b_rows": json_safe(b_rows),
        "org_b_error": error,
    }


async def probe_rag_node(seed: dict[str, str]) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage

    from src.services.agent._nodes_rag import rag_node

    async def call(org_id: UUID, user_id: UUID) -> dict[str, Any]:
        state = {
            "messages": [HumanMessage(content=f"Tell me about {DOCUMENT_TITLE}")],
            "use_rag": True,
            "retrieved_contexts": [],
            "current_project_id": seed["project_id"],
        }
        config = {
            "configurable": {
                "user_id": str(user_id),
                "organization_id": str(org_id),
                "current_project_id": seed["project_id"],
            }
        }
        return await rag_node(state, config)

    error = None
    try:
        a_out = await call(ORG_A_ID, USER_A_ID)
        a_contexts = a_out.get("retrieved_contexts") or []
        a_rows = [
            c.get("document_id")
            for c in a_contexts
            if isinstance(c, dict) and c.get("document_id") == seed["document_id"]
        ]
    except Exception as exc:  # noqa: BLE001
        raise InfrastructureFailure(
            f"rag.rag_node: org-A's own call raised: {type(exc).__name__}: {exc}"
        ) from exc

    if not a_rows:
        raise InfrastructureFailure(
            "rag.rag_node: org-A's own retrieval returned no chunk from its "
            "own seeded document -- cannot distinguish isolation from an "
            "empty index (DO KB is disabled; this exercises the hybrid-"
            "search fallback path only)"
        )

    try:
        b_out = await call(ORG_B_ID, USER_B_ID)
        b_contexts = b_out.get("retrieved_contexts") or []
        b_rows = [
            c.get("document_id")
            for c in b_contexts
            if isinstance(c, dict) and c.get("document_id") == seed["document_id"]
        ]
    except Exception as exc:  # noqa: BLE001 - captured as probe evidence, not raised
        b_rows = []
        error = f"{type(exc).__name__}: {exc}"

    return {
        "probe_id": "rag.rag_node",
        "category": "rag",
        "query": {
            "instruction": f"Tell me about {DOCUMENT_TITLE}",
            "project_id": seed["project_id"],
        },
        "org_a_rows": json_safe(a_rows),
        "org_b_rows": json_safe(b_rows),
        "org_b_error": error,
    }


async def _run_probe(
    probe_id: str,
    category: str,
    query: dict[str, Any],
    seed: dict[str, str],
    call,
    rows_fn,
    *,
    needs_db: bool = True,
) -> dict[str, Any]:
    """Shared org-A-then-org-B probe shape for the ``db``-scoped tool wrappers."""
    from src.core.database import AsyncSessionLocal

    async def invoke(user: _FakeUser):
        if needs_db:
            async with AsyncSessionLocal() as db:
                return await call(user, db)
        return await call(user, None)

    a_payload = await invoke(_FakeUser(USER_A_ID, ORG_A_ID))
    a_rows = rows_fn(a_payload)
    if not a_rows:
        raise InfrastructureFailure(
            f"{probe_id}: org-A's own query returned nothing belonging to "
            "org A -- cannot distinguish isolation from an empty database"
        )

    error = None
    try:
        b_payload = await invoke(_FakeUser(USER_B_ID, ORG_B_ID))
        b_rows = rows_fn(b_payload)
        if isinstance(b_payload, dict) and b_payload.get("error"):
            error = str(b_payload["error"])
    except Exception as exc:  # noqa: BLE001 - captured as probe evidence, not raised
        b_rows = []
        error = f"{type(exc).__name__}: {exc}"

    return {
        "probe_id": probe_id,
        "category": category,
        "query": json_safe(query),
        "org_a_rows": json_safe(a_rows),
        "org_b_rows": json_safe(b_rows),
        "org_b_error": error,
    }


PROBE_FUNCTIONS = (
    probe_search_documents,
    probe_summarize_document,
    probe_compare_documents,
    probe_list_projects,
    probe_list_project_documents,
    probe_search_knowledge_graph,
    probe_explore_entity_neighborhood,
    probe_find_entity_paths,
    probe_get_graph_stats,
    probe_memory_retrieval,
    probe_load_project_skill,
    probe_rag_node,
)


# ---------------------------------------------------------------------------
# independent post-run reads (secondary snapshot; verifier re-reads itself)
# ---------------------------------------------------------------------------
async def independent_relational_snapshot() -> dict[str, Any]:
    from sqlalchemy import select

    from src.core.database import AsyncSessionLocal
    from src.models.collection import Collection
    from src.models.document import Document

    async with AsyncSessionLocal() as session:
        documents = (
            await session.execute(
                select(Document.id, Document.organization_id).where(
                    Document.is_deleted == False  # noqa: E712
                )
            )
        ).all()
        collections = (
            await session.execute(
                select(Collection.id, Collection.workspace_id).where(
                    Collection.is_deleted == False  # noqa: E712
                )
            )
        ).all()
    return {
        "document_count": len(documents),
        "collection_count": len(collections),
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
async def run_benchmark() -> dict[str, Any]:
    started_at = utc_now()
    started = time.monotonic()

    network_boundary = await validate_network_boundary(
        os.environ.get("AZURE_OPENAI_CHAT_ENDPOINT", "")
    )
    await bootstrap_schema()
    await seed_orgs()
    seed = await seed_org_a_fixture()

    probes: list[dict[str, Any]] = []
    for probe_fn in PROBE_FUNCTIONS:
        probes.append(await probe_fn(seed))

    probe_ids = [p["probe_id"] for p in probes]
    if len(probe_ids) != len(DECLARED_PROBES) or set(probe_ids) != set(DECLARED_PROBES):
        raise InfrastructureFailure(
            f"probe matrix drift: ran {sorted(probe_ids)}, declared "
            f"{sorted(DECLARED_PROBES)}"
        )

    relational_snapshot = await independent_relational_snapshot()

    return {
        "schema_version": "1.0",
        "benchmark_id": BENCHMARK_ID,
        "source_revision": SOURCE_REVISION,
        "agent_revision": AGENT_REVISION,
        "started_at": started_at,
        "completed_at": utc_now(),
        "synthetic_actor": {
            "org_a": {
                "organization_id": str(ORG_A_ID),
                "user_id": str(USER_A_ID),
                "workspace_id": str(WORKSPACE_A_ID),
            },
            "org_b": {
                "organization_id": str(ORG_B_ID),
                "user_id": str(USER_B_ID),
                "workspace_id": str(WORKSPACE_B_ID),
            },
        },
        "network_boundary": network_boundary,
        "seed": seed,
        "leak_vocabulary": leak_vocabulary(),
        "probes": probes,
        "relational_snapshot": relational_snapshot,
        "termination_reason": "completed",
        "model_usage": {"input_tokens": 0, "output_tokens": 0, "cache_tokens": 0},
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "notes": (
            "12-probe tenant-isolation matrix: every declared read tool/node "
            "called once as org A (proving there is something to leak) and "
            "once as org B with the identical query, in one process, one "
            "trial batch."
        ),
    }


def build_trajectory(evidence: dict[str, Any]) -> dict[str, Any]:
    """Minimal ATIF-shaped trajectory: one step per probe, not a message log."""
    probes = evidence.get("probes") or []
    steps = []
    for index, probe in enumerate(probes, start=1):
        steps.append(
            {
                "step_id": index,
                "source": "agent",
                "message": f"probe:{probe.get('probe_id')}",
                "observation": {"results": [{"content": json.dumps(json_safe(probe))}]},
            }
        )
    return {
        "schema_version": "ATIF-v1.7",
        "session_id": BENCHMARK_ID,
        "trajectory_id": f"{BENCHMARK_ID}:{evidence.get('started_at')}",
        "agent": {
            "name": "nous-production-agent",
            "version": str(evidence.get("agent_revision") or "")[:12],
            "model_name": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        },
        "steps": steps,
        "notes": evidence.get("notes") or "",
        "final_metrics": {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cached_tokens": 0,
            "total_steps": len(steps),
        },
        "extra": {
            "benchmark_id": BENCHMARK_ID,
            "source_revision": evidence.get("source_revision"),
            "termination_reason": evidence.get("termination_reason"),
        },
    }


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
            from src.services.knowledge_graph.knowledge_graph_service import (
                KnowledgeGraphService,
            )

            KnowledgeGraphService.close_driver()
        except Exception:
            pass
        try:
            from src.services.agent._pool_utils import close_shared_langgraph_pool

            await close_shared_langgraph_pool()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
