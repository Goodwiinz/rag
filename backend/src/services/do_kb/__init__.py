"""DigitalOcean Knowledge Base integration.

Phase 1 foundation: client, provisioner, models. One KB per organization,
lazy-provisioned on first ingest. Replaces Qdrant via migrate-then-cutover.
"""

from .backfill import BackfillReport, backfill_org, iter_organizations_to_backfill
from .backfill_model import DOKBBackfillProgress
from .client import DOKnowledgeBaseClient, DOKnowledgeBaseError, get_do_kb_client
from .ingest import sync_document_to_kb, sync_documents_to_kb
from .models import Chunk, DataSource, IndexingJob, KnowledgeBase, RetrieveResult
from .provisioner import ensure_kb_for_org

__all__ = [
    "BackfillReport",
    "Chunk",
    "DataSource",
    "DOKBBackfillProgress",
    "DOKnowledgeBaseClient",
    "DOKnowledgeBaseError",
    "IndexingJob",
    "KnowledgeBase",
    "RetrieveResult",
    "backfill_org",
    "ensure_kb_for_org",
    "get_do_kb_client",
    "iter_organizations_to_backfill",
    "sync_document_to_kb",
    "sync_documents_to_kb",
]
