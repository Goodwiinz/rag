# LangSmith Audit Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dev manual-test traces trustworthy, prevent weak intent guesses from hiding required tools, and stop irrelevant or sensitive DO KB chunks from reaching the model or LangSmith.

**Architecture:** Establish a real current-turn boundary in the online evaluators, add a fail-closed evidence gate plus deterministic action overrides in routing, run all tenant-filtered DO KB chunks through one sanitize/deduplicate/rerank pipeline, and attach release plus durable request identifiers to every agent root trace. The implementation keeps evaluator, routing, retrieval, and observability changes independently testable, then verifies them together against the original manual inputs on dev.

**Tech Stack:** Python 3.11, FastAPI, LangGraph, LangSmith, Pydantic, pytest, Azure Cohere rerank, Helm/ArgoCD, PostgreSQL/Supabase.

## Global Constraints

- Preserve tenant and project filtering before any chunk is returned or sent to the reranker.
- Never log, snapshot, or assert the literal email address or phone number observed in the live resume. Tests must use synthetic PII.
- Sanitization and content deduplication are mandatory even when Cohere is disabled, unavailable, times out, or opens its circuit breaker.
- A low-confidence specialized intent may not win solely because the keyword classifier returned zero evidence.
- The explicit project-creation override must route to the subgraph that exposes `create_project`; it must not execute the tool without the normal model/tool flow.
- A missing evaluator turn boundary is an evaluator failure, not a vacuous pass.
- Trace metadata contains identifiers and release facts only. It must not contain prompts, document text, tool results, secrets, or raw user content.
- Do not upload or replace LangSmith online evaluator rules, deploy to dev, mutate Supabase data, or change ArgoCD state until the code review and local gates are green.
- Do not stage the pre-existing RLS migrations, manual-test document, or `skills-lock.json` with this work.

---

## Finding-to-Task Map

| Finding | Fix task | Acceptance evidence |
|---|---|---|
| P1: prior tool calls counted as current | Task 1 | Live-shaped multi-turn fixture counts only tool calls after the latest human boundary |
| P1: synthetic ranking exposes irrelevant PII | Tasks 3-4 | Returned/model/trace chunks are sanitized and deduplicated; dev uses Cohere reranking |
| P2: weak guesses select specialized routes | Task 2 | 0.28 KG and 0.33 writing guesses fall back; project creation routes to research deterministically |
| P2: missing release and request correlation | Task 5 | Root trace carries release, run, user message, client message, and request identifiers; cancellation ledger correlates by run/request ID |

## Execution Order and Ownership Boundaries

1. **Evaluation contract:** Task 1. Land first so later dev results are measured against the correct turn.
2. **Routing contract:** Task 2. Independent of retrieval and tracing.
3. **Retrieval data-minimization contract:** Tasks 3 and 4. Task 4 depends on Task 3's shared pipeline.
4. **Trace correlation contract:** Task 5. May proceed independently after Task 1, but must be present before the dev acceptance run.
5. **Integrated verification:** Task 6. Depends on Tasks 1-5.

Keep each boundary in its own commit. If implementation is parallelized later, no two workers should edit the same files: Task 3 owns the shared DO KB postprocessor and redactor; Task 4 owns its call sites/config; Task 5 owns streaming/run-event metadata.

---

### Task 1: Scope trajectory evaluators to the current human turn

**Files:**

- Modify: `backend/tests/eval/langsmith_trajectory_evaluators.py`
- Modify: `backend/tests/eval/test_eval_harness.py`
- Modify: `backend/tests/eval/upload_trajectory_rules.py`

**Contract:**

`_extract_messages(run)` must scan `outputs.messages` backward to the latest message with `type == "human"` and return only the messages after that boundary. It must return `None` when outputs are malformed or no human boundary exists. `tool_call_validity`, `no_tool_loop`, and `plan_adherence` must return score `0` with an explicit boundary error comment when the helper returns `None`.

This uses the same semantic boundary as the runtime's current-turn tool dedupe and iteration ledger: the latest human message begins the current turn. It deliberately does not subtract input IDs because live roots have asymmetric input/output histories.

- [ ] **Step 1: Replace synthetic evaluator fixtures with live-shaped turns**

