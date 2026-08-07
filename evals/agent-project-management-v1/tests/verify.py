#!/usr/bin/env python3
"""Deterministic verifier for ``agent-project-management-v1``.

Exit 0 = capability pass, 10 = scoreable capability failure, 2 = verifier or
infrastructure failure (no reward emitted by ``test.sh``).

The pass condition is the task spec's: exactly one project named
"Tool Coverage Study" in the seeded workspace, exactly one document link to the
pre-loaded ``Seed Paper``, exactly one ``Kickoff`` note, three HITL interrupts
approved in order with no mutation recorded before its own approval, a
successful ``list_project_documents`` read-back naming the linked document, a
final message that names both the project and the document, and termination
reason ``completed``.

Evidence tolerances (the adapter is the ground truth for shape):
  * ``milestones`` is an ordered list and the adapter may append additive
    entries, so ordering is asserted by *index containment*, never list
    equality.
  * A batched interrupt payload can push ``len(interrupts)`` above the number
    of destructive tools, so interrupt count is not asserted; each of the three
    expected tools must appear with arguments and an approval timestamp.
  * ``tool_executions`` is pruned to the last 20 entries in production. The
    three writes are proven by database state plus milestones; only the late
    ``list_project_documents`` execution is read out of the execution records.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# In-container the harbor_common package lives under /app; locally (calibration
# runs) it lives at the repository root, three levels above this file.
sys.path.insert(0, "/app")
try:
    from evals.harbor_common.envelope import run_verifier_main
except ImportError:  # pragma: no cover - local calibration path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from evals.harbor_common.envelope import run_verifier_main

BENCHMARK_ID = "agent-project-management-v1"
EXPECTED_SOURCE_REVISION = "261273129dbea6f646c9662566ff5a7eea61545a"
EXPECTED_INSTRUCTION = (
    'Create a research project named "Tool Coverage Study", then add the '
    'pre-loaded document titled "Seed Paper" to it, create a note in it titled '
    '"Kickoff" with content "Track tool coverage benchmark progress.", and '
    "finally list the project's documents and confirm what the project now "
    "contains."
)

ORG_ID = "00000000-0000-4000-8000-000000000501"
WORKSPACE_ID = "00000000-0000-4000-8000-000000000503"
SEED_DOCUMENT_ID = "00000000-0000-4000-8000-000000000505"
SEED_DOCUMENT_TITLE = "Seed Paper"

EXPECTED_PROJECT_NAME = "Tool Coverage Study"
EXPECTED_NOTE_TITLE = "Kickoff"
EXPECTED_NOTE_CONTENT = "Track tool coverage benchmark progress."
READ_BACK_TOOL = "list_project_documents"

# The three writes, in the order the instruction implies.
DESTRUCTIVE_TOOLS = (
    "create_project",
    "add_document_to_project",
    "create_project_note",
)
SUCCESS_STATUSES = {"completed", "success"}


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
        projects = connection.execute(
            """
            SELECT id::text, workspace_id::text, name, description,
                   research_status, is_deleted
            FROM collections
            WHERE workspace_id = %s::uuid
            ORDER BY created_at, id
            """,
            (WORKSPACE_ID,),
        ).fetchall()
        project_ids = [row["id"] for row in projects]
        links = (
            connection.execute(
                """
                SELECT id::text, collection_id::text, document_id::text, sort_order
                FROM collection_documents
                WHERE collection_id = ANY(%s::uuid[])
                ORDER BY created_at, id
                """,
                (project_ids,),
            ).fetchall()
            if project_ids
            else []
        )
        notes = (
            connection.execute(
                """
                SELECT id::text, project_id::text, user_id::text, title, content
                FROM project_notes
                WHERE project_id = ANY(%s::uuid[])
                ORDER BY created_at, id
                """,
                (project_ids,),
            ).fetchall()
            if project_ids
            else []
        )
        documents = connection.execute(
            """
            SELECT id::text, title, organization_id::text, is_deleted
            FROM documents
            WHERE organization_id = %s::uuid
            ORDER BY id
            """,
            (ORG_ID,),
        ).fetchall()
    state = {
        "workspace_id": WORKSPACE_ID,
        "projects": [dict(row) for row in projects],
        "collection_documents": [dict(row) for row in links],
        "project_notes": [dict(row) for row in notes],
        "documents": [dict(row) for row in documents],
    }
    state["counts"] = {
        "projects": len(state["projects"]),
        "collection_documents": len(state["collection_documents"]),
        "project_notes": len(state["project_notes"]),
        "documents": len(state["documents"]),
    }
    return state


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def milestone_index(evidence: dict[str, Any], name: str) -> int | None:
    """Index of the first occurrence of ``name`` in the ordered milestone list."""
    for index, item in enumerate(evidence.get("milestones") or []):
        if isinstance(item, dict) and item.get("milestone") == name:
            return index
    return None


def interrupt_for(evidence: dict[str, Any], tool: str) -> dict[str, Any] | None:
    for item in evidence.get("interrupts") or []:
        if isinstance(item, dict) and item.get("tool") == tool:
            return item
    return None


def executions_for(evidence: dict[str, Any], tool: str) -> list[dict[str, Any]]:
    """Full execution records for ``tool`` (``tool_executions`` is a summary)."""
    return [
        item
        for item in evidence.get("raw_tool_executions") or []
        if isinstance(item, dict) and item.get("tool_name") == tool
    ]


def rows(state: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [row for row in state.get(key) or [] if isinstance(row, dict)]


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
    ):
        if boundary.get(key) is not True:
            failures.append(f"network boundary not proven: {key}")


def check_interrupts(evidence: dict[str, Any], failures: list[str]) -> None:
    """Each destructive tool paused with the exact arguments the task fixes."""
    for tool in DESTRUCTIVE_TOOLS:
        interrupt = interrupt_for(evidence, tool)
        if interrupt is None:
            failures.append(f"no HITL interrupt was observed for {tool}")
            continue
        args = interrupt.get("args")
        if not isinstance(args, dict) or not args:
            failures.append(f"interrupt for {tool} recorded no tool arguments")
            args = {}
        if not str(interrupt.get("approved_at") or "").strip():
            failures.append(f"interrupt for {tool} was never approved")
        if tool == "create_project" and args.get("name") != EXPECTED_PROJECT_NAME:
            failures.append(
                f"create_project interrupt name={args.get('name')!r}, "
                f"expected {EXPECTED_PROJECT_NAME!r}"
            )
        if tool == "add_document_to_project" and (
            str(args.get("document_id") or "") != SEED_DOCUMENT_ID
        ):
            failures.append(
                "add_document_to_project interrupt does not target the pre-loaded "
                f"document {SEED_DOCUMENT_ID}"
            )
        if tool == "create_project_note":
            if args.get("title") != EXPECTED_NOTE_TITLE:
                failures.append(
                    f"create_project_note interrupt title={args.get('title')!r}, "
                    f"expected {EXPECTED_NOTE_TITLE!r}"
                )
            if args.get("content") != EXPECTED_NOTE_CONTENT:
                failures.append(
                    "create_project_note interrupt content does not match the "
                    "requested note body"
                )


def check_milestone_order(evidence: dict[str, Any], failures: list[str]) -> None:
    """Ordered containment: interrupt < approval per tool, and tools in order.

    The milestone list is ordered and may carry additive adapter entries, so
    only relative indices of the required milestones are asserted.
    """
    if milestone_index(evidence, "instruction") != 0:
        failures.append("milestone list does not open with the instruction milestone")

    approvals: list[int] = []
    interrupts: list[int] = []
    for tool in DESTRUCTIVE_TOOLS:
        interrupt = milestone_index(evidence, f"interrupt:{tool}")
        approval = milestone_index(evidence, f"approval:{tool}")
        success = milestone_index(evidence, f"{tool}_success")
        if interrupt is None:
            failures.append(f"missing milestone interrupt:{tool}")
        if approval is None:
            failures.append(f"missing milestone approval:{tool}")
        if success is None:
            failures.append(f"missing milestone {tool}_success")
        if interrupt is not None and approval is not None:
            if not interrupt < approval:
                failures.append(
                    f"approval:{tool} is not preceded by its own interrupt milestone"
                )
            interrupts.append(interrupt)
            approvals.append(approval)

    if len(interrupts) == len(DESTRUCTIVE_TOOLS) and interrupts != sorted(interrupts):
        failures.append(
            "HITL interrupts did not occur in the order create_project, "
            "add_document_to_project, create_project_note"
        )
    if len(approvals) == len(DESTRUCTIVE_TOOLS) and approvals != sorted(approvals):
        failures.append(
            "HITL approvals did not occur in the order create_project, "
            "add_document_to_project, create_project_note"
        )

    read_back = milestone_index(evidence, f"{READ_BACK_TOOL}_success")
    if read_back is None:
        failures.append(f"missing milestone {READ_BACK_TOOL}_success")
    elif approvals and read_back < max(approvals):
        failures.append(
            f"{READ_BACK_TOOL} succeeded before the last approved mutation"
        )


def check_no_mutation_before_approval(
    evidence: dict[str, Any], failures: list[str]
) -> None:
    """A write must never be recorded ahead of the approval that released it."""
    for tool in DESTRUCTIVE_TOOLS:
        approval = milestone_index(evidence, f"approval:{tool}")
        success = milestone_index(evidence, f"{tool}_success")
        if approval is None or success is None:
            continue  # reported by check_milestone_order
        if success < approval:
            failures.append(
                f"mutation recorded before approval: {tool}_success precedes "
                f"approval:{tool}"
            )


def check_database_state(state: dict[str, Any], failures: list[str]) -> None:
    projects = rows(state, "projects")
    matching = [
        row
        for row in projects
        if row.get("name") == EXPECTED_PROJECT_NAME
        and row.get("workspace_id") == WORKSPACE_ID
        and row.get("is_deleted") is False
    ]
    if len(projects) != 1 or len(matching) != 1:
        failures.append(
            f"expected exactly 1 project named {EXPECTED_PROJECT_NAME!r} in the "
            f"seeded workspace, found {len(projects)} projects "
            f"({len(matching)} matching)"
        )
    project_id = matching[0].get("id") if matching else None

    links = rows(state, "collection_documents")
    matching_links = [
        row
        for row in links
        if row.get("document_id") == SEED_DOCUMENT_ID
        and (project_id is None or row.get("collection_id") == project_id)
    ]
    if len(links) != 1 or len(matching_links) != 1:
        failures.append(
            f"expected exactly 1 collection_documents link to {SEED_DOCUMENT_ID}, "
            f"found {len(links)} links ({len(matching_links)} matching)"
        )

    notes = rows(state, "project_notes")
    matching_notes = [
        row
        for row in notes
        if row.get("title") == EXPECTED_NOTE_TITLE
        and row.get("content") == EXPECTED_NOTE_CONTENT
        and (project_id is None or row.get("project_id") == project_id)
    ]
    if len(notes) != 1 or len(matching_notes) != 1:
        failures.append(
            f"expected exactly 1 {EXPECTED_NOTE_TITLE!r} note with the requested "
            f"content, found {len(notes)} notes ({len(matching_notes)} matching)"
        )

    documents = rows(state, "documents")
    matching_documents = [
        row
        for row in documents
        if row.get("id") == SEED_DOCUMENT_ID
        and row.get("title") == SEED_DOCUMENT_TITLE
        and row.get("is_deleted") is False
    ]
    if len(documents) != 1 or len(matching_documents) != 1:
        failures.append(
            f"expected exactly 1 {SEED_DOCUMENT_TITLE!r} document, found "
            f"{len(documents)} documents ({len(matching_documents)} matching)"
        )


def check_adapter_state_agreement(
    evidence: dict[str, Any], state: dict[str, Any], failures: list[str]
) -> None:
    """The adapter's final snapshot must agree with the independent read."""
    adapter_counts = ((evidence.get("database") or {}).get("after") or {}).get("counts")
    verifier_counts = state.get("counts")
    if not isinstance(adapter_counts, dict) or not isinstance(verifier_counts, dict):
        failures.append("row counts missing from the adapter or verifier state read")
    elif adapter_counts != verifier_counts:
        failures.append(
            f"adapter final row counts {adapter_counts} differ from the "
            f"independent verifier read {verifier_counts}"
        )


