"""Shared document-resolution logic for DO Knowledge Base chunks.

Both the agent tool (``tools_impl._tool_do_kb_retrieve``) and the RAG node
(``_nodes_rag._try_primary_do_kb_read``) need to:

1. Map storage-key ``document_id`` values from DO KB back to canonical
   ``Document.id`` + ``Document.title`` rows.
2. Optionally post-filter by project membership via ``CollectionDocument``.

This module extracts that near-identical logic into one helper so callers
stay DRY and any future bug-fix lands in a single place.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.collection import CollectionDocument
from src.models.document import Document
from src.services.do_kb.models import Chunk

logger = logging.getLogger(__name__)


def _escape_like(s: str) -> str:
    """Escape SQL LIKE wildcards in untrusted strings.

    Storage keys come from the DO Knowledge Base API — an external service.
    Backslash escapes ``%`` (multi-char wildcard) and ``_`` (single char) so
    a malformed/malicious key cannot broaden the suffix match.
    Use with ``Column.like(pattern, escape='\\\\')``.
    """
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def resolve_and_filter_chunks(
    *,
    chunks: Sequence[Chunk],
    org_id: UUID,
    session: AsyncSession,
    project_id: Optional[str] = None,
) -> tuple[dict[str, tuple[str, str]], list[Chunk]]:
    """Resolve DO KB chunks to Documents and optionally filter by project.

    Parameters
    ----------
    chunks:
        Raw chunks from ``DOKnowledgeBaseClient.retrieve()``.
    org_id:
        The current user's ``organization_id``.
    session:
        An open SQLAlchemy ``AsyncSession`` for DB queries.
    project_id:
        When set, post-filters chunks so only documents belonging to this
        project (via ``CollectionDocument``) survive.

    Returns
    -------
    (title_by_key, chunks_to_emit)
        *title_by_key* maps each storage-key leaf to ``(doc_id_str, title)``.
        *chunks_to_emit* is the (possibly filtered) list of chunks the caller
        should use.  When *project_id* is active and either no chunks resolve
        or all resolved chunks are filtered out, *chunks_to_emit* is empty —
        callers decide what that means (return ``None`` for fallback or return
        an empty payload).
    """
    if not chunks:
        return {}, []

    # ------------------------------------------------------------------
    # Step 1: storage-key extraction → DB lookup → suffix match
    # ------------------------------------------------------------------
    storage_keys = {c.document_id for c in chunks if c.document_id}
    title_by_key: dict[str, tuple[str, str]] = {}

    if storage_keys:
        filters = [Document.storage_path == k for k in storage_keys]
        filters += [
            Document.storage_path.like(
                f"%/{_escape_like(k)}", escape="\\"
            )
            for k in storage_keys
        ]
        rows = await session.execute(
            select(Document.id, Document.storage_path, Document.title)
            .where(Document.organization_id == org_id)
            .where(or_(*filters))
        )
        for doc_id, storage_path, title in rows:
            if storage_path in storage_keys:
                leaf = storage_path
            else:
                leaf = storage_path.rsplit("/", 1)[-1] if storage_path else ""
            title_by_key[leaf] = (str(doc_id), title or leaf)

    # ------------------------------------------------------------------
    # Step 2: project scoping via CollectionDocument
    # ------------------------------------------------------------------
    chunks_to_emit: list[Chunk] = list(chunks)

    if project_id and not title_by_key and chunks:
        # No chunks resolved to known docs under project scope — callers
        # should treat this as empty to avoid leaking unscoped content.
        return title_by_key, []

    if project_id and title_by_key:
        resolved_doc_ids = {
            UUID(doc_id) for doc_id, _ in title_by_key.values() if doc_id
        }
        if resolved_doc_ids:
            try:
                pid = UUID(str(project_id))
            except (ValueError, TypeError):
                pid = None
            if pid is not None:
                membership_rows = await session.execute(
                    select(CollectionDocument.document_id).where(
                        CollectionDocument.collection_id == pid,
                        CollectionDocument.document_id.in_(resolved_doc_ids),
                    )
                )
                in_project = {str(r[0]) for r in membership_rows}
                chunks_to_emit = [
                    c
                    for c in chunks
                    if (
                        title_by_key.get(
                            c.document_id or "", (None, None)
                        )[0]
                        or ""
                    )
                    in in_project
                ]

    return title_by_key, chunks_to_emit
