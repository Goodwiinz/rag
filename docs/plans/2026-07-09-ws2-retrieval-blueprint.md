# WS2 Implementation Blueprint — Iterative retrieve-then-read + calibrated reranking

All anchors below verified against the working tree on 2026-07-09. All branches cut from **`origin/develop`** (local `develop` is a diverged fork — see memory). All flags default off → every PR merges inert.

## Corrections to the plan / explore reports (verified)

1. **Plan's "revive reranker.py" is dead-wrong** (confirmed): `cohere` SDK absent from requirements, `SearchOrchestrator`/`SearchReranker` constructed only in `tests/integration/test_search_pipeline.py`. The live reranker is `cohere_rerank_service` (Azure httpx, global instance, circuit-breaker). PR-0 deletes the corpse.
2. **Explore "eval-harness" report errors**: it says the hybrid fallback uses `SearchReranker` ("Postgres hybrid + SearchReranker") — false; `hybrid_search_service` uses `cohere_rerank_service.rerank_sync` (the "dead-reranker" report is the correct one). Ignore its "two reranker impls coexist, confirm which" hedge — only the Azure one is live.
3. **Explore "agent-loop-fit"** places `_tool_do_kb_retrieve` in `execute.py:1219` — it's defined in `src/api/agent/tools_impl.py:1219-1352` (`execute.py` re-exports; `tools.py:244` imports via `execute`).
4. **Plan says "8-loop cap"** — stale; `MAX_RESEARCH_TOOL_LOOPS = 5` (`research_agent.py:54`, lowered after trace 019e18f0).
5. `_nodes_rag.py` module docstring + comments still say "Qdrant fallback" — Qdrant is removed; the fallback is Postgres hybrid. Fix the comment in PR-1 while touching the file.
6. **Wiring `evaluate_search` verbatim is anti-goal**: `SearchResponse`/`SearchResult` (`src/models/search_schemas.py:98-153`) have ~14 required fields each. PR-3 calls the existing `SearchQualityService._calculate_recall` through a 6-line typed shim instead of constructing real responses (letter of the requirement kept, bloat avoided).

---

## PR-0 (separate tiny cleanup): delete the dead search-pipeline island

**Branch:** `chore/ws2-delete-dead-search-orchestrator`

