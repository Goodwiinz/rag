# Feature Specification: Research Assistant

**Feature Branch**: `004-research-assistant-feature`
**Created**: 2026-01-14
**Status**: Draft
**Input**: Transform the RAG system into a comprehensive research assistant that helps researchers draft papers based on uploaded documents, manage citations, and integrate research tools - supporting both local (WebLLM) and cloud execution.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask Questions About Papers Using Local AI (Priority: P1)

As a researcher with privacy concerns or limited internet access, I want to ask questions about my uploaded research papers using local AI models (running in my browser), so that I can get answers with proper citations without sending my data to external servers.

**Why this priority**: This is the critical foundation - local models currently bypass RAG entirely, making them unable to answer questions about uploaded documents. Fixing this unblocks all other research workflows for privacy-conscious users.

**Independent Test**: Can be fully tested by uploading a single paper, selecting a local model (e.g., Llama-3.2-1B), and asking a question about the paper's content. Success is receiving an answer that references the paper with a clickable citation.

**Acceptance Scenarios**:

1. **Given** I have uploaded a research paper and selected a local model (Llama, Phi, Gemma, or Qwen), **When** I ask "What are the key findings in this paper?", **Then** I receive an answer that includes at least one citation in `[Doc N]` format
2. **Given** I have RAG enabled and am using a local model, **When** I submit a question, **Then** the system retrieves relevant document sections before generating a response
3. **Given** I receive a response with citations, **When** I click on a citation link, **Then** I see a preview of the source document section
4. **Given** a conversation has occurred with citations, **When** I refresh the page, **Then** the citations are still visible and clickable (persisted to database)

---

### User Story 2 - Generate Bibliography from Research Collection (Priority: P2)

As a researcher writing a paper, I want to automatically generate a properly formatted bibliography from my uploaded papers, so that I can include accurate references without manually typing each citation.

**Why this priority**: Bibliography generation is a fundamental research task that's time-consuming when done manually. This feature provides immediate value once citation extraction is working.

**Independent Test**: Can be tested by uploading 3-5 ArXiv papers, clicking "Generate Bibliography", and downloading a .bib file. Success is a valid BibTeX file that can be used with LaTeX.

**Acceptance Scenarios**:

1. **Given** I have 5 research papers uploaded, **When** I request a bibliography export in BibTeX format, **Then** I receive a .bib file containing entries for all papers with authors, title, year, and venue
2. **Given** I have papers from ArXiv, **When** citations are extracted, **Then** metadata includes ArXiv ID and DOI where available
3. **Given** I want IEEE format, **When** I select IEEE and export, **Then** I receive a text file with citations in IEEE reference style
4. **Given** some papers have incomplete metadata, **When** I export bibliography, **Then** the system indicates which citations need manual review

---

### User Story 3 - Visualize Citation Network (Priority: P2)

As a researcher exploring a topic, I want to see how papers cite each other in an interactive graph, so that I can identify seminal papers and understand the evolution of ideas in my field.

**Why this priority**: Citation graphs help researchers discover important papers they might have missed and understand research lineage. This builds on the citation extraction foundation.

**Independent Test**: Can be tested by uploading a paper with references, clicking "Show Citation Graph", and seeing an interactive network visualization. Success is viewing connected nodes representing papers.

**Acceptance Scenarios**:

1. **Given** I have uploaded a paper with 10+ references, **When** I click "Extract Citations", **Then** I see a graph showing my paper connected to its references
2. **Given** I am viewing a citation graph, **When** I click on a node, **Then** I see the paper's title, authors, year, and option to add to my collection
3. **Given** multiple papers are in my collection, **When** I view the combined graph, **Then** I see how papers are interconnected through shared references

---

### User Story 4 - Organize Documents into Research Projects (Priority: P3)

As a researcher working on multiple topics, I want to organize my papers into named projects with notes and tags, so that I can keep related work together and track my progress.

**Why this priority**: Organization improves research workflow but isn't critical for basic functionality. Users can work without it but benefit significantly from structured organization.

**Independent Test**: Can be tested by creating a new project, adding 3 papers, writing a note, and verifying all content appears together on the project page.

**Acceptance Scenarios**:

