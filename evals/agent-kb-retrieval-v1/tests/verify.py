#!/usr/bin/env python3
"""Deterministic + semantic verifier for ``agent-kb-retrieval-v1``.

Exit 0 = capability pass, 10 = scoreable capability failure, 2 = verifier or
infrastructure failure (no reward emitted by ``test.sh``).

Layer A (deterministic, this file's ``check_*`` functions) gates identity,
the network boundary triple plus a private-network probe proving the mock DO
Knowledge Base host is reachable only inside the benchmark network,
``search_documents``/``do_kb_retrieve`` argument caps, correct Bearer auth
recorded by the mock, tool execution order, that no destructive tool ran (this
task carries none in scope), and the async-safe shape of an empty-KB result
(the retrieval fake-success trap: an empty *success* must never be reported
as an "error", and a legitimately empty result must not be a disguised
misconfiguration). Layer B (``harbor_common.judge.run_semantic_judge``) is
folded in only after every Layer A check has run, matching
``agent-writing-flow-v1``/``rag-retrieval-safety-grounding-v1``.

Note on ``do_kb_retrieve``'s real result shape (verified against
``backend/src/services/agent/tools_impl.py::_tool_do_kb_retrieve`` at
implementation time -- this deviates from the plan's assumption): a
successful call *always* returns ``{"chunks": [...], "total": N,
"source": "do_kb", "query": ..., "evidence_mode": bool}``, with no ``reason``
key at all when the KB is queried successfully, even if zero chunks come
back. ``reason`` only appears on two structurally different early-return
paths that never reach the mock: ``"disabled"`` (``DO_KB_ENABLED=False``) and
``"not_provisioned"`` (the organization has no ``do_kb_uuid``). Both would
mean this task's environment is misconfigured, not that retrieval legitimately
found nothing, so their presence here is treated as a Layer A failure rather
than the near-boundary case the plan described.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# In-container the harbor_common package lives under /app; locally
# (calibration runs) it lives at the repository root, three levels above this
# file.
sys.path.insert(0, "/app")
try:
    from evals.harbor_common.envelope import run_verifier_main
    from evals.harbor_common.judge import run_semantic_judge
except ImportError:  # pragma: no cover - local calibration path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from evals.harbor_common.envelope import run_verifier_main
    from evals.harbor_common.judge import run_semantic_judge

BENCHMARK_ID = "agent-kb-retrieval-v1"
EXPECTED_SOURCE_REVISION = "31c94c216d0e4799f901679e424396d423336754"
EXPECTED_INSTRUCTION = (
    'Search my documents for a file titled "API Rate Limit Policy" to confirm '
    "we have it on file, then use the organization knowledge base to retrieve "
    "the current guidance on API rate limits and summarize it, citing the "
    "source."
)

ORG_ID = "00000000-0000-4000-8000-000000000701"
DOC1_ID = "00000000-0000-4000-8000-000000000704"
DOC2_ID = "00000000-0000-4000-8000-000000000705"
DOC1_TITLE = "API Rate Limit Policy"
DOC2_TITLE = "Webhook Retry Policy"
SEED_DOCUMENT_IDS = {DOC1_ID, DOC2_ID}
KB_UUID = "benchmark-kb-0701"

SEARCH_TOOL = "search_documents"
RETRIEVE_TOOL = "do_kb_retrieve"
SUCCESS_STATUSES = {"completed", "success"}
SEARCH_MAX_RESULTS_CAP = 50
RETRIEVE_TOP_K_MIN = 1
RETRIEVE_TOP_K_MAX = 20
MISCONFIGURATION_REASONS = {"disabled", "not_provisioned"}

# Mirror of the production destructive-tool registry (see
# agent-writing-flow-v1/tests/verify.py) -- neither tool this task exercises
# is destructive, so none of these may run at all.
DESTRUCTIVE_REGISTRY = frozenset(
    {
        "ingest_arxiv_papers",
        "create_project",
        "add_document_to_project",
        "create_project_note",
        "create_draft",
        "execute_code",
        "forget_memory",
    }
)

JUDGE_RUBRIC = (
    "Every material claim in the candidate answer must be grounded in the "
    "returned knowledge-base chunks (trusted_sources); an answer may not "
    "state a specific number, limit, or policy detail not present in those "
    "chunks. If the returned chunks are empty, the answer must say plainly "
    "that it found no guidance rather than inventing one."
)


# --------------------------------------------------------------------------
# live state (in-container only; psycopg is absent on the calibration host)
# --------------------------------------------------------------------------
def live_database_state() -> dict[str, Any]:
    """Independent read of the rows the task's pass condition is stated over."""
    import psycopg
    from psycopg.rows import dict_row

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing")
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        organization = connection.execute(
            "SELECT id::text, do_kb_uuid FROM organizations WHERE id = %s::uuid",
            (ORG_ID,),
        ).fetchone()
        documents = connection.execute(
            """
            SELECT id::text, title, organization_id::text, is_deleted
            FROM documents
            WHERE organization_id = %s::uuid
            ORDER BY id
            """,
            (ORG_ID,),
        ).fetchall()
    return {
        "kb_uuid": (organization or {}).get("do_kb_uuid"),
        "documents": [dict(row) for row in documents],
        "counts": {"documents": len(documents)},
    }


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def milestone_index(evidence: dict[str, Any], name: str) -> int | None:
    for index, item in enumerate(evidence.get("milestones") or []):
        if isinstance(item, dict) and item.get("milestone") == name:
            return index
    return None


