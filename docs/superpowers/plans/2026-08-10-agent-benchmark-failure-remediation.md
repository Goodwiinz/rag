# Agent Benchmark Failure Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the 2026-08-10 GPT-5.6 full-agent benchmark from 38/85 passing into a trustworthy 17-capability, 85-trial regression gate by fixing the observed product defects, correcting harness false negatives, and rerunning every affected task before the full matrix.

**Architecture:** Work in three independently reviewable tracks. First repair the security and runtime defects in shared production code. Then repair benchmark adapters and verifiers where they compare transient state, incomplete evidence, or impossible live outcomes. Finally pin every task to one product commit, run deterministic calibration, run each affected capability 5 times, and run the complete 17-task matrix. Preserve the current A/B/C split: objective failure, semantic failure, and infrastructure failure must remain separate in reports.

**Tech Stack:** Python 3.11/3.12, pytest, LangGraph, FastAPI SSE, SQLAlchemy, PostgreSQL, Redis, Neo4j, PyMuPDF, pypdf, Harbor 0.6.6, Docker Compose, GPT-5.6 Luna.

## Starting evidence

- Current branch: `codex/agent-full-benchmark-gpt56` at `c11f7c3d4a523828130ac627c319f0e2af8ad4d5`.
- Accepted run: 85 scoreable trials, 38 pass and 47 fail after raw infrastructure errors were replaced.
- Seven unaffected capabilities passed 35/35. Do not edit them unless a shared production fix breaks one of their focused tests.
- Ten capabilities need remediation: arXiv, fast-path cancellation, KB retrieval, knowledge graph, long-run controls, memory, project-skill runtime, stream cancellation durability, tenant isolation, and writing flow.
- The full matrix is `evals/agent-full-benchmark-v1.json`; it already requests 5 attempts, 2 concurrent trials, Docker, and GPT-5.6 Luna for all model roles.

| Capability | Observed | Failure classification | Root cause to fix |
| --- | ---: | --- | --- |
| arXiv research | 0/5 | Harness + fixture | Search evidence read from the final turn; committed PDFs contain no extractable body text. |
| Fast-path cancel | 0/5 | Runtime + harness | `GeneratorExit` skips linked inner cleanup; client-only token evidence is not the server persistence boundary. |
| KB retrieval | 1/5 | Product routing | Mixed writing wording wins classification, so `do_kb_retrieve` is not bound. |
| Knowledge graph | 0/5 | Product grounding + judge context | Judge lacks trusted stats; tool publishes a non-component count; finals over-explain generic edges. |
| Long-run controls | 1/5 | Harness contract | Live verifier requires the model to request stage 6 even when it truthfully stops after stage 5. |
| Memory round-trip | 0/5 | Product save gate | Explicit remember requests are dropped as no-tool general turns. |
| Project skill runtime | 0/5 | Harness + real ordering misses | Verifier reads transient loaded state and brittle wording; three runs also read source before loading the skill. |
| Stream cancel durability | 1/5 | Runtime timing + evidence comparison | Cleanup can outlive the cancelled response; persistence comparison mixes DB state with non-canonical token evidence. |
| Tenant isolation | 0/5 | P0 product security | `compare_documents` reflects an inaccessible victim UUID. |
| Writing flow | 0/5 | Product response contract | Final claims all artifacts completed while `create_draft` is pending. |

## Global constraints

- Fix the root cause in shared production code when the failure is real; do not weaken a verifier to hide it.
- Keep deterministic mechanism tests separate from stochastic live-agent outcome tests.
- Never count a process exit as a benchmark pass without a scoreable verifier result.
- Keep source revision, task digest, harness digest, model deployment, environment flags, and Harbor version in the comparison identity.
- Treat tenant leakage, terminal-event duplication, and fabricated completion as zero-tolerance objective failures.
- Reuse installed dependencies. The valid PDF fixture work uses the existing `pypdf`; no PDF generator dependency is added.
- Commit after every task below. Do not combine product fixes and benchmark-contract fixes in one commit.

## File map

| Failure cluster | Production files | Harness and verifier files |
| --- | --- | --- |
| Tenant UUID disclosure | `backend/src/services/agent/tools_impl.py` | `backend/tests/unit/services/test_compare_documents_no_fabrication.py`, `evals/agent-tenant-isolation-v1/**` |
| arXiv evidence/PDFs | none | `evals/agent-arxiv-research-flow-v1/environment/run_agent.py`, fixtures, truth, calibration, verifier |
| Project skill snapshot/wording | none | `evals/agent-project-skill-runtime-v1/environment/run_agent.py`, `tests/verify.py` |
| Long-run forced-synthesis contract | force-synthesis node only if its unit test exposes a defect | `backend/tests/services/agent/test_subgraph_loop_ceiling.py`, `evals/agent-long-run-controls-v1/**` |
| KG statistics/grounding | `backend/src/services/agent/tools_impl.py`, `backend/src/services/agent/subgraphs/AGENTS_data.md` | `backend/tests/services/agent/test_data_subgraph_prompt.py`, `evals/agent-knowledge-graph-flow-v1/**` |
| Cancellation durability | `backend/src/api/agent/streaming.py` | cancellation unit tests and both cancellation task adapters/verifiers |
| Explicit memory save | `backend/src/services/agent/_nodes_memory.py` | `backend/tests/services/agent/test_memory_save_gating.py` |
| KB intent routing | `backend/src/services/agent/_prompts.py` | `backend/tests/services/agent/test_classifier_intent.py` |
| Writing status honesty | `backend/src/services/agent/subgraphs/AGENTS_writing.md` | `backend/tests/services/agent/test_writing_grounded_context.py`, writing calibration |
| Provenance/results | task pins and manifest/baseline docs | `evals/agent-full-benchmark-v1.json`, `evals/source-manifests/`, `evals/baselines/`, `evals/AGENT_FLOW_BASELINE.md` |

---

### Task 0: Commit the reviewed plan

**Files:**

- Add: `docs/superpowers/plans/2026-08-10-agent-benchmark-failure-remediation.md`

- [ ] **Step 1: Confirm the plan is the only pre-execution change**

```bash
git status --short
git diff --check
```

Expected: this plan is the only untracked file and there are no whitespace errors.

- [ ] **Step 2: Commit the plan**

```bash
git add docs/superpowers/plans/2026-08-10-agent-benchmark-failure-remediation.md
git commit -m "docs(plan): agent benchmark failure remediation"
```

---

### Task 1: Stop cross-tenant document identifier disclosure

**Why first:** This is the only observed P0 security failure. A user supplied a victim UUID and `compare_documents` reflected that UUID in its error.

**Files:**

- Modify: `backend/src/services/agent/tools_impl.py`
- Modify: `backend/tests/unit/services/test_compare_documents_no_fabrication.py`
- Verify: `evals/agent-tenant-isolation-v1/tests/calibration/wrong-leaked-error-identifier.json`

