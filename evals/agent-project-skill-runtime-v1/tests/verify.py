#!/usr/bin/env python3
"""Independent verifier for frozen project-skill execution across HITL."""

from __future__ import annotations

import os
import re
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

sys.path.insert(0, "/app")
try:
    from evals.harbor_common.envelope import run_verifier_main
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from evals.harbor_common.envelope import run_verifier_main

BENCHMARK_ID = "agent-project-skill-runtime-v1"
SOURCE_REVISION = "f568f1f4ceea65188b328ab47cd237cfeabf652f"
EXPECTED_INSTRUCTION = (
    "Use the active evidence-note project skill and the document in this project "
    "to create a source-grounded project note about sparse transformer attention."
)
ORG_ID = "00000000-0000-4000-8000-000000003000"
USER_ID = "00000000-0000-4000-8000-000000003001"
THREAD_ID = "00000000-0000-4000-8000-000000003004"
PROJECT_ID = "00000000-0000-4000-8000-000000003010"
DOCUMENT_ID = "00000000-0000-4000-8000-000000003011"
SKILL_ID = "00000000-0000-4000-8000-000000003012"
VERSION_1_ID = "00000000-0000-4000-8000-000000003013"
VERSION_2_ID = "00000000-0000-4000-8000-000000003014"
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
V1_HASH = sha256(VERSION_1.encode()).hexdigest()
V2_HASH = sha256(VERSION_2.encode()).hexdigest()
SUCCESS = {"completed", "success"}
ALLOWED_TOOLS = {
    "list_projects",
    "load_project_skill",
    "list_project_documents",
    "summarize_document",
    "create_project_note",
}
MEASUREMENT_SCOPE_RE = re.compile(
    r"\b(?:16k|16,?000)[ -]token\s+scientific\s+abstracts\b",
    re.IGNORECASE,
)


def mentions_measurement_scope(text: str) -> bool:
    return bool(MEASUREMENT_SCOPE_RE.search(text))


def live_state() -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(
        os.environ["DATABASE_URL"], row_factory=dict_row
    ) as connection:
        skill = connection.execute(
            "SELECT id::text, project_id::text, normalized_name AS name, "
            "active_version_id::text, is_archived FROM project_skills WHERE id=%s::uuid",
            (SKILL_ID,),
        ).fetchone()
        versions = connection.execute(
            "SELECT id::text, version, parsed_name, description, instructions, "
            "content_hash FROM project_skill_versions WHERE skill_id=%s::uuid "
            "ORDER BY version",
            (SKILL_ID,),
        ).fetchall()
        snapshots = connection.execute(
            "SELECT id::text, project_id::text, user_id::text, thread_id::text, "
            "skill_catalog, loaded_skill_versions, tool_metadata "
            "FROM agent_runtime_snapshots WHERE project_id=%s::uuid ORDER BY created_at",
            (PROJECT_ID,),
        ).fetchall()
        notes = connection.execute(
            "SELECT id::text, project_id::text, user_id::text, title, content, tags "
            "FROM project_notes WHERE project_id=%s::uuid ORDER BY created_at",
            (PROJECT_ID,),
        ).fetchall()
        document = connection.execute(
            "SELECT id::text, title, content_text, is_deleted FROM documents "
            "WHERE id=%s::uuid",
            (DOCUMENT_ID,),
        ).fetchone()
    return {
        "skill": dict(skill) if skill else None,
        "versions": [dict(row) for row in versions],
        "snapshots": [dict(row) for row in snapshots],
        "notes": [dict(row) for row in notes],
        "document": dict(document) if document else None,
    }


def executions(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in evidence.get("raw_tool_executions") or []
        if isinstance(item, dict)
    ]


def check_identity(evidence: dict[str, Any], failures: list[str]) -> None:
    if evidence.get("benchmark_id") != BENCHMARK_ID:
        failures.append("benchmark identity mismatch")
    if evidence.get("source_revision") != SOURCE_REVISION:
        failures.append("source revision mismatch")
    if evidence.get("instruction") != EXPECTED_INSTRUCTION:
        failures.append("instruction mismatch")
    boundary = evidence.get("network_boundary") or {}
    for key in (
        "direct_public_socket_blocked",
        "approved_model_host_reachable_via_proxy",
        "unrelated_https_blocked_by_proxy",
    ):
        if boundary.get(key) is not True:
            failures.append(f"network boundary failed: {key}")


