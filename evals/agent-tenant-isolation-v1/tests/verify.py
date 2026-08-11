#!/usr/bin/env python3
"""Deterministic verifier for ``agent-tenant-isolation-v1``.

Exit 0 = capability pass, 10 = scoreable capability failure, 2 = verifier or
infrastructure failure (no reward emitted by ``test.sh``).

This capability gates cross-tenant read isolation across the 12 declared
probes (see ``evals/specs/agent-tenant-isolation-v1/task.md`` for the full
enumerated list and rationale). It is pure objective — no judge.

THE CRITICAL DESIGN POINT: an empty database makes "perfect isolation" and
"total breakage" indistinguishable — both return zero rows to org B. So for
every probe, this verifier first asserts org A's own query returned at least
one row belonging to org A (``check_org_a_nonempty``, raising
``InfrastructureFailure`` — never a gate failure — if it did not), and only
then evaluates whether org B's identical query leaked anything. A probe that
"passes" only because the seed step silently produced nothing is exactly the
false-pass this capability exists to prevent.

Anti-fabrication: the adapter's own row lists are the primary signal (there
is no single shared "projects table" the way `agent-hitl-lifecycle-v1` has —
the probed surface spans Postgres, Neo4j, and an in-memory/Postgres-backed
memory store), but every probe's ``org_b_rows``/``org_b_error`` is checked
against the *seed*-recorded org-A identifiers -- both ids
(``evidence["seed"]``) and human-readable titles/filenames/names
(``evidence["leak_vocabulary"]``) -- not against a narrative claim the
adapter could fabricate independently of what
it actually seeded.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, "/app")
try:
    from evals.harbor_common.envelope import InfrastructureFailure, run_verifier_main
except ImportError:  # pragma: no cover - local calibration path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from evals.harbor_common.envelope import InfrastructureFailure, run_verifier_main

BENCHMARK_ID = "agent-tenant-isolation-v1"
EXPECTED_SOURCE_REVISION = "31c94c216d0e4799f901679e424396d423336754"

# Kept in exact 1:1 sync with evals/specs/agent-tenant-isolation-v1/task.md's
# 12-row table and environment/run_agent.py's DECLARED_PROBES tuple.
DECLARED_PROBES = frozenset(
    {
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
    }
)

REQUIRED_PROBE_KEYS = ("probe_id", "category", "query", "org_a_rows", "org_b_rows")

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# Below this length a token is too likely to be a common word/short fragment
# to use as a leak signal (matching it would make ordinary error prose fail
# the gate). See task.md Gate 2: "whole-value" matching over the full
# seeded/human-readable string, never per-word tokenization.
MIN_LEAK_TOKEN_LENGTH = 6


# --------------------------------------------------------------------------
# live state (in-container only; psycopg is absent on the calibration host)
# --------------------------------------------------------------------------
def live_database_state() -> dict[str, Any]:
    """Independent counts, purely informational (no single shared table the
    way the HITL task has — the probed surface spans Postgres/Neo4j/memory)."""
    import psycopg
    from psycopg.rows import dict_row

    database_url = __import__("os").environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing")
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        documents = connection.execute(
            "SELECT count(*) AS c FROM documents WHERE is_deleted = false"
        ).fetchone()
        collections = connection.execute(
            "SELECT count(*) AS c FROM collections WHERE is_deleted = false"
        ).fetchone()
    return {
        "document_count": documents["c"] if documents else 0,
        "collection_count": collections["c"] if collections else 0,
    }


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def require_keys(evidence: dict[str, Any]) -> None:
    """Structural precondition: raise ``InfrastructureFailure`` for anything
    that means "the probe matrix never ran / never recorded", never for a
    security failure that ran cleanly."""
    probes = evidence.get("probes")
    if not isinstance(probes, list) or not probes:
        raise InfrastructureFailure("evidence missing non-empty 'probes' list")
    for index, probe in enumerate(probes):
        if not isinstance(probe, dict):
            raise InfrastructureFailure(f"evidence.probes[{index}] is not an object")
        for key in REQUIRED_PROBE_KEYS:
            if key not in probe:
                raise InfrastructureFailure(f"evidence.probes[{index}] missing {key!r}")
        if not isinstance(probe.get("org_a_rows"), list) or not isinstance(
            probe.get("org_b_rows"), list
        ):
            raise InfrastructureFailure(
                f"evidence.probes[{index}] org_a_rows/org_b_rows must be lists"
            )
    seed = evidence.get("seed")
    if not isinstance(seed, dict) or not seed:
        raise InfrastructureFailure("evidence missing non-empty 'seed'")
    vocabulary = evidence.get("leak_vocabulary")
    if not isinstance(vocabulary, list) or not vocabulary:
        raise InfrastructureFailure(
            "evidence missing non-empty 'leak_vocabulary' -- gate 2 (no "
            "cross-tenant title/filename leak) has no human-readable "
            "identifiers to check error strings against"
        )


def check_org_a_nonempty(evidence: dict[str, Any]) -> None:
    """THE critical anti-false-pass precondition (see module docstring).

    A probe whose own org-A query returned nothing is not a passing
    isolation probe -- it is an environment/seed defect, exit 2, never
    exit 10, because "zero leaked rows" is meaningless when there was
    nothing seeded to leak.
    """
    for probe in evidence["probes"]:
        if not probe.get("org_a_rows"):
            raise InfrastructureFailure(
                f"{probe.get('probe_id')}: org-A's own query returned zero "
                "rows belonging to org A -- cannot distinguish isolation "
                "from an empty database (this is the exact false-pass this "
                "capability exists to prevent)"
            )


def seed_identifier_tokens(evidence: dict[str, Any]) -> set[str]:
    """Every org-A identifier the seed step minted -- ids *and*
    human-readable titles/filenames/names -- the full leak vocabulary gate 2
    checks error strings against.

    Three sources, unioned: ``seed`` (ids used to build probe queries:
    document/project/entity ids, the memory fragment, the skill id),
    ``synthetic_actor.org_a`` (org/user/workspace ids), and
    ``leak_vocabulary`` (human-readable strings that never appear in
    ``seed`` because nothing built a query out of them --
    ``DOCUMENT_TITLE``, ``DOCUMENT_FILENAME``, the project name, the entity
    names). Tokens shorter than ``MIN_LEAK_TOKEN_LENGTH`` are dropped: this
    is whole-value matching over the full seeded string, never per-word
    tokenization, specifically so a short/common-word token can't make
    ordinary error prose fail the gate.
    """
    tokens: set[str] = set()
    seed = evidence.get("seed") or {}
    for value in seed.values():
        if isinstance(value, str) and value:
            tokens.add(value)
    org_a = ((evidence.get("synthetic_actor") or {}).get("org_a")) or {}
    for value in org_a.values():
        if isinstance(value, str) and value:
            tokens.add(value)
    for value in evidence.get("leak_vocabulary") or []:
        if isinstance(value, str) and value:
            tokens.add(value)
    return {token for token in tokens if len(token) >= MIN_LEAK_TOKEN_LENGTH}


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


def check_network_boundary(evidence: dict[str, Any], failures: list[str]) -> None:
    boundary = evidence.get("network_boundary") or {}
    for key in (
        "direct_public_socket_blocked",
        "approved_model_host_reachable_via_proxy",
        "unrelated_https_blocked_by_proxy",
    ):
        if boundary.get(key) is not True:
            failures.append(f"network boundary not proven: {key}")


def check_probe_coverage(evidence: dict[str, Any], failures: list[str]) -> None:
    """Gate 3 half A + the coverage-hole guard: exactly the declared 12
    probe_ids, no more, no fewer, no duplicates, all in one evidence.probes
    list (the "same trial batch" requirement)."""
    probes = evidence["probes"]
    probe_ids = [p.get("probe_id") for p in probes]
    if len(probe_ids) != len(set(probe_ids)):
        failures.append(f"duplicate probe_id(s) recorded: {probe_ids}")
    observed = set(probe_ids)
    missing = DECLARED_PROBES - observed
    unexpected = observed - DECLARED_PROBES
    if missing:
        failures.append(
            f"probe coverage hole: {len(missing)} declared probe(s) never "
            f"ran: {sorted(missing)}"
        )
    if unexpected:
        failures.append(f"undeclared probe_id(s) recorded: {sorted(unexpected)}")
    if len(probe_ids) != len(DECLARED_PROBES):
        failures.append(
            f"probe count {len(probe_ids)} does not match the declared "
            f"list count {len(DECLARED_PROBES)}"
        )


def check_no_leaked_rows(evidence: dict[str, Any], failures: list[str]) -> None:
    """Gate 1 — every probe's org_b_rows must be empty."""
    for probe in evidence["probes"]:
        leaked = probe.get("org_b_rows") or []
        if leaked:
            failures.append(
                f"{probe.get('probe_id')}: org-B's identical query returned "
                f"{len(leaked)} row(s) belonging to org A: {leaked!r}"
            )