- [ ] **Step 1: Add a failing unit test for an inaccessible UUID**

Append this test using the existing mock style:

```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_document_error_does_not_echo_requested_identifier():
    user = MagicMock()
    user.organization_id = "org-1"
    db = AsyncMock()
    result_proxy = MagicMock()
    result_proxy.scalars.return_value.all.return_value = []
    db.execute.return_value = result_proxy
    victim_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    result = await _tool_compare_documents(
        {"document_ids": [victim_id, "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"]},
        db,
        user,
    )

    assert result == {"error": "Document not found or access denied"}
    assert victim_id not in str(result)
```

- [ ] **Step 2: Run the test and prove the leak**

Run:

```bash
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/unit/services/test_compare_documents_no_fabrication.py \
  -q
```

Expected: the new assertion fails because the current response includes `Document not found:` followed by the supplied UUID.

- [ ] **Step 3: Replace the interpolated error with the existing generic contract**

In `_tool_compare_documents`, change only the unresolved-document return:

```python
if not doc:
    return {"error": "Document not found or access denied"}
```

This matches the generic wording already used by sibling document tools and does not reveal whether an identifier exists in another tenant.

- [ ] **Step 4: Run focused security tests**

Run:

```bash
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/unit/services/test_compare_documents_no_fabrication.py \
  tests/unit/services/test_kg_tenant_scope.py \
  tests/unit/services/test_agent_audit_security.py \
  -q
```

Expected: all pass.

- [ ] **Step 5: Prove the tenant verifier still rejects leaked identifiers**

Run the task's calibration script with `wrong-leaked-error-identifier.json`; expected verifier exit is 10. Then run `pass.json`; expected exit is 0. Use the environment variables and invocation already encoded in `evals/agent-tenant-isolation-v1/tests/test.sh` rather than duplicating them.

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/agent/tools_impl.py \
  backend/tests/unit/services/test_compare_documents_no_fabrication.py
git commit -m "fix(agent): hide cross-tenant document identifiers"
```

---

### Task 2: Preserve arXiv evidence across turns and replace invalid PDF fixtures

**Observed failure:** All 5 trials failed. The adapter retained `tool_executions_after_search_1` and `_2`, but built `search_executions` only from the final post-ingest state. The two PDF fixtures were 139/142-byte `%PDF` shells with no extractable text, so ingestion fell back to metadata text and missed the expected checksum.

**Files:**

- Modify: `evals/agent-arxiv-research-flow-v1/environment/run_agent.py`
- Replace: `evals/agent-arxiv-research-flow-v1/environment/mock_services/fixtures/2401.10001.pdf`
- Replace: `evals/agent-arxiv-research-flow-v1/environment/mock_services/fixtures/2401.10002.pdf`
- Modify: `evals/agent-arxiv-research-flow-v1/environment/mock_services/fixtures/papers.json`
- Modify: `evals/agent-arxiv-research-flow-v1/tests/truth.json`
- Modify: `evals/agent-arxiv-research-flow-v1/tests/calibration/pass.json`
- Verify: `evals/agent-arxiv-research-flow-v1/tests/verify.py`

- [ ] **Step 1: Build search evidence from the two captured search turns**

Replace the current final-state lookup with:

```python
search_executions = [
    *tool_executions_for(tool_executions_after_search_1, "search_arxiv"),
    *tool_executions_for(tool_executions_after_search_2, "search_arxiv"),
]
```

Do not merge all turn executions blindly; the verifier needs exactly the two search calls and the existing ingest call remains sourced from the final ingest snapshot.

- [ ] **Step 2: Add an adapter invariant and compile it**

Immediately after assembling the list, classify missing or duplicate search evidence as infrastructure:

```python
if len(search_executions) != 2:
    raise InfrastructureFailure(
        f"expected two search_arxiv executions, observed {len(search_executions)}"
    )
```

Run:

```bash
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m py_compile \
  evals/agent-arxiv-research-flow-v1/environment/run_agent.py
```

Expected: exit 0.

- [ ] **Step 3: Replace each shell PDF with a deterministic one-page valid PDF**

Generate each fixture once with the already-installed PyMuPDF module and validate it with `pypdf`. The page text must contain the title, authors, arXiv ID, and abstract from `papers.json`. Keep the generated binary committed so benchmark runs do not regenerate it.

```bash
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python - <<'PY'
import json
from pathlib import Path

import fitz

root = Path("evals/agent-arxiv-research-flow-v1/environment/mock_services/fixtures")
papers = json.loads((root / "papers.json").read_text())["papers"]
for paper in papers:
    text = "\n".join(
        [
            paper["title"],
            f"arXiv: {paper['versioned_id']}",
            f"Authors: {', '.join(paper['authors'])}",
            "",
            "Abstract",
            paper["abstract"],
        ]
    )
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    remaining = page.insert_textbox(
        fitz.Rect(54, 54, 558, 738),
        text,
        fontsize=11,
        fontname="helv",
        lineheight=1.25,
    )
    assert remaining >= 0, paper["id"]
    document.save(root / paper["pdf_filename"], garbage=4, deflate=True)
    document.close()
PY
```

Validate both files:

```bash
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python - <<'PY'
from pathlib import Path
from pypdf import PdfReader

root = Path("evals/agent-arxiv-research-flow-v1/environment/mock_services/fixtures")
for path in sorted(root.glob("*.pdf")):
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert len(reader.pages) == 1, path
    assert len(text.strip()) > 100, path
    print(path.name, len(path.read_bytes()), len(text))
PY
```

Expected: both PDFs parse, contain one page, and expose more than 100 characters of text.

- [ ] **Step 4: Recompute fixture checksums and update every consumer**

Run:

```bash
shasum -a 256 \
  evals/agent-arxiv-research-flow-v1/environment/mock_services/fixtures/2401.10001.pdf \
  evals/agent-arxiv-research-flow-v1/environment/mock_services/fixtures/2401.10002.pdf
```

Copy the exact hashes into `papers.json`, `tests/truth.json`, and `tests/calibration/pass.json`. Search for stale values:

```bash
rg -n '2401\.1000[12]|sha256|checksum' evals/agent-arxiv-research-flow-v1
```

Expected: each paper has one consistent hash across fixture metadata, truth, and passing calibration.

- [ ] **Step 5: Run positive and negative calibration**

Run `tests/test.sh` once with `BENCHMARK_CALIBRATION_FIXTURE` pointing to `pass.json` and once to `wrong-ingest-before-approval.json`.

Expected:

- `pass.json` exits 0.
- `wrong-ingest-before-approval.json` exits 10.

- [ ] **Step 6: Commit**

```bash
git add evals/agent-arxiv-research-flow-v1
git commit -m "fix(evals): preserve arxiv evidence and valid pdfs"
```

---

### Task 3: Make project-skill verification read one canonical snapshot

**Observed failure:** The database snapshot correctly showed skill version `v1` loaded, but root `final_values.loaded_skill_versions` was transient and empty. The verifier compared the two. It also rejected valid wording such as `16,000-token` and treated harmless `list_projects` as forbidden. The genuine load-before-read ordering gate must remain.

**Files:**

- Modify: `evals/agent-project-skill-runtime-v1/environment/run_agent.py`
- Modify: `evals/agent-project-skill-runtime-v1/tests/verify.py`
- Create: `evals/agent-project-skill-runtime-v1/tests/calibration/pass.json`
- Create: `evals/agent-project-skill-runtime-v1/tests/calibration/wrong-read-before-load.json`
- Verify: `backend/tests/unit/agent/test_project_skill_runtime.py`

- [ ] **Step 1: Extract one exact measurement-scope matcher**

Extract the current limitation match into a helper:

```python
MEASUREMENT_SCOPE_RE = re.compile(
    r"\b(?:16k|16,?000)[ -]token\s+scientific\s+abstracts\b",
    re.IGNORECASE,
)


