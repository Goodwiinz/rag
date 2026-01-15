"""
Research Assistant schemas for citation management, citation graphs, research projects, and literature review generation.

This module contains Pydantic schemas for the Research Assistant feature (User Stories 1-5).
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


# ============================================================================
# Enums
# ============================================================================

class ProjectType(str, Enum):
    """Research project types"""
    RESEARCH = "research"
    LITERATURE_REVIEW = "literature_review"
    THESIS = "thesis"
    PAPER = "paper"


class ResearchStatus(str, Enum):
    """Research project status"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CitationRelationshipType(str, Enum):
    """Citation relationship types for graph edges"""
    CITES = "cites"
    CITED_BY = "cited_by"
    RELATED_TO = "related_to"


class MetadataSource(str, Enum):
    """Sources for citation metadata extraction"""
    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CROSSREF = "crossref"
    MANUAL = "manual"


# ============================================================================
# T019: Citation Schemas (User Story 2)
# ============================================================================

class CitationAuthor(BaseModel):
    """Author information for citations"""
    name: str = Field(..., description="Author's full name")
    affiliation: Optional[str] = Field(None, description="Author's institution/affiliation")


class CitationWithMetadata(BaseModel):
    """Enhanced citation with scholarly metadata"""
    id: UUID
    message_id: UUID
    document_id: Optional[UUID] = None
    external_reference_id: Optional[str] = None
    document_title: Optional[str] = None
    document_type: Optional[str] = None

    # Chunk information
    chunk_index: Optional[int] = None
    chunk_id: Optional[str] = None
    snippet: Optional[str] = None
    page_number: Optional[int] = None

    # Relevance scores
    score: Optional[float] = None
    rerank_score: Optional[float] = None

    # Scholarly metadata
    authors: Optional[List[Dict[str, Any]]] = Field(default=None, description="List of authors")
    year: Optional[int] = Field(None, ge=1900, le=2100, description="Publication year")
    venue: Optional[str] = Field(None, description="Journal or conference name")
    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    arxiv_id: Optional[str] = Field(None, description="arXiv identifier (e.g., 2512.14313v1)")
    abstract: Optional[str] = Field(None, description="Paper abstract")
    metadata_source: Optional[MetadataSource] = Field(None, description="Source of metadata")
    needs_review: bool = Field(default=False, description="Flag for incomplete metadata")

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CitationExtraction(BaseModel):
    """Request to extract citation metadata from external sources"""
    citation_id: UUID = Field(..., description="Citation ID to enrich with metadata")
    source: Optional[MetadataSource] = Field(None, description="Preferred metadata source (auto-detect if None)")
    identifier: Optional[str] = Field(None, description="DOI, arXiv ID, or other identifier to use for lookup")


class CitationUpdate(BaseModel):
    """Update citation metadata (partial updates allowed)"""
    authors: Optional[List[Dict[str, Any]]] = None
    year: Optional[int] = Field(None, ge=1900, le=2100)
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    abstract: Optional[str] = None
    metadata_source: Optional[MetadataSource] = None
    needs_review: Optional[bool] = None


# ============================================================================
# T020: Citation Graph Schemas (User Story 3)
# ============================================================================

class CitationNode(BaseModel):
    """Node in the citation graph (represents a citation)"""
    id: str = Field(..., description="Citation ID (UUID as string)")
    title: str = Field(..., description="Document/paper title")
    authors: Optional[List[str]] = Field(default=None, description="List of author names")
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    citation_count: Optional[int] = Field(default=0, description="Number of citations to this paper")

    class Config:
        from_attributes = True


class CitationEdge(BaseModel):
    """Edge in the citation graph (represents a relationship between citations)"""
    id: str = Field(..., description="Relationship ID (UUID as string)")
    source: str = Field(..., description="Source citation ID")
    target: str = Field(..., description="Target citation ID")
    type: CitationRelationshipType = Field(default=CitationRelationshipType.CITES)
    context: Optional[str] = Field(None, description="Where the citation appears in text")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Extraction confidence")

    class Config:
        from_attributes = True


class CitationGraphRequest(BaseModel):
    """Request to retrieve citation graph for a project"""
    project_id: UUID = Field(..., description="Research project ID")
    max_depth: int = Field(default=2, ge=1, le=5, description="Maximum depth of citation relationships to traverse")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence score for edges")
    relationship_types: Optional[List[CitationRelationshipType]] = Field(
        default=None,
        description="Filter by relationship types (None = all types)"
    )


