# Task 16 Report: Preserve Logical KG Neighborhood Relationship Types

## Status

Complete. The shared `get_neighborhood` Cypher projection now returns
`coalesce(rel.type, type(rel))`, preserving seeded logical relationship types
while retaining the physical `RELATED_TO` label as the legacy fallback.
Traversal, tenant scoping, depth clamping, strengths, intermediate nodes,
deduplication, and the response schema are unchanged.

## Caller Inspection

Every `get_neighborhood` reference was inspected before editing. The shared
producer serves:

- `backend/src/services/agent/tools_impl.py` via
  `_tool_explore_entity_neighborhood`.
- `backend/src/api/search/knowledge_graph.py` via the authenticated
  neighborhood endpoint.
- `backend/tests/unit/services/test_agent_audit_security.py` contains only a
  test stub.

No consumer was changed.

## Exact Files Changed

- `backend/src/services/knowledge_graph/knowledge_graph_service.py`
- `backend/tests/unit/services/test_knowledge_graph_neighborhood.py`
- `.superpowers/sdd/2026-08-10-agent-benchmark-failure-remediation/task-16-report.md`

`evals/agent-full-benchmark-v1.json` was preserved, unstaged, and excluded from
the Task 16 commit.

## TDD Evidence

RED, before the production edit:

```sh
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/unit/services/test_knowledge_graph_neighborhood.py -q --no-cov
```

Result: `1 failed`; the captured query still projected `{label: type(rel)}` and
did not contain `coalesce(rel.type, type(rel))`.

GREEN after the one-line production edit: the focused test passed. Its mocked
path returns `WORKS_FOR`, and the response-level assertion confirms
`RelationshipResponse.relationship_type is RelationshipType.WORKS_FOR`.

## Verification

- Focused test plus KG hardening, tenant-scope, and relationship org-scope
  tests: `47 passed`.
- KG calibration `pass.json`: exit `0`.
- KG calibration `empty-kg-honest.json`: exit `0`.
- KG calibration `wrong-cross-tenant.json`: exit `10`, rejected the leaked
  second-organization entity.
- Python compile: passed for both owned Python files.
- Black: passed for both owned Python files.
- Ruff: passed for both owned Python files.
- Calibration JSON parsing: passed for all three fixtures.
- `git diff --check`: passed.
- Harbor: not run, as required.

The calibration verifier's local default `/logs` report path was read-only and
initially produced infrastructure exit `2`; rerunning the unchanged fixtures
with the verifier's documented `VERIFIER_REPORT_PATH` redirected to `/tmp`
produced the required `0`, `0`, and `10` results above.

## Commit

`fix(kg): preserve logical neighborhood relationship types`

## Remaining Risk

A fresh Harbor run is still required to prove that the live Neo4j product query
returns logical relationship properties and changes Luna's final answer. The
existing Harbor artifacts predate this query change and cannot provide that
evidence.
