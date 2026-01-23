# Data Model: Entity Management Feature

**Date**: 2026-01-14
**Feature**: Entity Management Feature Improvements
**Branch**: `003-entity-management-feature`

## Overview

This document describes the data model for the Entity Management feature. The model is based on existing backend entities with frontend TypeScript type definitions.

---

## Core Entities

### Entity (Knowledge Graph Node)

Represents a real-world concept in the knowledge graph.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Yes | Unique identifier |
| name | string | Yes | Display name (e.g., "John Smith") |
| entity_type | string | Yes | Classification (PERSON, LOCATION, etc.) |
| confidence_score | float | No | 0.0-1.0, extraction confidence |
| extraction_method | string | No | How entity was created (manual, nlp, ocr) |
| position | object | No | Location in source document |
| context | string | No | Surrounding text context |
| metadata | object | No | Arbitrary key-value pairs |
| source_document_id | UUID | No | Linked document if extracted |
| created_at | datetime | Yes | Creation timestamp |
| updated_at | datetime | Yes | Last modification |

**Validation Rules**:
- `name` cannot be empty or whitespace-only
- `entity_type` must be from predefined set (25+ types)
- `confidence_score` must be 0.0-1.0 if provided
- Duplicate check: `name` + `entity_type` combination should warn

**State Transitions**:
- Created → Active (default)
- Active → Merged (when merged with another entity)
- Active → Deleted (soft delete)

### Relationship (Knowledge Graph Edge)

Represents a directed connection between two entities.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | Yes | Unique identifier |
| source_entity_id | UUID | Yes | Starting entity |
| target_entity_id | UUID | Yes | Ending entity |
| relationship_type | string | Yes | Type (COLLABORATES_WITH, etc.) |
| strength | float | No | 0.0-1.0, relationship weight |
| confidence_score | float | No | 0.0-1.0, extraction confidence |
| context | string | No | Evidence text |
| evidence | string[] | No | Supporting evidence snippets |
| metadata | object | No | Arbitrary key-value pairs |
| created_at | datetime | Yes | Creation timestamp |

**Validation Rules**:
- `source_entity_id` and `target_entity_id` must be valid entity UUIDs
- `relationship_type` must be from predefined set (14 types)
- Self-referencing relationships allowed but flagged in health monitor

### Entity Type (Enumeration)

Classification categories for entities. Stored as string values.

**Current Types** (25+):
- PERSON - Human individuals
- ORGANIZATION - Companies, institutions, groups
- LOCATION - Geographic places
- CONCEPT - Abstract ideas, topics
- EVENT - Occurrences, happenings
- PRODUCT - Goods, services
- DATE - Temporal references
- TECHNOLOGY - Technical systems, tools
- DOCUMENT - Written materials
- OTHER - Unclassified entities

### Relationship Type (Enumeration)

Classification for relationships. Stored as string values.

**Current Types** (14):
- COLLABORATES_WITH - Partnership/teamwork
- RELATED_TO - General association
- MENTIONS - Reference in text
- WORKS_FOR - Employment
- LOCATED_IN - Geographic presence
- KNOWS - Personal connection
- PART_OF - Membership/inclusion
- OWNS - Possession/control
- CREATED_BY - Authorship
- USES - Utilization
- MANAGES - Oversight
- AFFILIATED_WITH - Organizational ties
- PRECEDED_BY - Temporal sequence
- FOLLOWED_BY - Temporal sequence

---

## Frontend Type Definitions

### TypeScript Types (existing in `frontend/src/types/entity.ts`)

```typescript
export interface Entity {
  id: string;
  name: string;
  type: string;
  confidence?: number;
  confidence_score?: number;
  extraction_method?: string;
  position?: { start: number; end: number };
  context?: string;
  metadata?: Record<string, any>;
  source_document_id?: string;
  created_at: string;
  updated_at?: string;
}

export interface EntityResponse {
  id: string;
  name: string;
  entity_type: string;
  confidence_score: number;
  extraction_method: string;
  position?: { start: number; end: number };
  context?: string;
  metadata?: Record<string, any>;
  source_document_id?: string;
  created_at: string;
  updated_at?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight?: number;
  strength?: number;
  confidence?: number;
  context?: string;
  metadata?: Record<string, any>;
}

export type EntityType =
  | 'PERSON'
  | 'ORGANIZATION'
  | 'LOCATION'
  | 'CONCEPT'
  | 'EVENT'
  | 'PRODUCT'
  | 'DATE'
  | 'TECHNOLOGY'
  | 'DOCUMENT'
  | 'OTHER'
  | string; // Allow dynamic types
```

### New Types Required

```typescript
// For duplicate detection
export interface DuplicateCheckResult {
  isDuplicate: boolean;
  existingEntities: Entity[];
  suggestedName?: string; // e.g., "John Smith (2)"
}

// For authorization
export interface EntityPermissions {
  canCreate: boolean;
  canEdit: boolean;
  canDelete: boolean;
  canBulkEdit: boolean;
}

// For type filter with counts
export interface EntityTypeOption {
  value: string;
  label: string;
  count: number;
  isSpecial?: boolean; // For null type filter
}
```

---

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                    Knowledge Graph Schema                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐                           ┌──────────┐       │
│  │  Entity  │◄────── Relationship ─────►│  Entity  │       │
│  │  (Node)  │         (Edge)            │  (Node)  │       │
│  └────┬─────┘                           └────┬─────┘       │
│       │                                      │             │
│       │ has type                             │ has type    │
│       ▼                                      ▼             │
│  ┌──────────┐                           ┌──────────┐       │
│  │  Entity  │                           │Relationship│     │
│  │   Type   │                           │   Type    │      │
│  └──────────┘                           └──────────┘       │
│                                                             │
│  ┌──────────┐                                              │
│  │ Document │───────extracts────────────►  Entity          │
│  └──────────┘                                              │
│                                                             │
│  ┌──────────┐                                              │
│  │   User   │───────creates─────────────►  Entity          │
│  │  (Auth)  │───────creates─────────────► Relationship     │
│  └──────────┘                                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Storage Architecture

| Data | Storage | Purpose |
|------|---------|---------|
| Entity metadata | PostgreSQL | Relational queries, full-text search |
| Graph structure | Neo4j | Traversal, path finding, analytics |
| Vector embeddings | Qdrant | Similarity search, semantic queries |
| Session data | Redis | Auth tokens, cache |

---

## Indexing Strategy

### PostgreSQL Indexes
- `entities.name` - Text search
- `entities.entity_type` - Type filtering
- `entities.created_at` - Sorting
- `entities.source_document_id` - Document linkage

### Neo4j Indexes
- Node label: `Entity(id)`
- Property: `Entity(name)`
- Property: `Entity(entity_type)`
- Relationship: `(:Entity)-[:RELATIONSHIP_TYPE]->(:Entity)`

---

## Data Quality Considerations

### Null Type Entities
- **Current count**: 211 entities with null/empty type
- **Impact**: Break filtering, categorization
- **Resolution**: Bulk type assignment via BulkOperations component
- **Prevention**: FR-025 requires type selection on creation

### Duplicate Handling
- **Detection**: Pre-submit check via search API
- **Resolution options**:
  1. Cancel creation
  2. Force-create with auto-suffix
  3. Navigate to existing entity