def mentions_measurement_scope(text: str) -> bool:
    return bool(MEASUREMENT_SCOPE_RE.search(text))
```

Replace the current `16k-token` check in `check_note` with `mentions_measurement_scope(content)`.

- [ ] **Step 2: Add calibration fixtures that exercise wording and ordering**

Create:

- `evals/agent-project-skill-runtime-v1/tests/calibration/pass.json` with durable version 1, the phrase `16,000-token scientific abstracts`, optional `list_projects`, and correct load-before-source-read order.
- `evals/agent-project-skill-runtime-v1/tests/calibration/wrong-read-before-load.json` with the same state except `list_project_documents` occurs before `load_project_skill`.

The passing fixture proves the comma form. The negative fixture preserves the real ordering gate. Use the same evidence-plus-state shape consumed by `run_verifier_main` in neighboring tasks.

- [ ] **Step 3: Run calibration before the verifier change**

Run both fixtures through `evals/agent-project-skill-runtime-v1/tests/test.sh` using `BENCHMARK_CALIBRATION_FIXTURE`.

Expected before the matcher and snapshot changes: `pass.json` exits 10. `wrong-read-before-load.json` also exits 10.

- [ ] **Step 4: Source loaded versions from the durable final database snapshot**

After the adapter reads `final_db`, derive the evidence field once:

```python
final_snapshots = final_db.get("snapshots") or []
if len(final_snapshots) != 1:
    raise InfrastructureFailure(
        f"expected one final runtime snapshot, observed {len(final_snapshots)}"
    )
loaded_skill_versions = list(
    final_snapshots[0].get("loaded_skill_versions") or []
)
```

Write `json_safe(loaded_skill_versions)` to `runtime.loaded_skill_versions` instead of reading root `final_values`. Keep the verifier comparison between runtime evidence and the independently read durable snapshot; it now compares two views of the same canonical source.

- [ ] **Step 5: Permit only the harmless discovery call**

Add `list_projects` to `ALLOWED_TOOLS`. Do not remove `list_project_documents` from the required sequence. Keep the existing position assertion that `load_project_skill` occurs before `list_project_documents`, `summarize_document`, and `create_project_note`.

- [ ] **Step 6: Run calibration and the product unit test**

Expected:

- `pass.json` exits 0.
- `wrong-read-before-load.json` exits 10.
- `backend/tests/unit/agent/test_project_skill_runtime.py` passes.

- [ ] **Step 7: Commit**

```bash
git add evals/agent-project-skill-runtime-v1 \
  backend/tests/unit/agent/test_project_skill_runtime.py
git commit -m "fix(evals): verify durable project skill runtime state"
```

---

### Task 4: Separate live long-run outcomes from the forced-synthesis mechanism test

**Observed failure:** Four of five runs truthfully stopped after stage 5, but the verifier required a stage-6 tool request that only exists when the production loop ceiling fires. Requiring the stochastic model to request one more tool conflates the live bounded outcome with deterministic force-synthesis mechanics.

**Files:**

- Modify: `evals/agent-long-run-controls-v1/tests/verify.py`
- Modify: `evals/agent-long-run-controls-v1/tests/calibration/pass.json`
- Create: `evals/agent-long-run-controls-v1/tests/calibration/pass-voluntary-stop.json`
- Modify: `evals/agent-long-run-controls-v1/instruction.md`
- Modify: `evals/specs/agent-long-run-controls-v1/task.md`
- Modify: `evals/specs/agent-long-run-controls-v1/harness.md`
- Modify: `backend/tests/services/agent/test_subgraph_loop_ceiling.py`
- Modify production force-synthesis code only if the deterministic test fails for a real defect.

- [ ] **Step 1: Pin the deterministic mechanism in the existing loop-ceiling unit test**

Add one test that constructs a state at the research loop ceiling and invokes the existing force-synthesis node. Assert the node does not execute the unmatched tool request and returns a final AI message explaining that the operation stopped at the tool limit.

Use the production symbol already imported by `test_subgraph_loop_ceiling.py`; do not add a new helper or graph just for the benchmark.

Core assertions:

```python
assert result["tool_loop_count"] == MAX_RESEARCH_TOOL_LOOPS + 1
assert result["_force_synthesis_fired"] is True
assert result["messages"][-1].tool_calls == []
assert "limit" in str(result["messages"][-1].content).lower()
```

- [ ] **Step 2: Run the mechanism test before changing the live verifier**

```bash
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/services/agent/test_subgraph_loop_ceiling.py \
  -q
```

Expected: pass if the mechanism already works. If it fails, fix only the shared force-synthesis node and rerun; do not change the task verifier to compensate for a broken node.

- [ ] **Step 3: Define two valid live outcomes in the verifier**

Refactor the existing stage/linkage checks into these explicit cases:

```python
forced = tool_loop_count == 6 and len(unmatched_stage6_calls) == 1
voluntary = tool_loop_count == 5 and len(unmatched_stage6_calls) == 0

if not (forced or voluntary):
    failures.append(
        "expected either a stage-5 voluntary stop or one unmatched stage-6 "
        "request handled by forced synthesis"
    )
```

For both cases continue to require stages 1–5, compaction evidence, reflection evidence, no stage-6 side effect, and a truthful final answer. Require `force_synthesis` only in the `forced` case.

- [ ] **Step 4: Add a voluntary-stop passing fixture**

Create `pass-voluntary-stop.json` by copying the valid common evidence from `pass.json`, setting `tool_loop_count` to 5, removing the unmatched stage-6 call, setting `force_synthesis` false, and retaining a final answer that says stages 1–5 completed and stage 6 did not run.

Keep `pass.json` as the forced-synthesis passing fixture. Keep `wrong-stage6.json` failing because it records a real stage-6 side effect.

- [ ] **Step 5: Update the task contract**

In the instruction and specs, state that the live task must complete the five required stages and must not execute stage 6. The benchmark accepts either voluntary synthesis after stage 5 or production-enforced synthesis after an attempted stage-6 call. The deterministic unit test owns the exact ceiling mechanism.

- [ ] **Step 6: Run all three calibrations**

Expected:

- `pass.json` exits 0.
- `pass-voluntary-stop.json` exits 0.
- `wrong-stage6.json` exits 10.

- [ ] **Step 7: Commit**

```bash
git add backend/tests/services/agent/test_subgraph_loop_ceiling.py \
  evals/agent-long-run-controls-v1 \
  evals/specs/agent-long-run-controls-v1