1. **Given** I am on the research page, **When** I click "Create Project" and enter a name like "Machine Learning in Healthcare", **Then** an empty project is created that I can add documents to
2. **Given** I have a project, **When** I drag a document into it, **Then** the document appears in the project's document list
3. **Given** I have documents in a project, **When** I click "Project Bibliography", **Then** I see citations for all documents in that project
4. **Given** I am viewing a project, **When** I add a note with markdown formatting, **Then** the note is saved and displays with proper formatting

---

### User Story 5 - Generate Literature Review Draft (Priority: P3)

As a researcher starting to write, I want AI to generate a draft literature review based on my uploaded papers, so that I have a starting point that synthesizes key findings with proper citations.

**Why this priority**: Draft generation is the ultimate value proposition but requires citation management and project organization to work well. It's the "wow" feature that depends on earlier foundations.

**Independent Test**: Can be tested by adding 5+ papers to a project, clicking "Generate Literature Review", and receiving a multi-paragraph document with citations. Success is a readable draft with at least 3 citations.

**Acceptance Scenarios**:

1. **Given** I have 5 papers in a research project, **When** I click "Generate Literature Review", **Then** I receive a 3-5 paragraph summary with citations to my papers in `[Doc N]` format
2. **Given** I specify themes like "methodology" and "findings", **When** the review is generated, **Then** content is organized around those themes
3. **Given** a draft is generated, **When** I click "Export to LaTeX", **Then** I receive a .tex file with a .bib file for references

---

### Edge Cases

- What happens when a paper has no extractable references? System indicates "No references found" and allows manual entry
- How does system handle papers in non-English languages? System processes text but may have reduced accuracy; warns user of potential issues
- What happens when local model context is exceeded? System truncates older context while preserving most recent documents and conversation
- How does system handle duplicate papers uploaded? System detects by title/DOI and prompts user to merge or keep separate
- What happens if citation extraction fails for a PDF? System shows partial results with option to manually correct entries
- What happens during bulk upload (50+ papers)? System queues extraction requests to respect external API rate limits; shows progress indicator

## Requirements *(mandatory)*

### Functional Requirements

**Local AI RAG Integration (Phase 1)**

- **FR-001**: System MUST retrieve relevant document sections when users ask questions, regardless of whether they use local or cloud AI models
- **FR-002**: System MUST include inline citations in `[Doc N]` format in AI responses when RAG is enabled
- **FR-003**: System MUST persist citations to the database so they remain accessible across sessions
- **FR-004**: System MUST provide clickable citation links that display the source document section
- **FR-005**: System MUST adapt document retrieval based on model size (fewer documents for smaller models to fit context limits)
- **FR-006**: System MUST allow users to toggle RAG on/off for any conversation

**Citation Management (Phase 2)**

- **FR-007**: System MUST extract citation metadata (title, authors, year, venue, DOI, ArXiv ID) from uploaded research papers using a hybrid strategy: (1) ArXiv API for ArXiv papers, (2) CrossRef/Semantic Scholar lookup for papers with DOI/title, (3) PDF text parsing as fallback, (4) manual entry when automated extraction fails
- **FR-008**: System MUST display citation relationships as an interactive graph visualization
- **FR-009**: System MUST export citations in BibTeX, IEEE, APA, and MLA formats
- **FR-010**: System MUST store citation relationships showing which papers cite which other papers

**Research Project Organization (Phase 3)**

- **FR-011**: System MUST allow users to create named research projects with optional description, tags, and deadline; projects are private to the creator (no sharing until Phase 5)
- **FR-012**: System MUST allow users to add and remove documents from projects
- **FR-013**: System MUST allow users to write and save notes associated with projects in markdown format
- **FR-014**: System MUST auto-generate project bibliography from all documents in the project

**Research Assistant Features (Phase 4)**

- **FR-015**: System MUST generate literature review drafts based on documents in a research project; each generation creates a new version that is saved and can be compared with previous versions
- **FR-016**: System MUST allow users to specify themes or sections for generated content
- **FR-017**: Generated drafts MUST include citations to source documents
- **FR-018**: System MUST export generated content to LaTeX format with accompanying bibliography file

### Key Entities