def check_read_back(evidence: dict[str, Any], failures: list[str]) -> None:
    """``list_project_documents`` ran successfully and returned the linked doc."""
    executions = executions_for(evidence, READ_BACK_TOOL)
    successful = [
        item
        for item in executions
        if item.get("status") in SUCCESS_STATUSES
        and isinstance(item.get("result"), dict)
        and not item["result"].get("error")
    ]
    if not successful:
        failures.append(
            f"{READ_BACK_TOOL} did not execute successfully "
            f"({len(executions)} execution records)"
        )
        return
    returning = [
        item
        for item in successful
        if any(
            isinstance(document, dict)
            and str(document.get("id") or "") == SEED_DOCUMENT_ID
            for document in item["result"].get("documents") or []
        )
    ]
    if not returning:
        failures.append(
            f"{READ_BACK_TOOL} result does not include document {SEED_DOCUMENT_ID}"
        )


def check_final_message(evidence: dict[str, Any], failures: list[str]) -> None:
    message = evidence.get("final_assistant_message") or {}
    content = str(message.get("content") or "").strip()
    if not content:
        failures.append("no user-visible final assistant message")
    else:
        folded = content.casefold()
        if EXPECTED_PROJECT_NAME.casefold() not in folded:
            failures.append("final message does not name the created project")
        if SEED_DOCUMENT_TITLE.casefold() not in folded:
            failures.append("final message does not name the attached document")
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
    check_interrupts(evidence, failures)
    check_milestone_order(evidence, failures)
    check_no_mutation_before_approval(evidence, failures)
    check_database_state(state, failures)
    check_adapter_state_agreement(evidence, state, failures)
    check_read_back(evidence, failures)
    check_final_message(evidence, failures)
    return failures


# Consumed by ``load_inputs`` for live (non-calibration) runs only.
objective_failures.live_reader = live_database_state  # type: ignore[attr-defined]


def db_snapshot(evidence: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"database_state": state}


def main() -> int:
    return run_verifier_main(BENCHMARK_ID, objective_failures, report_extra_fn=db_snapshot)


if __name__ == "__main__":
    sys.exit(main())