git commit -m "fix(evals): separate long-run outcome from loop mechanism"
```

---

### Task 5: Ground knowledge-graph answers and stop publishing fake component counts

**Observed failure:** The semantic judge saw entity and relationship fixtures but not the graph statistics the user requested. Production also labeled `max(1, total_entities - isolated_entities)` as `connected_components`; that is a count of connected nodes, not connected components. Finals then explained generic `RELATED_TO` edges more specifically than the graph supported.

**Files:**

- Modify: `backend/src/services/agent/tools_impl.py`
- Modify: `backend/src/services/agent/subgraphs/AGENTS_data.md`
- Create: `backend/tests/services/agent/test_data_subgraph_prompt.py`
- Modify: `backend/tests/unit/services/test_agent_audit_security.py`
- Modify: `evals/agent-knowledge-graph-flow-v1/tests/truth.json`
- Modify: `evals/agent-knowledge-graph-flow-v1/tests/verify.py`
- Modify: `evals/agent-knowledge-graph-flow-v1/tests/calibration/pass.json`

- [ ] **Step 1: Add a failing prompt-contract test**

Create the smallest file-level test:

```python
from pathlib import Path


def test_data_prompt_forbids_explaining_untyped_edges() -> None:
    prompt = (
        Path(__file__).parents[3]
        / "src/services/agent/subgraphs/AGENTS_data.md"
    ).read_text()
    assert "Only state the relationship label returned by the graph" in prompt
    assert "Do not infer why two entities are related" in prompt
```

- [ ] **Step 2: Add the literal-edge rule to the existing prompt**

Under `## Constraints` add:

```markdown
- Only state the relationship label returned by the graph. Do not infer why two entities are related from names, types, or outside knowledge. A generic `RELATED_TO` edge supports only “related to,” not a causal, architectural, or implementation explanation.
```

- [ ] **Step 3: Remove the invented statistic at the agent tool boundary**

In the agent-facing `get_graph_stats` result assembly in `tools_impl.py`, omit `connected_components` unless the service returns an independently computed exact value. For this fix, delete that output field and retain the exact totals already available:

```python
return {
    "total_entities": analytics.total_entities,
    "total_relationships": analytics.total_relationships,
    "entity_type_distribution": analytics.entity_type_counts,
    "relationship_type_distribution": analytics.relationship_type_counts,
    "average_degree": round(analytics.average_degree, 2),
}
```

Do not add a Neo4j GDS dependency or advertise an approximation under the exact field name.

- [ ] **Step 4: Add an exact tool-response regression assertion**

Add this test to `backend/tests/unit/services/test_agent_audit_security.py`, which already owns the agent KG dispatcher checks:

```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_graph_stats_omits_inexact_connected_components():
    from src.services.agent import tools_impl

    current_user = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    analytics = SimpleNamespace(
        total_entities=20,
        total_relationships=20,
        entity_type_counts={"PERSON": 6},
        relationship_type_counts={"RELATED_TO": 5},
        average_degree=2.0,
        connected_components=17,
    )
    fake_service = SimpleNamespace(get_graph_analytics=lambda **kwargs: analytics)

    with patch(
        "src.services.knowledge_graph.knowledge_graph_service.knowledge_graph_service",
        fake_service,
    ):
        result = await tools_impl._tool_get_graph_stats({}, current_user)

    assert result["total_entities"] == 20
    assert result["total_relationships"] == 20
    assert result["average_degree"] == 2.0
    assert "connected_components" not in result
```

- [ ] **Step 5: Give the judge the trusted graph statistics**

Add this structure to `tests/truth.json` using the fixture's actual direct Cypher counts:

```json
"graph_stats": {
  "total_entities": 20,
  "total_relationships": 20
}
```

In `tests/verify.py`, append `{"kind": "graph_stats", **TRUTH["graph_stats"]}` to `trusted_sources` beside entities and relationships. Do not judge `connected_components`.

- [ ] **Step 6: Update the passing calibration final**

Make the final answer report only exact trusted totals and literal relationship labels. Remove any explanation of what a generic `RELATED_TO` edge means beyond “related to.”

- [ ] **Step 7: Run prompt, tool, and verifier checks**

```bash
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/services/agent/test_data_subgraph_prompt.py \
  tests/unit/services/test_agent_audit_security.py \
  tests/unit/services/test_kg_tenant_scope.py \
  -q
```

Then run KG calibration:

- `pass.json` exits 0.
- `wrong-cross-tenant.json` exits 10.
- `empty-kg-honest.json` exits 0.

- [ ] **Step 8: Commit product and harness changes separately**

```bash
git add backend/src/services/agent/tools_impl.py \
  backend/src/services/agent/subgraphs/AGENTS_data.md \
  backend/tests/services/agent/test_data_subgraph_prompt.py \
  backend/tests/unit/services/test_agent_audit_security.py
git commit -m "fix(agent): ground knowledge graph statistics and edges"

git add evals/agent-knowledge-graph-flow-v1
git commit -m "fix(evals): judge knowledge graph answers against stats"
```

---

### Task 6: Make cancellation cleanup survive generator close and repeated cancellation

**Observed failure:** Fast-path runs could finish with `assistant_message_id = null` because closing the inner generator raises `GeneratorExit`, while `_stream_luna_fast_path` caught only `CancelledError`. In graph and confirm routes, `await asyncio.shield(coro)` protects the cleanup coroutine from cancellation but still raises immediately in the caller; a second cancellation can let the response finish before cleanup commits. The durability task also observed terminalization timeouts.

**Files:**

- Modify: `backend/src/api/agent/streaming.py`
- Modify: `backend/tests/api/agent/test_stream_fast_path.py`
- Modify: `backend/tests/api/agent/test_stream_cancel_run_linkage.py`
- Modify: `backend/tests/api/agent/test_stream_cancel_buffer_prefix.py`
- Modify: `backend/tests/unit/api/test_agent_streaming_response_cancellation.py`

- [ ] **Step 1: Add a fast-path generator-close regression test**

Extend `test_stream_fast_path.py` with a test that reads the first token from `stream_event_generator`, calls `await generator.aclose()`, and then asserts:

```python
persist_assistant.assert_awaited_once()
assert persist_assistant.await_args.kwargs["stopped"] is True
assert finalize_calls[0]["event_type"] is RunEventType.RUN_CANCELLED
assert finalize_calls[0]["payload"]["assistant_message_id"] == "partial-row-id"
```