Update `_run`, `_traj`, and `TestToolCallValidity._run` in `backend/tests/eval/test_eval_harness.py` so every normal trajectory contains a human boundary before the AI/tool messages under evaluation.

Add a helper that builds this exact regression shape:

```python
{
    "inputs": {
        "messages": [
            {"type": "human", "id": "human-old"},
            {"type": "human", "id": "human-current"},
        ]
    },
    "outputs": {
        "messages": [
            {"type": "human", "id": "human-old"},
            {
                "type": "ai",
                "id": "ai-old",
                "tool_calls": [{"id": "tc-old", "name": "search_documents", "args": {}}],
            },
            {"type": "tool", "id": "tool-old", "tool_call_id": "tc-old"},
            {"type": "human", "id": "human-current"},
            {
                "type": "ai",
                "id": "ai-current",
                "tool_calls": [{"id": "tc-current", "name": "do_kb_retrieve", "args": {}}],
            },
            {"type": "tool", "id": "tool-current", "tool_call_id": "tc-current"},
            {"type": "ai", "id": "final-current", "content": "Answer"},
        ]
    },
}
```

- [ ] **Step 2: Add failing evaluator regressions**

Add tests proving:

- `_extract_messages` excludes `ai-old` and `tool-old` while retaining the current AI/tool/final suffix.
- an unmatched prior-turn tool call does not fail current-turn tool validity.
- three prior-turn duplicate calls do not fail the current turn's loop score.
- a prior `search_documents` call does not satisfy or distort the current plan's `do_kb_retrieve` step.
- a run with output AI/tool messages but no human boundary fails each affected evaluator with a comment containing `turn boundary`.

- [ ] **Step 3: Run the focused tests and confirm RED**

Run:

```bash
backend/.venv/bin/python -m pytest -q backend/tests/eval/test_eval_harness.py
```

Expected: the live-shaped scoping and missing-boundary tests fail against ID subtraction; pre-existing evaluator tests remain otherwise intact.

- [ ] **Step 4: Implement the explicit boundary**

In `backend/tests/eval/langsmith_trajectory_evaluators.py`:

- remove input-ID subtraction from `_extract_messages`;
- validate `outputs` and `outputs.messages` shapes;
- scan backward for the latest human message;
- return the suffix after that message;
- return `None` when no safe boundary exists;
- add the same fail-closed guard and concise comment to all three consumers.

Keep the helper sandbox-compatible: imports must be inside functions and it may not import `src.*`.

- [ ] **Step 5: Keep uploaded evaluator blobs self-contained**

Update `backend/tests/eval/upload_trajectory_rules.py` only if the helper name or helper set changes. Extend its smoke call to include a human boundary so normal evaluator code is actually exercised during extraction. Do not call the LangSmith API in this task.

- [ ] **Step 6: Run the focused evaluator gate and uploader extraction smoke test**

Run:

```bash
backend/.venv/bin/python -m pytest -q backend/tests/eval/test_eval_harness.py
backend/.venv/bin/python - <<'PY'
from pathlib import Path
from tests.eval.upload_trajectory_rules import METRICS, _extract_function

source = Path("backend/tests/eval/langsmith_trajectory_evaluators.py").read_text()
for function_name, _ in METRICS:
    _extract_function(source, function_name)
print("all evaluator blobs compile and smoke-call")
PY
```

Expected: all tests pass and every evaluator blob compiles and executes its smoke call without network access.

- [ ] **Step 7: Commit the evaluator fix**

```bash
git add backend/tests/eval/langsmith_trajectory_evaluators.py backend/tests/eval/test_eval_harness.py backend/tests/eval/upload_trajectory_rules.py
git commit -m "fix(eval): scope trajectory rules to current turn"
```

---

### Task 2: Require evidence for specialized intent routes

**Files:**

- Modify: `backend/src/services/agent/classifier.py`
- Modify: `backend/src/services/agent/_prompts.py`
- Modify: `backend/tests/unit/services/test_agent_classifier.py`

**Contract:**

Introduce `_SPECIALIZED_LLM_MIN_CONFIDENCE = 0.60`. When keyword confidence is `0.0`, retain a sub-threshold LLM result only when it is `general` or its confidence is at least `0.60`. Specialized results below `0.60` fall back to a `general` result with `source="fallback"` and the original confidence preserved for telemetry.

