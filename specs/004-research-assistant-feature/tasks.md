# Tasks: Research Assistant

**Input**: Design documents from `/specs/004-research-assistant-feature/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in spec. Test tasks are NOT included.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)

## User Story Mapping

| Story | Title | Priority | Phase |
|-------|-------|----------|-------|
| US1 | Ask Questions About Papers Using Local AI | P1 | Phase 1 |
| US2 | Generate Bibliography from Research Collection | P2 | Phase 2 |
| US3 | Visualize Citation Network | P2 | Phase 2 |
| US4 | Organize Documents into Research Projects | P3 | Phase 3 |
| US5 | Generate Literature Review Draft | P3 | Phase 4 |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and base structure

- [X] T001 [P] Install backend dependencies: `pybtex==0.24.0`, `aiohttp-retry==2.8.3` in `backend/requirements.txt`
- [X] T002 [P] Install frontend dependencies: `cytoscape-popper@2.0.0`, `cytoscape-context-menus@4.1.0` in `frontend/package.json`
- [X] T003 [P] Create directory structure for new services: `backend/src/services/{citation_extraction_service.py, bibliography_service.py, citation_graph_service.py, draft_generation_service.py}`
- [X] T004 [P] Create directory structure for frontend components: `frontend/src/components/{citations/, research/}`
- [X] T005 [P] Create directory structure for stores: `frontend/src/store/{citationStore.ts, projectStore.ts}`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database migrations and core models that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Database Migrations

- [X] T006 Create Alembic migration 1: Extend citations table with scholarly metadata fields in `backend/alembic/versions/xxx_extend_citations_metadata.py`
  - Add columns: authors, year, venue, doi, arxiv_id, abstract, metadata_source, needs_review
  - Add unique constraints on doi, arxiv_id
  - Add indexes on arxiv_id, doi, document_id

- [X] T007 Create Alembic migration 2: Create citation_relationships table in `backend/alembic/versions/xxx_create_citation_relationships.py`
  - Table with source_citation_id, target_citation_id, relationship_type, citation_context, confidence
  - Unique constraint, self-reference check, indexes

- [X] T008 Create Alembic migration 3: Extend collections table for research projects in `backend/alembic/versions/xxx_extend_collections_research.py`
  - Add columns: project_type, research_status, research_goals, deadline, tags, is_private

- [X] T009 Create Alembic migration 4: Create project_notes table in `backend/alembic/versions/xxx_create_project_notes.py`
  - Table with project_id, user_id, title, content, linked_document_ids, tags, is_pinned
  - Indexes on project_id, user_id

- [X] T010 Create Alembic migration 5: Create generated_drafts and draft_citations tables in `backend/alembic/versions/xxx_create_generated_drafts.py`
  - generated_drafts table with versioning, themes, generation_params
  - draft_citations table linking drafts to documents/citations
  - Version retention trigger function

- [X] T011 Run all migrations: `alembic upgrade head`

### Core Models (Backend)

- [X] T012 [P] Extend Citation model with scholarly metadata fields in `backend/src/models/citation.py`
  - Add: authors, year, venue, doi, arxiv_id, abstract, metadata_source, needs_review
  - Add validation for year range, arxiv_id format

- [X] T013 [P] Create CitationRelationship model in `backend/src/models/citation_relationship.py`
  - Fields: source_citation_id, target_citation_id, relationship_type, citation_context, confidence
  - Relationships to Citation model

- [X] T014 [P] Create/Extend ResearchProject model in `backend/src/models/research_project.py`
  - Extend collections with: project_type, research_status, research_goals, deadline, tags, is_private
  - State transition logic

- [X] T015 [P] Create ProjectNote model in `backend/src/models/project_note.py`
  - Fields: project_id, user_id, title, content, linked_document_ids, tags, is_pinned

- [X] T016 [P] Create GeneratedDraft model in `backend/src/models/generated_draft.py`
  - Fields: project_id, version, title, content, themes, word_count, citation_count, generation_params, is_current

- [X] T017 [P] Create DraftCitation model in `backend/src/models/draft_citation.py`
  - Fields: draft_id, citation_index, document_id, citation_id, snippet, context

- [X] T018 Update models __init__.py to export all new models in `backend/src/models/__init__.py`

### Core Pydantic Schemas

- [X] T019 [P] Create Citation schemas (Create, Update, Response, List) in `backend/src/shared/research_schemas.py`
- [X] T020 [P] Create Project schemas (Create, Update, Response, Detail) in `backend/src/shared/research_schemas.py`
- [X] T021 [P] Create Note schemas (Create, Update, Response) in `backend/src/shared/research_schemas.py`
- [X] T022 [P] Create Draft schemas (Generate, Response, Comparison, Export) in `backend/src/shared/research_schemas.py`

**Checkpoint**: Foundation ready - models, migrations, schemas complete. User story implementation can begin.

---

## Phase 3: User Story 1 - Ask Questions Using Local AI (Priority: P1) 🎯 MVP

**Goal**: Enable WebLLM local models to answer questions about uploaded documents with proper citations

**Independent Test**: Upload a PDF, select Llama-3.2-1B, enable RAG, ask "What are the key findings?". Verify response includes `[Doc N]` citation that's clickable and persisted.

### Backend Implementation for US1

- [X] T023 [US1] Add citation persistence endpoint `POST /api/v1/citations` in `backend/src/api/citations.py`
  - Create citation from chat message context
  - Link to message_id and document_id

- [X] T024 [US1] Add citation retrieval endpoint `GET /api/v1/citations` in `backend/src/api/citations.py`
  - Filter by message_id, document_id
  - Include snippet preview

- [X] T025 [US1] Add single citation detail `GET /api/v1/citations/{id}` in `backend/src/api/citations.py`
  - Return full citation with document snippet

- [X] T026 [US1] Create message citation service in `backend/src/services/message_citation_service.py`
  - Save citations from AI responses
  - Parse [Doc N] format from response text
  - Link citations to source documents

- [X] T027 [US1] Register citations router in `backend/src/main.py`

### Frontend Implementation for US1

- [X] T028 [US1] Extend ragService.ts with citation persistence in `frontend/src/services/ragService.ts`
  - After WebLLM response, extract [Doc N] citations
  - POST citations to backend for persistence
  - Return citation IDs for linking

- [X] T029 [US1] Create citationService.ts API client in `frontend/src/services/citationService.ts`
  - createCitation(), getCitation(), listCitations()
  - Handle citation preview fetching

- [X] T030 [US1] Create citationStore.ts Zustand store in `frontend/src/store/citationStore.ts`
  - State: citations, loading, error
  - Actions: fetchCitations, addCitation, clearCitations

- [X] T031 [US1] Modify chat page to integrate RAG with WebLLM in `frontend/app/(dashboard)/chat/page.tsx`
  - Before WebLLM inference: call ragService.retrieveContext()
  - Inject context into prompt based on model size
  - After response: persist citations via citationService

- [X] T032 [US1] Create CitationPreview component in `frontend/src/components/citations/CitationPreview.tsx`
  - Render clickable [Doc N] links
  - Show popover/modal with source snippet on click

- [X] T033 [US1] Integrate CitationPreview into chat messages in `frontend/src/components/chat/ChatMessage.tsx`
  - Parse message for [Doc N] patterns
  - Replace with CitationPreview components

- [X] T034 [US1] Add model-aware context configuration in `frontend/src/services/ragService.ts`
  - 1B: 2 docs, 600 tokens, 2 history
  - 3B: 3 docs, 1000 tokens, 4 history
  - 7B+: 5 docs, 2000 tokens, 8 history
  - Cloud: 8 docs, 4000 tokens, 20 history

- [X] T035 [US1] Add RAG toggle UI to chat interface in `frontend/app/(dashboard)/chat/page.tsx`
  - Toggle switch to enable/disable RAG
  - Persist preference to localStorage

- [X] T036 [US1] Add observability logging for citation operations in `backend/src/services/message_citation_service.py`
  - Log citation creation with structlog
  - Track citation_created events

**Checkpoint**: User Story 1 complete. Local AI can answer questions with persisted, clickable citations.

---

## Phase 4: User Story 2 - Generate Bibliography (Priority: P2)

**Goal**: Extract citation metadata from papers and export as BibTeX/IEEE/APA/MLA

**Independent Test**: Upload 3-5 ArXiv papers, click "Generate Bibliography", download .bib file. Verify valid BibTeX with authors, title, year, venue.

### Backend Implementation for US2

- [X] T037 [US2] Create ArXiv citation extractor in `backend/src/services/citation_extraction_service.py`
  - Use existing arxiv_service.py for API calls
  - Extract title, authors, year, arxiv_id, abstract
  - Rate limit: 3 req/sec

- [X] T038 [US2] Add Semantic Scholar client in `backend/src/services/semantic_scholar_service.py`
  - Lookup by ArXiv ID, DOI, or title
  - Extract citation metadata and citation counts
  - Rate limit: 100/min

- [X] T039 [US2] Add CrossRef client in `backend/src/services/crossref_service.py`
  - DOI-based lookup
  - Extract venue, publisher metadata
  - Rate limit: 50/sec

- [X] T040 [US2] Implement hybrid extraction pipeline in `backend/src/services/citation_extraction_service.py`
  - Strategy: ArXiv → Semantic Scholar → CrossRef → PDF parsing → manual
  - Return extraction source and confidence score

- [X] T041 [US2] Add citation extraction endpoint `POST /api/v1/citations/extract` in `backend/src/api/citations.py`
  - Accept document_id, strategy (auto/arxiv/crossref/etc)
  - Return extracted citations with confidence

- [X] T042 [US2] Create bibliography formatting service in `backend/src/services/bibliography_service.py`
  - BibTeX formatter using pybtex
  - IEEE formatter (custom)
  - APA formatter (custom)
  - MLA formatter (custom)

- [X] T043 [US2] Add bibliography export endpoint `POST /api/v1/citations/export` in `backend/src/api/citations.py`
  - Accept format (bibtex/ieee/apa/mla), citation_ids or project_id
  - Return formatted bibliography file

- [X] T044 [US2] Add citation lookup endpoint `POST /api/v1/citations/lookup` in `backend/src/api/citations.py`
  - Lookup by arxiv_id, doi, or title
  - Return Citation schema

- [X] T045 [US2] Add observability metrics for extraction in `backend/src/services/citation_extraction_service.py`
  - Histogram: citation_extraction_duration_seconds
  - Counter: citation_extraction_success_total by source

### Frontend Implementation for US2

- [X] T046 [US2] Add extraction methods to citationService.ts in `frontend/src/services/citationService.ts`
  - extractCitations(documentId, strategy)
  - lookupCitation(arxivId?, doi?, title?)
  - exportBibliography(format, citationIds?, projectId?)

- [X] T047 [US2] Create BibliographyExport component in `frontend/src/components/citations/BibliographyExport.tsx`
  - Format selector dropdown (BibTeX, IEEE, APA, MLA)
  - Citation selection checkboxes
  - Download button
  - "Needs review" warnings

- [X] T048 [US2] Add citation extraction UI to document detail page in `frontend/app/(dashboard)/documents/[id]/page.tsx`
  - "Extract Citations" button
  - Progress indicator during extraction
  - Display extracted citations list

- [X] T049 [US2] Create CitationList component in `frontend/src/components/citations/CitationList.tsx`
  - Display citations with metadata (title, authors, year)
  - "Needs review" badge for incomplete metadata
  - Edit button for manual correction

- [X] T050 [US2] Create CitationEditModal component in `frontend/src/components/citations/CitationEditModal.tsx`
  - Form for editing citation metadata
  - Auto-lookup by ArXiv ID or DOI

**Checkpoint**: User Story 2 complete. Users can extract citations and export bibliographies.

---

## Phase 5: User Story 3 - Visualize Citation Network (Priority: P2)

**Goal**: Interactive graph showing citation relationships between papers

**Independent Test**: Upload paper with 10+ references, click "Extract Citations" then "Show Citation Graph". Verify interactive network with clickable nodes.

### Backend Implementation for US3

- [X] T051 [US3] Create citation graph service in `backend/src/services/citation_graph_service.py`
  - Sync citations to Neo4j as :Citation nodes
  - Create :CITES relationships
  - Compute layout positions (force-directed)

- [X] T052 [US3] Add Neo4j citation graph queries in `backend/src/services/citation_graph_service.py`
  - get_citation_graph(project_id?, document_id?, depth)
  - get_node_details(node_id)
  - Add influence_score calculation

- [X] T053 [US3] Add citation relationship endpoints in `backend/src/api/citations.py`
  - `GET /api/v1/citations/relationships` - list relationships
  - `POST /api/v1/citations/relationships` - create relationship

- [X] T054 [US3] Add graph endpoints in `backend/src/api/citations.py`
  - `GET /api/v1/citations/graph` - get graph data with positions
  - `GET /api/v1/citations/graph/node/{id}` - get node details

### Frontend Implementation for US3

- [X] T055 [US3] Create CitationGraph component with Cytoscape.js in `frontend/src/components/citations/CitationGraph.tsx`
  - Initialize Cytoscape with preset layout (backend positions)
  - Node styling: size by citation count, color by type (uploaded/external)
  - Edge styling: weight by relationship type
  - Viewport optimizations for 500+ nodes

- [X] T056 [US3] Add graph interaction handlers in `frontend/src/components/citations/CitationGraph.tsx`
  - Click node → show details panel
  - Hover → show tooltip (title, year)
  - Context menu → add to collection, view paper

- [X] T057 [US3] Create CitationNodeDetails component in `frontend/src/components/citations/CitationNodeDetails.tsx`
  - Display full paper metadata
  - "Add to Collection" button for external papers
  - Link to source (ArXiv, DOI)

- [X] T058 [US3] Add graph methods to citationService.ts in `frontend/src/services/citationService.ts`
  - getCitationGraph(projectId?, documentId?, depth, includeExternal)
  - getGraphNodeDetails(nodeId)

- [X] T059 [US3] Add graph view to document detail page in `frontend/app/(dashboard)/documents/[id]/page.tsx`
  - "Show Citation Graph" button (after extraction)
  - Embed CitationGraph component in modal or tab

- [X] T060 [US3] Add graph filtering controls in `frontend/src/components/citations/CitationGraphControls.tsx`
  - Year range slider
  - Depth selector (1-3)
  - Include/exclude external papers toggle

**Checkpoint**: User Story 3 complete. Citation networks are visualized and interactive.

---

## Phase 6: User Story 4 - Organize Documents into Research Projects (Priority: P3)

**Goal**: Create named projects to organize documents with notes and tags

**Independent Test**: Create project "ML Healthcare", add 3 documents, write a markdown note. Verify all content appears on project page.

### Backend Implementation for US4

- [ ] T061 [US4] Create projects API router in `backend/src/api/projects.py`
  - `GET /api/v1/projects` - list user's projects
  - `POST /api/v1/projects` - create project
  - `GET /api/v1/projects/{id}` - get project detail
  - `PATCH /api/v1/projects/{id}` - update project
  - `DELETE /api/v1/projects/{id}` - delete project

- [ ] T062 [US4] Add project document management endpoints in `backend/src/api/projects.py`
  - `GET /api/v1/projects/{id}/documents` - list project documents
  - `POST /api/v1/projects/{id}/documents` - add document to project
  - `DELETE /api/v1/projects/{id}/documents/{doc_id}` - remove document

- [ ] T063 [US4] Add project notes endpoints in `backend/src/api/projects.py`
  - `GET /api/v1/projects/{id}/notes` - list notes
  - `POST /api/v1/projects/{id}/notes` - create note
  - `GET /api/v1/projects/{id}/notes/{note_id}` - get note
  - `PATCH /api/v1/projects/{id}/notes/{note_id}` - update note
  - `DELETE /api/v1/projects/{id}/notes/{note_id}` - delete note
  - `POST /api/v1/projects/{id}/notes/{note_id}/pin` - toggle pin

- [ ] T064 [US4] Add project bibliography endpoint in `backend/src/api/projects.py`
  - `GET /api/v1/projects/{id}/bibliography` - generate from all project docs

- [ ] T065 [US4] Create project service in `backend/src/services/project_service.py`
  - CRUD operations with ownership validation
  - is_private enforcement (always TRUE)
  - State transition logic

- [ ] T066 [US4] Register projects router in `backend/src/main.py`

### Frontend Implementation for US4

- [ ] T067 [US4] Create projectService.ts API client in `frontend/src/services/projectService.ts`
  - Project CRUD methods
  - Document add/remove methods
  - Note CRUD methods
  - Bibliography generation

- [ ] T068 [US4] Create projectStore.ts Zustand store in `frontend/src/store/projectStore.ts`
  - State: projects, currentProject, notes, loading
  - Actions: fetchProjects, createProject, addDocument, etc.

- [ ] T069 [US4] Create research projects page in `frontend/app/(dashboard)/research/page.tsx`
  - Project list with status badges
  - "Create Project" button
  - Filter by status, type, tag
  - Search functionality

- [ ] T070 [US4] Create ProjectList component in `frontend/src/components/research/ProjectList.tsx`
  - Grid/list view of projects
  - Status badge (active/paused/completed)
  - Document count, deadline display

- [ ] T071 [US4] Create ProjectCard component in `frontend/src/components/research/ProjectCard.tsx`
  - Project name, description preview
  - Quick actions: open, archive, delete

- [ ] T072 [US4] Create CreateProjectModal component in `frontend/src/components/research/CreateProjectModal.tsx`
  - Form: name, description, type, deadline, tags
  - Validation

- [ ] T073 [US4] Create project detail page in `frontend/app/(dashboard)/research/[id]/page.tsx`
  - Tabs: Documents, Notes, Bibliography, Drafts
  - Project metadata header
  - Edit/Archive buttons

- [ ] T074 [US4] Create ProjectDetail component in `frontend/src/components/research/ProjectDetail.tsx`
  - Tab navigation
  - Document list with add/remove
  - Drag-and-drop document adding

- [ ] T075 [US4] Create NoteEditor component in `frontend/src/components/research/NoteEditor.tsx`
  - Markdown editor with preview
  - Title input
  - Tag input
  - Save/cancel buttons
  - Link documents feature

- [ ] T076 [US4] Create NoteList component in `frontend/src/components/research/NoteList.tsx`
  - List of notes with title, preview
  - Pin/unpin toggle
  - Filter by tag
  - Edit/delete actions

- [ ] T077 [US4] Add navigation link to research page in `frontend/src/components/layout/AppSidebar.tsx`
  - Add "Research" menu item

**Checkpoint**: User Story 4 complete. Users can organize documents into projects with notes.

---

## Phase 7: User Story 5 - Generate Literature Review Draft (Priority: P3)

**Goal**: AI-generated literature review based on project documents with proper citations

**Independent Test**: Project with 5+ papers, click "Generate Literature Review" with themes "methodology, findings". Verify 3-5 paragraph draft with [Doc N] citations.

### Backend Implementation for US5

- [ ] T078 [US5] Create draft generation service in `backend/src/services/draft_generation_service.py`
  - Orchestrate multi-agent system for literature review
  - Parse themes, select documents
  - Inject [Doc N] citations
  - Track generation time

- [ ] T079 [US5] Add draft generation endpoint `POST /api/v1/projects/{id}/drafts` in `backend/src/api/drafts.py`
  - Accept themes, document_ids, style, max_sections
  - Return generation status (202 Accepted)

- [ ] T080 [US5] Add draft listing endpoint `GET /api/v1/projects/{id}/drafts` in `backend/src/api/drafts.py`
  - Return draft versions (newest first)
  - Optional include_content param

- [ ] T081 [US5] Add draft detail endpoints in `backend/src/api/drafts.py`
  - `GET /api/v1/projects/{id}/drafts/current` - get current draft
  - `GET /api/v1/projects/{id}/drafts/{draft_id}` - get specific draft
  - `DELETE /api/v1/projects/{id}/drafts/{draft_id}` - delete draft

- [ ] T082 [US5] Add draft citations endpoint `GET /api/v1/projects/{id}/drafts/{draft_id}/citations` in `backend/src/api/drafts.py`
  - Return citations mapped to [Doc N] indices

- [ ] T083 [US5] Add draft comparison endpoint `GET /api/v1/projects/{id}/drafts/compare` in `backend/src/api/drafts.py`
  - Compare two versions: word count diff, similarity score

- [ ] T084 [US5] Add draft export endpoint `POST /api/v1/projects/{id}/drafts/{draft_id}/export` in `backend/src/api/drafts.py`
  - Export to LaTeX (.tex + .bib) or Markdown
  - Return ZIP for LaTeX

- [ ] T085 [US5] Add generation status endpoint `GET /api/v1/projects/{id}/drafts/status` in `backend/src/api/drafts.py`
  - Return: status, progress, current_step, estimated_remaining

- [ ] T086 [US5] Add cancel generation endpoint `POST /api/v1/projects/{id}/drafts/cancel` in `backend/src/api/drafts.py`

- [ ] T087 [US5] Register drafts router in `backend/src/main.py`

- [ ] T088 [US5] Add observability metrics for draft generation in `backend/src/services/draft_generation_service.py`
  - Histogram: draft_generation_duration_seconds by num_documents
  - Counter: draft_generation_total by status

### Frontend Implementation for US5

- [ ] T089 [US5] Add draft methods to projectService.ts in `frontend/src/services/projectService.ts`
  - generateDraft(projectId, themes, options)
  - listDrafts(projectId)
  - getDraft(projectId, draftId)
  - compareDrafts(projectId, versionA, versionB)
  - exportDraft(projectId, draftId, format)
  - getGenerationStatus(projectId)
  - cancelGeneration(projectId)

- [ ] T090 [US5] Create DraftViewer component in `frontend/src/components/research/DraftViewer.tsx`
  - Markdown renderer with [Doc N] citations
  - Version selector dropdown
  - Export button (LaTeX/Markdown)

- [ ] T091 [US5] Create DraftGenerator component in `frontend/src/components/research/DraftGenerator.tsx`
  - Theme input (multi-select or chips)
  - Style selector (academic/technical/summary)
  - Max sections slider
  - Include abstract toggle
  - Generate button

- [ ] T092 [US5] Create DraftGenerationProgress component in `frontend/src/components/research/DraftGenerationProgress.tsx`
  - Progress bar
  - Current step display
  - ETA countdown
  - Cancel button

- [ ] T093 [US5] Create DraftComparison component in `frontend/src/components/research/DraftComparison.tsx`
  - Side-by-side view
  - Diff highlighting
  - Stats comparison (word count, citations)

- [ ] T094 [US5] Create DraftExportModal component in `frontend/src/components/research/DraftExportModal.tsx`
  - Format selector (LaTeX, Markdown)
  - Bibliography format selector (BibTeX/BibLaTeX)
  - Include bibliography toggle
  - Download button

- [ ] T095 [US5] Add Drafts tab content to ProjectDetail in `frontend/src/components/research/ProjectDetail.tsx`
  - Draft list with version numbers
  - Generate new draft button
  - View/compare/export actions

**Checkpoint**: User Story 5 complete. AI-generated literature reviews with citations and export.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements affecting multiple user stories

- [ ] T096 [P] Add error boundary for citation components in `frontend/src/components/citations/CitationErrorBoundary.tsx`
- [ ] T097 [P] Add error boundary for research components in `frontend/src/components/research/ResearchErrorBoundary.tsx`
- [ ] T098 [P] Add loading skeletons for citation graph in `frontend/src/components/citations/CitationGraphSkeleton.tsx`
- [ ] T099 [P] Add loading skeletons for project list in `frontend/src/components/research/ProjectListSkeleton.tsx`
- [ ] T100 Performance optimization: Add virtual scrolling to CitationList for 500+ items
- [ ] T101 Performance optimization: Add graph clustering for 1000+ nodes in CitationGraph
- [ ] T102 Security: Validate project ownership on all project endpoints in `backend/src/api/projects.py`
- [ ] T103 Security: Validate draft ownership on all draft endpoints in `backend/src/api/drafts.py`
- [ ] T104 Add structured logging throughout citation extraction pipeline
- [ ] T105 Run quickstart.md validation scenarios end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ────────────────────────────────────┐
                                                   │
Phase 2: Foundational (BLOCKING) ◄─────────────────┘
    │
    ├──► Phase 3: US1 - Local AI RAG (P1) 🎯 MVP
    │
    ├──► Phase 4: US2 - Bibliography Export (P2)
    │         │
    │         └──► Phase 5: US3 - Citation Graph (P2)
    │                   (depends on US2 extraction)
    │
    └──► Phase 6: US4 - Research Projects (P3)
              │
              └──► Phase 7: US5 - Draft Generation (P3)
                        (depends on US4 projects)

Phase 8: Polish ◄── All desired stories complete
```