Use the existing `_CancelDuringEmitLuna` setup and mocks rather than creating another test harness.

- [ ] **Step 2: Run the new test and prove `GeneratorExit` skips linked cleanup**

```bash
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/api/agent/test_stream_fast_path.py \
  -q
```

Expected before the fix: no linked fast-path cancellation finalization after `aclose()`.

- [ ] **Step 3: Handle both cancellation exit forms in the fast path**

Change the fast-path exception branch to:

```python
except (asyncio.CancelledError, GeneratorExit):
    cleanup_task = asyncio.create_task(cancel_fast_path())
    try:
        await asyncio.shield(cleanup_task)
    except asyncio.CancelledError:
        await cleanup_task
        raise
    raise
```

This preserves the original exception type, guarantees linked persistence/finalization completes, and lets the outer idempotent finalizer remain a no-op.

- [ ] **Step 4: Add a repeated-cancellation test for the graph route**

In `test_agent_streaming_response_cancellation.py`, arrange for `_finalize_run` to block on an event, cancel the response task again while cleanup is running, release the event, and assert the response does not finish until `graph.aclose`, partial persistence, buffer finish, and cancellation finalization have all completed.

Core shape:

```python
cleanup_started = asyncio.Event()
allow_cleanup = asyncio.Event()

async def blocking_finalize(*args, **kwargs):
    cleanup_started.set()
    await allow_cleanup.wait()

response_task.cancel()
await cleanup_started.wait()
response_task.cancel()
assert not response_task.done()
allow_cleanup.set()
with pytest.raises(asyncio.CancelledError):
    await response_task
```

- [ ] **Step 5: Await one owned cleanup task in graph and confirm routes**

For both `cleanup_cancelled_response` and `cleanup_cancelled_confirm_response`, replace direct `await asyncio.shield(cleanup())` with:

```python
cleanup_task = asyncio.create_task(cleanup_cancelled_response())
try:
    await asyncio.shield(cleanup_task)
except asyncio.CancelledError:
    await cleanup_task
    raise
```

Use the confirm-specific function name in the confirm branch. Do not create a shared abstraction; the two blocks call different finalizers and are already local.

- [ ] **Step 6: Run cancellation tests repeatedly**

```bash
cd backend
for run in 1 2 3 4 5; do
  /Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
    tests/api/agent/test_stream_fast_path.py \
    tests/api/agent/test_stream_cancel_run_linkage.py \
    tests/api/agent/test_stream_cancel_buffer_prefix.py \
    tests/unit/api/test_agent_streaming_response_cancellation.py \
    -q || exit 1
done
```

Expected: five clean repetitions with one cancellation terminal event, linked partials when tokens exist, and no buffered-prefix violation.

- [ ] **Step 7: Commit**

```bash
git add backend/src/api/agent/streaming.py \
  backend/tests/api/agent/test_stream_fast_path.py \
  backend/tests/api/agent/test_stream_cancel_run_linkage.py \
  backend/tests/api/agent/test_stream_cancel_buffer_prefix.py \
  backend/tests/unit/api/test_agent_streaming_response_cancellation.py
git commit -m "fix(agent): complete cancellation cleanup before exit"
```

---

### Task 7: Compare cancellation persistence with server-canonical token evidence

**Observed failure:** Fast-path verifier evidence was built from frames the client received before disconnect. The server can append a token to Redis immediately before the client closes, so client-only evidence can falsely call a valid persisted prefix a mismatch. Stream durability must use the same server-canonical replay history while retaining strict terminalization and linkage checks.

**Files:**

- Modify: `evals/agent-fast-path-cancel-v1/environment/run_agent.py`
- Modify: `evals/agent-fast-path-cancel-v1/tests/verify.py`
- Modify: `evals/agent-fast-path-cancel-v1/tests/calibration/pass.json`
- Modify: `evals/agent-stream-cancel-durability-v1/environment/run_agent.py`
- Modify: `evals/agent-stream-cancel-durability-v1/tests/verify.py`
- Modify: `evals/agent-stream-cancel-durability-v1/tests/calibration/pass.json`

- [ ] **Step 1: Expose Redis token frames in fast-path evidence**

Reuse the Redis snapshot pattern already implemented by `agent-stream-cancel-durability-v1`. In the fast-path adapter, read the isolated stream buffer after terminalization and add:

```python
"server_token_log": token_log_from_frames(redis_frames),
```

Keep `token_log` as the client observation for diagnostics, but stop using it as the persistence upper bound.

- [ ] **Step 2: Change the fast-path prefix gate to the server log**

In `check_prefix_retained`:

```python
server_text = "".join(
    entry["content"]
    for entry in evidence["server_token_log"]
    if isinstance(entry.get("content"), str)
)
persisted = str((state.get("assistant") or {}).get("content") or "")
if not server_text.startswith(persisted):
    failures.append(
        "persisted partial is not a prefix of the server replay token history"
    )
```

Also require the first client-observed token to appear in `server_text`; this proves the two evidence streams describe the same run.

- [ ] **Step 3: Keep cancellation correctness gates strict**

Do not relax any of these:

- terminal state reached within the task bound;
- exactly one durable terminal event;
- terminal event is `run.cancelled`;
- event payload and `AgentRun.assistant_message_id` point to the persisted partial;
- no later `run.completed`;
- replay buffer has a positive TTL and no done frame after cancel.

- [ ] **Step 4: Align stream-durability text comparison**

Its verifier already reads live Redis. Normalize both sides with the same token-frame extraction function and compare `persisted` as a prefix of concatenated Redis tokens. Keep missing Redis data classified as infrastructure, not an objective agent failure.

- [ ] **Step 5: Refresh passing fixtures and prove negative fixtures still fail**

Update only the new `server_token_log`/Redis evidence in each `pass.json`. Run:

- Fast path: `pass.json` → 0; every `wrong-*` fixture → 10; `infra-missing-finalize-attempts.json` → infrastructure exit 2.
- Stream durability: `pass.json` → 0; `wrong-late-completion.json` → 10.

- [ ] **Step 6: Commit adapters and verifiers**

```bash
git add evals/agent-fast-path-cancel-v1 \
  evals/agent-stream-cancel-durability-v1
git commit -m "fix(evals): use server token history for cancel durability"
```

---

### Task 8: Honor explicit user requests to remember information

**Observed failure:** All 5 memory trials used an explicit “Please remember…” request, but the classifier returned `general`; `memory_save_node` skipped every no-tool general turn before reading the user message.

**Files:**

- Modify: `backend/src/services/agent/_nodes_memory.py`
- Modify: `backend/tests/services/agent/test_memory_save_gating.py`
- Verify: `evals/agent-memory-roundtrip-v1/tests/calibration/pass.json`

- [ ] **Step 1: Add failing explicit-memory tests**

Append:

```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_explicit_remember_request_bypasses_general_no_tool_gate():
    save_mock = AsyncMock(return_value=True)
    store = MagicMock()
    state = _state(
        messages=[
            HumanMessage(content="Please remember that my preferred format is PDF."),
            AIMessage(content="I'll remember that."),
        ]
    )

    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock):
        await memory_save_node(state, _config())

    save_mock.assert_called_once()
```

Add a negative beside it:

```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_incidental_remember_word_does_not_bypass_general_gate():
    save_mock = AsyncMock(return_value=True)
    store = MagicMock()
    state = _state(
        messages=[
            HumanMessage(content="I remember seeing that paper."),
            AIMessage(content="That sounds familiar."),
        ]
    )
    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock):
        await memory_save_node(state, _config())

    save_mock.assert_not_called()
```

- [ ] **Step 2: Run the tests and prove the explicit request is dropped**

```bash
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/services/agent/test_memory_save_gating.py \
  -q
```

Expected before the fix: the explicit-memory test fails; greeting and incidental-word tests pass.

- [ ] **Step 3: Extract the last user message before applying the save gate**

Move the existing reverse message scan above the intent/tool gate. Add `import re` beside the standard-library imports, then add one narrow, anchored intent helper in the same module:

```python
_EXPLICIT_MEMORY_RE = re.compile(
    r"^\s*(?:please\s+)?(?:remember|save)\s+(?:this\s+)?(?:that\s+)?",
    re.IGNORECASE,
)


def _is_explicit_memory_request(text: str) -> bool:
    return bool(_EXPLICIT_MEMORY_RE.search(text))
```

Change the gate to:

```python
explicit_memory_request = _is_explicit_memory_request(last_user_content)
if (
    intent in ("", "general")
    and not tool_executions
    and not explicit_memory_request
):
    return {}
```

Do not bypass `user_id`, PII redaction, provenance, or background persistence checks.

- [ ] **Step 4: Run memory unit and calibration checks**

Run the focused unit file. Then run memory task calibration:

- `pass.json` exits 0.
- `wrong-unredacted-memory.json` exits 10.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/agent/_nodes_memory.py \
  backend/tests/services/agent/test_memory_save_gating.py
git commit -m "fix(agent): persist explicit memory requests"
```

---

### Task 9: Route knowledge-base requests to the research subgraph deterministically

**Observed failure:** Four of five KB trials were classified as `writing`; the writing subgraph does not bind `do_kb_retrieve`. Keyword scoring already knows “knowledge base,” but writing words can win the tie because writing has higher priority.

**Files:**

- Modify: `backend/src/services/agent/_prompts.py`
- Modify: `backend/tests/services/agent/test_classifier_intent.py`
- Verify: `evals/agent-kb-retrieval-v1/tests/calibration/pass.json`

- [ ] **Step 1: Add benchmark-shaped action-override tests**

Import `classify_intent_with_fallback`, the public async classifier entry point used by the graph, and add table-driven cases:

```python
@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "Compare the documents in our organization knowledge base about transformers.",
        "Write a summary using our knowledge base evidence.",
        "Search our docs and explain the retrieval policy.",
    ],
)
async def test_kb_actions_route_to_research_override(query: str) -> None:
    result = await classify_intent_with_fallback(query, page_context={})
    assert result.intent == "research"
    assert result.source == "action_override"
    assert result.confidence == 1.0
```

Keep the existing knowledge-graph cases unchanged.

- [ ] **Step 2: Run and capture the writing misroute**

```bash
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/services/agent/test_classifier_intent.py \
  -q
```

Expected before the override: one or more benchmark-shaped rows resolve to writing or lack `action_override` provenance.

- [ ] **Step 3: Reuse the existing deterministic override table**

Add these entries to `ACTION_INTENT_OVERRIDES` before broader project phrases:

```python
("organization knowledge base", "research"),
("knowledge base", "research"),
("search our docs", "research"),
```

Do not add bare `kb`; the current tests intentionally protect words such as `skbio` from substring false positives. Do not change `INTENT_PRIORITY`, which would affect unrelated mixed-intent requests.

- [ ] **Step 4: Run classifier, routing, and KB calibration checks**

```bash
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/services/agent/test_classifier_intent.py \
  tests/unit/services/test_agent_graph_topology.py \
  -q
```

Then run KB calibration:

- `pass.json` exits 0.
- `empty-kb-honest.json` exits 0.
- `wrong-hallucinated-grounding.json` exits 10.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/agent/_prompts.py \
  backend/tests/services/agent/test_classifier_intent.py
git commit -m "fix(agent): route knowledge base actions to research"
```

---

### Task 10: Report asynchronous writing artifacts honestly

**Observed failure:** The writing tools returned successfully, but `create_draft` returned a pending asynchronous status while the final said “Completed all three.” That is a fabricated completion, not a tool failure.

**Files:**

- Modify: `backend/src/services/agent/subgraphs/AGENTS_writing.md`
- Modify: `backend/tests/services/agent/test_writing_grounded_context.py`
- Modify: `evals/agent-writing-flow-v1/tests/calibration/pass.json`
- Verify: `evals/agent-writing-flow-v1/tests/calibration/wrong-premature-draft.json`

- [ ] **Step 1: Add a prompt-contract test for pending status**

Add `from pathlib import Path` and this test to the existing file:

```python
def test_writing_prompt_forbids_claiming_pending_artifacts_are_complete() -> None:
    prompt = (
        Path(__file__).parents[3]
        / "src/services/agent/subgraphs/AGENTS_writing.md"
    ).read_text()
    assert "A pending artifact is not complete" in prompt
    assert "repeat the tool's status" in prompt
```

- [ ] **Step 2: Run the test and prove the contract is absent**

```bash
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/services/agent/test_writing_grounded_context.py \
  -q
```

Expected before the prompt change: the two new assertions fail.

- [ ] **Step 3: Add one explicit status rule to the writing protocol**

Under `## Constraints` add:

```markdown
- A pending artifact is not complete. For `create_draft`, notes, exports, and other asynchronous writes, repeat the tool's returned status accurately. Say “started” or “pending” until the tool returns a completed status; never summarize several results as “all completed” when any result is pending or failed.
```

- [ ] **Step 4: Update passing calibration without weakening the negative**

Change `pass.json` so the final says the comparison and bibliography completed and the draft is pending. Leave `wrong-premature-draft.json` claiming completion and verify it still exits 10.

- [ ] **Step 5: Run writing tests and calibration**

```bash
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/services/agent/test_writing_grounded_context.py \
  tests/services/agent/test_writing_subgraph_tools.py \
  -q
```

Expected calibration: pass fixture exits 0; premature-draft fixture exits 10.

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/agent/subgraphs/AGENTS_writing.md \
  backend/tests/services/agent/test_writing_grounded_context.py
