# Feature Specification: Research Assistant

**Feature Branch**: `004-users-goodwiinz-claude`
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
- **Research Project**: Collection of related documents organized by user; contains name, description, tags, deadline, status
- **Project Note**: User-written note associated with a project; supports markdown formatting
- **Generated Draft**: AI-created content based on project documents; links to source citations; versioned (each generation creates new version with timestamp, user can compare versions)
- **Message Citation**: Association between an AI response and the documents cited within it

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Local AI RAG (Phase 1)**

- **SC-001**: 100% of local models (Llama, Phi, Gemma, Qwen families) retrieve document context when RAG is enabled
- **SC-002**: 80% or more of AI responses include properly formatted citations for 3B+ parameter models
- **SC-003**: 50% or more of AI responses include properly formatted citations for 1B parameter models
- **SC-004**: Users receive document-grounded responses within 5 seconds (retrieval + generation)
- **SC-005**: Citation links work correctly and display source content 99% of the time

**Citation Management (Phase 2)**

- **SC-006**: Citation metadata is correctly extracted for 90% or more of ArXiv papers
- **SC-007**: Citation graph displays 100+ papers with relationships without performance issues
- **SC-008**: Bibliography exports are valid and error-free for 95% or more of citations
- **SC-009**: Users can export bibliography in any supported format within 3 seconds

**Research Projects (Phase 3)**

- **SC-010**: Users can create a project and add documents in under 30 seconds
- **SC-011**: Project notes save and display correctly 100% of the time
- **SC-012**: Project bibliography generates correctly for collections of 50+ documents

**Research Assistant (Phase 4)**

- **SC-013**: Literature review drafts are generated within 60 seconds for projects with 10 documents
- **SC-014**: 70% or more of citations in generated drafts are relevant to the claims they support
- **SC-015**: Researchers can go from uploading papers to having a draft literature review in under 5 minutes

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

## Assumptions

- ArXiv papers will be the primary source with highest extraction accuracy (~90%); non-ArXiv papers use hybrid lookup (CrossRef/Semantic Scholar → PDF parsing → manual) with lower expected accuracy (~70%)
- Users accept that smaller local models (1B parameters) will have lower citation compliance than larger models
- Users have sufficient browser resources to run WebLLM models locally (modern browser, adequate RAM)
- Research papers are primarily in English; non-English papers will have best-effort support
- Citation extraction accuracy is acceptable at 90% for ArXiv papers; manual correction handles remaining cases
