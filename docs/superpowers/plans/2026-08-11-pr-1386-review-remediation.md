# PR #1386 Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve every actionable review finding on PR #1386 without weakening tenant isolation, execution evidence, or benchmark calibration.

**Architecture:** Keep production behavior changes local to deterministic routing, force-synthesis evidence classification, and Neo4j traversal scoping. Harden benchmark verifiers at their existing deterministic Layer A/trusted-source boundaries, with calibration fixtures or unit tests that first reproduce each false positive.

**Tech Stack:** Python 3.11, pytest/pytest-asyncio, LangGraph/LangChain messages, Neo4j Cypher, Harbor JSON calibration fixtures, Black/isort/mypy.

## Global Constraints

- Work only in the isolated PR worktree and preserve the user's dirty `develop` checkout.
- Follow red-green-refactor for every behavior change: add the smallest failing regression, observe the expected failure, implement, then rerun it.
- Preserve organization-first scoping precedence and the explicitly documented unscoped legacy fallback.
- Do not trust model-authored tool arguments or partial distributions as independent verifier evidence.
- Per repository guidance, execute this plan inline and use tests/CI as gates; do not add reviewer/verifier subagents.
- Commit cohesive fixes only after their focused tests pass. Do not push until the full validation matrix is green.

---

### Task 1: Make deterministic action routing action-aware

**Files:**
- Modify: `backend/tests/services/agent/test_classifier_intent.py`
- Modify: `backend/src/services/agent/_prompts.py`

- [ ] Replace the broad parameterized assertion with explicit routing cases: retrieval-only KB queries route to `research`, writing actions over KB evidence route to `writing`, and entity/relationship actions route to `knowledge_graph`.
- [ ] Run `cd backend && /tmp/pr1386-venv-311/bin/python -m pytest tests/services/agent/test_classifier_intent.py -q` and confirm the writing cases fail as `research` before production edits.
- [ ] Add ordered, more-specific action overrides for the established writing/KG tool vocabulary before the generic `knowledge base` phrases. Keep retrieval-only phrases mapped to `research`.
- [ ] Rerun the focused classifier tests and confirm green.

Expected contract examples:

```python
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Search our organization knowledge base for transformers", "research"),
        ("Compare the documents in our organization knowledge base", "writing"),
        ("Write a summary using our knowledge base evidence", "writing"),
        ("Extract entities from our knowledge base", "knowledge_graph"),
    ],
)
```

### Task 2: Preserve pending asynchronous execution evidence

**Files:**
- Modify: `backend/tests/services/agent/test_subgraph_loop_ceiling.py`
- Modify: `backend/src/services/agent/subgraphs/_factory.py`

- [ ] Add unit coverage proving a successful `ToolMessage` with JSON `{"status":"pending"}` is distinguished from failed/skipped placeholders.
- [ ] Add force-synthesis coverage proving a pending call ID is described as started and pending, never as completed or not executed.
- [ ] Run the focused test and observe the pending case fail under `_is_execution_evidence`/current prompt construction.
- [ ] Introduce a small execution-state helper returning `completed`, `pending`, or `none`; retain `_is_execution_evidence` as the compatibility predicate for completed or pending execution.
- [ ] Build separate `pending_ids` and `non_evidence_ids` prompt clauses. Explicitly instruct synthesis to report pending work as started/pending and not complete.
- [ ] Rerun `test_subgraph_loop_ceiling.py` and confirm failed/skipped behavior is unchanged.

### Task 3: Scope every Neo4j neighborhood path node and refetch

**Files:**
- Modify: `backend/tests/unit/services/test_knowledge_graph_neighborhood.py`
- Modify: `backend/src/services/knowledge_graph/knowledge_graph_service.py`

- [ ] Extend the fake session to return traversal rows on the first call and intermediate-node rows on the second call.
- [ ] Add a source-document-only regression asserting the traversal contains `all(n IN nodes(path) WHERE n.source_document_id IN $source_document_ids)` and the batch refetch repeats the same predicate and params.
- [ ] Add/retain an organization-scoped regression asserting both traversal and refetch use `organization_id` and that organization scope wins if both inputs are supplied.
- [ ] Run `cd backend && /tmp/pr1386-venv-311/bin/python -m pytest tests/unit/services/test_knowledge_graph_neighborhood.py -q` and observe the new source-document assertions fail.
- [ ] Derive one scope predicate/parameter set from organization first, then source document IDs, otherwise the legacy unscoped path. Apply it to both traversal and intermediate refetch.
- [ ] Rerun focused tests and confirm no cross-scope intermediate entity can be returned by the generated queries.