git commit -m "fix(agent): report pending writing artifacts honestly"
```

- [ ] **Step 7: Commit the benchmark calibration separately**

```bash
git add evals/agent-writing-flow-v1/tests/calibration/pass.json
git commit -m "fix(evals): calibrate pending writing artifact status"
```

---

### Task 11: Run the local regression and calibration gate

**Files:** No new production files. This task validates all changes before spending model budget.

- [ ] **Step 1: Run formatting and static checks on changed Python files**

Collect changed Python paths with Git, then run the repository's blocking checks from the repository root:

```bash
git diff --name-only origin/develop...HEAD -- '*.py' > /tmp/agent-benchmark-python-files.txt
rg '^(backend/(src|tests)|evals)/' /tmp/agent-benchmark-python-files.txt \
  | xargs /Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m ruff check
rg '^(backend/(src|tests)|evals)/' /tmp/agent-benchmark-python-files.txt \
  | xargs /Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m black --check
rg '^(backend/(src|tests)|evals)/' /tmp/agent-benchmark-python-files.txt \
  | xargs /Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m isort --check-only
```

Do not bulk-format unrelated code.

- [ ] **Step 2: Run the combined focused pytest gate**

```bash
cd backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/unit/services/test_compare_documents_no_fabrication.py \
  tests/services/agent/test_memory_save_gating.py \
  tests/services/agent/test_classifier_intent.py \
  tests/services/agent/test_data_subgraph_prompt.py \
  tests/services/agent/test_writing_grounded_context.py \
  tests/services/agent/test_writing_subgraph_tools.py \
  tests/services/agent/test_subgraph_loop_ceiling.py \
  tests/unit/services/test_kg_tenant_scope.py \
  tests/unit/services/test_agent_graph_topology.py \
  tests/unit/agent/test_project_skill_runtime.py \
  tests/api/agent/test_stream_fast_path.py \
  tests/api/agent/test_stream_cancel_run_linkage.py \
  tests/api/agent/test_stream_cancel_buffer_prefix.py \
  tests/unit/api/test_agent_streaming_response_cancellation.py \
  -q
```

Expected: zero failures.

- [ ] **Step 3: Run every touched verifier's calibration matrix**

Run every calibration directly so the verifier can write its local audit report:

```bash
set -e
for benchmark_task in \
  agent-arxiv-research-flow-v1 \
  agent-fast-path-cancel-v1 \
  agent-kb-retrieval-v1 \
  agent-knowledge-graph-flow-v1 \
  agent-long-run-controls-v1 \
  agent-memory-roundtrip-v1 \
  agent-project-skill-runtime-v1 \
  agent-stream-cancel-durability-v1 \
  agent-tenant-isolation-v1 \
  agent-writing-flow-v1
