# Feature Specification: Entity Management Feature Improvements

**Feature Branch**: `003-entity-management-feature`
**Created**: 2026-01-14
**Status**: Draft
**Input**: User description: "Entity Management Feature Improvements - Comprehensive UI enhancements to fully utilize backend capabilities for the /entities page, including entity/relationship creation, path finding, graph analytics, and document integration"
**Linear Issue**: GOO-95

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create New Entities (Priority: P1)

As a knowledge manager, I want to manually create new entities in the knowledge graph so that I can add information that wasn't automatically extracted from documents.

**Why this priority**: Entity creation is foundational - users need to add data before they can explore relationships or run analytics. The backend endpoint exists but the frontend form isn't wired up.

**Independent Test**: Can be fully tested by creating an entity with name, type, and properties, then verifying it appears in the entity list and can be searched.

**Acceptance Scenarios**:

1. **Given** I am on the entities page, **When** I click "Create Entity" and fill in name, type, and optional properties, **Then** the entity is created and appears in the entity list
2. **Given** I am creating an entity, **When** I select an entity type from the dropdown, **Then** I see type-specific property fields relevant to that entity type
3. **Given** I am creating an entity, **When** I submit without required fields (name, type), **Then** I see validation errors and the form is not submitted
4. **Given** I have created an entity, **When** I view the entity list, **Then** the new entity appears with correct type badge and is searchable

---

### User Story 2 - Create Relationships Between Entities (Priority: P1)

As a knowledge manager, I want to create relationships between entities so that I can build meaningful connections in the knowledge graph.

**Why this priority**: Relationships are the core value of a knowledge graph. Without relationship creation, the graph cannot grow beyond document extraction.

**Independent Test**: Can be fully tested by selecting two entities, choosing a relationship type, and verifying the connection appears in the graph visualization.

**Acceptance Scenarios**:

1. **Given** I am viewing an entity, **When** I click "Add Relationship", **Then** I see a dialog to select target entity and relationship type
2. **Given** I am creating a relationship, **When** I search for target entities, **Then** I can filter by entity type and see search results with type indicators
3. **Given** I am creating a relationship, **When** I select a relationship type (e.g., COLLABORATES_WITH, RELATED_TO, MENTIONS), **Then** I can optionally add properties to the relationship
4. **Given** a relationship is created, **When** I view either entity's detail page, **Then** the relationship appears in both entities' relationship lists

---

### User Story 3 - Dynamic Type Filtering (Priority: P1)

As a user browsing entities, I want filters that reflect actual data in the system so that I can efficiently find entities by their real types.

**Why this priority**: Currently filters may be hardcoded. Dynamic filters from the API ensure accuracy and reduce confusion when browsing 5,458 entities.

**Independent Test**: Can be fully tested by viewing the filter options and verifying they match actual entity types in the database.

**Acceptance Scenarios**:

1. **Given** I am on the entities page, **When** filters load, **Then** entity type options are fetched from the API reflecting actual types in the database
2. **Given** entity types load dynamically, **When** I view filters, **Then** I see counts next to each type indicating how many entities exist
3. **Given** I apply a type filter, **When** results update, **Then** only entities of the selected type are shown
4. **Given** the database has 25+ entity types, **When** I view filters, **Then** I can search/filter within the type list

---

### User Story 4 - Fix Null Entity Types (Priority: P1)

As a data administrator, I want to identify and fix entities with missing type information so that the knowledge graph maintains data quality.

**Why this priority**: 211 entities currently have null types, which breaks filtering and categorization. This is a data quality issue affecting usability.

**Independent Test**: Can be fully tested by identifying entities with null types and bulk-assigning appropriate types.

**Acceptance Scenarios**:

1. **Given** I am on the entities page, **When** I filter by "Unknown Type", **Then** I see all entities without type assignments
2. **Given** I am viewing entities with null types, **When** I select multiple entities, **Then** I can bulk-assign a type to all selected
3. **Given** I assign types to null type entities, **When** I confirm the action, **Then** entities are updated and no longer appear in the null type filter
4. **Given** new entities are created, **When** type is not specified, **Then** the system requires type selection (preventing new null types)

---

### User Story 5 - Find Paths Between Entities (Priority: P2)

As a researcher, I want to discover how two entities are connected so that I can understand hidden relationships in my knowledge base.

**Why this priority**: Path finding is a key differentiator for knowledge graphs - it reveals non-obvious connections. The backend endpoint exists but has no frontend UI.

