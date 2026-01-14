# Tasks: Entity Management Feature Improvements

**Input**: Design documents from `/specs/003-entity-management-feature/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/entity-api.yaml
**Linear Issue**: GOO-95
**Branch**: `003-entity-management-feature`

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions
- **Backend**: `backend/src/`
- **Frontend**: `frontend/src/`, `frontend/app/`

---

## Phase 1: Setup (No tasks needed)

**Purpose**: The project structure already exists. Entity management components are implemented in `frontend/src/components/entities/` (17 components). This feature is primarily about filling gaps in existing implementation.

**Existing Structure**:
- `frontend/app/entities/page.tsx` - Main page with tabs
- `frontend/src/components/entities/` - 17 entity components
- `frontend/src/services/entityService.ts` - API client
- `frontend/src/types/entity.ts` - TypeScript types

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core utilities that MUST be complete before ANY user story can be implemented

**CRITICAL**: These foundational tasks enable authorization and API reliability across all features

- [X] T001 [US-ALL] Add API retry utility `withRetry<T>()` in `frontend/src/services/entityService.ts`
- [X] T002 [P] [US-ALL] Create authorization utility hook in `frontend/src/hooks/useEntityPermissions.ts`
- [X] T003 [P] [US-ALL] Add new TypeScript types (DuplicateCheckResult, EntityPermissions, EntityTypeOption) in `frontend/src/types/entity.ts`

**Checkpoint**: Foundation ready - authorization and retry logic available for all user stories

---

## Phase 3: User Story 1 - Create New Entities (Priority: P1)

**Goal**: Enable manual entity creation with validation and duplicate detection

**Independent Test**: Create an entity with name, type, and properties, verify it appears in entity list

### Implementation for User Story 1

- [X] T004 [US1] Add admin check to "Create Entity" button in `frontend/app/entities/page.tsx`
- [X] T005 [US1] Implement duplicate detection in `frontend/src/components/entities/EntityForm.tsx`
  - Add `checkForDuplicates(name, type)` function using `entityService.searchEntities()`
  - Show warning dialog when duplicate found
  - Allow force-create with auto-suffix option
- [X] T006 [US1] Add required type validation (prevent null types) in EntityForm submit handler
- [X] T007 [US1] Apply retry wrapper to `createEntity()` in `frontend/src/services/entityService.ts`

**Acceptance Criteria**:
- [x] Entity creation form exists (already implemented)
- [ ] Admin-only create button (disabled for non-admins)
- [ ] Duplicate warning with force-create option
- [ ] Type field is required (prevents null types)
- [ ] API failures retry once automatically

**Checkpoint**: User Story 1 complete - entities can be created with proper validation

---

## Phase 4: User Story 2 - Create Relationships Between Entities (Priority: P1)

**Goal**: Enable relationship creation between any two entities

**Independent Test**: Select two entities, create relationship, verify connection appears in both entities

### Implementation for User Story 2

- [X] T008 [US2] Add admin check to "Add Relationship" button in `frontend/src/components/entities/EntityDetail.tsx`
- [X] T009 [US2] Disable relationship form for non-admin users in `frontend/src/components/entities/RelationshipForm.tsx`
- [X] T010 [US2] Apply retry wrapper to `createRelationship()` in `frontend/src/services/entityService.ts`
- [ ] T011 [US2] Ensure bidirectional display in entity detail views (verify FR-008)

**Acceptance Criteria**:
- [x] Relationship form exists (already implemented)
- [ ] Admin-only relationship creation
- [ ] Relationships visible from both entities
- [ ] API failures retry once automatically

**Checkpoint**: User Story 2 complete - relationships can be created with authorization

---

## Phase 5: User Story 3 - Dynamic Type Filtering (Priority: P1)

**Goal**: Filters reflect actual data with type counts

**Independent Test**: View filter options, verify they match actual entity types in database

### Implementation for User Story 3

- [X] T012 [US3] Add type counts to filter options in `frontend/src/components/entities/EntityFilters.tsx`
  - Fetch counts from `graphAnalyticsService.getAnalytics().entity_type_distribution`
  - Display count next to each type option (e.g., "PERSON (1,234)")
- [X] T013 [US3] Add search/filter input within type dropdown for large type sets (FR-028)
- [X] T014 [P] [US3] Apply retry wrapper to `getEntityTypes()` in `frontend/src/services/entityService.ts`

**Acceptance Criteria**:
- [x] Dynamic type filters from API (already implemented)
- [ ] Type counts displayed next to filter options
- [ ] Searchable filter dropdown for 25+ types
- [ ] API failures retry once automatically

**Checkpoint**: User Story 3 complete - filters show accurate counts and are searchable

---

## Phase 6: User Story 4 - Fix Null Entity Types (Priority: P1)

**Goal**: Identify and fix entities with missing type information

**Independent Test**: Filter by null type, bulk-assign type, verify entities updated

### Implementation for User Story 4

- [X] T015 [US4] Add "Unknown Type" filter option in `frontend/src/components/entities/EntityFilters.tsx`
  - Add special filter value `__null__` for null type entities
  - Calculate null type count from analytics (total - sum of known types)
- [X] T016 [US4] Handle null type filter in page query logic in `frontend/app/entities/page.tsx`
  - When `__null__` selected, filter client-side for `entity_type === null || entity_type === ''`
- [ ] T017 [US4] Verify bulk type assignment works via existing BulkOperations component

**Acceptance Criteria**:
- [x] Bulk operations component exists (already implemented)
- [ ] "Unknown Type" filter option visible
- [ ] Null type entities can be filtered and selected
- [ ] Bulk type assignment updates entities correctly

**Checkpoint**: User Story 4 complete - null type entities can be identified and fixed

---

## Phase 7: User Story 5 - Find Paths Between Entities (Priority: P2)

**Goal**: Discover connections between two entities via path finding

**Independent Test**: Select two entities, find paths, view intermediate entities and relationships

### Implementation for User Story 5

- [ ] T018 [US5] Verify PathFinder component integration in `frontend/app/entities/page.tsx`
- [X] T019 [US5] Apply retry wrapper to `findPaths()` in `frontend/src/services/entityService.ts`
- [ ] T020 [US5] Ensure clickable entities in path results navigate to entity detail

**Acceptance Criteria**:
- [x] PathFinder component exists (already implemented)
- [x] Configurable depth 1-5 (already implemented)
- [ ] API failures retry once, then show error with retry button
- [ ] Intermediate entities are clickable

**Checkpoint**: User Story 5 complete - path finding works with retry logic

---

## Phase 8: User Story 6 - Explore Entity Neighborhood (Priority: P2)

**Goal**: Explore entities related to a specific entity

**Independent Test**: Select entity, explore neighborhood at different depths, navigate to related entities

### Implementation for User Story 6

- [ ] T021 [US6] Verify NeighborhoodExplorer depth slider (1-3 levels) works correctly
- [X] T022 [US6] Apply retry wrapper to `getNeighborhood()` in `frontend/src/services/entityService.ts`
- [ ] T023 [US6] Ensure clicking related entity makes it the new exploration center

**Acceptance Criteria**:
- [x] NeighborhoodExplorer component exists (already implemented via EntityDetail)
- [x] Depth control exists (already implemented)
- [ ] API failures retry once automatically
- [ ] Related entities are clickable and become new center

**Checkpoint**: User Story 6 complete - neighborhood exploration works with retry logic

---

## Phase 9: User Story 7 - View Graph Analytics Dashboard (Priority: P2)

**Goal**: View statistics about knowledge graph health and coverage

**Independent Test**: View analytics dashboard, verify metrics match known graph statistics

### Implementation for User Story 7

- [ ] T024 [US7] Verify GraphAnalyticsDashboard displays all required metrics (FR-016 to FR-019)
- [X] T025 [US7] Apply retry wrapper to `getAnalytics()` in `frontend/src/services/entityService.ts`
- [X] T026 [US7] Add click handler to entity type distribution to filter entity list by that type

**Acceptance Criteria**:
- [x] GraphAnalyticsDashboard component exists (already implemented)
- [x] Shows total entities, relationships (already implemented)
- [x] Shows type distributions (already implemented)
- [ ] Clicking type in chart filters entity list
- [ ] API failures retry once automatically

**Checkpoint**: User Story 7 complete - analytics dashboard fully functional

---

## Phase 10: User Story 8 - Extract Entities from Documents (Priority: P3)

**Goal**: Automatically extract entities from documents

**Independent Test**: Select document, trigger extraction, verify extracted entities appear with confidence scores

### Implementation for User Story 8

- [ ] T027 [US8] Verify DocumentEntityExtractor component integration
- [ ] T027.1 [US8] Verify entity extraction handles zero-entity documents gracefully (SC-009)
  - Test with documents containing no extractable entities
  - Verify user receives clear messaging (e.g., "No entities found in this document")
  - Ensure no errors or crashes occur
  - Verify empty state UI in DocumentEntityExtractor
- [ ] T027.2 [US8] Validate 80% entity extraction accuracy with test dataset (SC-008)
  - Create/use ground-truth test dataset with known entities
  - Run extraction on test set
  - Calculate precision, recall, F1-score
  - Verify ≥80% F1-score threshold
  - Document results in test report
- [ ] T028 [US8] Apply retry wrapper to extraction API calls
- [ ] T029 [US8] Ensure extracted entities link to source document (FR-022)

**Acceptance Criteria**:
- [x] DocumentEntityExtractor component exists (already implemented)
- [x] Extraction results show confidence scores (already implemented)
- [ ] Extracted entities link back to source document
- [ ] Zero-entity documents handled gracefully with clear messaging
- [ ] 80% extraction accuracy validated on ground-truth test set
- [ ] API failures retry once automatically

**Checkpoint**: User Story 8 complete - document entity extraction works

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T030 [P] Add comprehensive authorization checks across all entity components
  - `EntityList.tsx` - hide edit/delete buttons for non-admins
  - `EntityDetail.tsx` - hide edit/delete for non-admins
  - `BulkOperations.tsx` - disable for non-admins
  - `EntityMergeTool.tsx` - disable for non-admins
- [ ] T031 Verify URL state persistence works for all filter combinations (FR-031)
- [ ] T032 [P] Add loading indicators to any operations missing them (FR-029)
- [ ] T033 Run full end-to-end test of entity management workflow
- [ ] T034 Update GOO-95 Linear issue with implementation status

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No tasks - already complete
- **Phase 2 (Foundational)**: No dependencies - start immediately - BLOCKS all user stories
- **User Stories (Phase 3-10)**: All depend on Phase 2 completion
  - P1 stories (US1-US4) should be completed first
  - P2 stories (US5-US7) can proceed after P1
  - P3 story (US8) can proceed after P2
- **Polish (Phase 11)**: Depends on all user stories being complete

### User Story Dependencies

All user stories can technically proceed in parallel after Phase 2, but recommended order:

1. **US1 (Create Entities)** - Foundation for US2
2. **US2 (Create Relationships)** - Uses entities from US1
3. **US3 (Dynamic Filtering)** - Independent
4. **US4 (Null Type Fix)** - Uses filtering from US3
5. **US5-US7 (P2 stories)** - Can run in parallel
6. **US8 (Document Extraction)** - Can run independently

### Parallel Opportunities

Within Phase 2 (Foundational):
```
T001 (retry utility) || T002 (auth utility) || T003 (types)
```

Within Phase 11 (Polish):
```
T030 (auth checks) || T032 (loading indicators)
```

---

## Implementation Summary

| Phase | Tasks | Effort | Dependencies |
|-------|-------|--------|--------------|
| 2. Foundational | T001-T003 | 1-2 hours | None |
| 3. US1 Create Entities | T004-T007 | 2-3 hours | Phase 2 |
| 4. US2 Relationships | T008-T011 | 1-2 hours | Phase 2 |
| 5. US3 Filtering | T012-T014 | 1-2 hours | Phase 2 |
| 6. US4 Null Types | T015-T017 | 1-2 hours | Phase 2, US3 |
| 7. US5 Path Finding | T018-T020 | 1 hour | Phase 2 |
| 8. US6 Neighborhood | T021-T023 | 1 hour | Phase 2 |
| 9. US7 Analytics | T024-T026 | 1-2 hours | Phase 2 |
| 10. US8 Extraction | T027-T029 | 2-3 hours | Phase 2 |
| 11. Polish | T030-T034 | 2-3 hours | All stories |

**Total Tasks**: 36
**Estimated Total Effort**: 14-20 hours
**Critical Path**: Phase 2 → US1 → US2 → US3 → US4 → Polish

---

## Notes

- Most components already implemented - tasks focus on gaps (auth, retry, null filter)
- [P] tasks can run in parallel (different files, no dependencies)
- [Story] label maps task to specific user story for traceability
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