### User Story Dependencies

| Story | Can Start After | Dependencies on Other Stories |
|-------|-----------------|------------------------------|
| US1 | Phase 2 (Foundational) | None - fully independent |
| US2 | Phase 2 (Foundational) | None - fully independent |
| US3 | Phase 2 + US2 extraction tasks | Needs citation extraction from US2 |
| US4 | Phase 2 (Foundational) | None - fully independent |
| US5 | Phase 2 + US4 project tasks | Needs project structure from US4 |

### Within Each User Story

1. Backend models → Backend services → Backend API endpoints
2. Frontend services → Frontend stores → Frontend components → Frontend pages
3. Integration with existing components last

### Parallel Opportunities

**Phase 1 Setup** (all [P]):
- T001, T002, T003, T004, T005 can run in parallel

**Phase 2 Foundational**:
- T012-T017 models can run in parallel after migrations
- T019-T022 schemas can run in parallel

**After Foundational Complete**:
- US1 and US2 can start in parallel (no dependencies)
- US4 can start in parallel with US1/US2
- US3 waits for US2 extraction
- US5 waits for US4 projects

---

## Parallel Execution Examples

### Phase 2 Models (after migrations)
```bash
# All model files can be created in parallel:
T012: backend/src/models/citation.py (extend)
T013: backend/src/models/citation_relationship.py (new)
T014: backend/src/models/research_project.py (new)
T015: backend/src/models/project_note.py (new)
T016: backend/src/models/generated_draft.py (new)
T017: backend/src/models/draft_citation.py (new)
```

