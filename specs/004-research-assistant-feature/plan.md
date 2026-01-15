# Implementation Plan: Research Assistant

**Branch**: `004-research-assistant-feature` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-research-assistant-feature/spec.md`

## Summary

Transform the RAG system into a comprehensive research assistant enabling researchers to:
1. **Phase 1 (P1)**: Use local AI models (WebLLM) with RAG retrieval and inline citations
2. **Phase 2 (P2)**: Extract citations, visualize citation graphs, and export bibliographies
3. **Phase 3 (P3)**: Organize documents into research projects with notes
4. **Phase 4 (P3)**: Generate AI-powered literature review drafts

Technical approach: Extend existing chat infrastructure to inject RAG context into WebLLM prompts, build citation extraction service using hybrid API lookups, create Neo4j-based citation graph, and leverage existing multi-agent system for draft generation.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**:
- Backend: FastAPI, SQLAlchemy, Neo4j Driver, httpx (API calls), pybtex (BibTeX)
- Frontend: Next.js 15, React 18, WebLLM, Cytoscape.js (graph viz), Zustand
**Storage**: PostgreSQL (citations, projects, drafts), Neo4j (citation graph), Qdrant (vectors)
**Testing**: pytest (backend), Vitest + Playwright (frontend)
**Target Platform**: Web (Chrome/Edge/Firefox with WebGPU for local models)
**Project Type**: Web application (backend + frontend)
**Performance Goals**:
- Retrieval: <2s latency
- Citation extraction: <5s per paper (ArXiv API)
- Graph rendering: <3s for 100 nodes
- Draft generation: <60s for 10 documents
**Constraints**:
- WebLLM requires WebGPU (Chrome 113+, Edge 113+)
- 4GB+ RAM for 1B models, 8GB+ for 3B+ models
- External API rate limits: CrossRef 50/s, Semantic Scholar 100/min
**Scale/Scope**:
- Target: 100+ papers per user collection
- Citation graph: Up to 2000 nodes (100 uploaded + references)
- Draft versions: Last 10 retained per project

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence/Justification |
|-----------|--------|------------------------|
| **I. Evaluation-First Development** | ✅ PASS | Success criteria defined with measurable thresholds (SC-001 to SC-015); acceptance scenarios written for all user stories |
| **II. Modular Component Architecture** | ✅ PASS | Feature designed as 4 independent phases; new services (citation extraction, bibliography formatting) are separate modules |
| **III. Multi-Agent Orchestration** | ✅ PASS | Phase 4 draft generation leverages existing 6-agent system; agent responsibilities remain specialized |
| **IV. Hybrid Search Integration** | ✅ PASS | RAG retrieval uses existing hybrid search (vector + graph + keyword); no changes to core search |
| **V. Enterprise Security and Compliance** | ✅ PASS | Projects are private to creator (FR-011); existing auth/RBAC enforced; no new security concerns |
| **VI. Performance and Scalability** | ✅ PASS | Performance targets defined (retrieval <2s, graph <3s); warm-start assumption documented |
| **VII. Observability and Monitoring** | ⚠️ PARTIAL | Must add: logging for citation extraction pipeline, metrics for draft generation latency |

**Gate Decision**: PASS with observability remediation required in implementation

## Project Structure

### Documentation (this feature)

```
specs/004-research-assistant-feature/
├── plan.md              # This file
├── spec.md              # Feature specification (complete)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI specs)
│   ├── citations-api.yaml
│   ├── projects-api.yaml
│   └── drafts-api.yaml
├── checklists/
│   └── requirements.md  # Spec validation checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```
backend/
├── src/
│   ├── api/
│   │   ├── citations.py          # NEW: Citation extraction & graph endpoints
│   │   ├── projects.py           # NEW: Research project CRUD + notes
│   │   └── drafts.py             # NEW: Draft generation endpoints
│   ├── models/
│   │   ├── citation.py           # MODIFY: Add metadata fields
│   │   ├── citation_relationship.py  # NEW: Citation graph edges
│   │   ├── research_project.py   # NEW: Project entity
│   │   ├── project_note.py       # NEW: Project notes
│   │   └── generated_draft.py    # NEW: Draft versions
│   └── services/
│       ├── citation_extraction_service.py  # NEW: Hybrid extraction
│       ├── bibliography_service.py         # NEW: Format exports
│       ├── citation_graph_service.py       # NEW: Neo4j graph ops
│       └── draft_generation_service.py     # NEW: Multi-agent drafts
└── tests/
    ├── unit/
    │   ├── test_citation_extraction.py
    │   ├── test_bibliography_service.py
    │   └── test_citation_graph.py
    └── integration/
        ├── test_citations_api.py
        ├── test_projects_api.py
        └── test_drafts_api.py

frontend/
├── src/
│   ├── components/
│   │   ├── citations/
│   │   │   ├── CitationGraph.tsx      # NEW: Cytoscape.js visualization
│   │   │   └── BibliographyExport.tsx # NEW: Export dialog
│   │   ├── research/
│   │   │   ├── ProjectList.tsx        # NEW: Project listing
│   │   │   ├── ProjectDetail.tsx      # NEW: Project view with tabs
│   │   │   ├── NoteEditor.tsx         # NEW: Markdown editor
│   │   │   └── DraftViewer.tsx        # NEW: Draft version comparison
│   │   └── chat/
│   │       └── [existing]             # MODIFY: Add RAG to WebLLM flow
│   ├── services/
│   │   ├── citationService.ts         # NEW: Citation API client
│   │   ├── projectService.ts          # NEW: Project API client
│   │   └── ragService.ts              # MODIFY: Add model-aware config
│   └── store/
│       ├── citationStore.ts           # NEW: Citation state
│       └── projectStore.ts            # NEW: Project state
├── app/
│   └── (dashboard)/
│       ├── chat/
│       │   └── page.tsx               # MODIFY: WebLLM RAG integration
│       └── research/
│           ├── page.tsx               # NEW: Projects listing
│           └── [id]/
│               └── page.tsx           # NEW: Project detail
└── tests/
    └── e2e/
        ├── chat-webllm-rag.spec.ts    # NEW: WebLLM RAG tests
        ├── citations.spec.ts          # NEW: Citation workflow tests
        └── research-projects.spec.ts  # NEW: Project workflow tests
```

**Structure Decision**: Web application pattern with backend API services and frontend React components. Follows existing project structure with new modules added to respective layers.

## Complexity Tracking

*No Constitution violations requiring justification.*

| Aspect | Complexity Level | Rationale |
|--------|------------------|-----------|
| Citation extraction | Medium | Multiple fallback strategies (ArXiv → CrossRef → PDF → manual) |
| Graph visualization | Low | Cytoscape.js is established library |
| Draft versioning | Low | Simple append-only version table |
| WebLLM RAG integration | High | Modifying core chat flow; model-aware context management |