def check_versions(
    evidence: dict[str, Any], state: dict[str, Any], failures: list[str]
) -> None:
    versions = state.get("versions") or []
    if [item.get("id") for item in versions] != [VERSION_1_ID, VERSION_2_ID]:
        failures.append("live skill versions differ from the two seeded versions")
        return
    expected = ((1, VERSION_1, V1_HASH), (2, VERSION_2, V2_HASH))
    for row, (number, instructions, digest) in zip(versions, expected):
        if (
            row.get("version") != number
            or row.get("parsed_name") != "evidence-note"
            or row.get("instructions") != instructions
            or row.get("content_hash") != digest
            or sha256(str(row.get("instructions") or "").encode()).hexdigest() != digest
        ):
            failures.append(f"version {number} body or content hash changed")

    final_skill = state.get("skill") or {}
    if (
        final_skill.get("id") != SKILL_ID
        or final_skill.get("project_id") != PROJECT_ID
        or final_skill.get("active_version_id") != VERSION_2_ID
        or final_skill.get("is_archived") is not False
    ):
        failures.append("live skill did not finish active on version 2")

    database = evidence.get("database") or {}
    initial = database.get("initial") or {}
    after_snapshot = database.get("after_snapshot") or {}
    after_activation = database.get("after_activation") or {}
    before_approval = database.get("before_approval") or {}
    if (initial.get("skill") or {}).get("active_version_id") != VERSION_1_ID:
        failures.append("version 1 was not active at trial start")
    if initial.get("snapshots") or initial.get("notes"):
        failures.append("trial did not start without snapshots and notes")
    if (after_snapshot.get("skill") or {}).get("active_version_id") != VERSION_1_ID:
        failures.append("version changed before the runtime snapshot was durable")
    if len(after_snapshot.get("snapshots") or []) != 1:
        failures.append("runtime snapshot was not durably recorded")
    if (after_activation.get("skill") or {}).get("active_version_id") != VERSION_2_ID:
        failures.append("version 2 was not activated before model execution")
    if not before_approval or before_approval.get("notes"):
        failures.append("note existed before the authentic HITL approval")


def check_snapshot(
    evidence: dict[str, Any], state: dict[str, Any], failures: list[str]
) -> None:
    runtime = evidence.get("runtime") or {}
    snapshots = state.get("snapshots") or []
    if len(snapshots) != 1:
        failures.append(
            f"expected one live runtime snapshot, observed {len(snapshots)}"
        )
        return
    snapshot = snapshots[0]
    snapshot_id = snapshot.get("id")
    if not snapshot_id or {
        runtime.get("snapshot_id"),
        runtime.get("snapshot_id_before_resume"),
        runtime.get("snapshot_id_after_resume"),
    } != {snapshot_id}:
        failures.append("runtime snapshot identity changed across HITL resume")
    if (
        snapshot.get("project_id") != PROJECT_ID
        or snapshot.get("user_id") != USER_ID
        or snapshot.get("thread_id") != THREAD_ID
        or runtime.get("project_id_before_resume") != PROJECT_ID
    ):
        failures.append("runtime snapshot lost its actor, thread, or project binding")

    catalog = snapshot.get("skill_catalog") or []
    if len(catalog) != 1:
        failures.append("snapshot catalog did not freeze exactly one skill")
    else:
        entry = catalog[0]
        if (
            entry.get("version_id") != VERSION_1_ID
            or entry.get("version") != 1
            or entry.get("name") != "evidence-note"
            or entry.get("content_hash") != V1_HASH
        ):
            failures.append("snapshot catalog did not freeze evidence-note version 1")
    loaded = snapshot.get("loaded_skill_versions") or []
    if len(loaded) != 1 or (
        loaded[0].get("version_id") != VERSION_1_ID
        or loaded[0].get("name") != "evidence-note"
        or loaded[0].get("content_hash") != V1_HASH
    ):
        failures.append("durable loaded-version audit did not record only version 1")
    if runtime.get("loaded_skill_versions") != loaded:
        failures.append("checkpoint loaded versions differ from durable snapshot audit")
    descriptor_names = {
        item.get("name")
        for item in (snapshot.get("tool_metadata") or {}).get("descriptors") or []
    }
    if "load_project_skill" not in descriptor_names:
        failures.append(
            "conditional project-skill loader was absent from snapshot tools"
        )
    prompt_catalog = str(runtime.get("prompt_catalog") or "")
    if (
        "evidence-note (v1)" not in prompt_catalog
        or "load_project_skill" not in prompt_catalog
        or "Before writing" in prompt_catalog
        or "Executive Brief" in prompt_catalog
    ):
        failures.append("prompt catalog leaked bodies or omitted frozen metadata")


