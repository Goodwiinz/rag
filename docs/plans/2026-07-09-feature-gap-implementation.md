# Feature-gap implementation plan — ultracode, 2026-07-09

Source: deep-research gap audit (run `wf_70a2105a-a71`, 109 agents, 46/48 claims verified; synthesis code-checked against this repo). Wiki: `[[nous-feature-gaps]]` pending; audit summary in `[[azure-openai-model-selection]]`-adjacent session notes.

## Model policy (per Abdel, 2026-07-09)

| Stage | Model | Effort |
|---|---|---|
| Explore / code-mapping | **Opus** | `xhigh` |
| Design / implementation planning | **Fable** | `high` |
| Coding / TDD implementation | **Sonnet 5** | `xhigh` |
| Adversarial review / verify | Sonnet 5 | `xhigh` (same as coding tier) |

Workflow `agent()` mapping: explore `{model:'opus', effort:'xhigh'}`, plan `{model:'fable', effort:'high'}`, implement `{model:'sonnet', effort:'xhigh', isolation:'worktree'}` when agents mutate files in parallel.

## Workstreams (priority order from the audit)

Each workstream = one ultracode session: **Explore → Design → Implement → Review**, one phase per Workflow run, human reads results between phases. Branches cut from `origin/develop` (local develop is a diverged fork — never base on it). PRs target `develop`; babysit with `/nous-merge-loop`.

### WS1 — Citation-faithfulness verifier + reviewer pass (LOW-MED)

The audit's top gap: NOUS handles citation *format* only (BibTeX/APA), zero claim-to-evidence alignment. SOTA to copy: CiteCheck (retrieval cascade over CrossRef/S2/OpenAlex/arXiv → structured LLM verifier → EXACT/MINOR/MAJOR; 88.7 macro-F1) and DeepSciVerify (abstract-first, escalate to full text; 67% resolved without full text). Claude Science's reviewer-agent pattern.

- **Explore (Opus/xhigh):** map `draft_generation_service.py`, `citation_extraction_service.py`, bibliography export, and where drafts cite documents; inventory the existing CrossRef/S2 clients (the retrieval cascade is already half-built).
- **Design (Fable/high):** verifier service API (`verify_citation(claim, citation) → {verdict, severity, evidence}`); where the reviewer pass hooks in (post-draft tool? `create_draft` pipeline stage?); deterministic BibTeX (never LLM-generated metadata — clibib two-stage pattern, +27pp fully-correct).
- **Implement (Sonnet 5/xhigh):** TDD; new `src/services/research/citation_verification_service.py` + agent tool + reviewer stage in the draft path; reuse existing clients, no new connectors.
- **Review:** adversarial verify (identifier-hijacking case: DOI resolves but authors/title mismatch must FAIL).

### WS2 — Iterative retrieve-then-read + calibrated reranking (MED)

**Premise corrected by the 2026-07-09 explore pass:** `reranker.py` is dead twice over (cohere SDK not in requirements, zero live construction sites) — delete, don't revive. The **live** reranker is `cohere_rerank_service.py` (Azure httpx, global instance), already used by the hybrid fallback. DO KB retrieve already reranks server-side (`reranking=True`) but returns **synthetic scores** (`1.0 − 0.05·rank`) — the real win is a calibrated Cohere re-score over resolved chunks + the PaperQA2 RCS loop (retrieve → rerank → contextual summaries) via the research-subgraph tool path, no graph restructure. Recall math exists (`search_quality_service._calculate_recall`) but has no ground-truth dataset — the before/after gate needs a small qrels set. Blueprint: `docs/plans/2026-07-09-ws2-retrieval-blueprint.md` (pending).

- **Explore (Opus/xhigh):** trace the live DO-KB read path end-to-end; confirm reranker deadness; map the research subgraph's tool loop.
- **Design (Fable/high):** gather-evidence node design (top-k → Cohere rerank → scored ≤300-word summaries feeding the answer); quote-level citation spans through to the SSE `rag_context` event; loop-ceiling interplay with the existing 8-loop cap.
- **Implement (Sonnet 5/xhigh):** rewire reranker onto the DO-KB path first (small PR, immediately shippable), then the RCS loop as a second PR behind a flag (`AGENT_ITERATIVE_RETRIEVAL`, default off — merge inert, flip in values-dev).
- **Review:** recall before/after on a fixed query set vs the golden examples in `tests/eval/`.

### WS3 — Figure extraction, PyMuPDF first; Docling deferred (MED)

**Premise corrected by the 2026-07-09 explore pass:** Docling is not a `requirements.txt` line on this cluster — it needs a dedicated worker deployment (4–6Gi vs the live 2Gi pod / 900MB-child recycle), pre-baked HF models (~0.5–1.5GB, else cold-download per pod), its own queue, and the global `task_acks_late=True` makes OOM a **redelivery poison loop**. **Phase 1 = PyMuPDF** (already installed, already rasterizes pages): figure/image regions + captions into the existing `MultimodalContent` table (no migration), org-scoped crops via the `_canonical_key` pattern, flag default-off. Also fixes two explore-confirmed s3-path bugs (`table_extraction_service` local-disk-only; legacy `fitz.open(s3://…)`). **Phase 2 (Docling, deferred):** revisit only if equation→LaTeX becomes a hard requirement — then it's an infra workstream (new deployment + queue), not an ingestion PR. Ceiling of phase 1: regions not semantics; no equation→LaTeX. Blueprint: `docs/plans/2026-07-09-ws3-figures-blueprint.md` (pending).

## Sequencing & rules

1. WS1 → WS2 → WS3 (value-per-effort order). WS2's reranker-revival sub-PR can ship during WS1 review downtime — it's independent.
2. One worktree per workstream off `origin/develop` (`feedback_use_own_worktree`: push early).
3. Flags default **off**; merge inert, flip in values-dev after verify. No new env vars without Infisical `/do-kb` entries.
4. Every PR: tests + black/isort on touched files only; `/code-review` before ready; `/nous-merge-loop` to land.
5. Out of scope (audit "skip/later"): GRADE grading, 3D molecule rendering, compute-cluster pipelines, multi-agent coordinator rewrite, hypothesis-gen (revisit after WS1-3).