Add deterministic action overrides before keyword and LLM classification:

```python
ACTION_INTENT_OVERRIDES = (
    ("create a project", "research"),
    ("create project", "research"),
    ("new project", "research"),
)
```

Match normalized whole phrases, return confidence `1.0`, and use `source="action_override"`. This route exposes `create_project`; it does not itself execute the action.

- [ ] **Step 1: Add failing route regressions**

In `backend/tests/unit/services/test_agent_classifier.py`, add:

- LLM `knowledge_graph/0.28` plus zero keyword evidence returns `general/fallback`.
- LLM `writing/0.33` plus zero keyword evidence returns `general/fallback`.
- LLM `writing/0.59` plus zero evidence returns `general/fallback`.
- LLM `writing/0.60` plus zero evidence remains `writing/llm`.
- existing `finish the plan` with `writing/0.62` and prior-tool context remains writing.
- `create a project named Security Review` returns `research/action_override` and never calls the LLM.
- `recreate a projection chart` does not trigger the project-creation override.

- [ ] **Step 2: Run the focused classifier tests and confirm RED**

```bash
backend/.venv/bin/python -m pytest -q backend/tests/unit/services/test_agent_classifier.py
```

Expected: the low-confidence specialized-route and action-override tests fail; the existing 0.62 continuation behavior still documents the compatibility boundary.

- [ ] **Step 3: Implement action override matching**

Put the immutable override table in `backend/src/services/agent/_prompts.py` beside `INTENT_KEYWORDS` and re-export it through the existing graph compatibility seam. In `classifier.py`, add a small matcher using the same normalized, word-boundary-safe phrase semantics as keyword classification and execute it before the short-query and LLM paths.

- [ ] **Step 4: Implement the specialized confidence floor**

Replace the unconditional zero-keyword branch at `classifier.py:404-420` with:

- return the LLM result when its intent is `general`;
- return it when specialized confidence is at least `0.60`;
- otherwise return `general/fallback`, preserve the weak confidence value, and record a reason that specialized evidence was insufficient.

Update the function docstring and structured log fields so dashboards distinguish `action_override`, accepted weak specialized classifications, and rejected weak guesses.

- [ ] **Step 5: Run focused and route-level tests**

```bash
backend/.venv/bin/python -m pytest -q \
  backend/tests/unit/services/test_agent_classifier.py \
  backend/tests/unit/services/test_agent_graph_partial.py
```

Expected: all classifier and subgraph-route tests pass; project creation resolves to the route that contains `create_project`.

- [ ] **Step 6: Commit the routing fix**

```bash
git add backend/src/services/agent/classifier.py backend/src/services/agent/_prompts.py backend/tests/unit/services/test_agent_classifier.py
git commit -m "fix(agent): gate weak specialized intent routes"
```

---

### Task 3: Build a mandatory DO KB model-boundary sanitizer and deduplicator

**Files:**

- Create: `backend/src/services/do_kb/postprocess.py`
- Modify: `backend/src/services/agent/_pii_redact.py`
- Modify: `backend/tests/services/agent/test_pii_redact.py`
- Create: `backend/tests/services/do_kb/test_postprocess.py`

**Contract:**

Create one pure function:

```python
def sanitize_and_deduplicate_chunks(chunks: list[Chunk]) -> list[Chunk]:
    ...
```

For each chunk, it must:

1. redact PII from `Chunk.text`;
2. recursively redact string values in `Chunk.metadata` without modifying `document_id`;
3. normalize the sanitized text with Unicode normalization, collapsed whitespace, and `casefold()`;
4. hash the normalized text with SHA-256;
5. retain only the first occurrence, which is the highest-ranked occurrence because upstream order is preserved;
6. return model copies and never mutate the input chunks.

Deduplicate on sanitized content, not raw content, so copies that differ only by contact information collapse before reranking. Drop empty chunks after redaction. Export counts through a frozen result object so call sites can record `input_count`, `output_count`, `duplicate_count`, and `redacted_count` without logging content.

- [ ] **Step 1: Add focused redaction regressions**