def check_tools(evidence: dict[str, Any], failures: list[str]) -> None:
    runs = executions(evidence)
    names = [item.get("tool_name") for item in runs]
    if any(name not in ALLOWED_TOOLS for name in names):
        failures.append(f"unexpected tool executed: {names}")
    required = [
        "load_project_skill",
        "list_project_documents",
        "summarize_document",
        "create_project_note",
    ]
    positions: list[int] = []
    for name in required:
        try:
            positions.append(names.index(name))
        except ValueError:
            failures.append(f"required tool did not execute: {name}")
    if len(positions) == len(required) and positions != sorted(positions):
        failures.append("skill load, source read, and note write occurred out of order")
    if any(item.get("status") not in SUCCESS for item in runs):
        failures.append("one or more tool executions did not complete")

    loader = next(
        (item for item in runs if item.get("tool_name") == "load_project_skill"), {}
    )
    result = loader.get("result") or {}
    if (
        result.get("version") != 1
        or result.get("content_hash") != V1_HASH
        or result.get("instructions") != VERSION_1
        or (result.get("loaded_skill_version") or {}).get("version_id") != VERSION_1_ID
    ):
        failures.append("loader did not return exact frozen version-1 instructions")
    if any(
        item.get("tool_name") == "load_project_skill"
        and (item.get("result") or {}).get("version") == 2
        for item in runs
    ):
        failures.append("version 2 leaked into the turn")


def check_hitl_and_messages(evidence: dict[str, Any], failures: list[str]) -> None:
    interrupts = evidence.get("interrupts") or []
    if len(interrupts) != 1 or interrupts[0].get("tool") != "create_project_note":
        failures.append("expected one authentic create_project_note interrupt")
    if (evidence.get("approval") or {}).get("count") != 1:
        failures.append("expected exactly one post-interrupt approval")
    if evidence.get("pending_interrupt_after_resume"):
        failures.append("HITL interrupt remained pending after approval")

    calls: set[str] = set()
    results: set[str] = set()
    for message in evidence.get("messages") or []:
        if not isinstance(message, dict):
            continue
        if message.get("type") == "ai":
            calls.update(
                str(call.get("id"))
                for call in message.get("tool_calls") or []
                if call.get("id")
            )
        elif message.get("type") == "tool" and message.get("tool_call_id"):
            results.add(str(message["tool_call_id"]))
    if calls != results:
        failures.append("tool-call/result message linkage is incomplete")
    final = evidence.get("final_assistant_message") or {}
    if not str(final.get("content") or "").strip() or final.get("tool_calls"):
        failures.append("run produced no terminal assistant response")
    if evidence.get("termination_reason") != "completed":
        failures.append("run did not terminate completed")


def check_note(
    evidence: dict[str, Any], state: dict[str, Any], failures: list[str]
) -> None:
    notes = state.get("notes") or []
    if len(notes) != 1:
        failures.append(f"expected one final note, observed {len(notes)}")
        return
    note = notes[0]
    if note.get("project_id") != PROJECT_ID or note.get("user_id") != USER_ID:
        failures.append("note was written outside the seeded actor/project")
    content = str(note.get("content") or "")
    headings = re.findall(r"^##\s+(.+?)\s*$", content, re.M)
    if headings != ["Finding", "Evidence", "Uncertainty"]:
        failures.append(f"note did not follow version-1 headings: {headings}")
    if not re.search(r"38\s*(?:percent|%)", content, re.I):
        failures.append("note omitted the source's 38-percent memory result")
    if not re.search(r"0\.4\s+percentage\s+points", content, re.I):
        failures.append("note omitted the source's 0.4-point accuracy context")
    if not mentions_measurement_scope(content):
        failures.append("note omitted the source's measurement scope")
    limitation = re.search(r"dense\s+cross[- ]token", content, re.I) and re.search(
        r"not\s+(?:evaluated|tested)", content, re.I
    )
    limitation = limitation or re.search(
        r"did\s+not\s+(?:include|evaluate|test)\s+dense\s+cross[- ]token",
        content,
        re.I,
    )
    if not limitation:
        failures.append("note omitted the source's explicit limitation")
    if re.search(r"^##\s+(?:Context|Recommendation|Next Steps)\s*$", content, re.M):
        failures.append("note drifted to active version 2 after snapshot creation")
    document = state.get("document") or {}
    if (
        document.get("id") != DOCUMENT_ID
        or document.get("content_text") != SOURCE_TEXT
        or document.get("is_deleted") is not False
    ):
        failures.append("seeded source document changed")
    final_evidence_notes = ((evidence.get("database") or {}).get("final") or {}).get(
        "notes"
    ) or []
    if (
        len(final_evidence_notes) != 1
        or final_evidence_notes[0].get("content") != content
    ):
        failures.append("adapter note evidence differs from the independent live row")


def gate(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    check_identity(evidence, failures)
    check_versions(evidence, state, failures)
    check_snapshot(evidence, state, failures)
    check_tools(evidence, failures)
    check_hitl_and_messages(evidence, failures)
    check_note(evidence, state, failures)
    return failures


gate.live_reader = live_state  # type: ignore[attr-defined]


def report_extra(_evidence: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"live_state": state}


if __name__ == "__main__":
    sys.exit(run_verifier_main(BENCHMARK_ID, gate, report_extra_fn=report_extra))
