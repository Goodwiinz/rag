# Deterministic Retrieval Mode

This document defines the deterministic behavior contract for hybrid search responses.

## Contract

- Deterministic mode is applied on `/search/hybrid` and `/search/authenticated/hybrid`.
- Responses include deterministic metadata fields:
  - `answer_type`
  - `confidence`
  - `coverage`
  - `decision_trace_id`
  - `trace.decision_trace_id`
  - `deterministic_status`
  - `deterministic_message`

## Gate Statuses

- `SUPPORTED`: coverage and signal checks passed.
- `INSUFFICIENT_EVIDENCE`: low cross-source coverage.
- `CONFLICTING_EVIDENCE`: top evidence indicates conflicting conclusions.
- `NO_MATCH`: no candidate evidence available.

## Tie-Break Ordering

When fused scores tie, ranking is deterministic by:
1. source quality tier,
2. newest `updated_at`,
3. lexicographic `document_id`.

## Replay Guarantee

Given same query, same index snapshot, and same config/version:
- deterministic payload fields should remain stable,
- gate status should be reproducible,
- trace id should be present for auditability.
