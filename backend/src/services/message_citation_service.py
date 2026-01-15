"""Message Citation Service for Research Assistant.

Handles parsing [Doc N] citations from AI responses and persisting them to the database.
"""

import re
import time
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from structlog import get_logger

from backend.src.models import Citation, Document
from backend.src.shared.research_schemas import CitationCreate

logger = get_logger()


class MessageCitationService:
    """Service for extracting and persisting citations from chat messages."""

    CITATION_PATTERN = re.compile(r'\[Doc\s+(\d+)\]')

    def __init__(self, db: AsyncSession):
        """Initialize service with database session.

        Args:
            db: Database session
        """
        self.db = db

    async def extract_citations_from_message(
        self,
        message_id: UUID,
        message_content: str,
        retrieved_documents: List[Dict[str, Any]],
    ) -> List[Citation]:
        """Extract and save citations from AI response.

        Args:
            message_id: Chat message ID
            message_content: AI response text with [Doc N] citations
            retrieved_documents: List of documents retrieved for RAG context
                Format: [{"id": UUID, "title": str, "snippet": str, "score": float}, ...]

        Returns:
            List of created Citation objects
        """
        start_time = time.time()
        try:
            # Find all [Doc N] citations in message
            citation_matches = self.CITATION_PATTERN.findall(message_content)
            
            if not citation_matches:
                logger.debug(
                    "no_citations_found",
                    message_id=str(message_id),
                    content_length=len(message_content),
                )
                return []

            # Map citation indices to documents
            citations_created = []
            unique_indices = set(int(idx) for idx in citation_matches)

            for citation_index in sorted(unique_indices):
                # Document indices in retrieved_documents are 0-based
                # [Doc 1] refers to retrieved_documents[0]
                doc_index = citation_index - 1

                if doc_index < 0 or doc_index >= len(retrieved_documents):
                    logger.warning(
                        "citation_index_out_of_range",
                        message_id=str(message_id),
                        citation_index=citation_index,
                        retrieved_count=len(retrieved_documents),
                    )
                    continue

                retrieved_doc = retrieved_documents[doc_index]
                document_id = retrieved_doc.get("id")

                # Fetch full document metadata
                document = await self._get_document(document_id)
                if not document:
                    logger.warning(
                        "citation_document_not_found",
                        message_id=str(message_id),
                        document_id=str(document_id),
                    )
                    continue

                # Create citation record
                citation_data = CitationCreate(
                    message_id=message_id,
                    document_id=document_id,
                    document_title=document.filename or "Untitled",
                    document_type="document",
                    snippet=retrieved_doc.get("snippet", ""),
                    page_number=retrieved_doc.get("page_number"),
                    score=retrieved_doc.get("score", 0.0),
                    metadata_source="rag",
                    needs_review=False,
                )

                citation = Citation(
                    message_id=citation_data.message_id,
                    document_id=citation_data.document_id,
                    document_title=citation_data.document_title,
                    document_type=citation_data.document_type,
                    snippet=citation_data.snippet,
                    page_number=citation_data.page_number,
                    score=citation_data.score,
                    metadata_source=citation_data.metadata_source,
                    needs_review=citation_data.needs_review,
                )

                self.db.add(citation)
                citations_created.append(citation)

            # Commit all citations
            await self.db.commit()

            # Enhanced observability logging
            elapsed_ms = (time.time() - start_time) * 1000
            unique_docs = len(set(c.document_id for c in citations_created if c.document_id))
            logger.info(
                "citations_saved",
                message_id=str(message_id),
                count=len(citations_created),
                unique_docs=unique_docs,
                total_matches=len(citation_matches),
                duration_ms=round(elapsed_ms, 2),
                event="citation_batch_created",
            )
            
            # Log individual citation details for debugging
            for citation in citations_created:
                logger.debug(
                    "citation_created",
                    citation_id=str(citation.id) if citation.id else "pending",
                    message_id=str(message_id),
                    document_id=str(citation.document_id),
                    document_title=citation.document_title,
                    score=citation.score,
                    metadata_source=citation.metadata_source,
                    event="individual_citation",
                )

            return citations_created

        except Exception as e:
            await self.db.rollback()
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                "citation_extraction_failed",
                message_id=str(message_id),
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(elapsed_ms, 2),
                event="citation_error",
            )
            raise

    async def _get_document(self, document_id: UUID) -> Optional[Document]:
        """Fetch document by ID.

        Args:
            document_id: Document UUID

        Returns:
            Document object or None
        """
        try:
            query = select(Document).where(Document.id == document_id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                "document_fetch_failed",
                document_id=str(document_id),
                error=str(e),
            )
            return None

    @staticmethod
    def parse_citation_indices(message_content: str) -> List[int]:
        """Parse [Doc N] indices from message content.

        Args:
            message_content: Message text with citations

        Returns:
            List of unique citation indices (sorted)
        """
        matches = MessageCitationService.CITATION_PATTERN.findall(message_content)
        return sorted(set(int(idx) for idx in matches))