Extend `backend/tests/services/agent/test_pii_redact.py` with synthetic nested metadata cases. Assert that email, phone, SSN, credentials, tokens, and UUID-shaped secrets are replaced while ordinary prose remains.

- [ ] **Step 2: Add failing postprocessor tests**

Create `backend/tests/services/do_kb/test_postprocess.py` covering:

- text email and phone redaction;
- nested metadata redaction;
- exact duplicate chunks with different document IDs collapse to one;
- chunks differing only by synthetic contact information collapse after redaction;
- distinct text from the same document remains distinct;
- first/highest-ranked duplicate is retained;
- whitespace/case variants collapse;
- an empty-after-sanitization chunk is dropped;
- original `Chunk` objects and metadata dicts are unchanged;
- returned counts contain numbers only and no content.

- [ ] **Step 3: Run the new tests and confirm RED**

```bash
backend/.venv/bin/python -m pytest -q \
  backend/tests/services/agent/test_pii_redact.py \
  backend/tests/services/do_kb/test_postprocess.py
```

Expected: imports or assertions for the new postprocessor fail before implementation.

- [ ] **Step 4: Implement recursive safe redaction reuse**

Expose `redact_nested_pii(value: Any) -> Any`, a non-truncating recursive sanitizer in `backend/src/services/agent/_pii_redact.py` for trusted server-side model-boundary use. Keep the existing browser/tool-argument cap behavior unchanged. The new DO KB postprocessor must reuse the established regexes rather than duplicate them.

- [ ] **Step 5: Implement the postprocessor**

Use `unicodedata.normalize("NFKC", text)`, whitespace collapse, `casefold()`, and `hashlib.sha256`. Return a frozen `ChunkPostprocessResult` containing the sanitized chunk list and integer counters. Keep the module free of database, network, settings, and logging dependencies.

- [ ] **Step 6: Run the focused data-minimization tests**

```bash
backend/.venv/bin/python -m pytest -q \
  backend/tests/services/agent/test_pii_redact.py \
  backend/tests/services/do_kb/test_postprocess.py
```

Expected: all tests pass without literal sensitive values appearing in pytest output.

- [ ] **Step 7: Commit the shared retrieval boundary**

```bash
git add backend/src/services/agent/_pii_redact.py backend/src/services/do_kb/postprocess.py backend/tests/services/agent/test_pii_redact.py backend/tests/services/do_kb/test_postprocess.py
git commit -m "feat(retrieval): sanitize and deduplicate DO KB chunks"
```

---

### Task 4: Enforce the sanitizer in both DO KB paths and enable calibrated reranking

**Files:**

- Modify: `backend/src/core/config.py`
- Modify: `backend/src/services/do_kb/models.py`
- Modify: `backend/src/services/do_kb/rerank.py`
- Modify: `backend/src/services/agent/tools_impl.py`
- Modify: `backend/src/services/agent/_nodes_rag.py`
- Modify: `backend/tests/unit/services/test_do_kb_rerank.py`
- Modify: `backend/tests/services/do_kb/test_retrieval_shared.py`
- Modify: `backend/tests/unit/services/test_agent_citation_context_regressions.py`
- Modify: `infrastructure/helm/knowledge-graph-analytics/values-dev.yaml`

**Contract:**

Both `_tool_do_kb_retrieve` and `_try_primary_do_kb_read` must execute this order:

```text
DO retrieve -> tenant/project resolve+filter -> sanitize+deduplicate -> Cohere rerank -> payload/context shaping
```

The sanitizer runs unconditionally. Reranking is enabled by default and explicitly enabled in dev. Cohere receives only sanitized text. A rerank failure returns the already-sanitized, deduplicated chunks in their prior order.

`cohere_rescore_chunks` must mark successful results with `metadata["score_source"] = "cohere"`. Passthrough chunks retain `score_source="rank_proxy"` when DO omitted a score. Payload shaping includes `score_source` so a synthetic rank proxy is never represented as calibrated relevance in trace evidence.

- [ ] **Step 1: Add failing tool-path safety tests**

Extend `backend/tests/unit/services/test_do_kb_rerank.py` to assert:

