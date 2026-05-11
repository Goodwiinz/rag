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
    """One retrieved chunk from kbaas.do-ai.run/v1/{kb_uuid}/retrieve.

    DO uses ``text_content`` in the wire format; we expose ``text`` as the
    canonical attribute so downstream code stays stable if DO renames it.
    """

    text: str
    score: float = 0.0
    document_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_do_payload(cls, raw: dict[str, Any], rank: int = 0) -> "Chunk":
        text = (
            raw.get("text_content")
            or raw.get("text")
            or raw.get("content")
            or ""
        )
        meta = raw.get("metadata") or {}
        doc_id = (
            raw.get("document_id")
            or meta.get("document_id")
            or meta.get("item_name")
        )
        # DO retrieve Public Preview omits relevance scores in responses, so
        # we synthesize a monotonically-decreasing proxy from rank position
        # (1.0 at rank 0, floor 0.1). Lets downstream rank/dedup/threshold
        # logic keep working without conditional branches.
        score_raw = raw.get("score") or raw.get("relevance_score")
        if score_raw is not None:
            score = float(score_raw)
        else:
            score = max(0.1, 1.0 - 0.05 * rank)
        return cls(text=text, score=score, document_id=doc_id, metadata=meta)


class RetrieveResult(_Permissive):
    """Wraps the retrieve response chunks."""

    chunks: List[Chunk]
    total: int = 0
