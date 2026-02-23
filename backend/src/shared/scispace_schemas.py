"""SciSpace integration schemas shared across features."""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_SAFE_COLUMN_NAME_RE = re.compile(r"^[\w\s\-\(\)\/\.,:]+$")


# Feature 1: Extraction Matrix


class ExtractionColumn(BaseModel):
    """A column definition for the extraction matrix."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Column header name"
    )
    description: Optional[str] = Field(
        None, max_length=500, description="What to extract"
    )

    @field_validator("name")
    @classmethod
    def name_must_be_safe(cls, v: str) -> str:
        if not _SAFE_COLUMN_NAME_RE.match(v):
            raise ValueError("Column name contains disallowed characters")
        return v


class ExtractionCellResponse(BaseModel):
    """A single cell in the extraction matrix."""

    document_id: UUID
    column_name: str
    value: Optional[str] = None
    citation_snippet: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class CreateMatrixRequest(BaseModel):
    """Request to create an extraction matrix."""

    name: str = Field(..., min_length=1, max_length=255)
    columns: List[ExtractionColumn] = Field(..., min_length=1, max_length=20)


class TriggerExtractionRequest(BaseModel):
    """Request to trigger extraction on selected documents."""

    document_ids: List[UUID] = Field(..., min_length=1, max_length=100)


# Feature 3: Tone Engine

_ALLOWED_MODELS = {"gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "claude-sonnet-4-6"}


class ToneOption(str, Enum):
    """Available tone adjustment options."""

    ACADEMIC = "academic"
    SIMPLIFIED = "simplified"
    CONCISE = "concise"
    EXPANDED = "expanded"


class RewriteRequest(BaseModel):
    """Request to rewrite text with a specific tone."""

    text: str = Field(..., min_length=20, max_length=50_000, description="Text to rewrite (min 20, max 50000 chars)")
    tone: ToneOption
    preserve_citations: bool = Field(True, description="Maintain citation markers")
    model: Optional[str] = Field(None, description="LLM model override")

    @field_validator("text")
    @classmethod
    def text_not_too_short(cls, v: str) -> str:
        if len(v.split()) < 5:
            raise ValueError("Text must contain at least 5 words")
        return v

    @field_validator("model")
    @classmethod
    def model_must_be_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _ALLOWED_MODELS:
            raise ValueError(f"model must be one of {sorted(_ALLOWED_MODELS)}")
        return v


class RewriteResponse(BaseModel):
    """Response from the tone engine."""

    original: str
    rewritten: str
    tone_applied: ToneOption
    citations_preserved: List[str] = Field(default_factory=list)


# Feature 5: Integrity Detector


class IntegritySegmentScore(BaseModel):
    """AI detection score for a text segment."""

    text_preview: str = Field(..., max_length=200)
    ai_probability: float = Field(..., ge=0.0, le=1.0)


class IntegrityScoreResponse(BaseModel):
    """Full integrity score for a document."""

    document_id: str
    ai_probability: float = Field(..., ge=0.0, le=1.0)
    human_probability: float = Field(..., ge=0.0, le=1.0)
    method: str = "roberta-base-openai-detector"
    analyzed_at: Optional[datetime] = None
    segment_scores: List[IntegritySegmentScore] = Field(default_factory=list)