def check_no_leaked_identifiers(evidence: dict[str, Any], failures: list[str]) -> None:
    """Gate 2 — no org-A UUID/identifier appears in any error string."""
    tokens = seed_identifier_tokens(evidence)
    for probe in evidence["probes"]:
        error = probe.get("org_b_error")
        if not error:
            continue
        error_text = str(error)
        for token in tokens:
            if token and token in error_text:
                failures.append(
                    f"{probe.get('probe_id')}: org_b_error leaks org-A "
                    f"identifier {token!r}: {error_text[:200]!r}"
                )
        for match in _UUID_RE.findall(error_text):
            if match in tokens:
                failures.append(
                    f"{probe.get('probe_id')}: org_b_error embeds org-A "
                    f"UUID {match!r}"
                )


def objective_failures(evidence: dict[str, Any], state: dict[str, Any]) -> list[str]:
    require_keys(evidence)  # raises InfrastructureFailure on structural defects
    check_org_a_nonempty(
        evidence
    )  # raises InfrastructureFailure — the false-pass guard

    failures: list[str] = []
    check_identity(evidence, failures)
    check_network_boundary(evidence, failures)
    check_probe_coverage(evidence, failures)
    check_no_leaked_rows(evidence, failures)
    check_no_leaked_identifiers(evidence, failures)
    return failures


# Consumed by ``load_inputs`` for live (non-calibration) runs only.
objective_failures.live_reader = live_database_state  # type: ignore[attr-defined]


def db_snapshot(evidence: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return {"database_state": state}


def main() -> int:
    return run_verifier_main(
        BENCHMARK_ID, objective_failures, report_extra_fn=db_snapshot
    )


if __name__ == "__main__":
    sys.exit(main())