class CitationGraphResponse(BaseModel):
    """Citation graph response with nodes and edges"""
    project_id: UUID
    nodes: List[CitationNode] = Field(..., description="Citations (papers) in the graph")
    edges: List[CitationEdge] = Field(..., description="Relationships between citations")
    total_nodes: int = Field(..., description="Total number of nodes")
    total_edges: int = Field(..., description="Total number of edges")
    depth: int = Field(..., description="Actual depth of the graph")

    class Config:
        from_attributes = True


# ============================================================================
# T021: Research Project Schemas (User Story 4)
# ============================================================================

class ProjectCreate(BaseModel):
    """Create a new research project"""
    workspace_id: UUID = Field(..., description="Parent workspace ID")
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    project_type: ProjectType = Field(default=ProjectType.RESEARCH)
    research_status: ResearchStatus = Field(default=ResearchStatus.ACTIVE)
    research_goals: Optional[str] = Field(None, description="Project objectives and goals")
    deadline: Optional[datetime] = Field(None, description="Project deadline")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$", description="Hex color for UI")
    icon: Optional[str] = Field(None, max_length=50, description="Icon name for UI")
    is_private: bool = Field(default=True, description="Privacy setting (always TRUE for Phase 3)")


class ProjectUpdate(BaseModel):
    """Update research project (partial updates allowed)"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    project_type: Optional[ProjectType] = None
    research_status: Optional[ResearchStatus] = None
    research_goals: Optional[str] = None
    deadline: Optional[datetime] = None
    tags: Optional[List[str]] = None
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: Optional[str] = Field(None, max_length=50)


class ProjectResponse(BaseModel):
    """Research project response"""
    id: UUID
    workspace_id: UUID
    name: str
    description: Optional[str] = None
    project_type: ProjectType
    research_status: ResearchStatus
    research_goals: Optional[str] = None
    deadline: Optional[datetime] = None
    tags: List[str]
    color: Optional[str] = None
    icon: Optional[str] = None
    is_private: bool
    document_count: int = Field(default=0, description="Number of documents in project")
    note_count: int = Field(default=0, description="Number of notes in project")
    draft_count: int = Field(default=0, description="Number of drafts in project")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectNoteCreate(BaseModel):
    """Create a new project note"""
    project_id: UUID = Field(..., description="Parent project ID")
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., description="Markdown content")
    linked_document_ids: List[UUID] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    is_pinned: bool = Field(default=False)


class ProjectNoteUpdate(BaseModel):
    """Update project note (partial updates allowed)"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    linked_document_ids: Optional[List[UUID]] = None
    tags: Optional[List[str]] = None
    is_pinned: Optional[bool] = None


class ProjectNoteResponse(BaseModel):
    """Project note response"""
    id: UUID
    project_id: UUID
    user_id: UUID
    title: str
    content: str
    content_preview: str
    linked_document_ids: List[UUID]
    linked_document_count: int
    tags: List[str]
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# T022: Draft Schemas (User Story 5)
# ============================================================================

class DraftGenerateRequest(BaseModel):
    """Request to generate a new literature review draft"""
    project_id: UUID = Field(..., description="Research project ID")
    title: str = Field(..., min_length=1, max_length=255, description="Draft title")
    themes: List[str] = Field(default_factory=list, description="Themes/topics to focus on")
    generation_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Generation parameters (model, temperature, max_tokens, etc.)"
    )
    max_citations: int = Field(default=50, ge=1, le=200, description="Maximum number of citations to include")


class DraftCitationData(BaseModel):
    """Citation data within a draft"""
    citation_index: int = Field(..., ge=1, description="Order of citation in the draft")
    document_id: Optional[UUID] = None
    citation_id: Optional[UUID] = None
    snippet: Optional[str] = None
    context: Optional[str] = None


class DraftResponse(BaseModel):
    """Generated draft response"""
    id: UUID
    project_id: UUID
    version: int
    title: str
    content: str
    content_preview: str
    themes: List[str]
    word_count: Optional[int] = None
    citation_count: Optional[int] = None
    generation_params: Optional[Dict[str, Any]] = None
    generation_time_ms: Optional[int] = None
    is_current: bool
    citations: Optional[List[DraftCitationData]] = Field(default=None, description="Citations in this draft")
    created_at: datetime

    class Config:
        from_attributes = True


class DraftVersion(BaseModel):
    """Draft version metadata (lightweight, for listing versions)"""
    id: UUID
    version: int
    title: str
    word_count: Optional[int] = None
    citation_count: Optional[int] = None
    themes: List[str]
    is_current: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DraftVersionListResponse(BaseModel):
    """List of draft versions for a project"""
    project_id: UUID
    versions: List[DraftVersion]
    total_versions: int
    current_version: Optional[int] = None