- flag on: sanitize/deduplicate runs before Cohere and Cohere sees sentinel-redacted content;
- flag off: sanitize/deduplicate still runs and raw PII never appears in returned chunks;
- Cohere timeout/failure: returned chunks remain sanitized and deduplicated;
- successful rerank reorders chunks, replaces scores, and sets `score_source="cohere"`;
- passthrough retains `score_source="rank_proxy"` rather than claiming calibrated relevance.

- [ ] **Step 2: Add failing primary-RAG parity tests**

In `backend/tests/services/do_kb/test_retrieval_shared.py`, add the same safety assertions for `_try_primary_do_kb_read`. In `backend/tests/unit/services/test_agent_citation_context_regressions.py`, assert shaped contexts contain sanitized content and score provenance.

- [ ] **Step 3: Add a configuration regression**

Add a test asserting the application default is `AGENT_DOKB_COHERE_RERANK=True`. Add the explicit dev Helm environment value:

```yaml
- name: AGENT_DOKB_COHERE_RERANK
  value: "true"
```

Do not add Cohere credentials to Git; they continue to come from the existing secret source.

- [ ] **Step 4: Run the focused retrieval tests and confirm RED**

```bash
backend/.venv/bin/python -m pytest -q \
  backend/tests/services/do_kb/test_postprocess.py \
  backend/tests/unit/services/test_do_kb_rerank.py \
  backend/tests/services/do_kb/test_retrieval_shared.py \
  backend/tests/unit/services/test_agent_citation_context_regressions.py
```

Expected: ordering, unconditional sanitization, provenance, and default-flag assertions fail before call-site changes.

- [ ] **Step 5: Wire the shared pipeline into both call sites**

After `resolve_and_filter_chunks`, call `sanitize_and_deduplicate_chunks`, record only its counters, and pass its chunks to `cohere_rescore_chunks`. Never shape or return the raw `result.chunks` list after this point.

Keep existing empty/project-scope fallback semantics: if sanitization removes every chunk, the primary RAG path returns `None` to invoke hybrid fallback and the tool path returns an empty chunk list with a non-sensitive reason.

- [ ] **Step 6: Mark score provenance and enable reranking**

In `Chunk.from_do_payload`, mark real upstream scores as `upstream` and synthesized scores as `rank_proxy`. In `cohere_rescore_chunks`, copy successful results with `score_source="cohere"`. Change the config default and dev Helm value to true. Extend the existing rerank tests to cover both `Chunk.from_do_payload` provenance branches.

- [ ] **Step 7: Run retrieval and static gates**

```bash
backend/.venv/bin/python -m pytest -q \
  backend/tests/services/do_kb \
  backend/tests/unit/services/test_do_kb_rerank.py \
  backend/tests/unit/services/test_agent_citation_context_regressions.py
backend/.venv/bin/python -m ruff check \
  backend/src/services/do_kb \
  backend/src/services/agent/_pii_redact.py \
  backend/src/services/agent/_nodes_rag.py \
  backend/src/services/agent/tools_impl.py
```

Expected: all tests and Ruff pass. No raw synthetic PII appears in failure output or snapshots.

- [ ] **Step 8: Render the dev chart**

```bash
helm template nous-dev infrastructure/helm/knowledge-graph-analytics \
  -f infrastructure/helm/knowledge-graph-analytics/values-dev.yaml \
  >/tmp/nous-dev-rendered.yaml
rg -n -A2 "AGENT_DOKB_COHERE_RERANK" /tmp/nous-dev-rendered.yaml
rm /tmp/nous-dev-rendered.yaml
```

Expected: the backend container receives exactly one effective `AGENT_DOKB_COHERE_RERANK=true` value. Delete the temporary rendered file after inspection.

- [ ] **Step 9: Commit retrieval enforcement**

```bash
git add backend/src/core/config.py backend/src/services/do_kb/rerank.py backend/src/services/do_kb/models.py backend/src/services/agent/tools_impl.py backend/src/services/agent/_nodes_rag.py backend/tests/unit/services/test_do_kb_rerank.py backend/tests/services/do_kb/test_retrieval_shared.py backend/tests/unit/services/test_agent_citation_context_regressions.py infrastructure/helm/knowledge-graph-analytics/values-dev.yaml
git commit -m "fix(retrieval): enforce safe reranked DO KB results"
```

---

### Task 5: Add release, submission, message, and cancellation correlation to root traces

