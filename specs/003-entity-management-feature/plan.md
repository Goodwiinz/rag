# Implementation Plan: Entity Management Feature Improvements

**Branch**: `003-entity-management-feature` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-entity-management-feature/spec.md`
**Linear Issue**: GOO-95

## Summary

Enhance the Entity Management feature to fully utilize backend capabilities. The frontend already has extensive UI components (EntityForm, RelationshipForm, PathFinder, GraphAnalyticsDashboard, BulkOperations, etc.) integrated into `/entities` page with tabs. Key gaps to address: authorization enforcement (role-based access), duplicate entity warnings, API retry logic, null type cleanup, and improved error handling.

## Technical Context

**Language/Version**:
- Backend: Python 3.11, FastAPI
- Frontend: TypeScript 5.x, Next.js 15.1.3, React 18

**Primary Dependencies**:
- Backend: FastAPI, SQLAlchemy, Neo4j (py2neo), Pydantic
- Frontend: shadcn/ui, Zustand, TanStack Query, Framer Motion, react-hot-toast

**Storage**:
- PostgreSQL (entities metadata)
- Neo4j (graph relationships)
- Qdrant (vector embeddings)

**Testing**:
- Backend: pytest
- Frontend: Jest, React Testing Library

**Target Platform**: Web application (desktop-first, responsive)

**Project Type**: Web (backend + frontend monorepo)

**Performance Goals**:
- Entity creation: <30s user flow
- Path finding: <3s for 10k entities
- Analytics dashboard: <2s load
- Neighborhood exploration: 100 entities without degradation

**Constraints**:
- Must use existing backend API endpoints (no new endpoints required)
- Must maintain Terminal Observatory theme (phosphor green, amber, cyan)
- Role-based auth: admin writes, all users read

**Scale/Scope**:
- 5,458 entities, 9,889 relationships baseline
- 25+ entity types, 14 relationship types
- 211 null-type entities requiring cleanup

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Evaluation-First Development | PASS | Spec has 34 FRs with acceptance scenarios |
| II. Modular Component Architecture | PASS | Components in `frontend/src/components/entities/` |
| III. Multi-Agent Orchestration | N/A | Feature is UI-focused, not agent-related |
| IV. Hybrid Search Integration | PASS | Uses existing search endpoints |
| V. Enterprise Security | PARTIAL | Authorization defined but not enforced in UI |
| VI. Performance and Scalability | PASS | Performance targets defined in spec |
| VII. Observability and Monitoring | PASS | Using structured logging, toast notifications |

**Gate Result**: PASS with action item - Implement FR-032 to FR-034 (authorization enforcement)

## Project Structure

### Documentation (this feature)

```
specs/003-entity-management-feature/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
│   └── entity-api.yaml
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```
backend/
├── src/
│   ├── api/
│   │   └── knowledge_graph.py    # Existing - 24 endpoints
│   ├── services/
│   │   └── knowledge_graph_service.py  # Existing
│   └── models/
│       └── entity.py             # Existing
└── tests/

frontend/
├── app/
│   └── entities/
│       └── page.tsx              # Existing - comprehensive page
├── src/
│   ├── components/
│   │   └── entities/             # 17 existing components
│   │       ├── EntityForm.tsx
│   │       ├── RelationshipForm.tsx
│   │       ├── PathFinder.tsx
│   │       ├── GraphAnalyticsDashboard.tsx
│   │       ├── BulkOperations.tsx
│   │       └── ... (12 more)
│   ├── services/
│   │   └── entityService.ts      # Existing - API client
│   ├── hooks/
│   │   └── useKeyboardShortcuts.ts
│   └── types/
│       └── entity.ts
└── tests/
```

**Structure Decision**: Web application with existing backend/frontend structure. No new directories needed - enhancements within existing module structure.

## Complexity Tracking

*No constitutional violations requiring justification.*

| Area | Complexity | Justification |
|------|------------|---------------|
| Authorization UI | Low | Leverage existing auth context from app |
| Duplicate Warning | Low | Add check in EntityForm before submit |
| API Retry | Medium | Add wrapper in entityService |
| Null Type Cleanup | Low | Backend endpoint exists, wire to UI |