### US1 Frontend Components
```bash
# These components touch different files:
T029: frontend/src/services/citationService.ts
T030: frontend/src/store/citationStore.ts
T032: frontend/src/components/citations/CitationPreview.tsx
```

### US2 + US4 in Parallel (different developers)
```bash
# Developer A: US2 Citation Extraction
T037: citation_extraction_service.py
T038: semantic_scholar_service.py
T039: crossref_service.py

# Developer B: US4 Research Projects
T061: projects.py (API)
T065: project_service.py
T067: projectService.ts (frontend)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T022)
3. Complete Phase 3: User Story 1 (T023-T036)
4. **STOP and VALIDATE**: Test local AI with citations
5. Deploy/demo if ready - users can ask questions with citations

### Incremental Delivery

| Increment | Stories | User Value |
|-----------|---------|------------|
| MVP | US1 | Ask questions with citations |
| +Citations | US1 + US2 | Export bibliographies |
| +Graphs | US1 + US2 + US3 | Visualize citation networks |
| +Projects | US1-4 | Organize documents |
| Full Feature | US1-5 | Generate literature reviews |

### Parallel Team Strategy

With 2 developers after Foundational:

```
Developer A: US1 (P1) → US2 (P2) → US3 (P2)
Developer B: US4 (P3) → US5 (P3)
```

With 3 developers:

```
Developer A: US1 (P1 MVP)
Developer B: US2 (P2) → US3 (P2)
Developer C: US4 (P3) → US5 (P3)
```

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1. Setup | T001-T005 (5) | Dependencies, directories |
| 2. Foundational | T006-T022 (17) | Migrations, models, schemas |
| 3. US1 - Local AI | T023-T036 (14) | WebLLM + RAG + citations |
| 4. US2 - Bibliography | T037-T050 (14) | Extraction + export |
| 5. US3 - Graph | T051-T060 (10) | Neo4j + Cytoscape |
| 6. US4 - Projects | T061-T077 (17) | CRUD + notes |
| 7. US5 - Drafts | T078-T095 (18) | Multi-agent generation |
| 8. Polish | T096-T105 (10) | Error handling, performance |

**Total**: 105 tasks

**MVP Scope**: Phases 1-3 (36 tasks) - Local AI with persisted citations
