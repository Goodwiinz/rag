# Decision: Neo4j knowledge-graph disaster recovery

**Status:** Accepted
**Date:** 2026-07-11
**Audit finding:** D8 (P5.7) — dead `backup:` block in the
`knowledge-graph-analytics` Helm values consumed by no template.
**Scope:** `dev` (the only actively deployed env). Production is scaffolded but
not promoted.

## Context

The `infrastructure/helm/knowledge-graph-analytics` chart carried a
`backup:` block (`enabled`, `schedule`, `retention`, `storageClass`,
`storageSize`) in `values.yaml` and a `backup: { enabled: false }` override in
`values-production.yaml`. **No template referenced `.Values.backup`** — there is
no CronJob, no VolumeSnapshot, no backup sidecar. The block was aspirational
configuration that did nothing: it advertised a backup capability the chart
never implemented, which is worse than silence because it implies a DR posture
that does not exist.

The Neo4j StatefulSet (`templates/neo4j-statefulset.yaml`) uses a single PVC
(`neo4j.persistence.size`, default `10Gi`) on the cluster's default storage
class. There is no snapshot, replication, or off-cluster copy of the graph.

## Decision

**Document the DR posture; do not build backup automation now.**

The knowledge graph is **derived data**. Every entity and relationship in Neo4j
is (re)producible from the source documents, which are the durable systems of
record:

- Document metadata and text live in Supabase Postgres.
- Original files live in DO Spaces (`STORAGE_BACKEND=s3`).

The graph is populated by extraction over those documents, so the recovery
procedure is **rebuild, not restore**:

- `backend/scripts/maintenance/rebuild_kg_llm.py` — wipes Neo4j and re-extracts
  entities/relationships from every document via the LLM extraction pipeline
  (the canonical full rebuild).
- `backend/scripts/repair_kg.py` / `backend/scripts/maintenance/repair_kg.py` —
  targeted repair/reconciliation of graph state against Postgres.

Because the graph can be rebuilt from durable sources, **PVC loss on `dev` is
accepted**: the cost of loss is compute time to re-extract, not permanent data
loss. Backing up derived data on `dev` is not worth the operational surface.

## Consequences

- The dead `backup:` block is removed from `values.yaml` and
  `values-production.yaml`. A comment in each points here.
- DR for `dev` = run the rebuild script after any Neo4j data loss. Expect a
  re-extraction window proportional to the document corpus (LLM calls per
  chunk), during which KG-backed features return partial/empty results.
- No RPO/RTO guarantee is claimed for the graph on `dev`.

## Revisit before production promotion

This decision is scoped to `dev`. Before production is actively deployed, the DR
story **must be revisited**, because a full LLM re-extraction may be too slow /
costly to serve as the only recovery path at production scale. Options to
evaluate then:

- Managed/scheduled Neo4j backups (e.g. `neo4j-admin database dump` to DO
  Spaces on a CronJob) with a defined retention and RPO/RTO.
- DO block-storage volume snapshots of the Neo4j PVC.
- Keeping rebuild-from-source as the fallback path regardless.

Whatever is chosen must ship as an actual template in the chart — not a values
block with no consumer.
