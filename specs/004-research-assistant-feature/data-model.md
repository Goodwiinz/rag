# Data Model: Research Assistant

**Feature**: Research Assistant
**Date**: 2026-01-14

## Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────────┐       ┌──────────────┐
│   User      │───────│ ResearchProject │───────│   Document   │
└─────────────┘  1:N  └─────────────────┘  N:M  └──────────────┘
                              │                        │
                              │ 1:N                    │ 1:N
                              ▼                        ▼
                      ┌───────────────┐        ┌─────────────┐
                      │  ProjectNote  │        │  Citation   │
                      └───────────────┘        └─────────────┘
                              │                        │
                              │                        │ N:M
                              ▼                        ▼
                      ┌───────────────┐        ┌─────────────────────┐
                      │GeneratedDraft │        │ CitationRelationship│
                      └───────────────┘        └─────────────────────┘
                              │
                              │ 1:N
                              ▼
                      ┌───────────────┐
                      │  DraftCitation│
                      └───────────────┘
```

## Entities

### 1. Citation (Modify Existing)

Extends existing `citations` table with scholarly metadata.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, DEFAULT uuid_generate_v4() | Unique identifier |
| message_id | UUID | FK → chat_messages(id), NULLABLE | Chat message containing citation |
| document_id | UUID | FK → documents(id), NULLABLE | Linked uploaded document |
| external_reference_id | VARCHAR(255) | NULLABLE | ArXiv ID or DOI |
| document_title | VARCHAR(500) | NOT NULL | Paper title |
| document_type | VARCHAR(100) | DEFAULT 'paper' | Type: paper, preprint, article |
| authors | TEXT[] | NULLABLE | Author list |
| year | INTEGER | NULLABLE | Publication year |
| venue | VARCHAR(255) | NULLABLE | Journal/conference name |
| doi | VARCHAR(100) | NULLABLE, UNIQUE | Digital Object Identifier |
| arxiv_id | VARCHAR(50) | NULLABLE, UNIQUE | ArXiv identifier |
| abstract | TEXT | NULLABLE | Paper abstract |
| snippet | TEXT | NULLABLE | Cited text snippet |
| page_number | INTEGER | NULLABLE | Page of citation |
| score | FLOAT | DEFAULT 0.0 | Relevance score |
| metadata_source | VARCHAR(50) | DEFAULT 'manual' | arxiv, crossref, semantic_scholar, manual |
| needs_review | BOOLEAN | DEFAULT FALSE | Incomplete metadata flag |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last update |

**Indexes**:
- `idx_citations_arxiv_id` ON arxiv_id
- `idx_citations_doi` ON doi
- `idx_citations_document_id` ON document_id

**Validation Rules**:
- Either `message_id` or `document_id` must be set
- `year` must be between 1900 and current year + 1
- `arxiv_id` format: `YYMM.NNNNN` or `category/YYMMNNN`

---

### 2. CitationRelationship (New)

Represents citation links between papers.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, DEFAULT uuid_generate_v4() | Unique identifier |
| source_citation_id | UUID | FK → citations(id), NOT NULL | Citing paper |
| target_citation_id | UUID | FK → citations(id), NOT NULL | Cited paper |
| relationship_type | VARCHAR(50) | DEFAULT 'cites' | cites, extends, contradicts, supports |
| citation_context | TEXT | NULLABLE | Text surrounding citation |
| confidence | FLOAT | DEFAULT 1.0 | Extraction confidence (0-1) |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

**Constraints**:
- UNIQUE(source_citation_id, target_citation_id)
- CHECK(source_citation_id != target_citation_id)

**Indexes**:
- `idx_citation_rel_source` ON source_citation_id
- `idx_citation_rel_target` ON target_citation_id

---

### 3. ResearchProject (Extend Collections)

Extends existing `collections` table for research project features.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK (existing) | Collection ID |
| user_id | UUID | FK → users(id) (existing) | Owner |
| name | VARCHAR(255) | NOT NULL (existing) | Project name |
| description | TEXT | NULLABLE (existing) | Project description |
| project_type | VARCHAR(50) | DEFAULT 'research' | research, literature_review, thesis, paper |
| research_status | VARCHAR(50) | DEFAULT 'active' | active, paused, completed, archived |
| research_goals | TEXT | NULLABLE | Research objectives |
| deadline | TIMESTAMP | NULLABLE | Target completion date |
| tags | TEXT[] | DEFAULT '{}' | Organizational tags |
| is_private | BOOLEAN | DEFAULT TRUE | Visibility (always TRUE until Phase 5) |
| created_at | TIMESTAMP | DEFAULT NOW() (existing) | Creation timestamp |
| updated_at | TIMESTAMP | DEFAULT NOW() (existing) | Last update |

**State Transitions**:
```
active → paused → active (toggle)
active → completed (mark done)
completed → archived (cleanup)
archived → active (reopen)
```

**Validation Rules**:
- `project_type` IN ('research', 'literature_review', 'thesis', 'paper')
- `research_status` IN ('active', 'paused', 'completed', 'archived')
- `is_private` must be TRUE (enforced at application level until Phase 5)

---

### 4. ProjectNote (New)

User notes associated with research projects.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, DEFAULT uuid_generate_v4() | Unique identifier |
| project_id | UUID | FK → collections(id), ON DELETE CASCADE | Parent project |
| user_id | UUID | FK → users(id), NOT NULL | Note author |
| title | VARCHAR(255) | NOT NULL | Note title |
| content | TEXT | NOT NULL | Markdown content |
| linked_document_ids | UUID[] | DEFAULT '{}' | Referenced documents |
| tags | TEXT[] | DEFAULT '{}' | Note tags |
| is_pinned | BOOLEAN | DEFAULT FALSE | Pinned to top |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last update |

**Indexes**:
- `idx_project_notes_project` ON project_id
- `idx_project_notes_user` ON user_id

**Validation Rules**:
- `content` max length: 100,000 characters
- `title` max length: 255 characters
- `linked_document_ids` must reference existing documents in same project

---

### 5. GeneratedDraft (New)

Versioned AI-generated literature review drafts.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, DEFAULT uuid_generate_v4() | Unique identifier |
| project_id | UUID | FK → collections(id), ON DELETE CASCADE | Parent project |
| version | INTEGER | NOT NULL | Version number (1, 2, 3...) |
| title | VARCHAR(255) | NOT NULL | Draft title |
| content | TEXT | NOT NULL | Markdown content with [Doc N] citations |
| themes | TEXT[] | DEFAULT '{}' | Specified themes for generation |
| word_count | INTEGER | NULLABLE | Content word count |
| citation_count | INTEGER | NULLABLE | Number of citations in draft |
| generation_params | JSONB | DEFAULT '{}' | Model, temperature, etc. |
| generation_time_ms | INTEGER | NULLABLE | Time to generate |
| is_current | BOOLEAN | DEFAULT TRUE | Most recent version flag |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

**Constraints**:
- UNIQUE(project_id, version)
- Only one draft per project can have `is_current = TRUE`

**Indexes**:
- `idx_drafts_project_version` ON (project_id, version DESC)
- `idx_drafts_current` ON project_id WHERE is_current = TRUE

**Version Retention Policy**:
- Keep last 10 versions per project
- Trigger auto-archives older versions (sets is_current = FALSE, keeps data)

---

### 6. DraftCitation (New)

Links between generated drafts and cited documents.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, DEFAULT uuid_generate_v4() | Unique identifier |
| draft_id | UUID | FK → generated_drafts(id), ON DELETE CASCADE | Parent draft |
| citation_index | INTEGER | NOT NULL | Citation number [Doc N] |
| document_id | UUID | FK → documents(id), NULLABLE | Cited document |
| citation_id | UUID | FK → citations(id), NULLABLE | Linked citation record |
| snippet | TEXT | NULLABLE | Relevant passage from document |
| context | TEXT | NULLABLE | How citation is used in draft |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

**Constraints**:
- UNIQUE(draft_id, citation_index)
- Either `document_id` or `citation_id` must be set

**Indexes**:
- `idx_draft_citations_draft` ON draft_id

---

### 7. MessageCitation (Modify Existing)

Association between chat messages and citations (existing, enhanced).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK (existing) | Unique identifier |
| message_id | UUID | FK → chat_messages(id) (existing) | Chat message |
| citation_id | UUID | FK → citations(id) (NEW) | Linked citation |
| document_id | UUID | FK → documents(id) (existing) | Cited document |
| citation_index | INTEGER | NOT NULL | [Doc N] index in message |
| snippet | TEXT | NULLABLE | Cited text |
| score | FLOAT | NULLABLE | Relevance score |
| created_at | TIMESTAMP | DEFAULT NOW() | Creation timestamp |

---

## Neo4j Graph Schema

For citation network visualization and analysis.

### Nodes

```cypher
// Citation node (paper in citation network)
(:Citation {
    id: UUID,
    title: String,
    authors: [String],
    year: Integer,
    arxiv_id: String?,
    doi: String?,
    venue: String?,
    citation_count: Integer,
    influence_score: Float
})