- **Document**: Research paper uploaded by user (PDF, text); contains title, authors, abstract, full text, metadata
- **Citation**: Reference to a source document; contains title, authors, year, venue, DOI, ArXiv ID; links to document if available
- **Citation Relationship**: Connection between two citations indicating one cites the other
- **Research Project**: Collection of related documents organized by user; contains name, description, tags, deadline, status; private to creator
- **Project Note**: User-written note associated with a project; supports markdown formatting
- **Generated Draft**: AI-created content based on project documents; links to source citations; versioned (each generation creates new version with timestamp, user can compare versions; last 10 versions retained)
- **Message Citation**: Association between an AI response and the documents cited within it

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Local AI RAG (Phase 1)**

- **SC-001**: 100% of local models (Llama, Phi, Gemma, Qwen families) retrieve document context when RAG is enabled
- **SC-002**: 80% or more of AI responses include properly formatted citations for 3B+ parameter models
- **SC-003**: 50% or more of AI responses include properly formatted citations for 1B parameter models
- **SC-004**: Document retrieval completes within 2 seconds; generation time depends on model size (1B: ~10-20s, 3B: ~20-40s, 7B: ~40-60s for typical responses; assumes model already loaded)
- **SC-005**: Citation links work correctly and display source content 99% of the time

**Citation Management (Phase 2)**

- **SC-006**: Citation metadata is correctly extracted for 90% or more of ArXiv papers
- **SC-007**: Citation graph displays 100+ uploaded papers with relationships without performance issues (may include up to 2000 referenced nodes)
- **SC-008**: Bibliography exports are valid and error-free for 95% or more of citations
- **SC-009**: Users can export bibliography in any supported format within 3 seconds

**Research Projects (Phase 3)**

- **SC-010**: Users can create a project and add documents in under 30 seconds
- **SC-011**: Project notes save and display correctly 100% of the time
- **SC-012**: Project bibliography generates correctly for collections of 50+ documents

**Research Assistant (Phase 4)**

- **SC-013**: Literature review drafts are generated within 60 seconds for projects with 10 documents
- **SC-014**: 70% or more of citations in generated drafts are relevant to the claims they support
- **SC-015**: Researchers can go from uploading papers to having a draft literature review in under 5 minutes (excluding model load time)

## Scope & Boundaries

### In Scope (Phases 1-4)

- Local AI models with RAG retrieval and citations
- Citation extraction from research papers (primarily ArXiv)
- Citation graph visualization
- Bibliography export (BibTeX, IEEE, APA, MLA)
- Research project creation and document organization
- Project notes in markdown
- AI-generated literature review drafts
- LaTeX export with bibliography

### Out of Scope (Phase 5 - Future)

- Real-time collaborative editing between multiple users
- DOCX export format
- PDF export via LaTeX compilation
- Public sharing links for projects
- Annotation/highlighting in PDF viewer
- Fully offline operation (local models still use server-side retrieval)

## Dependencies

### Existing Capabilities Required

- Document upload and processing pipeline (exists)
- WebLLM integration for local AI (exists)
- Cloud AI integration (exists)
- PostgreSQL for data persistence (exists)
- Neo4j for knowledge graph storage (exists)
- Multi-agent orchestration system for draft generation (exists)

### New Capabilities Needed

- Citation extraction service (to be built)
- Bibliography formatting service (to be built)
- Citation graph visualization component (to be built)
- Research projects UI (to be built)

## Clarifications

### Session 2026-01-14

- Q: Are research projects private per-user or visible to others before Phase 5? → A: Strictly private - projects visible only to the creator, no sharing until Phase 5
- Q: What extraction strategy for non-ArXiv papers? → A: Hybrid - Try metadata lookup first (CrossRef/Semantic Scholar), fall back to PDF parsing, then manual entry
- Q: What happens to AI-generated literature review drafts? → A: Versioned - Each generation creates a new version; user can compare and select preferred
- Q: Is local AI fully offline or uses server retrieval? → A: Local inference + server-side retrieval is acceptable; fully offline deferred to future phase
- Q: What are realistic performance targets for local models? → A: Retrieval within 2 seconds; generation time varies by model size (10-60s); assumes warm start

## Testing Requirements *(mandatory per Constitution Principle I)*

### Unit Tests

**Backend Services (pytest, >80% coverage target)**