The whole orchestrator pipeline has zero live construction sites (verified: only consumers are `src/services/search/__init__.py` exports and `tests/integration/test_search_pipeline.py`; `hybrid_search_service` has its own internal `_fusion_ranking`; `tests/scaffolding/unit/services/test_hybrid_search_service.py`'s `TestResultFusion` uses mocks, not the real class).

**Delete** (2,218 LoC):
- `src/services/search/reranker.py` (337)
- `src/services/search/orchestrator.py` (337)
- `src/services/search/fusion.py` (211)
- `src/services/search/cache.py` (419)
- `src/services/search/metrics.py` (296)
- `tests/integration/test_search_pipeline.py` (618)

**Modify:** `src/services/search/__init__.py` — keep only the `base` imports (`SearchExecutor, SearchQuery, SearchResult, SearchSource`); drop `SearchOrchestrator, SearchReranker, ResultFusion, SearchCache, SearchMetrics` from imports and `__all__`. Keep `base.py` (175 LoC) this PR — it's the exported type surface; flag as follow-up orphan candidate.

**Verify:** `grep -rn "SearchOrchestrator\|SearchReranker\|ResultFusion\|SearchCache\|SearchMetrics" src tests` → only scaffolding-mock class names remain; `pytest tests/unit -q` collects. Pre-existing quirk, don't fix: `tests/standalone/test_agents_simple.py:25` imports `MultiAgentSearchServiceV2` from the package `__init__`, which never exported it.

**Out of scope:** deleting `base.py`, `multi_agent_search_service*.py`, any behavior change.

---

## PR-1: calibrated Cohere rerank of DO-KB chunks (shared-funnel helper, both paths)

**Branch:** `feat/ws2-dokb-cohere-rerank`
**Flag:** `AGENT_DOKB_COHERE_RERANK: bool = False`

**Decision — placement:** shared helper called by BOTH `_try_primary_do_kb_read` (node) and `_tool_do_kb_retrieve` (tool), inserted immediately after `resolve_and_filter_chunks` (tenancy stays the single upstream funnel; rerank is scope-agnostic reordering, per explore). Helper is unconditional mechanism; the settings-flag check lives at the two call sites — this lets PR-3's script invoke rerank directly without env mutation.

**Decision — budget:** rerank gets its own budget, outside the 3.0s `DO_KB_RETRIEVE_TIMEOUT_SECONDS` (that `wait_for` wraps only `client.retrieve`, `_nodes_rag.py:318-321`). Module constant, not a setting: worst-case node retrieval becomes ~3.0s retrieve + resolve + 2.0s rerank ≈ 5.5s, still under the 15s fallback ceiling. On timeout → original order, never degrade retrieval.

### Files

**Create `src/services/do_kb/rerank.py`** (~60 LoC):

```python
"""Cohere re-scoring of DO KB chunks.

DO KB Public Preview returns no relevance scores; Chunk synthesizes
1.0 - 0.05*rank (models.py:from_do_payload). This replaces synthetic
scores with calibrated cross-encoder relevance via the live Azure
Cohere service. Tenant filtering stays upstream in
resolve_and_filter_chunks — never here.
"""
import asyncio
import logging
from src.services.do_kb.models import Chunk

logger = logging.getLogger(__name__)

# ponytail: constant, not a setting — promote to config if ops ever need to tune
_RERANK_TIMEOUT_SECONDS = 2.0


async def cohere_rescore_chunks(query: str, chunks: list[Chunk]) -> list[Chunk]:
    """Reorder + re-score chunks via cohere_rerank_service.

    Passthrough (input returned unchanged) when: <2 chunks, service
    disabled, circuit open, timeout, or any failure. Never raises,
    never drops chunks (top_n = len(chunks)).
    """
```

Implementation contract:
- Early return `chunks` if `len(chunks) < 2`.
- Lazy-import `from src.services.search.cohere_rerank_service import cohere_rerank_service`; if `not cohere_rerank_service.is_enabled` → passthrough (log debug).
- `docs = [{"content": c.text, "id": c.document_id or str(i), "score": c.score} for i, c in enumerate(chunks)]` — dict fields match the service's extraction (`cohere_rerank_service.py:104-116`; it truncates to 4096 chars itself). Rerank happens **before** the `[:3000]` envelope truncation → full chunk text feeds the cross-encoder.
- `results = await asyncio.wait_for(cohere_rerank_service.rerank(query, docs, top_n=len(docs)), timeout=_RERANK_TIMEOUT_SECONDS)` in `try/except (asyncio.TimeoutError, Exception)` → passthrough on any raise.
- After the call: `if cohere_rerank_service.last_failure is not None: return chunks` (the service's `_fallback_rerank` echoes original scores — detect via `last_failure`, don't emit fake "calibrated" scores).
- Map back: `reranked = [chunks[r.index].model_copy(update={"score": float(r.relevance_score)}) for r in results]`; append any index not covered by `results` in original order (defensive; count should be preserved). Return `reranked`.

**Modify `src/services/agent/_nodes_rag.py`** — in `_try_primary_do_kb_read`, between the `async with AsyncSessionLocal()` block closing (after the two `project_scope_empty` branches, line ~398) and `_record_do_kb_read("success")` (line 400):

```python
        from src.core.config import settings as _cfg
        if getattr(_cfg, "AGENT_DOKB_COHERE_RERANK", False) and chunks_to_emit:
            from src.services.do_kb.rerank import cohere_rescore_chunks
            chunks_to_emit = await cohere_rescore_chunks(query, chunks_to_emit)
```
(`_kb_cfg` already imported at line 296 — reuse it, drop the re-import.) Also fix the stale "Qdrant" wording in the module docstring/comments (lines 14-18, 381).

**Modify `src/api/agent/tools_impl.py`** — in `_tool_do_kb_retrieve`, after `resolve_and_filter_chunks` (line ~1333), before the `chunks_payload` loop:

```python
    if chunks_to_emit and getattr(_kb_settings, "AGENT_DOKB_COHERE_RERANK", False):
        from src.services.do_kb.rerank import cohere_rescore_chunks
        chunks_to_emit = await cohere_rescore_chunks(query, chunks_to_emit)
```

**Modify `src/core/config.py`** — AGENT flag block (after `AGENT_LEDGER_DIR`, ~line 409):

```python
    # Re-score DO KB chunks with the Azure Cohere cross-encoder after
    # resolve/filter. DO KB Public Preview returns no scores (we synthesize
    # 1.0-0.05*rank); this replaces them with calibrated relevance. Requires
    # COHERE_RERANK_ENDPOINT + COHERE_RERANK_API_KEY (already provisioned).
    AGENT_DOKB_COHERE_RERANK: bool = False
```

### Data shape
Context envelope unchanged: `{document_id, title, content[:3000], score}` — `score` semantics change from synthetic rank-proxy to Cohere relevance (0-1). Verified safe: `_retrieval_context_part` (`_nodes_llm.py:226`) reads only `title`+`content`; `rag_context` SSE (`streaming.py:462`) and persistence are display-only. Tool payload `{text, score, document_id, title, metadata}` likewise unchanged in shape.

**Double-rerank note:** DO KB still reranks server-side (`reranking=True`). Keep it — Cohere adds calibration, DO adds candidate ordering; do NOT also flip `DO_KB_RERANKING_ENABLED` in this PR (one variable at a time).

### Tests — `tests/unit/services/do_kb/test_rerank.py`
1. `<2` chunks → passthrough, service not called.
2. Service `is_enabled=False` → passthrough, original synthetic scores intact.
3. Success → reordered by `relevance_score` desc, scores replaced, count preserved, input objects not mutated (`model_copy`).
4. `last_failure` set after call (circuit open / fallback) → passthrough.
5. `asyncio.TimeoutError` → passthrough.
6. Partial results (subset of indices) → covered chunks first, leftovers appended in original order.

Plus one call-site test extending the existing `_tool_do_kb_retrieve` unit tests (grep `tests/unit` for the existing file): flag on + mocked `cohere_rescore_chunks` → payload scores reflect rerank; flag off → helper never imported/called.

### Rollout
Merge inert. Before flipping in dev: confirm `COHERE_RERANK_ENDPOINT`/`COHERE_RERANK_API_KEY` present in Infisical (`/do-kb` path convention — they are existing config fields, no new secrets). Flip `AGENT_DOKB_COHERE_RERANK=true` in values-dev, watch: rag_node latency (LangSmith retriever spans), `Cohere rerank completed in Xms` logs, circuit-breaker warnings. Capture PR-3 baseline **before** flipping.

**Out of scope:** cutting chunk count via `top_n`, touching `DO_KB_RERANKING_ENABLED`, reranking the hybrid fallback (already Cohere-reranked internally), frontend changes.

---

## PR-2: PaperQA2-style gather-evidence (RCS) behind `AGENT_ITERATIVE_RETRIEVAL`

**Branch:** `feat/ws2-gather-evidence`
**Flag:** `AGENT_ITERATIVE_RETRIEVAL: bool = False`

**Decision — shape:** enrich the existing `do_kb_retrieve` tool, NOT a new tool and NOT the rag_node. Rationale (from explore, verified): a new tool needs registration in `RESEARCH_TOOLS` + `ALL_TOOLS` + planner name lists (miss one and it's invisible); `rag_node` runs once pre-loop and isn't agentic; the tool path is the mid-loop lever, and the whole retrieve→rerank→summarize pass counts as **one** `tool_loop_count` tick, so narrow-then-broad iteration = the LLM re-calling `do_kb_retrieve` with reformulated queries inside the existing `MAX_RESEARCH_TOOL_LOOPS = 5` ceiling. **No graph restructure.**

**Decision — quote grounding (minimal envelope change):** each enriched tool-result chunk gains `summary`, `relevance`, `quote` keys. `quote` must be a **verbatim substring of the chunk text** — validated with a Python `in` check, set to `None` if the LLM fabricated it. The `retrieved_contexts` state envelope and SSE contract are untouched (RCS never runs on the pre-node path); tool results already flow to the LLM as ToolMessage and to the client via the existing `tool_end` event.

### Files

**Create `src/services/agent/evidence.py`** (~110 LoC):

```python
"""PaperQA2-style RCS: per-chunk contextual relevance summaries."""

# ponytail: aggregate wall-clock cap for the whole gather; the tool path has
# no per-node timeout, so this is the only bound. Tune here if traces demand.
_EVIDENCE_BUDGET_SECONDS = 20.0
_MAX_EVIDENCE_CHUNKS = 5

RCS_PROMPT = """You are extracting evidence for a research question.

Question: {query}

Excerpt from "{title}":
\"\"\"{text}\"\"\"

Return STRICT JSON and nothing else:
{{"relevance": <integer 0-10, 0 = irrelevant to the question>,
  "summary": "<how this excerpt bears on the question; specific, <=300 words, no filler>",
  "quote": "<the single most load-bearing sentence, copied VERBATIM from the excerpt>"}}

If the excerpt is irrelevant: {{"relevance": 0, "summary": "", "quote": ""}}"""


async def summarize_evidence(
    query: str,
    chunks: list[dict],
) -> list[dict]:
    """Enrich chunk dicts with 'summary' (str), 'relevance' (int 0-10),
    'quote' (verbatim excerpt or None); sorted relevance desc.

    Input dicts are the do_kb_retrieve payload shape:
    {text, score, document_id, title, metadata}. Only the first
    _MAX_EVIDENCE_CHUNKS (already rerank-ordered) are summarized; the
    rest pass through unenriched at the tail. On timeout or total
    failure, returns the input unchanged. Never raises.
    """
```

Implementation contract:
- `llm = build_lightweight_llm(temperature=0, max_tokens=512)` (`src/services/agent/llm_factory.py:145` — cached, model-router deployment, `AGENT_LIGHTWEIGHT_REQUEST_TIMEOUT=30s` built in).
- Per chunk: `llm.ainvoke(RCS_PROMPT.format(query=query, title=..., text=chunk["text"][:3000]))`; run the ≤5 calls with `asyncio.gather(..., return_exceptions=True)` inside `asyncio.wait_for(_EVIDENCE_BUDGET_SECONDS)`; `except asyncio.TimeoutError: return chunks`.
- Parse: `json.loads` on the response text, fallback to a `re.search(r"\{.*\}", text, re.S)` extract; on parse failure or exception result → that chunk passes through unenriched.
- Clamp `relevance = max(0, min(10, int(...)))`; truncate summary at ~2,000 chars defensively; **quote guard:** `if quote and quote not in chunk["text"]: quote = None`.
- Sort enriched chunks by `relevance` desc (relevance-0 chunks kept, sorted last — the agent decides, we don't silently discard evidence); unenriched tail preserves original order after them.
- structlog/logging: one info line — `summarize_evidence: n_chunks, n_enriched, elapsed_ms`.

**Modify `src/api/agent/tools_impl.py`** — end of `_tool_do_kb_retrieve`, after `chunks_payload` is built (~line 1346):

```python
    evidence_mode = False
    if chunks_payload and getattr(_kb_settings, "AGENT_ITERATIVE_RETRIEVAL", False):
        from src.services.agent.evidence import summarize_evidence
        chunks_payload = await summarize_evidence(query, chunks_payload)
        evidence_mode = True
    return {
        "chunks": chunks_payload,
        "total": len(chunks_payload) if project_id else result.total,
        "source": "do_kb",
        "query": query,
        "evidence_mode": evidence_mode,
    }
```

**Modify `src/services/agent/tools.py`** — `do_kb_retrieve` docstring (line 242; the docstring is the LLM's tool spec, this is what makes iteration happen):

```
"""Semantic retrieval over the organization's DigitalOcean Knowledge Base.

When evidence mode is on, each chunk includes 'relevance' (0-10), a
'summary' of how it bears on the query, and a verbatim 'quote'. Cite
using the quote. If top relevance is below 5, call this tool again
with a narrower or broader reformulation instead of settling for weak
evidence."""
```

**Modify `src/core/config.py`** — AGENT block, next to the PR-1 flag:

```python
    # PaperQA2-style gather-evidence inside do_kb_retrieve: rerank-ordered
    # chunks get per-chunk contextual relevance summaries + verbatim quotes
    # from the lightweight LLM, enabling narrow-then-broad iteration within
    # the existing tool-loop ceiling. Adds up to 5 lightweight LLM calls
    # (~20s budget) per do_kb_retrieve call.
    AGENT_ITERATIVE_RETRIEVAL: bool = False
```

### Latency/budget accounting
Tool path worst case: retrieve ≤30s (client default; tool path is not under the 3s hot-path cap) + rerank 2s + RCS 20s ≈ 52s inside one `tool_node` batch — comparable to `search_arxiv` long-timeouts; bounded and flag-gated.

### Tests
`tests/unit/services/agent/test_evidence.py`:
1. Happy path (mocked LLM, valid JSON) → enriched, sorted relevance desc.
2. Fabricated quote (not a substring) → `quote is None`, summary kept.
3. Malformed JSON / LLM exception → chunk passes through unenriched, others fine.
4. Budget timeout → input returned unchanged.
5. >5 chunks → only first 5 enriched, tail preserved after them.
6. Relevance clamping (LLM returns 15 / "-3" / "high") → clamped or unenriched.

Extend the `_tool_do_kb_retrieve` unit tests: flag off → payload has `evidence_mode: False` and `summarize_evidence` not called; flag on → called with `(query, chunks_payload)`.

### Rollout
Merge inert. Flip on dev only after PR-3 baseline exists. Watch: lightweight-LLM token spend (up to 5 extra calls per retrieve), `do_kb_retrieve` tool duration in LangSmith, whether the agent actually iterates (re-calls with reformulations) vs burns loops.

**Out of scope:** RCS on the rag_node pre-path (latency), a separate `gather_evidence` tool, surfacing quotes in the citations UI (frontend, separate PR), changing `MAX_RESEARCH_TOOL_LOOPS`, SSE contract changes, `retrieved_contexts` envelope changes.

---

## PR-3: retrieval-quality gate — hand-labeled qrels + recall@k / rerank-lift script

**Branch:** `feat/ws2-retrieval-eval`
**No flag** (operator tooling; never runs in CI — needs live DO KB + dev DB creds from Infisical `/do-kb`).

**Decision:** doc-level qrels (not chunk-level), driven through the **production funnel** (`client.retrieve` → `resolve_and_filter_chunks` → optional `cohere_rescore_chunks`) — the eval-harness report is right that instrumenting `hybrid_search_service` would measure a path the agent doesn't take. Metrics: recall@3, recall@5, MRR@8. (Recall@8 over 8 results can't see reordering — MRR is the rerank-lift detector; 4 lines of code.)

### Files

**Create `tests/eval/retrieval_qrels.py`** (~80 LoC):

```python
@dataclass(frozen=True)
class RetrievalCase:
    name: str
    query: str
    relevant_doc_ids: tuple[str, ...]  # canonical org Document UUIDs (post-resolve), NOT KB storage keys
    project_id: str | None = None

CASES: tuple[RetrievalCase, ...] = (
    # 10-15 hand-labeled cases over the dev corpus
)
```
Module docstring documents the labeling procedure: run `python -m scripts.retrieval_eval --org-id <org> --dump` against the dev org (`e050bd43…`, KB `6343a77f…` per the DO-KB design audit) to see candidates per query, then hand-mark relevant Document UUIDs (from the documents API/DB). Ground truth must be **resolved org Document IDs** — a mislabeled org silently yields recall=0 (known "silent by design" failure mode).

**Create `scripts/retrieval_eval.py`** (~150 LoC), pattern-matched to `scripts/agent_eval.py`:

```python
"""Retrieval-quality gate: recall@k + rerank lift over hand-labeled qrels.

Usage:
  python -m scripts.retrieval_eval --org-id <uuid> [--k 3 5] [--rerank both|on|off] [--dump]

Read-only against the live dev DO KB + DB (Infisical /do-kb env).
"""
```

Flow per case:
1. `async with AsyncSessionLocal() as session:` → `Organization.do_kb_uuid`.
2. `result = await get_do_kb_client().retrieve(kb_uuid=kb_uuid, query=case.query)` (default `top_k=8`).
3. `title_by_key, chunks = await resolve_and_filter_chunks(chunks=result.chunks, org_id=org_id, session=session, project_id=case.project_id)` — operator supplies org explicitly; no ownership guard needed (no untrusted caller; note this in a comment).
4. Variant `off`: DO order. Variant `on`: `chunks = await cohere_rescore_chunks(case.query, chunks)` — callable directly because PR-1 put the flag at call sites, mechanism stays unconditional.
5. Ranked doc-id list: `title_by_key.get(c.document_id, (None,))[0]` per chunk, drop `None`, dedupe preserving order.
6. Metrics — wire the **existing** math via a 6-line shim:
   ```python
   @dataclass
   class _Result: document_id: str
   @dataclass
   class _Shim: results: list[_Result]

   recall_at_k = SearchQualityService()._calculate_recall(
       _Shim([_Result(d) for d in ranked_ids[:k]]), list(case.relevant_doc_ids)
   )
   ```
   (`_calculate_recall` at `search_quality_service.py:238-252` reads only `.results[*].document_id`; truncating to k before the call gives recall@k without touching the service.) MRR@8 computed inline: `1 / (1 + ranked_ids.index(first_relevant))` else 0.
7. `--rerank both` (default) prints per-case + mean table: `recall@3 / recall@5 / MRR@8 — off | on | Δ`. Exit 0 always — this is a human gate, not a CI gate.
8. `--dump` prints each query's resolved `(doc_id, title, score)` candidates for the labeling pass.

**Create `tests/unit/scripts/test_retrieval_eval.py`** — 3 pure-function asserts on the script's `_recall_at_k` shim wiring and `_mrr` (creds-free; the ONE runnable check for the metric logic).

### Rollout / usage
1. Land PR-1 + PR-3 (order between them irrelevant; both inert).
2. Label qrels against dev corpus (`--dump`), commit `CASES`.
3. Baseline: `python -m scripts.retrieval_eval --org-id <dev-org> --rerank both` → record in the PR / ledger.
4. Flip `AGENT_DOKB_COHERE_RERANK` in values-dev only if `on` beats `off` (MRR@8, recall@3).
5. Same baseline stands as the "before" for flipping `AGENT_ITERATIVE_RETRIEVAL` (RCS doesn't change the retrieved set, only presentation — the gate for PR-2 is trajectory-level: agent iterates, cites quotes; the existing golden harness covers tool selection).

**Out of scope:** NDCG, LangSmith RAG datasets, CI wiring, a benchmarking platform, seeding a synthetic corpus (dev corpus is the corpus), chunk-level qrels, `agent_eval.py` subcommand (separate script is enough).

---

## Sequencing & conventions (all PRs)

- Order: PR-0 anytime (independent); PR-1 → PR-3 → flip rerank → PR-2 → flip iterative.
- One branch per PR off `origin/develop`; push early (worktree memory rule).
- black/isort/mypy-strict on touched files; stdlib `logging` module loggers match both touched modules' existing style (`_nodes_rag.py` and `cohere_rerank_service.py` use `logging`, not structlog — follow the file).
- No new tables, no migrations, no new secrets (COHERE_RERANK_* already exist as settings fields; verify presence in Infisical `/do-kb` before any flag flip).
- Tenancy invariant: `resolve_and_filter_chunks` remains the single funnel; rerank and RCS both operate strictly downstream of it and never re-scope.