// Document node (uploaded paper)
(:Document {
    id: UUID,
    title: String,
    file_type: String
})

// Project node (research project)
(:Project {
    id: UUID,
    name: String,
    status: String
})
```

### Relationships

```cypher
// Citation relationships
(:Citation)-[:CITES {
    context: String?,
    confidence: Float
}]->(:Citation)

// Document contains citations
(:Document)-[:HAS_CITATION {
    page_number: Integer?,
    position: Integer?
}]->(:Citation)

// Project includes documents
(:Project)-[:INCLUDES]->(:Document)

// Citation references external paper
(:Citation)-[:REFERENCES_EXTERNAL {
    source: String  // arxiv, crossref, semantic_scholar
}]->(:Citation)
```

### Indexes & Constraints

```cypher
CREATE CONSTRAINT citation_id IF NOT EXISTS
FOR (c:Citation) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT citation_arxiv IF NOT EXISTS
FOR (c:Citation) REQUIRE c.arxiv_id IS UNIQUE;

CREATE INDEX citation_year IF NOT EXISTS
FOR (c:Citation) ON (c.year);

CREATE INDEX citation_venue IF NOT EXISTS
FOR (c:Citation) ON (c.venue);
```

---

## Database Migration Plan

### Migration 1: Extend Citations Table
```sql
-- Add scholarly metadata fields to existing citations table
ALTER TABLE citations
ADD COLUMN IF NOT EXISTS authors TEXT[],
ADD COLUMN IF NOT EXISTS year INTEGER,
ADD COLUMN IF NOT EXISTS venue VARCHAR(255),
ADD COLUMN IF NOT EXISTS doi VARCHAR(100),
ADD COLUMN IF NOT EXISTS arxiv_id VARCHAR(50),
ADD COLUMN IF NOT EXISTS abstract TEXT,
ADD COLUMN IF NOT EXISTS metadata_source VARCHAR(50) DEFAULT 'manual',
ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT FALSE;