- **Citation Extraction Service**
  - `test_extract_arxiv_citation_success` - Extract metadata from valid ArXiv ID
  - `test_extract_arxiv_citation_invalid_id` - Handle malformed ArXiv ID gracefully
  - `test_extract_crossref_citation_success` - Extract metadata from DOI
  - `test_extract_hybrid_fallback_chain` - Verify fallback from ArXiv → CrossRef → PDF → manual
  - `test_extraction_rate_limiting` - Respect API rate limits (ArXiv 3/s, CrossRef 50/s)
  - `test_extraction_caching` - Cache results to avoid duplicate API calls

- **Bibliography Service**
  - `test_format_bibtex_single_citation` - Generate valid BibTeX entry
  - `test_format_bibtex_multiple_citations` - Generate multi-entry .bib file
  - `test_format_ieee_citation` - Generate IEEE reference format
  - `test_format_apa_citation` - Generate APA reference format
  - `test_format_mla_citation` - Generate MLA reference format
  - `test_format_incomplete_metadata` - Handle missing fields gracefully with "needs review" flag

- **Citation Graph Service**
  - `test_sync_citation_to_neo4j` - Create :Citation node in Neo4j
  - `test_create_cites_relationship` - Create :CITES edge between citations
  - `test_get_citation_graph_depth_1` - Retrieve direct citations
  - `test_get_citation_graph_depth_2` - Retrieve citations of citations
  - `test_influence_score_calculation` - Compute PageRank-based influence
  - `test_graph_performance_100_nodes` - <3s for 100 nodes with relationships

- **Project Service**
  - `test_create_project_success` - Create project with name, description
  - `test_create_project_is_private` - Verify is_private always TRUE
  - `test_add_document_to_project` - Associate document with project
  - `test_remove_document_from_project` - Disassociate document
  - `test_project_ownership_validation` - Deny access to non-owner
  - `test_project_bibliography_generation` - Generate bibliography from all project docs

- **Draft Generation Service**
  - `test_generate_draft_with_themes` - Generate draft organized by themes
  - `test_generate_draft_includes_citations` - Verify [Doc N] format in output
  - `test_draft_versioning` - New generation creates new version
  - `test_draft_version_retention` - Keep last 10, archive older
  - `test_draft_generation_timeout` - Timeout after 120s with proper error
  - `test_draft_export_latex` - Export to .tex + .bib format
  - `test_draft_export_markdown` - Export to markdown format

- **Message Citation Service**
  - `test_parse_doc_citations_from_response` - Extract [Doc 1], [Doc 2] from text
  - `test_persist_citation_to_database` - Save citation with message linkage
  - `test_citation_preview_snippet` - Return source document snippet
  - `test_citation_persistence_across_sessions` - Load citations on page refresh

**Frontend Components (Vitest, React Testing Library)**

- **CitationPreview Component**
  - `test_renders_clickable_citation_link` - [Doc N] displays as link
  - `test_shows_popover_on_click` - Clicking shows source snippet
  - `test_handles_missing_citation` - Graceful error for invalid citation ID

- **CitationGraph Component**
  - `test_renders_cytoscape_graph` - Initialize Cytoscape with data
  - `test_node_click_shows_details` - Click node displays paper metadata
  - `test_graph_zoom_pan` - Viewport controls work
  - `test_graph_clustering_large_dataset` - Cluster nodes when >1000

- **BibliographyExport Component**
  - `test_format_dropdown_options` - Shows BibTeX, IEEE, APA, MLA
  - `test_download_bibtex_file` - Triggers .bib download
  - `test_shows_needs_review_warnings` - Display incomplete citation warnings

- **ProjectList Component**
  - `test_renders_project_cards` - Display project grid
  - `test_filter_by_status` - Filter active/paused/completed
  - `test_search_projects` - Search by name

- **NoteEditor Component**
  - `test_markdown_preview` - Toggle preview mode
  - `test_save_note` - Call API on save
  - `test_link_documents` - Associate documents with note

- **DraftViewer Component**
  - `test_renders_markdown_content` - Display draft with formatting
  - `test_version_selector` - Switch between draft versions
  - `test_citation_links_clickable` - [Doc N] links work

- **DraftGenerator Component**
  - `test_theme_input` - Add/remove themes
  - `test_generate_button_calls_api` - Trigger generation
  - `test_progress_display` - Show generation progress

### Integration Tests

**API Integration (pytest with test database)**

- **Citations API**
  - `test_citations_crud_flow` - Create, read, update, delete citation
  - `test_citations_extract_arxiv_paper` - Full extraction from ArXiv
  - `test_citations_export_bibtex` - End-to-end export flow
  - `test_citations_graph_endpoint` - Get graph data with positions

