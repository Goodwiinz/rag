# Research: Entity Management Feature Improvements

**Date**: 2026-01-14
**Feature**: Entity Management Feature Improvements
**Branch**: `003-entity-management-feature`

## Research Summary

This document consolidates research findings for implementing the Entity Management feature gaps identified in the plan.

---

## 1. Authorization Implementation

### Decision: Use existing `useAuth` hook with role checking

### Rationale
The `useAuth` hook already provides access to `user.role` which can be `'admin' | 'user' | 'viewer'`. No new auth infrastructure needed.

### Implementation Pattern
```typescript
import { useAuth } from '@/hooks/useAuth';

function EntityManagementPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  // Disable write operations for non-admins
  return (
    <Button disabled={!isAdmin} onClick={handleCreate}>
      Create Entity
    </Button>
  );
}
```

### Alternatives Considered
1. **Permission-based system** - More flexible but overkill for simple admin/user distinction
2. **Backend-only enforcement** - Already exists but UX suffers without frontend hints

### Files to Modify
- `frontend/app/entities/page.tsx` - Add isAdmin checks
- `frontend/src/components/entities/EntityList.tsx` - Conditionally hide edit/delete buttons
- `frontend/src/components/entities/EntityForm.tsx` - Show read-only mode for non-admins

---

## 2. Duplicate Entity Detection

### Decision: Pre-submit check via search API with force-create option

### Rationale
The `entityService.searchEntities()` method can check for existing entities with the same name and type. This provides instant feedback without backend changes.

### Implementation Pattern
```typescript
// In EntityForm.tsx
const checkForDuplicates = async (name: string, type: string) => {
  const existing = await entityService.searchEntities(name, [type], 1);
  return existing.filter(e =>
    e.name.toLowerCase() === name.toLowerCase() &&
    e.type === type
  );
};

// On form submit
const duplicates = await checkForDuplicates(data.name, data.type);
if (duplicates.length > 0) {
  // Show warning dialog with options:
  // 1. Cancel
  // 2. Create anyway with suffix: "John Smith (2)"
}
```

### Alternatives Considered
1. **Backend duplicate check endpoint** - Would require new API endpoint
2. **Real-time validation on blur** - Could be slow, better as submit-time check

### Files to Modify
- `frontend/src/components/entities/EntityForm.tsx` - Add duplicate check and warning dialog

---

## 3. API Retry Logic

### Decision: Add retry wrapper utility to entityService

### Rationale
A simple retry-once pattern aligns with FR-030 without adding complexity. Use exponential backoff for single retry.

### Implementation Pattern
```typescript
// In entityService.ts
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 1
): Promise<T> {
  let lastError: Error | undefined;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error as Error;
      if (attempt < maxRetries) {
        await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
      }
    }
  }

  throw lastError;
}

// Usage
async getEntities(...): Promise<...> {
  return withRetry(() => apiClient.get(...));
}
```

### Alternatives Considered
1. **axios-retry library** - Adds dependency, more complex configuration
2. **Global interceptor** - Affects all API calls, less control

### Files to Modify
- `frontend/src/services/entityService.ts` - Add retry wrapper to critical methods

---

## 4. Null Type Filter

### Decision: Add "Unknown Type" option to EntityFilters

### Rationale
The backend already returns entities with null types. Frontend needs to expose this as a filter option. Backend has `fix_null_entity_types` endpoint for cleanup.

### Implementation Pattern
```typescript
// In EntityFilters.tsx
const SPECIAL_FILTERS = [
  { value: '__null__', label: 'Unknown Type', count: nullTypeCount }
];

// Combine with dynamic types from API
const allFilterOptions = [...SPECIAL_FILTERS, ...availableTypes];

// In page.tsx
const fetchEntities = async () => {
  if (selectedTypes.includes('__null__')) {
    // Filter client-side for null types, or use analytics endpoint
    params.include_null_types = true;
  }
};
```