### Architectural Policies

**Concurrent Edit Handling**: Entity updates use optimistic locking with `updated_at` timestamp validation. If concurrent edit detected (timestamp mismatch), API returns 409 Conflict. Frontend displays error toast with "Entity was modified by another user. Please refresh and try again." No automatic merge - user must manually reconcile.

**Entity Deletion Policy**: Cascade deletion enabled for relationships. When entity is deleted:
- All relationships where entity is source OR target are automatically deleted (Neo4j cascade)
- PostgreSQL metadata record soft-deleted (sets `deleted_at` timestamp)
- Qdrant embeddings removed via background job
- Frontend shows confirmation dialog listing affected relationship count before delete
- Orphaned entities (no relationships) can be filtered and bulk-deleted via existing BulkOperations component

## Implementation Gaps Analysis

Based on codebase research, the following gaps exist between spec and current implementation:

### P1 - Critical Gaps (Must Fix)

| Gap | FR | Current State | Required Change |
|-----|-----|---------------|-----------------|
| Authorization not enforced | FR-032-034 | No role checks in UI | Add admin check, disable controls for non-admins |
| Duplicate entity warning | FR-003 | No duplicate check | Add pre-submit check in EntityForm |
| API retry logic | FR-030 | No retry | Add retry wrapper in entityService |
| Null type filter | FR-023 | Not exposed in filters | Add "Unknown" option to EntityFilters |

### P2 - Enhancement Gaps (Should Fix)

| Gap | FR | Current State | Required Change |
|-----|-----|---------------|-----------------|
| Type counts in filters | FR-027 | Types shown, no counts | Fetch counts from analytics endpoint |
| Filter search | FR-028 | Basic filter UI | Add search input in type dropdown |
| Relationship direction | FR-008 | Shown in detail view | Ensure bidirectional display |

### Already Implemented

| Feature | Status | Component |
|---------|--------|-----------|
| Entity creation | ✓ | EntityForm.tsx |
| Relationship creation | ✓ | RelationshipForm.tsx |
| Path finding | ✓ | PathFinder.tsx |
| Neighborhood exploration | ✓ | NeighborhoodExplorer.tsx (via EntityDetail) |
| Analytics dashboard | ✓ | GraphAnalyticsDashboard.tsx |
| Bulk operations | ✓ | BulkOperations.tsx |
| Document extraction | ✓ | DocumentEntityExtractor.tsx |
| Dynamic type filters | ✓ | EntityFilters.tsx (fetches from API) |
| URL state persistence | ✓ | page.tsx (useSearchParams) |
| Keyboard shortcuts | ✓ | KeyboardShortcutsDialog.tsx |
| Loading states | ✓ | Throughout page |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Backend API incompatibility | Low | High | Existing endpoints well-documented |
| Auth context unavailable | Low | High | Check useAuth hook availability |
| Performance regression | Low | Medium | Test with full dataset |
| Breaking existing functionality | Medium | High | Add tests before changes |

---

## Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design completion.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Evaluation-First Development | PASS | Test specifications in spec.md |
| II. Modular Component Architecture | PASS | Leveraging existing modular components |
| III. Multi-Agent Orchestration | N/A | UI feature |
| IV. Hybrid Search Integration | PASS | Uses existing search endpoints |
| V. Enterprise Security | PASS | Authorization implementation planned |
| VI. Performance and Scalability | PASS | Targets defined, using existing infrastructure |
| VII. Observability and Monitoring | PASS | Toast notifications, structured logging |

**Post-Design Gate Result**: PASS - Ready for task generation

---

## Phase 1 Artifacts Generated

| Artifact | Path | Description |
|----------|------|-------------|
| Research | `research.md` | Technical decisions and patterns |
| Data Model | `data-model.md` | Entity/relationship definitions |
| API Contract | `contracts/entity-api.yaml` | OpenAPI 3.0 specification |
| Quickstart | `quickstart.md` | Implementation guide |

## Next Steps

Run `/speckit.tasks` to generate detailed task breakdown for implementation.