- **Projects API**
  - `test_projects_crud_flow` - Create, read, update, delete project
  - `test_projects_add_remove_documents` - Document management
  - `test_projects_notes_crud` - Note creation and editing
  - `test_projects_bibliography` - Project-level bibliography

- **Drafts API**
  - `test_drafts_generation_async` - 202 Accepted response
  - `test_drafts_status_polling` - Status endpoint during generation
  - `test_drafts_versioning` - Multiple versions created
  - `test_drafts_export` - LaTeX/Markdown export

**Database Integration**

- `test_citation_cascade_delete` - Deleting document cascades to citations
- `test_project_cascade_delete` - Deleting project cascades to notes, drafts
- `test_neo4j_sync_on_citation_create` - Citation node synced to Neo4j

### End-to-End Tests (Playwright)

**User Story 1: Local AI RAG**

- `test_e2e_upload_pdf_ask_question_local_model` - Upload paper → select Llama-3.2-1B → ask question → receive answer with [Doc N] citation
- `test_e2e_citation_click_shows_preview` - Click [Doc N] → popover shows source text
- `test_e2e_citations_persist_on_refresh` - Refresh page → citations still visible

**User Story 2: Bibliography Export**

- `test_e2e_extract_citations_from_arxiv` - Upload ArXiv paper → Extract Citations → see metadata
- `test_e2e_export_bibtex` - Select papers → Export BibTeX → download valid .bib
- `test_e2e_export_ieee` - Select papers → Export IEEE → download formatted text

**User Story 3: Citation Graph**

- `test_e2e_view_citation_graph` - Upload paper → Extract Citations → Show Graph → see network
- `test_e2e_graph_node_interaction` - Click node → see details panel
- `test_e2e_graph_add_external_to_collection` - Click external node → Add to Collection

**User Story 4: Research Projects**

- `test_e2e_create_project` - Create Project "ML Healthcare" → see empty project
- `test_e2e_add_documents_to_project` - Drag documents → see in project list
- `test_e2e_write_project_note` - Add Note → write markdown → see formatted

**User Story 5: Draft Generation**

- `test_e2e_generate_literature_review` - 5 papers in project → Generate → see draft with citations
- `test_e2e_compare_draft_versions` - Generate twice → compare versions
- `test_e2e_export_draft_latex` - Export LaTeX → download .tex + .bib ZIP

### Performance Tests

- `test_perf_retrieval_latency_under_2s` - RAG retrieval <2000ms (p95)
- `test_perf_citation_extraction_under_5s` - Single paper extraction <5000ms
- `test_perf_graph_render_100_nodes_under_3s` - Graph with 100 nodes <3000ms
- `test_perf_draft_generation_10_docs_under_60s` - Draft from 10 papers <60000ms
- `test_perf_bibliography_export_50_citations_under_3s` - 50 citation export <3000ms

### Security Tests

- `test_security_project_access_denied_non_owner` - Non-owner cannot access project
- `test_security_draft_access_denied_non_owner` - Non-owner cannot access draft
- `test_security_note_access_denied_non_owner` - Non-owner cannot access notes
- `test_security_citation_injection_prevention` - No SQL injection via citation fields
- `test_security_xss_prevention_note_content` - Markdown sanitized for XSS

## Assumptions

- ArXiv papers will be the primary source with highest extraction accuracy (~90%); non-ArXiv papers use hybrid lookup (CrossRef/Semantic Scholar → PDF parsing → manual) with lower expected accuracy (~70%)
- Users accept that smaller local models (1B parameters) will have lower citation compliance than larger models
- Users have sufficient browser resources to run WebLLM models locally (WebGPU-capable browser, 4GB+ RAM for 1B models, 8GB+ for 3B+ models)
- Research papers are primarily in English; non-English papers will have best-effort support
- Citation extraction accuracy is acceptable at 90% for ArXiv papers; manual correction handles remaining cases
- Local AI means local inference with server-side retrieval; fully offline mode is out of scope
- WebLLM model load time (30-60s on first use) is excluded from performance targets; generation times assume warm start
- Draft versions are retained up to last 10 per project; older versions auto-archived
- External APIs (CrossRef, Semantic Scholar) have rate limits; bulk operations are queued accordingly