do
  for fixture in "evals/$benchmark_task"/tests/calibration/*.json
  do
    fixture_name="$(basename "$fixture")"
    report_path="/tmp/$benchmark_task-$fixture_name-audit.json"
    set +e
    BENCHMARK_CALIBRATION_FIXTURE="$fixture" \
      VERIFIER_REPORT_PATH="$report_path" \
      /Users/goodwiinz/development/RAG_system/backend/.venv/bin/python \
      "evals/$benchmark_task/tests/verify.py" >/dev/null
    actual_rc=$?
    set -e
    case "$fixture_name" in
      pass*.json|empty-*-honest.json) expected_rc=0 ;;
      wrong-*.json) expected_rc=10 ;;
      infra-*.json) expected_rc=2 ;;
      *) echo "unclassified calibration fixture: $fixture"; exit 1 ;;
    esac
    printf '%s/%s expected=%s actual=%s\n' \
      "$benchmark_task" "$fixture_name" "$expected_rc" "$actual_rc"
    test "$actual_rc" -eq "$expected_rc" || exit 1
  done
done
```

Expected: every `pass*` and honest-empty fixture exits 0; every `wrong-*` fixture exits 10; fixtures named `infra-*` exit 2. Any other exit blocks live runs.

- [ ] **Step 4: Run shared Harbor self-test and diff hygiene**

```bash
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python \
  evals/harbor_common/selftest.py
git diff --check
git status --short
```

Expected: `selftest ok`, no whitespace errors, and only intended files changed.

- [ ] **Step 5: Record the source revision**

```bash
git rev-parse HEAD | tee /tmp/agent-benchmark-source-sha
```

The printed full SHA is `SOURCE_SHA`: the immutable repository revision containing the product and harness remediation before the mechanical pin commit. All task pins in Task 12 must use this exact commit; do not pin to a dirty working tree.

---

### Task 12: Pin provenance, rerun 10 affected capabilities, then rerun all 17

**Files:**

- Modify: each of the 17 task `task.toml` files only where the source revision is pinned.
- Modify: adapter/verifier revision constants that assert the old `27018e69c0c9e0339aab5db5f76d34e1715a316c` value.
- Modify: `evals/agent-full-benchmark-v1.json`
- Create: `evals/source-manifests/agent-full-2026-08-10-gpt56.json`
- Create: `evals/baselines/agent-full-2026-08-10-gpt56.json`
- Modify: `evals/AGENT_FLOW_BASELINE.md`
- Modify: `evals/README.md`

- [ ] **Step 1: Pin every task to `SOURCE_SHA` consistently**

Find all old pins:

```bash
rg -n '27018e69c0c9e0339aab5db5f76d34e1715a316c' \
  evals/agent-*-v1 evals/rag-retrieval-safety-grounding-v1
```

Load `SOURCE_SHA` with `SOURCE_SHA="$(tr -d '\n' < /tmp/agent-benchmark-source-sha)"`. Replace the source URL revision, `source_revision`, `agent_revision`, and verifier constants together. Then prove no old pin remains in any of the 17 matrix task directories. Commit this mechanical change:

```bash
git add evals
git commit -m "test(evals): pin full agent matrix to remediation revision"
```

- [ ] **Step 2: Verify the model routing before the paid run**

Confirm `evals/agent-full-benchmark-v1.json` contains all three values:

```json
"AZURE_OPENAI_CHAT_DEPLOYMENT_NAME": "gpt-5.6-luna",
"AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT": "gpt-5.6-luna",
"AZURE_OPENAI_SYNTHESIS_DEPLOYMENT": "gpt-5.6-luna"
```

Also verify `AGENT_FAST_PATH_DEPLOYMENT` resolves to `gpt-5.6-luna`. Search the built task environment and result trajectories for `gpt-5-mini-2025-08-07`; any hit in an active model role blocks the run. Historical baseline prose may retain old model names.

- [ ] **Step 3: Load approved secrets without printing them**

Use Infisical's approved dev `/do-kb` path as the parent process for every Harbor command. Validate presence without printing values:

```bash
infisical run --env=dev --path=/do-kb --silent -- sh -c '
  for name in \
    AZURE_OPENAI_CHAT_ENDPOINT \
    AZURE_OPENAI_CHAT_API_KEY \
    AZURE_OPENAI_CHAT_API_VERSION \
    HARBOR_JUDGE_ENDPOINT \
    HARBOR_JUDGE_API_KEY \
    HARBOR_JUDGE_MODEL \
    HARBOR_JUDGE_API_VERSION
  do
    printenv "$name" >/dev/null || { echo "missing: $name"; exit 1; }
  done
  echo "required benchmark secrets present"
'
```

Expected: only `required benchmark secrets present`; no secret values appear.

- [ ] **Step 4: Run the 10 affected tasks at 5 attempts each**

Run the affected tasks serially to preserve external-service stability:

```bash
SOURCE_SHA="$(tr -d '\n' < /tmp/agent-benchmark-source-sha)"
source_sha_7="${SOURCE_SHA%${SOURCE_SHA#???????}}"
for benchmark_task in \
  agent-arxiv-research-flow-v1 \
  agent-fast-path-cancel-v1 \
  agent-kb-retrieval-v1 \
  agent-knowledge-graph-flow-v1 \
  agent-long-run-controls-v1 \
  agent-memory-roundtrip-v1 \
  agent-project-skill-runtime-v1 \
  agent-stream-cancel-durability-v1 \
  agent-tenant-isolation-v1 \
  agent-writing-flow-v1
do
  infisical run --env=dev --path=/do-kb --silent -- \
    env \
      AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-5.6-luna \
      AZURE_OPENAI_LIGHTWEIGHT_DEPLOYMENT=gpt-5.6-luna \
      AZURE_OPENAI_SYNTHESIS_DEPLOYMENT=gpt-5.6-luna \
      AGENT_FAST_PATH_DEPLOYMENT=gpt-5.6-luna \
    harbor run \
      --path "evals/$benchmark_task" \
      --agent-import-path evals.harbor_agents.nous_production_agent:NousProductionAgent \
      --env docker \
      --jobs-dir evals/jobs \
      --job-name "$benchmark_task-5x-$source_sha_7" \
      --force-build \
      --n-attempts 5 \
      --n-concurrent 1 \
      --yes || exit 1
done
```

Acceptance for this stage: 50 scoreable trials, zero infrastructure failures, all objective gates 5/5, semantic gates at least 4/5 where applicable, and no use of `gpt-5-mini-2025-08-07` in active model traces.

- [ ] **Step 5: Audit every affected failure before proceeding**

Produce a 10-row table with these columns:

```markdown
| Capability | Pass/5 | Objective failures | Semantic failures | Infra failures | Model(s) | p50 | p95 | Decision |
```

For each non-pass, link the exact job/trial and quote the verifier failure category. Do not continue to the full matrix while a zero-tolerance objective gate or infrastructure issue remains.

- [ ] **Step 6: Run the complete matrix**

After the affected suite is green:

```bash
infisical run --env=dev --path=/do-kb --silent -- \
  harbor run \
    --config evals/agent-full-benchmark-v1.json \
    --yes
```

Expected: 17 capabilities × 5 attempts = 85 scoreable trials, no infrastructure failures, each objective capability 5/5, and each semantic capability at least 4/5.

- [ ] **Step 7: Validate result identity and model evidence**

Before aggregating, assert every trial reports:

- `repository_revision == SOURCE_SHA`;
- `agent_revision == SOURCE_SHA`;
- one stable task digest for each task;
- one stable harness digest for the run;
- Harbor version 0.6.6;
- chat, lightweight, synthesis, and fast-path deployments all `gpt-5.6-luna`;
- no raw infrastructure exception mis-scored as reward 0.

If a digest or environment flag differs, report that trial as a separate baseline and rerun it under the accepted identity.

- [ ] **Step 8: Write the machine-readable baseline and human results table**

Create `evals/baselines/agent-full-2026-08-10-gpt56.json` using the existing baseline schema. Its aggregate must include 17 capabilities, 85 trials, passed, failed, objective failures, semantic failures, infrastructure failures, p50/p95 timing, model deployment fields, and the Harbor job path.

Create `evals/source-manifests/agent-full-2026-08-10-gpt56.json` with repository/agent SHA, Harbor version, sorted task digests, harness digest, dataset digests, and environment flags.

Append a 17-row table to `evals/AGENT_FLOW_BASELINE.md` using observed values only:

```markdown
| Capability | Pass/5 | Objective | Semantic | Infra | p50 | p95 | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
```

Populate one row per task directly from the accepted Harbor job. Include aggregate `passed/85`, model deployment, `SOURCE_SHA`, job name, and recorded timestamp above the table. Do not write rows until each value has been read from the job artifacts.

- [ ] **Step 9: Recompute and verify digests**

Use the digest algorithm already documented in `evals/AGENT_FLOW_BASELINE.md`: hash sorted repository-relative `shasum -a 256` lines, excluding `__pycache__`. Recompute each digest independently after writing the baseline. Any mismatch blocks the commit.

- [ ] **Step 10: Commit evidence**

```bash
git add evals/source-manifests/agent-full-2026-08-10-gpt56.json \
  evals/baselines/agent-full-2026-08-10-gpt56.json \
  evals/AGENT_FLOW_BASELINE.md \
  evals/README.md
git commit -m "test(evals): record full gpt-5.6 agent benchmark"
```

- [ ] **Step 11: Final branch verification and PR update**

Run:

```bash
git status --short
git diff --check origin/develop...HEAD
git log --oneline origin/develop..HEAD
gh pr checks 1383
```

Expected: clean worktree, no whitespace errors, intentional commit series, and all required PR checks green. Push the branch and update PR #1383 rather than opening a duplicate PR unless #1383 was closed or its scope was intentionally replaced.

## Final acceptance checklist

- [ ] P0 tenant probe returns a generic error without reflecting the victim identifier.
- [ ] arXiv adapter preserves both search turns and valid PDFs extract deterministic text.
- [ ] project-skill verifier uses durable state, accepts equivalent token-limit wording, and still rejects read-before-load.
- [ ] long-run verifier accepts stage-5 voluntary stop while the unit test pins forced synthesis.
- [ ] KG answers use trusted statistics, literal edge labels, and no fake component count.
- [ ] fast, graph, and confirm cancellation cleanup completes before generator exit.
- [ ] both cancellation verifiers compare persistence to server-canonical token evidence.
- [ ] explicit remember requests persist; greetings and incidental “remember” phrases do not.
- [ ] knowledge-base actions route to research without changing global intent priority.
- [ ] writing finals distinguish pending from completed artifacts.
- [ ] all touched calibration fixtures produce their prescribed 0, 10, or 2 exits.
- [ ] affected suite is 50/50 scoreable with zero infrastructure failures.
- [ ] full suite is 85/85 scoreable and meets every capability threshold.
- [ ] every active model role is `gpt-5.6-luna`; `gpt-5-mini-2025-08-07` is absent from run traces.
- [ ] source, harness, task, and dataset digests reproduce exactly.
- [ ] the 17-row result table and machine-readable baseline contain observed values only.