**Independent Test**: Can be fully tested by selecting two entities and viewing the path(s) connecting them with intermediate entities and relationship types.

**Acceptance Scenarios**:

1. **Given** I am on the entities page, **When** I select "Find Path" and choose two entities, **Then** I see all paths connecting them up to a configurable depth
2. **Given** paths exist between two entities, **When** results are displayed, **Then** I see each intermediate entity and relationship type in the path
3. **Given** I am viewing path results, **When** I click on any entity in the path, **Then** I navigate to that entity's detail view
4. **Given** no path exists between two entities within the search depth, **When** I search, **Then** I see a clear message indicating no connection was found

---

### User Story 6 - Explore Entity Neighborhood (Priority: P2)

As a researcher, I want to explore entities related to a specific entity so that I can discover relevant information in context.

**Why this priority**: Neighborhood exploration enables serendipitous discovery - users can find related entities they didn't know to search for.

**Independent Test**: Can be fully tested by selecting an entity and viewing its immediate and extended neighborhood with depth control.

**Acceptance Scenarios**:

1. **Given** I am viewing an entity, **When** I click "Explore Neighborhood", **Then** I see related entities organized by relationship type
2. **Given** I am exploring a neighborhood, **When** I adjust the depth slider (1-3 levels), **Then** the visualization updates to show entities at that distance
3. **Given** I am viewing the neighborhood, **When** I hover over a relationship, **Then** I see the relationship type and any properties
4. **Given** I am exploring, **When** I click on a related entity, **Then** that entity becomes the center of exploration

---

### User Story 7 - View Graph Analytics Dashboard (Priority: P2)

As a knowledge manager, I want to see statistics about my knowledge graph so that I can understand its health and coverage.

**Why this priority**: Analytics provide insight into graph completeness and help identify gaps or data quality issues.

**Independent Test**: Can be fully tested by viewing the analytics dashboard and verifying metrics match known graph statistics.

**Acceptance Scenarios**:

1. **Given** I navigate to the entities page, **When** I click "Analytics", **Then** I see a dashboard with key graph metrics
2. **Given** I am viewing analytics, **When** the dashboard loads, **Then** I see total entities, relationships, entity type distribution, and relationship type distribution
3. **Given** I am viewing analytics, **When** I click on an entity type in the distribution chart, **Then** I see the entity list filtered by that type
4. **Given** I am viewing analytics, **When** I see "orphan entities" (entities with no relationships), **Then** I can click to view and potentially connect them

---

### User Story 8 - Extract Entities from Documents (Priority: P3)

As a content manager, I want to extract entities from existing documents so that I can automatically populate the knowledge graph.

**Why this priority**: Automated extraction scales the knowledge graph without manual effort, but requires documents to be uploaded first.

**Independent Test**: Can be fully tested by selecting a document and triggering entity extraction, then verifying extracted entities appear in the graph.

**Acceptance Scenarios**:

1. **Given** I am viewing a document, **When** I click "Extract Entities", **Then** the system analyzes the document and shows discovered entities
2. **Given** entity extraction completes, **When** I review results, **Then** I see entities grouped by type with confidence scores
3. **Given** I am reviewing extracted entities, **When** I select entities to add, **Then** they are added to the knowledge graph with source document linkage
4. **Given** entities are extracted, **When** I view the document later, **Then** I see linked entities highlighted in the document view

---

### Edge Cases

- Duplicate entity creation: System warns and allows force-create with auto-suffix
- How does the system handle relationship creation between entities that already have a relationship of the same type?
- Path finding timeout: Auto-retry once, then show error with retry button and suggest reducing depth
- API failures: Auto-retry once, then show user-friendly error with manual retry option
- How does entity extraction handle documents with no recognizable entities?
- What happens when bulk type assignment fails for some entities?
- How does the system handle concurrent edits to the same entity?
- What happens when an entity is deleted but has existing relationships?

## Requirements *(mandatory)*

### Functional Requirements

**Entity Management**
- **FR-001**: System MUST allow users to create entities with name, type, and optional properties
- **FR-002**: System MUST validate entity creation forms before submission
- **FR-003**: System MUST warn users when creating entities with duplicate name+type, allowing force-create with auto-generated suffix (e.g., "John Smith (2)")
- **FR-004**: System MUST display entity type badges consistently throughout the interface

