"""Pydantic models for DigitalOcean Knowledge Base API responses.

Schemas are intentionally permissive (extra="allow") because DO KB is in
Public Preview and may add fields. We only assert the fields we depend on.
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Permissive(BaseModel):
    model_config = ConfigDict(extra="allow")


class KnowledgeBase(_Permissive):
    """Result of POST /v2/gen-ai/knowledge-bases."""

    uuid: str
    name: str
    region: Optional[str] = None
    project_id: Optional[str] = None
    embedding_model_uuid: Optional[str] = None
    is_public: bool = False
    created_at: Optional[datetime] = None


class DataSource(_Permissive):
    """Result of POST /v2/gen-ai/knowledge-bases/{kb_uuid}/data-sources."""

    uuid: str
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class IndexingJob(_Permissive):
    """Result of POST /v2/gen-ai/knowledge-bases/{kb_uuid}/indexing-jobs."""

    uuid: str
    status: Optional[str] = None
    total_datasources: Optional[int] = None
    tokens: Optional[int] = None


class Chunk(_Permissive):
    """One retrieved chunk from kbaas.do-ai.run/v1/{kb_uuid}/retrieve."""

    text: str
    score: float = 0.0
    document_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrieveResult(_Permissive):
    """Wraps the retrieve response chunks."""

    chunks: List[Chunk]
    total: int = 0