-- Add unique constraints
ALTER TABLE citations
ADD CONSTRAINT citations_doi_unique UNIQUE (doi),
ADD CONSTRAINT citations_arxiv_unique UNIQUE (arxiv_id);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_citations_arxiv_id ON citations(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_citations_doi ON citations(doi);
```

### Migration 2: Create Citation Relationships
```sql
CREATE TABLE IF NOT EXISTS citation_relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_citation_id UUID NOT NULL REFERENCES citations(id) ON DELETE CASCADE,
    target_citation_id UUID NOT NULL REFERENCES citations(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) DEFAULT 'cites',
    citation_context TEXT,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT citation_rel_unique UNIQUE (source_citation_id, target_citation_id),
    CONSTRAINT citation_rel_no_self CHECK (source_citation_id != target_citation_id)
);

CREATE INDEX idx_citation_rel_source ON citation_relationships(source_citation_id);
CREATE INDEX idx_citation_rel_target ON citation_relationships(target_citation_id);
```

### Migration 3: Extend Collections for Research Projects
```sql
ALTER TABLE collections
ADD COLUMN IF NOT EXISTS project_type VARCHAR(50) DEFAULT 'research',
ADD COLUMN IF NOT EXISTS research_status VARCHAR(50) DEFAULT 'active',
ADD COLUMN IF NOT EXISTS research_goals TEXT,
ADD COLUMN IF NOT EXISTS deadline TIMESTAMP,
ADD COLUMN IF NOT EXISTS tags TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT TRUE;
```

### Migration 4: Create Project Notes
```sql
CREATE TABLE IF NOT EXISTS project_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    linked_document_ids UUID[] DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    is_pinned BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_project_notes_project ON project_notes(project_id);
CREATE INDEX idx_project_notes_user ON project_notes(user_id);
```

### Migration 5: Create Generated Drafts
```sql
CREATE TABLE IF NOT EXISTS generated_drafts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    themes TEXT[] DEFAULT '{}',
    word_count INTEGER,
    citation_count INTEGER,
    generation_params JSONB DEFAULT '{}',
    generation_time_ms INTEGER,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT drafts_version_unique UNIQUE (project_id, version)
);

CREATE INDEX idx_drafts_project_version ON generated_drafts(project_id, version DESC);
CREATE INDEX idx_drafts_current ON generated_drafts(project_id) WHERE is_current = TRUE;

-- Create draft citations table
CREATE TABLE IF NOT EXISTS draft_citations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    draft_id UUID NOT NULL REFERENCES generated_drafts(id) ON DELETE CASCADE,
    citation_index INTEGER NOT NULL,
    document_id UUID REFERENCES documents(id),
    citation_id UUID REFERENCES citations(id),
    snippet TEXT,
    context TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT draft_citation_unique UNIQUE (draft_id, citation_index)
);

CREATE INDEX idx_draft_citations_draft ON draft_citations(draft_id);
```

### Migration 6: Version Retention Trigger
```sql
-- Trigger to maintain max 10 versions per project
CREATE OR REPLACE FUNCTION maintain_draft_versions()
RETURNS TRIGGER AS $$
BEGIN
    -- Mark all other versions as not current
    UPDATE generated_drafts
    SET is_current = FALSE
    WHERE project_id = NEW.project_id AND id != NEW.id;

    -- Delete versions beyond 10 (keep data for archival, just remove from active)
    WITH ranked AS (
        SELECT id, ROW_NUMBER() OVER (
            PARTITION BY project_id
            ORDER BY version DESC
        ) as rn
        FROM generated_drafts
        WHERE project_id = NEW.project_id
    )
    DELETE FROM generated_drafts
    WHERE id IN (SELECT id FROM ranked WHERE rn > 10);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER draft_version_cleanup
AFTER INSERT ON generated_drafts
FOR EACH ROW
EXECUTE FUNCTION maintain_draft_versions();
```
