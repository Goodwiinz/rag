#!/usr/bin/env python3
"""Deterministic verifier for ``agent-direct-project-action-v1``.

Exit 0 means capability pass, 10 means a valid scoreable capability failure,
and any other non-zero code means verifier/infrastructure failure.  The shell
wrapper emits no reward for infrastructure failures.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

EXPECTED_NAME = "The Discovery Note"
EXPECTED_INSTRUCTION = "Create a project named The Discovery Note."
EXPECTED_WORKSPACE_ID = "00000000-0000-4000-8000-000000000103"
EXPECTED_SOURCE_REVISION = "debb4b1506b3524a134888d0f13c66807901efca"
DEFAULT_EVIDENCE = Path("/logs/agent/evidence.json")
REPORT_PATH = Path("/logs/verifier/audit.json")


def live_database_state() -> dict[str, Any]:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing")
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        projects = connection.execute(
            """
            SELECT id::text, workspace_id::text, name, research_status, is_deleted
            FROM collections
            WHERE workspace_id = %s::uuid
            ORDER BY created_at, id
            """,
            (EXPECTED_WORKSPACE_ID,),
        ).fetchall()
        document_links = connection.execute(
            "SELECT count(*) AS count FROM collection_documents"
        ).fetchone()["count"]
        notes = connection.execute(
            "SELECT count(*) AS count FROM project_notes"
        ).fetchone()["count"]
        documents = connection.execute(
            "SELECT count(*) AS count FROM documents"
        ).fetchone()["count"]
    return {
        "workspace_id": EXPECTED_WORKSPACE_ID,
        "projects": [dict(row) for row in projects],
        "document_links": int(document_links),
        "project_notes": int(notes),
        "documents": int(documents),
    }


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], str]:
    calibration = os.environ.get("BENCHMARK_CALIBRATION_FIXTURE")
    if calibration:
        fixture = json.loads(Path(calibration).read_text())
        return fixture["evidence"], fixture["database_state"], calibration
    if not DEFAULT_EVIDENCE.exists():
        raise FileNotFoundError(f"agent evidence missing: {DEFAULT_EVIDENCE}")
    return json.loads(DEFAULT_EVIDENCE.read_text()), live_database_state(), "live"


def interrupt_tools(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    payload = (evidence.get("interrupt") or {}).get("payload") or {}
    return list(payload.get("tools") or [])


def evaluate(evidence: dict[str, Any], db: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    if evidence.get("benchmark_id") != "agent-direct-project-action-v1":
        failures.append("benchmark id does not match")
    if evidence.get("source_revision") != EXPECTED_SOURCE_REVISION:
        failures.append("source revision does not match the approved benchmark")
    if evidence.get("instruction") != EXPECTED_INSTRUCTION:
        failures.append("instruction does not match the approved task")

    boundary = evidence.get("network_boundary") or {}
    for key in (
        "direct_public_socket_blocked",
        "approved_model_host_reachable_via_proxy",
        "unrelated_https_blocked_by_proxy",
    ):
        if boundary.get(key) is not True:
            failures.append(f"network boundary not proven: {key}")

    interrupt = evidence.get("interrupt") or {}
    tools = interrupt_tools(evidence)
    matching_interrupts = [
        tool
        for tool in tools
        if tool.get("name") == "create_project"
        and (tool.get("args") or {}).get("name") == EXPECTED_NAME
    ]
    if interrupt.get("observed") is not True or len(matching_interrupts) != 1:
        failures.append("exact create_project HITL interrupt was not observed once")

    approval = evidence.get("approval") or {}
    if (
        approval.get("sent") is not True
        or approval.get("text") != "Yes, create it."
        or approval.get("resume") != {"confirmed": True}
    ):
        failures.append("fixed approval was not sent through Command(resume)")

    before = (evidence.get("database") or {}).get("before_approval") or {}
    if before.get("projects"):
        failures.append("project mutation occurred before approval")

    projects = db.get("projects") or []
    expected_projects = [
        row
        for row in projects
        if row.get("name") == EXPECTED_NAME
        and row.get("workspace_id") == EXPECTED_WORKSPACE_ID
        and row.get("research_status") == "active"
        and row.get("is_deleted") is False
    ]
    if len(projects) != 1 or len(expected_projects) != 1:
        failures.append(
            f"independent DB state has {len(projects)} total projects and "
            f"{len(expected_projects)} expected active projects"
        )

    for count_key in ("documents", "document_links", "project_notes"):
        if int(db.get(count_key, -1)) != 0:
            failures.append(f"unexpected {count_key} rows: {db.get(count_key)}")

    executions = [
        item
        for item in evidence.get("tool_executions") or []
        if item.get("tool_name") == "create_project"
    ]
    successful = [
        item
        for item in executions
        if item.get("status") in {"completed", "success"}
        and (item.get("result") or {}).get("status") == "success"
    ]
    if len(executions) != 1 or len(successful) != 1:
        failures.append(
            f"create_project executions={len(executions)}, successful={len(successful)}"
        )
    elif expected_projects:
        result_id = str((successful[0].get("result") or {}).get("project_id") or "")
        if result_id != str(expected_projects[0].get("id")):
            failures.append("tool result project_id does not match independent DB row")

    milestones = evidence.get("milestones") or {}
    ordered_names = (
        "interrupt",
        "preapproval_database_read",
        "approval",
        "create_project_success",
        "postapproval_database_read",
        "final_assistant_message",
    )
    values = [milestones.get(name) for name in ordered_names]
    if any(not isinstance(value, int) for value in values) or values != sorted(values):
        failures.append(f"HITL/tool/final milestone order invalid: {milestones}")

    if evidence.get("pending_interrupt_after_resume") is not None:
        failures.append("run ended with another pending confirmation")
    if evidence.get("termination_reason") != "completed":
        failures.append(
            f"termination_reason={evidence.get('termination_reason')!r}, expected completed"
        )
    final_message = evidence.get("final_assistant_message") or {}
    final_content = str(final_message.get("content") or "").strip()
    if not final_content:
        failures.append("no user-visible final assistant acknowledgement")
    elif EXPECTED_NAME.casefold() not in final_content.casefold():
        failures.append("final acknowledgement does not name the created project")
    if final_message.get("tool_calls"):
        failures.append("final assistant message still contains pending tool calls")

    after = (evidence.get("database") or {}).get("after") or {}
    if after != db:
        failures.append(
            "adapter final DB snapshot differs from independent verifier read"
        )

    return failures


def main() -> int:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        evidence, db, source = load_inputs()
        if evidence.get("schema_version") != "1.0":
            raise ValueError("unsupported or missing evidence schema_version")
        failures = evaluate(evidence, db)
        report = {
            "benchmark_id": "agent-direct-project-action-v1",
            "input_source": source,
            "passed": not failures,
            "failures": failures,
            "database_state": db,
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True))
        print(json.dumps(report, sort_keys=True))
        return 0 if not failures else 10
    except Exception as exc:
        report = {
            "benchmark_id": "agent-direct-project-action-v1",
            "verifier_error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True))
        print(json.dumps(report, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