**Relationship Management**
- **FR-005**: System MUST allow users to create relationships between any two entities
- **FR-006**: System MUST support all 14 existing relationship types (COLLABORATES_WITH, RELATED_TO, MENTIONS, etc.)
- **FR-007**: System MUST allow optional properties on relationships
- **FR-008**: System MUST display relationships bidirectionally (visible from both entities)

**Path Finding**
- **FR-009**: System MUST find paths between two selected entities
- **FR-010**: System MUST allow users to configure path depth (1-5 hops)
- **FR-011**: System MUST display all paths found within the configured depth
- **FR-012**: System MUST show intermediate entities and relationship types in path results

**Neighborhood Exploration**
- **FR-013**: System MUST display related entities for any selected entity
- **FR-014**: System MUST allow depth control (1-3 levels) for neighborhood exploration
- **FR-015**: System MUST group related entities by relationship type

**Analytics**
- **FR-016**: System MUST display total entity and relationship counts
- **FR-017**: System MUST display entity type distribution
- **FR-018**: System MUST display relationship type distribution
- **FR-019**: System MUST identify orphan entities (no relationships)

**Document Integration**
- **FR-020**: System MUST allow entity extraction from uploaded documents
- **FR-021**: System MUST display extraction results with confidence scores
- **FR-022**: System MUST link extracted entities to source documents

**Data Quality**
- **FR-023**: System MUST provide a filter to view entities with null/missing types
- **FR-024**: System MUST allow bulk type assignment for multiple entities
- **FR-025**: System MUST require entity type selection on creation (prevent null types)

**Filtering & Search**
- **FR-026**: System MUST load entity type filters dynamically from the API
- **FR-027**: System MUST display entity counts per type in filter options
- **FR-028**: System MUST support search within filter options for large type sets

**Loading States & UX**
- **FR-029**: System MUST display loading indicators during all async operations
- **FR-030**: System MUST retry failed API calls once automatically, then display error message with manual retry button
- **FR-031**: System MUST persist filter and view state in URL for shareability

**Authorization**
- **FR-032**: System MUST restrict entity/relationship creation, editing, and deletion to admin users
- **FR-033**: System MUST allow all authenticated users to read, search, and explore entities
- **FR-034**: System MUST hide or disable create/edit/delete UI controls for non-admin users

### Key Entities

- **Entity**: A node in the knowledge graph representing a real-world concept (person, location, organization, concept). Has name, type, properties, and relationships to other entities.
- **Relationship**: A directed connection between two entities with a type (e.g., COLLABORATES_WITH) and optional properties.
- **Entity Type**: A classification category for entities (PERSON, LOCATION, ORGANIZATION, CONCEPT, etc.). 25+ types currently exist.
- **Relationship Type**: A classification for relationships (COLLABORATES_WITH, RELATED_TO, MENTIONS, etc.). 14 types currently exist.
- **Path**: A sequence of entities connected by relationships, used to show how two entities are connected.
- **Neighborhood**: The set of entities related to a focal entity within a specified depth.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can create a new entity in under 30 seconds
- **SC-002**: Users can create a relationship between two entities in under 45 seconds
- **SC-003**: Path finding returns results in under 3 seconds for graphs up to 10,000 entities
- **SC-004**: 100% of entity type filters reflect actual data in the system (zero hardcoded options)
- **SC-005**: Zero entities with null types after data cleanup (currently 211)
- **SC-006**: Analytics dashboard loads within 2 seconds
- **SC-007**: Neighborhood exploration displays up to 100 related entities without performance degradation
- **SC-008**: Entity extraction identifies at least 80% of named entities in documents
- **SC-009**: All async operations show loading states (zero silent waiting periods)
- **SC-010**: Users can share filtered views via URL (state persistence)

## Clarifications

### Session 2026-01-14

- Q: What happens when a user creates a duplicate entity (same name and type)? → A: Show warning, allow force-create with suffix (e.g., "John Smith (2)")
- Q: What permission model applies to entity operations? → A: Role-based (admins create/edit/delete, all users read/explore)
- Q: How should the system handle backend API failures? → A: Retry once automatically, then show error with manual retry button

## Assumptions

- The backend API endpoints for all features already exist and are functional
- Entity types are predefined in the system (users cannot create new types through this feature)
- The existing 5,458 entities and 9,889 relationships are the baseline dataset
- Graph visualization will leverage existing server-side layout capabilities
- Role-based permission model exists: admin role for create/edit/delete, authenticated users for read/explore
- Document entity extraction uses existing NLP capabilities in the backend