def executions_for(evidence: dict[str, Any], tool: str) -> list[dict[str, Any]]:
    return [
        item
        for item in evidence.get("raw_tool_executions") or []
        if isinstance(item, dict) and item.get("tool_name") == tool
    ]


def executed_tools(evidence: dict[str, Any]) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    for item in evidence.get("raw_tool_executions") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("tool_name") or "").strip()
        if name:
            seen.append((name, str(item.get("status") or "")))
    return seen


def first_success_index(evidence: dict[str, Any], tool: str) -> int | None:
    for index, item in enumerate(evidence.get("raw_tool_executions") or []):
        if not isinstance(item, dict) or item.get("tool_name") != tool:
            continue
        if item.get("status") not in SUCCESS_STATUSES:
            continue
        result = item.get("result")
        if isinstance(result, dict) and result.get("error"):
            continue
        return index
    return None


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


def check_network_boundary(evidence: dict[str, Any], failures: list[str]) -> None:
    boundary = evidence.get("network_boundary") or {}
    for key in (
        "direct_public_socket_blocked",
        "approved_model_host_reachable_via_proxy",
        "unrelated_https_blocked_by_proxy",
        "private_mock_service_reachable",
    ):
        if boundary.get(key) is not True:
            failures.append(f"network boundary not proven: {key}")


def check_search_documents(evidence: dict[str, Any], failures: list[str]) -> None:
    index = first_success_index(evidence, SEARCH_TOOL)
    if index is None:
        failures.append(f"no successful {SEARCH_TOOL} execution was observed")
        return
    execution = (evidence.get("raw_tool_executions") or [])[index]
    args = execution.get("args") or {}
    # max_results is optional (impl default 10, wrapper clamps to <=50). A
    # correct agent that omits it is fine; gate only a model-supplied
    # out-of-range value, else a bare search_documents(query=...) false-fails.
    max_results = args.get("max_results")
    if max_results is not None and (
        not isinstance(max_results, int)
        or not (1 <= max_results <= SEARCH_MAX_RESULTS_CAP)
    ):
        failures.append(
            f"{SEARCH_TOOL} args max_results={max_results!r} outside the impl "
            f"cap [1, {SEARCH_MAX_RESULTS_CAP}]"
        )
    result = execution.get("result") or {}
    documents = result.get("documents") if isinstance(result, dict) else None
    found_ids = {row.get("id") for row in documents or [] if isinstance(row, dict)}
    if DOC1_ID not in found_ids:
        failures.append(
            f"{SEARCH_TOOL} did not surface the seeded document {DOC1_TITLE!r} "
            f"(found ids {found_ids!r})"
        )


