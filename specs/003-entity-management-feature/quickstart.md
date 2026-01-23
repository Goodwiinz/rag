# Quickstart: Entity Management Feature

**Date**: 2026-01-14
**Feature**: Entity Management Feature Improvements
**Branch**: `003-entity-management-feature`

## Overview

This guide covers the implementation tasks for enhancing the Entity Management feature. Most components already exist - this focuses on the gaps identified in the plan.

## Prerequisites

- Node.js 18+
- Docker running (for backend services)
- Access to development environment

## Setup

```bash
# Ensure on correct branch
git checkout 003-entity-management-feature

# Start backend services
docker-compose -f docker-compose.development.yml up -d

# Install frontend dependencies
cd frontend && npm install

# Start frontend dev server
npm run dev
```

## Implementation Tasks

### Task 1: Add Authorization Checks

**File**: `frontend/app/entities/page.tsx`

```typescript
// Add at top of component
import { useAuth } from '@/hooks/useAuth';

// Inside component
const { user } = useAuth();
const isAdmin = user?.role === 'admin';

// Use isAdmin to conditionally render buttons
<Button disabled={!isAdmin}>Create Entity</Button>
```

**Files to modify**:
- `frontend/app/entities/page.tsx`
- `frontend/src/components/entities/EntityList.tsx`
- `frontend/src/components/entities/EntityForm.tsx`

### Task 2: Add Duplicate Detection

**File**: `frontend/src/components/entities/EntityForm.tsx`

Add pre-submit check:
```typescript
const checkForDuplicates = async (name: string, type: string) => {
  const existing = await entityService.searchEntities(name, [type], 5);
  return existing.filter(e =>
    e.name.toLowerCase() === name.toLowerCase() && e.type === type
  );
};
```

Add confirmation dialog when duplicate found.

### Task 3: Add API Retry Logic

**File**: `frontend/src/services/entityService.ts`

Add retry wrapper:
```typescript
async function withRetry<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    await new Promise(r => setTimeout(r, 1000));
    return fn(); // Single retry
  }
}
```

Apply to critical methods like `getEntities`, `createEntity`.

### Task 4: Add Null Type Filter

**File**: `frontend/src/components/entities/EntityFilters.tsx`

Add special filter option:
```typescript
const SPECIAL_FILTERS = [
  { value: '__null__', label: 'Unknown Type' }
];
```

### Task 5: Add Type Counts

**File**: `frontend/src/components/entities/EntityFilters.tsx`

Fetch from analytics endpoint and display counts in filter dropdown.

## Testing

```bash
# Run frontend tests
cd frontend && npm run test

# Run type checks
npm run type-check

# Run linting
npm run lint
```

## Verification Checklist

- [ ] Admin users can create/edit/delete entities
- [ ] Non-admin users see disabled controls
- [ ] Duplicate warning shows for same name+type
- [ ] API failures retry once before showing error
- [ ] Null type filter option appears in filters
- [ ] Type counts display next to filter options
- [ ] All existing functionality still works

## Key Files Reference

| Purpose | File |
|---------|------|
| Main page | `frontend/app/entities/page.tsx` |
| Entity form | `frontend/src/components/entities/EntityForm.tsx` |
| API service | `frontend/src/services/entityService.ts` |
| Filters | `frontend/src/components/entities/EntityFilters.tsx` |
| Auth hook | `frontend/src/hooks/useAuth.tsx` |
| Entity types | `frontend/src/types/entity.ts` |

## Common Issues

### Auth context not available
Ensure the page is wrapped in `AuthProvider`. Check `frontend/app/layout.tsx`.

### API returns 403
User doesn't have admin role. Check `user.role` value.

### Duplicate check slow
Increase debounce timeout or make check on form submit only.

## Next Steps

After completing these tasks:
1. Run `/speckit.tasks` to generate detailed task breakdown
2. Create PR for review
3. Update GOO-95 Linear issue status
