#!/usr/bin/env python3
"""Deterministic verifier for ``agent-arxiv-research-flow-v1``.

Exit 0 = capability pass, 10 = scoreable capability failure, 2 = verifier or
infrastructure failure (no reward emitted by ``test.sh``). Layer B (semantic)
is N/A for this task — no judge is configured or consumed.

Pass condition (design doc capability 5): a research-routed turn searches the
arXiv double for a fixture topic, a byte-identical repeat search is served
from the shared Redis cache with no second query reaching the double, and
`ingest_arxiv_papers` — DESTRUCTIVE — pauses for exactly one HITL approval
before any document row or storage object exists, then persists both
requested papers with a checksum-verified local object and a document UUID
distinct from the arXiv paper id.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, "/app")
try:
    from evals.harbor_common.envelope import run_verifier_main
except ImportError:  # pragma: no cover - local calibration path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from evals.harbor_common.envelope import run_verifier_main

BENCHMARK_ID = "agent-arxiv-research-flow-v1"
EXPECTED_SOURCE_REVISION = "31c94c216d0e4799f901679e424396d423336754"
SEARCH_TEXT = "Search arXiv for deterministic benchmark retrieval evaluation."
EXPECTED_INSTRUCTION = SEARCH_TEXT

TRUTH_PATH = Path("/tests/truth.json")
try:
    TRUTH = json.loads(TRUTH_PATH.read_text())
except FileNotFoundError:  # pragma: no cover - local calibration without /tests mount
    TRUTH = json.loads((Path(__file__).resolve().parent / "truth.json").read_text())

ORG_ID = TRUTH["organization_id"]
PROJECT_ID = TRUTH["project_id"]
REQUESTED_PAPER_IDS = list(TRUTH["requested_paper_ids"])
PAPER_SHA256 = {p["id"]: p["pdf_sha256"] for p in TRUTH["papers"]}
REDIS_PREFIX = TRUTH["redis_key_prefix"]
REDIS_STALE_TTL = int(TRUTH["redis_stale_ttl_seconds"])
REDIS_TTL_JITTER = float(TRUTH["redis_ttl_jitter_fraction"])
# `core/cache.cache_set` applies +/-15% jitter to the requested TTL — the
# max bound must absorb that, not just the nominal 1800s (Landmine 6).
REDIS_TTL_MAX = int(REDIS_STALE_TTL * (1 + REDIS_TTL_JITTER))

INGEST_TOOL = "ingest_arxiv_papers"
SEARCH_TOOL = "search_arxiv"
SUCCESS_STATUSES = {"completed", "success"}


# --------------------------------------------------------------------------
# live state (in-container only; psycopg/redis/httpx absent on the
# calibration host, which always sets BENCHMARK_CALIBRATION_FIXTURE instead)
# --------------------------------------------------------------------------
def live_database_state() -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing")
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        documents = connection.execute(
            """
            SELECT id::text, title, organization_id::text, processing_status,
                   checksum_sha256, file_path, storage_path, storage_backend,
                   filename, (search_vector IS NOT NULL) AS has_search_vector,
                   document_metadata, is_deleted
            FROM documents
            WHERE organization_id = %s::uuid
            ORDER BY id
            """,
            (ORG_ID,),
        ).fetchall()
        document_ids = [row["id"] for row in documents]
        links = (
            connection.execute(
                """
                SELECT id::text, collection_id::text, document_id::text
                FROM collection_documents
                WHERE collection_id = %s::uuid
                ORDER BY created_at, id
                """,
                (PROJECT_ID,),
            ).fetchall()
            if document_ids
            else []
        )
    return {
        "documents": [dict(row) for row in documents],
        "collection_documents": [dict(row) for row in links],
        "counts": {"documents": len(documents), "collection_documents": len(links)},
    }


def live_redis_state() -> dict[str, Any]:
    import redis

    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        raise RuntimeError("REDIS_URL is missing")
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    try:
        keys = sorted(client.keys(f"{REDIS_PREFIX}*"))
        entries = []
        for key in keys:
            raw = client.get(key)
            ttl = client.ttl(key)
            parsed = None
            if raw is not None:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
            entries.append({"key": key, "ttl_seconds": ttl, "value": parsed})
        return {"matching_keys": keys, "entries": entries}
    finally:
        client.close()


def live_storage_listing() -> list[dict[str, Any]]:
    import hashlib

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


def live_mock_events() -> list[dict[str, Any]]:
    import httpx

    response = httpx.get("http://mock-services:8080/events", timeout=10)
    response.raise_for_status()
    return response.json().get("events", [])


def live_state() -> dict[str, Any]:
    return {
        "database": live_database_state(),
        "redis": live_redis_state(),
        "storage": live_storage_listing(),
        "mock_events": live_mock_events(),
    }


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def milestone_index(evidence: dict[str, Any], name: str) -> int | None:
    for index, item in enumerate(evidence.get("milestones") or []):
        if isinstance(item, dict) and item.get("milestone") == name:
            return index
    return None


def rows(container: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [row for row in container.get(key) or [] if isinstance(row, dict)]


def interrupt_for(evidence: dict[str, Any], tool: str) -> dict[str, Any] | None:
    for item in evidence.get("interrupts") or []:
        if isinstance(item, dict) and item.get("tool") == tool:
            return item
    return None


def executions_for(
    evidence: dict[str, Any], tool: str, evidence_key: str = "tool_executions"
) -> list[dict[str, Any]]:
    return [
        item
        for item in evidence.get(evidence_key) or []
        if isinstance(item, dict) and item.get("tool_name") == tool
    ]


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------
def check_identity(evidence: dict[str, Any], failures: list[str]) -> None:
    if evidence.get("schema_version") != "1.0":
        failures.append(
            f"evidence schema_version={evidence.get('schema_version')!r}, expected '1.0'"
        )
    if evidence.get("benchmark_id") != BENCHMARK_ID:
        failures.append("benchmark id does not match")
    if evidence.get("source_revision") != EXPECTED_SOURCE_REVISION:
        failures.append("source revision does not match the approved benchmark")
    if evidence.get("instruction") != EXPECTED_INSTRUCTION:
        failures.append("instruction does not match the approved task")
    if evidence.get("search_instruction") != SEARCH_TEXT:
        failures.append(
            "recorded search_instruction does not match the fixed turn text"
        )
    actor = evidence.get("synthetic_actor") or {}
    if actor.get("project_id") != PROJECT_ID:
        failures.append("synthetic_actor.project_id does not match the seeded project")


def check_network_boundary(evidence: dict[str, Any], failures: list[str]) -> None:
    boundary = evidence.get("network_boundary") or {}
    for key in (
        "direct_public_socket_blocked",
        "approved_model_host_reachable_via_proxy",
        "unrelated_https_blocked_by_proxy",
        "private_mock_services_reachable",
        "private_redis_reachable",
    ):
        if boundary.get(key) is not True:
            failures.append(f"network boundary not proven: {key}")


def check_arxiv_client_patch(evidence: dict[str, Any], failures: list[str]) -> None:
    patch = evidence.get("arxiv_client_patch") or {}
    if "mock-services" not in str(patch.get("ARXIV_API_BASE") or ""):
        failures.append("ARXIV_API_BASE was not patched to the mock double")
    if "mock-services" not in str(patch.get("ARXIV_PDF_BASE") or ""):
        failures.append("ARXIV_PDF_BASE was not patched to the mock double")


def check_search(evidence: dict[str, Any], failures: list[str]) -> None:
    """search_arxiv executed against the double, capped, drawn from fixtures."""
    executions = executions_for(evidence, SEARCH_TOOL, "search_executions")
    successful = [
        item
        for item in executions
        if item.get("status") in SUCCESS_STATUSES
        and isinstance(item.get("result"), dict)
        and not item["result"].get("error")
    ]
    if len(executions) != 2 or len(successful) != 2:
        failures.append(
            f"expected exactly 2 successful {SEARCH_TOOL} executions "
            f"(initial + cache-proof repeat), found {len(successful)} successful "
            f"of {len(executions)} total"
        )
        return

    first, second = successful[0], successful[1]
    first_papers = (first.get("result") or {}).get("papers") or []
    if not first_papers:
        failures.append("first search_arxiv result carried no papers")
    if len(first_papers) > 5:
        failures.append(
            f"search_arxiv returned {len(first_papers)} papers, impl cap is 5"
        )
    fixture_ids = {p["id"] for p in TRUTH["papers"]}
    result_ids = {
        re.sub(r"v\d+$", "", str(p.get("id") or ""), flags=re.IGNORECASE)
        for p in first_papers
    }
    if not result_ids <= fixture_ids:
        failures.append(
            f"search_arxiv result ids {result_ids} are not a subset of the fixture "
            f"corpus {fixture_ids}"
        )

    if first.get("args") != second.get("args"):
        failures.append("second search_arxiv call was not a byte-identical repeat")

    if not (second.get("result") or {}).get("cached"):
        failures.append(
            "second identical search_arxiv call did not report cached: true"
        )


def check_mock_events(evidence: dict[str, Any], failures: list[str]) -> None:
    events = evidence.get("mock_events") or []
    topic_queries = [
        item
        for item in events
        if isinstance(item, dict) and item.get("kind") == "topic_search"
    ]
    if len(topic_queries) != 1:
        failures.append(
            f"expected exactly 1 non-id: topic query event at the mock double "
            f"(the repeat search must be served from cache), found {len(topic_queries)}"
        )
    unknown = [
        item
        for item in events
        if isinstance(item, dict) and item.get("type") == "unknown_host_or_path"
    ]
    if unknown:
        failures.append(f"mock double received unexpected requests: {unknown}")
    pdf_events = [
        item for item in events if isinstance(item, dict) and item.get("type") == "pdf"
    ]
    for item in pdf_events:
        if item.get("paper_id") not in REQUESTED_PAPER_IDS:
            failures.append(
                f"mock double served a PDF fetch for unrequested paper "
                f"{item.get('paper_id')!r}"
            )
        if not item.get("found"):
            failures.append(f"PDF fetch for {item.get('paper_id')!r} was not found")


def check_hitl_ordering(evidence: dict[str, Any], failures: list[str]) -> None:
    interrupt = interrupt_for(evidence, INGEST_TOOL)
    if interrupt is None:
        failures.append(f"no HITL interrupt was observed for {INGEST_TOOL}")
        return
    args = interrupt.get("args") or {}
    requested_ids = args.get("paper_ids") or []
    if set(requested_ids) - set(REQUESTED_PAPER_IDS):
        failures.append(
            f"ingest interrupt requested unsanctioned paper ids {requested_ids}"
        )
    if not str(interrupt.get("approved_at") or "").strip():
        failures.append(f"interrupt for {INGEST_TOOL} was never approved")

    pre = ((evidence.get("database") or {}).get("before_ingest_approval")) or {}
    pre_docs = rows(pre, "documents")
    if pre_docs:
        failures.append(
            f"mutation landed before approval: pre-approval snapshot already holds "
            f"{len(pre_docs)} document row(s)"
        )

    interrupt_idx = milestone_index(evidence, f"interrupt:{INGEST_TOOL}")
    approval_idx = milestone_index(evidence, f"approval:{INGEST_TOOL}")
    success_idx = milestone_index(evidence, "ingest_arxiv_papers_success")
    if interrupt_idx is None:
        failures.append(f"missing milestone interrupt:{INGEST_TOOL}")
    if approval_idx is None:
        failures.append(f"missing milestone approval:{INGEST_TOOL}")
    if success_idx is None:
        failures.append("missing milestone ingest_arxiv_papers_success")
    if (
        interrupt_idx is not None
        and approval_idx is not None
        and not (interrupt_idx < approval_idx)
    ):
        failures.append("approval was not preceded by its own interrupt milestone")
    if (
        approval_idx is not None
        and success_idx is not None
        and success_idx < approval_idx
    ):
        failures.append(
            "mutation recorded before approval: ingest_arxiv_papers_success "
            "precedes approval:ingest_arxiv_papers"
        )


def check_ingest_result(evidence: dict[str, Any], failures: list[str]) -> None:
    """document_ids are UUIDs distinct from the arXiv paper ids (Landmine 3)."""
    executions = executions_for(evidence, INGEST_TOOL)
    successful = [
        item
        for item in executions
        if item.get("status") in SUCCESS_STATUSES
        and isinstance(item.get("result"), dict)
        and not item["result"].get("error")
    ]
    if not successful:
        failures.append(
            f"{INGEST_TOOL} did not execute successfully ({len(executions)} records)"
        )
        return
    result = successful[-1]["result"]
    document_ids = result.get("document_ids") or []
    if len(document_ids) != len(REQUESTED_PAPER_IDS):
        failures.append(
            f"expected {len(REQUESTED_PAPER_IDS)} document_ids, got {len(document_ids)}"
        )
    for doc_id in document_ids:
        if doc_id in REQUESTED_PAPER_IDS:
            failures.append(
                f"document_id {doc_id!r} equals an arXiv paper id — the tool must "
                "report the created document UUID, not the source paper id"
            )
        try:
            import uuid as _uuid

            _uuid.UUID(str(doc_id))
        except (ValueError, AttributeError, TypeError):
            failures.append(f"document_id {doc_id!r} is not a valid UUID")
    if result.get("project_id") != PROJECT_ID:
        failures.append(
            f"ingest result project_id={result.get('project_id')!r}, "
            f"expected {PROJECT_ID!r}"
        )


def check_database_state(state: dict[str, Any], failures: list[str]) -> None:
    database = state.get("database") or {}
    documents = rows(database, "documents")
    if len(documents) != len(REQUESTED_PAPER_IDS):
        failures.append(
            f"expected {len(REQUESTED_PAPER_IDS)} documents, found {len(documents)}"
        )
    by_checksum = {row.get("checksum_sha256"): row for row in documents}
    for paper_id, sha256 in PAPER_SHA256.items():
        row = by_checksum.get(sha256)
        if row is None:
            failures.append(
                f"no document with checksum {sha256!r} (fixture PDF for {paper_id})"
            )
            continue
        if str(row.get("processing_status")).split(".")[-1].lower() != "completed":
            failures.append(
                f"document for {paper_id} processing_status="
                f"{row.get('processing_status')!r}, expected COMPLETED"
            )
        if not row.get("has_search_vector"):
            failures.append(f"document for {paper_id} has no search_vector")
        if row.get("is_deleted"):
            failures.append(f"document for {paper_id} is marked deleted")

    links = rows(database, "collection_documents")
    linked_document_ids = {row.get("document_id") for row in links}
    documented_ids = {row.get("id") for row in documents}
    if not documented_ids <= linked_document_ids or len(links) != len(documents):
        failures.append(
            f"expected every ingested document linked to project {PROJECT_ID}, "
            f"found {len(links)} link(s) for {len(documents)} document(s)"
        )


def check_storage(
    state: dict[str, Any], evidence: dict[str, Any], failures: list[str]
) -> None:
    database = state.get("database") or {}
    documents = rows(database, "documents")
    storage_files = {item["sha256"]: item for item in state.get("storage") or []}
    for row in documents:
        checksum = row.get("checksum_sha256")
        entry = storage_files.get(checksum)
        if entry is None:
            failures.append(
                f"no local storage object found matching checksum {checksum!r}"
            )
            continue
        expected_prefix = f"documents/{ORG_ID}/{row.get('id')}/"
        if not entry["path"].startswith(expected_prefix):
            failures.append(
                f"storage object for document {row.get('id')} is at "
                f"{entry['path']!r}, expected under {expected_prefix!r}"
            )
        if row.get("storage_backend") != "local":
            failures.append(
                f"document {row.get('id')} storage_backend="
                f"{row.get('storage_backend')!r}, expected 'local'"
            )


def check_redis(state: dict[str, Any], failures: list[str]) -> None:
    redis_state = state.get("redis") or {}
    entries = rows(redis_state, "entries")
    matching = [
        item for item in entries if str(item.get("key") or "").startswith(REDIS_PREFIX)
    ]
    if not matching:
        failures.append(f"no {REDIS_PREFIX}* key present in Redis")
        return
    for entry in matching:
        ttl = entry.get("ttl_seconds")
        if not isinstance(ttl, (int, float)) or not (0 < ttl <= REDIS_TTL_MAX):
            failures.append(
                f"redis key {entry.get('key')!r} TTL={ttl!r}, expected "
                f"0 < TTL <= {REDIS_TTL_MAX}"
            )
        value = entry.get("value")
        if (
            not isinstance(value, dict)
            or "payload" not in value
            or "cached_at" not in value
        ):
            failures.append(
                f"redis key {entry.get('key')!r} value is not the "
                "{'payload':..., 'cached_at':...} envelope"
            )


def check_final_message(evidence: dict[str, Any], failures: list[str]) -> None:
    message = evidence.get("final_assistant_message") or {}
    content = str(message.get("content") or "").strip()
    if not content:
        failures.append("no user-visible final assistant message")
    if message.get("tool_calls"):
        failures.append("final assistant message still contains pending tool calls")
    if evidence.get("termination_reason") != "completed":
        failures.append(
            f"termination_reason={evidence.get('termination_reason')!r}, "
            "expected 'completed'"
        )


def check_no_unsanctioned_destructive_tools(
    evidence: dict[str, Any], failures: list[str]
) -> None:
    approved = {
        str(item.get("tool") or "")
        for item in evidence.get("interrupts") or []
        if isinstance(item, dict) and str(item.get("approved_at") or "").strip()
    }
    for item in evidence.get("tool_executions") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("tool_name") or "")
        if name != INGEST_TOOL:
            continue
        status = item.get("status")
        result = item.get("result")
        succeeded = (
            status in SUCCESS_STATUSES
            and isinstance(result, dict)
            and not (result.get("error"))
        )
        if succeeded and name not in approved:
            failures.append(
                f"{name} executed successfully with no approved HITL interrupt"
            )


def objective_failures(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    check_identity(evidence, failures)
    check_network_boundary(evidence, failures)
    check_arxiv_client_patch(evidence, failures)
    check_search(evidence, failures)
    check_mock_events(evidence, failures)
    check_hitl_ordering(evidence, failures)
    check_no_unsanctioned_destructive_tools(evidence, failures)
    check_ingest_result(evidence, failures)
    check_database_state(state, failures)
    check_storage(state, evidence, failures)
    check_redis(state, failures)
    check_final_message(evidence, failures)
    return failures


objective_failures.live_reader = live_state  # type: ignore[attr-defined]


def main() -> int:
    return run_verifier_main(BENCHMARK_ID, objective_failures)


if __name__ == "__main__":
    sys.exit(main())