### Alternatives Considered
1. **Backend null-type endpoint** - `fix_null_entity_types` exists but for fixing, not filtering
2. **Separate "Data Quality" tab** - Already have BulkOperations which could handle this

### Files to Modify
- `frontend/src/components/entities/EntityFilters.tsx` - Add null type option
- `frontend/app/entities/page.tsx` - Handle null type filter logic

---

## 5. Type Counts in Filters

### Decision: Fetch from analytics endpoint on mount

### Rationale
The `get_graph_analytics` endpoint returns entity type distribution with counts. This can populate filter counts efficiently.

### Implementation Pattern
```typescript
// Fetch analytics for type counts
const fetchTypeCounts = async () => {
  const analytics = await graphAnalyticsService.getAnalytics();
  return analytics.entity_type_distribution; // { PERSON: 1234, LOCATION: 567, ... }
};

// In EntityFilters
const typeOptions = availableTypes.map(type => ({
  value: type,
  label: type,
  count: typeCounts[type] || 0
}));
```

### Alternatives Considered
1. **Inline count calculation** - Requires full entity fetch, expensive
2. **Separate count endpoint** - Backend already provides via analytics

### Files to Modify
- `frontend/src/components/entities/EntityFilters.tsx` - Display counts
- `frontend/app/entities/page.tsx` - Fetch type counts on mount

---

## 6. Existing Component Status

### Verified Working Components
Based on codebase analysis, these components are implemented and integrated:

| Component | Location | Status | Integration |
|-----------|----------|--------|-------------|
| EntityForm | `components/entities/EntityForm.tsx` | ✓ | In dialog |
| RelationshipForm | `components/entities/RelationshipForm.tsx` | ✓ | In dialog |
| PathFinder | `components/entities/PathFinder.tsx` | ✓ | Tab |
| NeighborhoodExplorer | `components/entities/NeighborhoodExplorer.tsx` | ✓ | Via EntityDetail |
| GraphAnalyticsDashboard | `components/entities/GraphAnalyticsDashboard.tsx` | ✓ | Tab |
| BulkOperations | `components/entities/BulkOperations.tsx` | ✓ | Tab |
| DocumentEntityExtractor | `components/entities/DocumentEntityExtractor.tsx` | ✓ | Tab |
| EntityMergeTool | `components/entities/EntityMergeTool.tsx` | ✓ | Tab |
| GraphHealthMonitor | `components/entities/GraphHealthMonitor.tsx` | ✓ | Tab |
| EnhancedSearch | `components/entities/EnhancedSearch.tsx` | ✓ | Tab |
| KeyboardShortcutsDialog | `components/entities/KeyboardShortcutsDialog.tsx` | ✓ | Dialog |
| Pagination | `components/entities/Pagination.tsx` | ✓ | In list tab |

### Backend Endpoint Coverage
All 24 knowledge graph endpoints are implemented. Key endpoints used:

| Endpoint | Frontend Method | Usage |
|----------|----------------|-------|
| GET /entities | `getEntities()` | List with pagination |
| POST /entities | `createEntity()` | Entity creation |
| GET /entity-types | `getEntityTypes()` | Dynamic filters |
| GET /relationship-types | `getRelationshipTypes()` | Relationship form |
| POST /relationships | `createRelationship()` | Relationship creation |
| GET /paths/{source}/{target} | PathFinder | Path finding |
| GET /analytics | GraphAnalyticsDashboard | Analytics |
| POST /batch | `batchCreate()` | Bulk operations |
| POST /documents/{id}/extract-entities | DocumentEntityExtractor | Entity extraction |

---

## Conclusion

All technical unknowns are resolved. The implementation is primarily frontend UI enhancements to existing components:

1. **Authorization**: Use existing `useAuth` hook with `user.role` check
2. **Duplicate detection**: Pre-submit search with warning dialog
3. **API retry**: Simple wrapper function in entityService
4. **Null type filter**: Add special filter option to EntityFilters
5. **Type counts**: Fetch from analytics endpoint

No backend changes required. All implementation can proceed with frontend modifications only.