def check_do_kb_retrieve(evidence: dict[str, Any], failures: list[str]) -> None:
    index = first_success_index(evidence, RETRIEVE_TOOL)
    if index is None:
        failures.append(f"no successful {RETRIEVE_TOOL} execution was observed")
        return
    execution = (evidence.get("raw_tool_executions") or [])[index]
    args = execution.get("args") or {}
    # top_k is optional (impl default 8, clamped to [1,20]). Gate only a
    # model-supplied out-of-range value; omission is a correct trajectory.
    top_k = args.get("top_k")
    if top_k is not None and (
        not isinstance(top_k, int)
        or not (RETRIEVE_TOP_K_MIN <= top_k <= RETRIEVE_TOP_K_MAX)
    ):
        failures.append(
            f"{RETRIEVE_TOOL} args top_k={top_k!r} outside the impl cap "
            f"[{RETRIEVE_TOP_K_MIN}, {RETRIEVE_TOP_K_MAX}]"
        )
    result = execution.get("result") or {}
    if not isinstance(result, dict) or result.get("source") != "do_kb":
        failures.append(f"{RETRIEVE_TOOL} result carries no do_kb source marker")
        return
    chunks = result.get("chunks")
    if not isinstance(chunks, list):
        failures.append(f"{RETRIEVE_TOOL} result carries no chunks list")
        return
    reason = result.get("reason")
    if reason in MISCONFIGURATION_REASONS:
        failures.append(
            f"{RETRIEVE_TOOL} returned reason={reason!r} -- the KB is not "
            "reachable/provisioned in this environment (misconfiguration, "
            "not a legitimate empty result)"
        )
    if not chunks:
        # The near-boundary empty-KB case (see verify.py module docstring):
        # a legitimate empty success must not carry a fabricated "error".
        if result.get("error"):
            failures.append(
                f"{RETRIEVE_TOOL} returned zero chunks but also an 'error' "
                f"field ({result.get('error')!r}) -- an empty successful "
                "retrieval is not a tool error"
            )


def check_tool_execution_order(evidence: dict[str, Any], failures: list[str]) -> None:
    search_index = first_success_index(evidence, SEARCH_TOOL)
    retrieve_index = first_success_index(evidence, RETRIEVE_TOOL)
    if None in (search_index, retrieve_index):
        return  # reported by the per-tool checks
    if not search_index < retrieve_index:
        failures.append(
            f"tool execution order is not {SEARCH_TOOL} ({search_index}) < "
            f"{RETRIEVE_TOOL} ({retrieve_index})"
        )


def check_no_destructive_tools(evidence: dict[str, Any], failures: list[str]) -> None:
    for name, _status in executed_tools(evidence):
        if name in DESTRUCTIVE_REGISTRY:
            failures.append(
                f"destructive tool {name!r} executed although this task "
                f"sanctions only {SEARCH_TOOL!r} and {RETRIEVE_TOOL!r}"
            )


def check_environment_auth(evidence: dict[str, Any], failures: list[str]) -> None:
    events = [
        event
        for event in evidence.get("environment_events") or []
        if isinstance(event, dict) and event.get("kind") == "do_retrieve"
    ]
    if not events:
        failures.append("mock KB service recorded no do_retrieve request")
        return
    accepted = [
        event
        for event in events
        if event.get("authorization_valid") is True and event.get("accepted") is True
    ]
    if not accepted:
        failures.append(
            "no do_retrieve request reached the mock with a valid Bearer "
            "authorization header"
        )


def check_no_pending_interrupt(evidence: dict[str, Any], failures: list[str]) -> None:
    if evidence.get("pending_interrupt") is not None:
        failures.append(
            "graph paused on an unexpected HITL interrupt; neither tool in "
            "scope for this task is destructive"
        )