**Files:**

- Create: `backend/src/services/agent/trace_metadata.py`
- Modify: `backend/src/api/agent/streaming.py`
- Modify: `backend/src/services/agent/agent_execution_service.py`
- Modify: `backend/src/services/agent/run_event_types.py`
- Create: `backend/tests/unit/services/agent/test_trace_metadata.py`
- Create: `backend/tests/unit/api/test_agent_streaming_trace_metadata.py`
- Modify: `backend/tests/unit/services/agent/test_run_event_types.py`
- Modify: `infrastructure/helm/knowledge-graph-analytics/templates/backend-deployment.yaml`

**Contract:**

Create a pure metadata builder that strips empty values, bounds every value to 128 characters, and returns only these keys when available:

```python
{
    "user_id": "...",
    "org_id": "...",
    "thread_id": "...",
    "request_id": "...",
    "agent_run_id": "...",
    "user_message_id": "...",
    "client_message_id": "...",
    "deployment_sha": "...",
    "image_tag": "...",
}
```

`deployment_sha` comes from `GIT_SHA` with `APP_VERSION` as fallback. `image_tag` comes from an `IMAGE_TAG` environment variable populated by the rendered Helm image tag. The stream path uses `AcceptedSubmission.run_id` and `AcceptedSubmission.user_message_id`; `client_message_id` comes from the current user request; `request_id` is the existing `_SeqEmitter.trace_id`.

The background job path uses the same builder with its `job_id` so traces from streaming and job execution share one query contract.

For disconnect cancellation, add optional `request_id` to `RunStoppingPayload` and `RunCancelledPayload`, and persist the same `request_id` carried in LangSmith metadata. This allows a root trace to be joined to `agent_runs`/`agent_run_events` by `agent_run_id`, and its specific disconnect request to be verified by `request_id`.

- [ ] **Step 1: Add failing pure metadata tests**

In `backend/tests/unit/services/agent/test_trace_metadata.py`, assert:

- all identifiers and release values are emitted when provided;
- `GIT_SHA` and `IMAGE_TAG` are read from patched environment variables;
- `APP_VERSION` is the SHA fallback;
- missing optional identifiers are omitted, not serialized as `"None"`;
- values longer than 128 characters are bounded;
- unknown kwargs cannot silently enter the metadata contract.

- [ ] **Step 2: Add failing streaming integration tests**

In `backend/tests/unit/api/test_agent_streaming_trace_metadata.py`, use the existing generator harness to capture the config passed to `graph.astream_events`. Assert the metadata contains the accepted run ID, persisted user message ID, current client message ID, emitter request ID, deployment SHA, image tag, user/org/thread IDs, and no prompt content.

Add a degraded no-durable-thread case proving release/request/client identifiers remain present while run/message identifiers are omitted.

- [ ] **Step 3: Add failing cancellation-payload tests**

Extend `backend/tests/unit/services/agent/test_run_event_types.py` to accept a bounded `request_id` on stopping/cancelled events and reject unexpected fields. Extend the streaming disconnect test to assert `_finalize_run` receives:

```python
{"reason": "client_disconnected", "request_id": expected_request_id}
```

- [ ] **Step 4: Run the focused trace tests and confirm RED**

```bash
backend/.venv/bin/python -m pytest -q \
  backend/tests/unit/services/agent/test_trace_metadata.py \
  backend/tests/unit/api/test_agent_streaming_trace_metadata.py \
  backend/tests/unit/api/test_agent_streaming_trace_bootstrap.py \
  backend/tests/unit/services/agent/test_run_event_types.py
```

Expected: missing metadata keys, release values, and cancellation request ID assertions fail.

- [ ] **Step 5: Implement and apply the shared metadata builder**

Use the builder for the root `config["metadata"]` dict in both `streaming.py` and `agent_execution_service.py`. Compute the current user `client_message_id` once from the latest request human message. Do not alter LangGraph's configurable IDs or runtime snapshot fields.

- [ ] **Step 6: Correlate disconnect cancellation**

Add `request_id` to the typed stopping/cancelled payloads. In the stream disconnect branch, pass `emitter.trace_id` into the terminal event payload. Keep `reason="client_disconnected"` as a separate stable field.

