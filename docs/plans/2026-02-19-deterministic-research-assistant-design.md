# Deterministic Research Assistant Design

Date: 2026-02-19
Mode: Hybrid deterministic (primary), optional narrative summary (secondary)
Status: Approved for implementation planning

## 1. Goals

- Make research answers reproducible and auditable.
- Ensure every surfaced claim is traceable to indexed evidence.
- Prevent speculative answers when evidence is weak or conflicting.
- Keep optional narrative output clearly separated from authoritative deterministic output.

## 2. Non-Goals

- Fully open-ended creative generation in primary mode.
- Unbounded agentic behavior in deterministic mode.
- Hidden ranking/selection decisions without trace metadata.

## 3. Selected Approach

Primary path: Deterministic Retrieval + Rule-Based Synthesis.

Fallback/optional path: Deterministic evidence pack + optional LLM narrative summary that is marked non-authoritative and can be disabled.

## 4. Core Architecture

1) Query Normalizer (deterministic)
- Normalize casing and punctuation.
- Apply fixed lexicon-based synonym expansion.
- Emit canonical query and expansion terms.

2) Hybrid Retriever (deterministic configuration)
- Run full-text, vector, and graph retrieval in parallel.
- Use fixed per-source limits and thresholds.

3) Deterministic Fusion/Rerank
- Apply fixed weighted formula to all candidates.
- Apply penalties for duplication/noise and source quality heuristics.
- Enforce stable tie-break ordering.

4) Evidence Builder
- Keep top-N chunks with max-M chunks per document.
- De-duplicate near-identical chunks via fixed similarity threshold.
- Produce a deterministic evidence pack.

5) Rule-Based Synthesizer
- Pick answer template by rule-based intent classifier.
- Fill templates from extracted evidence only.
- Drop unsupported claims.

6) Verifier/Gate
- Validate each claim has supporting chunk references.
- If evidence does not pass thresholds, return deterministic failure mode response.

## 5. Deterministic Data Flow

1. Normalize query -> canonical query + expansions.
2. Retrieve candidates from each source with fixed settings.
3. Fuse scores using fixed coefficients.
4. Stabilize final ordering with deterministic tie-break rules.
5. Build evidence pack (top-N, per-doc cap, de-dup).
6. Synthesize template-based answer.
7. Run confidence/coverage gate before returning.

### Proposed Scoring Formula

`final_score = 0.45 * vector_score + 0.35 * bm25_score + 0.20 * graph_score - penalties`

Notes:
- Coefficients are config-versioned and immutable per release.
- Penalties include repeated chunk penalty and low-quality-source penalty.

### Stable Tie-Break Rules

For equal `final_score`, rank by:
1) higher source quality tier,
2) newer document timestamp,
3) lexicographic `document_id`.

## 6. Confidence and Gating

Minimum recommended thresholds:
- At least 2 independent supporting sources for factual answers.
- Minimum mean fused score threshold by answer type.
- Coverage threshold (fraction of answer claims with evidence links) at 100% for deterministic mode.

Failure responses:
- `INSUFFICIENT_EVIDENCE`
- `CONFLICTING_EVIDENCE`
- `NO_MATCH`

Each failure response includes deterministic query refinement suggestions.

## 7. API Contract (Deterministic Response)

Always return a structured payload:

- `answer_type`
- `answer_text`
- `claims[]`
- `citations[]`
- `confidence`
- `coverage`
- `decision_trace_id`

### Claim Object

- `claim_text`
- `supporting_chunk_ids[]`
- `support_score`

### Citation Object

- `source_id`
- `document_id`
- `chunk_id`
- `page_or_section`
- `retrieval_scores` (bm25/vector/graph/final)

## 8. Decision Trace (Auditability)

Persist a deterministic trace per request:
- normalizer output,
- candidate counts per source,
- pre/post-fusion score tables,
- exclusions and reasons,
- gate decision and threshold evaluations.

This enables replay and debugging for reproducibility.

## 9. UX Contract

Required UI elements:
- Deterministic answer panel.
- Evidence quality badge.
- Expandable "Why this answer" panel with score trace.
- Explicit mode badge: `Deterministic` vs `Narrative Summary`.

Rules:
- Deterministic mode is default.
- Narrative summary mode cannot alter claims/citations.
- If modes disagree, deterministic output is authoritative.

## 10. Operational Determinism Requirements

- Version-pin embedding model and retrieval config.
- Version-pin lexicon/synonym dictionary.
- Use index snapshot/version in traces.
- Treat config changes as versioned releases.

Deterministic guarantee target:
Same query + same index snapshot + same config version => same output.

## 11. Risks and Mitigations

- Risk: Rigid tone in outputs.
  - Mitigation: Optional narrative mode with strict non-authoritative label.

- Risk: Corpus mismatch (irrelevant documents dominate retrieval).
  - Mitigation: collection filters, source tiers, query routing policies.

- Risk: Drift after config tweaks.
  - Mitigation: change control with versioned coefficients and trace replay tests.

## 12. Rollout Plan

Phase 1:
- Implement deterministic retrieval/fusion path and structured response schema.
- Add trace capture and deterministic gate.

Phase 2:
- Add UI evidence panel and mode indicators.
- Add deterministic failure mode UX.

Phase 3:
- Add optional narrative summary mode with strict guardrails.
- Add replay-based determinism regression tests.

## 13. Acceptance Criteria

- Deterministic mode enabled by default.
- Every returned claim has evidence linkage.
- No unsupported claims are emitted.
- Same input/config/index snapshot reproduces identical output.
- Trace payload is available for each response.