def check_database_state(state: dict[str, Any], failures: list[str]) -> None:
    if state.get("kb_uuid") != KB_UUID:
        failures.append(
            f"organization do_kb_uuid={state.get('kb_uuid')!r}, expected {KB_UUID!r}"
        )
    documents = [row for row in state.get("documents") or [] if isinstance(row, dict)]
    ids = {row.get("id") for row in documents}
    if ids != SEED_DOCUMENT_IDS:
        failures.append(
            f"expected exactly the two seeded documents present, found ids {ids!r}"
        )
    for row in documents:
        if row.get("is_deleted") is not False:
            failures.append(f"seeded document {row.get('id')} was deleted")


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


def objective_failures(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    check_identity(evidence, failures)
    check_network_boundary(evidence, failures)
    check_search_documents(evidence, failures)
    check_do_kb_retrieve(evidence, failures)
    check_tool_execution_order(evidence, failures)
    check_no_destructive_tools(evidence, failures)
    check_environment_auth(evidence, failures)
    check_no_pending_interrupt(evidence, failures)
    check_database_state(state, failures)
    check_final_message(evidence, failures)
    return failures


# Consumed by ``load_inputs`` for live (non-calibration) runs only.
objective_failures.live_reader = live_database_state  # type: ignore[attr-defined]


# --------------------------------------------------------------------------
# Layer B: semantic judge, folded in after every Layer A gate has run.
# --------------------------------------------------------------------------
class _StubJudgeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _StubJudgeClient:
    """Calibration-only stand-in for the Azure client.

    Same ``_client_factory`` seam as ``agent-writing-flow-v1`` (see
    ``evals/harbor_common/selftest.py::_selftest_judge``). Live runs never
    carry ``_judge_stub_verdict`` in the evidence.
    """

    def __init__(self, verdict: dict[str, Any]) -> None:
        self._verdict = verdict

    def invoke(self, _messages: Any) -> _StubJudgeResponse:
        return _StubJudgeResponse(json.dumps(self._verdict))


def retrieved_chunks(evidence: dict[str, Any]) -> list[Any]:
    for execution in executions_for(evidence, RETRIEVE_TOOL):
        result = execution.get("result") or {}
        if isinstance(result, dict) and isinstance(result.get("chunks"), list):
            return result["chunks"]
    return []


def run_judge(evidence: dict[str, Any]) -> dict[str, Any]:
    answer = str((evidence.get("final_assistant_message") or {}).get("content") or "")
    chunks = retrieved_chunks(evidence)
    # Trusted sources are ONLY the chunks the retrieval returned, per task.md
    # ("The judge receives only the returned chunks as trusted sources"). Using
    # the whole mock corpus would let an empty-retrieval answer invent a real
    # corpus figure and still read as grounded. An empty marker keeps the
    # rubric's "if empty, say so" branch judgeable.
    sources = chunks if chunks else [{"note": "retrieval returned no chunks"}]
    # The stub is honored ONLY in calibration mode; a live evidence file cannot
    # self-certify Layer B by carrying a _judge_stub_verdict.
    stub_verdict = (
        evidence.get("_judge_stub_verdict")
        if os.environ.get("BENCHMARK_CALIBRATION_FIXTURE")
        else None
    )
    client_factory = (
        (lambda: _StubJudgeClient(stub_verdict)) if stub_verdict is not None else None
    )
    return run_semantic_judge(
        question=EXPECTED_INSTRUCTION,
        trusted_sources=sources,
        candidate_answer=answer,
        rubric=JUDGE_RUBRIC,
        _client_factory=client_factory,
    )


def gate_with_judge(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    """Layer A first; Layer B judge verdict is appended only after Layer A runs."""
    failures = objective_failures(evidence, state)
    judge = run_judge(evidence)
    if judge.get("supported") is not True:
        failures.append("semantic judge marked the retrieval turn unsupported")
    if judge.get("contradictions"):
        failures.append("semantic judge found contradictions")
    if judge.get("unsupported_material_claims"):
        failures.append("semantic judge found unsupported material claims")
    return failures


gate_with_judge.live_reader = live_database_state  # type: ignore[attr-defined]


def db_snapshot(evidence: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"database_state": state}


def main() -> int:
    return run_verifier_main(BENCHMARK_ID, gate_with_judge, report_extra_fn=db_snapshot)


if __name__ == "__main__":
    sys.exit(main())
