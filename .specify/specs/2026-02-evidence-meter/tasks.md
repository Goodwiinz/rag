# Tasks: Evidence Agreement Meter

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Task Legend

- `[P]` = Can run in parallel
- `[B]` = Backend (Sonnet)
- `[F]` = Frontend (Gemini 3 Pro)
- `[US#]` = User Story reference

---

## Phase 1: Foundation (Backend Core)

- [ ] [B] [P] Create database migration for `stance_classifications` table
- [ ] [B] [P] Create Pydantic schemas: `StanceClassification`, `EvidenceMeter`, `ConsensusLevel`
- [ ] [B] [P] Create Neo4j Cypher templates for Claim nodes and TAKES_STANCE relationships
- [ ] [B] Implement `stance_classifier.py` service with LLM prompt
- [ ] [B] Implement `consensus_calculator.py` aggregation logic
- [ ] [B] Implement Redis caching layer in `cache.py`

**Checkpoint**: Stance classifier works in isolation with unit tests

---

## Phase 2: API Layer (Backend + Frontend Parallel)

- [ ] [B] [US1] Create `/api/v1/evidence/meter` endpoint
- [ ] [B] [US2] Create `/api/v1/evidence/breakdown` endpoint
- [ ] [B] [P] Add reproducibility hash generation to meter response
- [ ] [B] [P] Add retraction check integration (if source is retracted, exclude from count)
- [ ] [F] [P] [US1] Create `EvidenceMeter.tsx` component with color-coded bar
- [ ] [F] [P] [US1] Create `useEvidenceMeter.ts` hook for data fetching
- [ ] [F] [P] [US1] Add accessibility attributes (aria-label, role="meter")

**Checkpoint**: Basic meter displays on search results

---

## Phase 3: Drill-Down & Interactivity

- [ ] [F] [US2] Create `EvidenceBreakdown.tsx` expandable panel
- [ ] [F] [US2] Create `StanceBadge.tsx` component (green/red/gray pills)
- [ ] [F] [US2] Implement click-to-navigate from breakdown to source detail
- [ ] [F] [US3] Create `ConfidenceIndicator.tsx` warning component
- [ ] [F] [US3] Show confidence warning when classification confidence <85%
- [ ] [B] [US2] Add `stance_filter` query param to breakdown endpoint

**Checkpoint**: Full drill-down flow works end-to-end

---

## Phase 4: Edge Cases & Polish

- [ ] [B] [P] Handle "Limited evidence" case (<3 sources)
- [ ] [B] [P] Handle "Not Addressed" stance for irrelevant sources
- [ ] [F] [P] Add loading skeleton for meter while classifying
- [ ] [F] [P] Add empty state for "No sources found"
- [ ] [F] Add Framer Motion animations for meter segments
- [ ] [B] Implement confidence-based model fallback (low confidence → GPT-4o retry)

**Checkpoint**: All edge cases handled gracefully

---

## Phase 5: Testing & Quality

- [ ] [B] Write unit tests for `stance_classifier.py` (mock LLM responses)
- [ ] [B] Write unit tests for `consensus_calculator.py` 
- [ ] [B] Write integration tests for evidence API endpoints
- [ ] [B] Create test fixture: 100 source-claim pairs with human labels (for SC-001)
- [ ] [B] Write accuracy evaluation script (compare model vs human labels)
- [ ] [F] Write Jest tests for `EvidenceMeter.tsx`
- [ ] [F] Write Jest tests for `EvidenceBreakdown.tsx`
- [ ] [B] [F] [P] Write Playwright E2E test: search → view meter → click breakdown → navigate to source

**Checkpoint**: All tests passing, >80% coverage

---

## Phase 6: Systematic Review Support (P2)

- [ ] [B] [US4] Extend meter endpoint to accept large source sets (50+ papers)
- [ ] [B] [US4] Add temporal breakdown (agreement by publication year)
- [ ] [F] [US4] Create timeline visualization for consensus evolution
- [ ] [B] [US4] Add evidence meter data to export formats (BibTeX comments, CSV column)

**Checkpoint**: Systematic review workflow functional

---

## Completion Checklist

- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] E2E tests passing
- [ ] Code reviewed and approved
- [ ] API documentation updated (OpenAPI spec)
- [ ] SC-001 accuracy benchmark met (85%+)
- [ ] Accessibility audit passed (WCAG 2.1 AA)
- [ ] Deployed to staging
- [ ] Product review completed

---

## Notes for Agents

### Backend Agent (Sonnet)
- Start with Phase 1 database + schemas in parallel
- LLM prompt for stance classification should use structured output (JSON mode)
- Cache key MUST include model_version for reproducibility
- Retraction check can use existing Crossref integration if available

### Frontend Agent (Gemini 3 Pro)
- Use shadcn/ui `Progress` component as base for meter bar
- Breakdown panel should use `Collapsible` or `Accordion` from shadcn
- Framer Motion `AnimatePresence` for smooth breakdown expand/collapse
- Test with screen reader to verify accessibility