- [ ] **Step 7: Expose the deployed image tag to the backend container**

In `infrastructure/helm/knowledge-graph-analytics/templates/backend-deployment.yaml`, add:

```yaml
- name: IMAGE_TAG
  value: {{ .Values.backend.image.tag | default .Chart.AppVersion | quote }}
```

Place it after user-supplied environment values so the rendered deployment has one authoritative image tag matching the container image. Keep `GIT_SHA` sourced from the image build.

- [ ] **Step 8: Run trace, cancellation, and chart gates**

```bash
backend/.venv/bin/python -m pytest -q \
  backend/tests/unit/services/agent/test_trace_metadata.py \
  backend/tests/unit/api/test_agent_streaming_trace_metadata.py \
  backend/tests/unit/api/test_agent_streaming_trace_bootstrap.py \
  backend/tests/unit/api/test_agent_streaming_confirm_disconnect.py \
  backend/tests/unit/services/agent/test_run_event_types.py \
  backend/tests/unit/services/test_agent_cancellation.py
helm template nous-dev infrastructure/helm/knowledge-graph-analytics \
  -f infrastructure/helm/knowledge-graph-analytics/values-dev.yaml \
  >/tmp/nous-dev-rendered.yaml
rg -n -A2 "name: IMAGE_TAG" /tmp/nous-dev-rendered.yaml
rm /tmp/nous-dev-rendered.yaml
```

Expected: all tests pass and the rendered `IMAGE_TAG` equals the backend container image tag.

- [ ] **Step 9: Commit trace correlation**

```bash
git add backend/src/services/agent/trace_metadata.py backend/src/api/agent/streaming.py backend/src/services/agent/agent_execution_service.py backend/src/services/agent/run_event_types.py backend/tests/unit/services/agent/test_trace_metadata.py backend/tests/unit/api/test_agent_streaming_trace_metadata.py backend/tests/unit/services/agent/test_run_event_types.py infrastructure/helm/knowledge-graph-analytics/templates/backend-deployment.yaml
git commit -m "feat(agent): correlate traces with releases and runs"
```

---

### Task 6: Run the integrated gate, deploy to dev, and replay the audited inputs

**Files:**

- Modify only if results need durable documentation: `docs/testing/manual-dev-chat-fixes-2026-08-04.md`
- Do not modify: `docs/testing/manual-dev-chat-fixes-2026-08-03.md` (pre-existing user file)

- [ ] **Step 1: Run the complete focused local gate**

```bash
backend/.venv/bin/python -m pytest -q \
  backend/tests/eval/test_eval_harness.py \
  backend/tests/unit/services/test_agent_classifier.py \
  backend/tests/services/agent/test_pii_redact.py \
  backend/tests/services/do_kb \
  backend/tests/unit/services/test_do_kb_rerank.py \
  backend/tests/unit/services/test_agent_citation_context_regressions.py \
  backend/tests/unit/services/agent/test_trace_metadata.py \
  backend/tests/unit/api/test_agent_streaming_trace_metadata.py \
  backend/tests/unit/api/test_agent_streaming_trace_bootstrap.py \
  backend/tests/unit/api/test_agent_streaming_confirm_disconnect.py \
  backend/tests/unit/services/agent/test_run_event_types.py
```

Expected: green focused suite with no network credentials required.

- [ ] **Step 2: Run changed-Python quality gates**

Resolve the exact changed Python set first:

```bash
git diff --name-only --diff-filter=ACMR -- '*.py'
```

Run Ruff, Black check, isort check, and MyPy using the repository's normal changed-file CI commands. Do not broaden formatting to unrelated files.

- [ ] **Step 3: Review the final diff against the four findings**

Verify:

- no evaluator still subtracts only input message IDs;
- every specialized zero-evidence LLM route below `0.60` falls back to general;
- both DO KB call sites sanitize/deduplicate before rerank and never return the pre-pipeline list;
- rerank is on in app default and dev Helm;
- root trace metadata has release/run/message/request identifiers;
- cancellation persists the same request identifier;
- no secrets, literal live PII, or unrelated untracked files entered the diff.

- [ ] **Step 4: Deploy the reviewed commits to dev through the normal GitOps path**

After approval, deploy using the repository's established branch/PR workflow. Record all five release facts before manual testing:

1. merged commit SHA;
2. built registry tag/digest;
3. GitOps `backend.image.tag`;
4. ArgoCD revision and sync/health;
5. live backend pod image.

Do not treat `Synced/Healthy` alone as proof that the new image is live.

- [ ] **Step 5: Replace the online evaluator rules only after the new backend is live**

First run the local extraction smoke test from Task 1. Then, with explicit authorization and the LangSmith environment loaded, replace the rules using the repository uploader. Record the returned rule IDs and sampling rate. Confirm new root runs receive evaluator results; do not infer success from rule creation alone.

- [ ] **Step 6: Replay the original manual inputs on dev**

Use fresh client message IDs and record the accepted `agent_run_id` for each case:

| Case | Expected route/tools | Required evidence |
|---|---|---|
| Multi-turn retrieval after an earlier search | Current turn only | Evaluators exclude the earlier `search_documents`; tool count matches current child tool spans |
| The cache question that previously classified KG at 0.28 | `general`, unless new evidence exceeds the threshold | No irrelevant KG/document search from a weak guess |
| Create a named project | `research` action override; `create_project` available | Project action is performed or a legitimate confirmation is requested |
| DO KB query that previously surfaced the unrelated resume | Reranked DO KB retrieval | No literal email/phone in tool result, model input, or trace; returned texts have unique normalized hashes |
| Long answer followed by Stop/disconnect | Cancelled durable run | Root metadata and `run.cancelled` join on `agent_run_id` and `request_id`; no later completion event for that run |

Do not reuse the literal sensitive resume text in the test report. Identify the source only by a redacted document identifier or hash.

- [ ] **Step 7: Apply the acceptance gates**

The fix passes only if all are true:

- evaluator output is present on the new roots and scopes only the current turn;
- no weak specialized classification below `0.60` wins without deterministic evidence;
- project creation exposes the correct tool;
- returned/model/trace retrieval content contains no raw PII and no content duplicates;
- successful DO KB results show `score_source=cohere` in dev;
- every root reports the deployed SHA/image tag matching the live pod;
- the stop case has a durable `run.cancelled` event correlated to the same trace request and no terminal completion event.

- [ ] **Step 8: Roll back safely if a gate fails**

- Routing regression: revert only the Task 2 commit.
- Reranker availability/latency regression: set `AGENT_DOKB_COHERE_RERANK=false` in dev, but keep the sanitizer/deduplicator deployed.
- Retrieval content regression: revert the call-site commit only after disabling the affected retrieval path; never roll back the sanitizer while raw PII exposure remains possible.
- Trace metadata regression: revert Task 5; it is observability-only and must not block core chat.
- Evaluator regression: disable/replace the affected online rules, keeping the runtime fixes deployed.

- [ ] **Step 9: Record the verified result**

If a durable report is wanted, create `docs/testing/manual-dev-chat-fixes-2026-08-04.md` containing:

- deployed SHA/image/digest evidence;
- manual input labels, not sensitive verbatim data;
- agent run and LangSmith trace IDs;
- observed route/tool/evaluator/cancellation outcomes;
- explicit pass/fail per acceptance gate;
- any rollback performed.

Do not amend the pre-existing August 3 manual-test file.

---

## Final Review Checklist

- [ ] Every audit finding maps to an implementation task and a dev acceptance check.
- [ ] All normal evaluator fixtures contain an explicit human turn boundary.
- [ ] Missing evaluator boundaries fail closed.
- [ ] The 0.60 specialized-intent floor preserves the known 0.62 continuation case.
- [ ] Project creation uses an explicit phrase override and exposes `create_project`.
- [ ] Tenant/project resolution precedes sanitization and reranking.
- [ ] Sanitization and deduplication remain active during Cohere failure.
- [ ] Cohere receives sanitized text only.
- [ ] Synthetic rank proxies are labeled and not claimed as calibrated scores.
- [ ] Trace metadata contains no content or secrets.
- [ ] Stream and job roots share the same release/run metadata contract.
- [ ] Disconnect cancellation carries the trace request ID into the durable event ledger.
- [ ] Local tests, changed-file quality gates, Helm rendering, live image verification, and manual trace replay are all recorded before closing the audit.