### Task 4: Remove self-authored writing evidence and require exact KG distributions

**Files:**
- Modify: `evals/agent-writing-flow-v1/tests/verify.py`
- Add: `evals/agent-writing-flow-v1/tests/test_writing_verify.py`
- Modify: `evals/agent-knowledge-graph-flow-v1/tests/verify.py`
- Add: `evals/agent-knowledge-graph-flow-v1/tests/test_knowledge_graph_verify.py`

- [ ] Add a focused/calibration negative proving a writing answer cannot be supported solely by model-authored tool-call arguments.
- [ ] Add a KG calibration negative with a missing or strict-subset type distribution that the current verifier accepts.
- [ ] Run each verifier against the new negative fixture and capture the false pass.
- [ ] Remove `execution["args"]` from writing `trusted_sources`; expose only successful tool identity and actual result payloads.
- [ ] Require both KG distributions to be dictionaries exactly equal to seeded truth in `check_get_graph_stats`.
- [ ] Apply the same exact-equality rule before adding distributions to KG `trusted_sources`.
- [ ] Rerun pass/negative calibration and the verifier's embedded calibration assertions.

### Task 5: Require the complete long-run stage contract

**Files:**
- Modify: `evals/agent-long-run-controls-v1/tests/test_long_run_verify.py`
- Modify: `evals/agent-long-run-controls-v1/tests/verify.py`
- Modify: `evals/agent-long-run-controls-v1/tests/calibration/pass-forced-partial-stage5.json`

- [ ] Add a unit mutation that removes completed stage 5 from an otherwise valid fixture and assert a deterministic chain failure.
- [ ] Run the focused test and observe the current contiguous-prefix rule accept stages `[1, 2, 3, 4]`.
- [ ] Change `check_chain` to require exactly `[1, 2, 3, 4, 5]`, while continuing to reject any stage 6 execution.
- [ ] Update the forced-partial positive fixture to include completed stages 1-5 and an unmatched attempted stage 6, preserving its intended limit-exhaustion scenario.
- [ ] Rerun long-run verifier unit tests and all long-run calibration fixtures.

### Task 6: Enforce whole emitted-token boundaries for persisted cancellation text

**Files:**
- Add: `evals/agent-fast-path-cancel-v1/tests/test_fast_path_cancel_verify.py`
- Modify: `evals/agent-fast-path-cancel-v1/tests/verify.py`

- [ ] Add a unit/calibration negative whose persisted text is a character prefix of the first emitted token but not a cumulative whole-token boundary.
- [ ] Run the focused verifier and observe the current `server_text.startswith(persisted)` check accept it.
- [ ] Build cumulative server-token text boundaries and require persisted content to equal one of those boundaries.
- [ ] Keep the existing non-empty, replay equality, and client ordered-subsequence checks intact.
- [ ] Rerun the fast-path pass fixture and every `wrong-*`/`infra-*` fixture with expected verdicts.

### Task 7: Validate, review, and publish

**Files:**
- Modify only if validation exposes a regression in files already in scope.

- [ ] Run focused backend tests for classifier, force synthesis, and KG neighborhood.
- [ ] Run focused verifier tests and enumerate calibration fixtures, requiring `pass*.json` to exit 0, `wrong*.json` to exit 10, and `infra*.json` to exit 2.
- [ ] Run backend formatting/import/type gates on changed Python files (`black --check`, `isort --check-only`, and repository mypy command).
- [ ] Run the full backend unit/test command used by CI.
- [ ] Run the 17-task × 5-trial benchmark matrix or the repository's equivalent Release Gate command and save the result summary.
- [ ] Inspect `git diff --check`, the final diff, and worktree status for unrelated changes.
- [ ] Commit cohesive remediation changes, push `agent/agent-benchmark-remediation`, and monitor all PR checks through completion.
- [ ] Resolve review threads only after the corresponding pushed code and green verification evidence exist.
