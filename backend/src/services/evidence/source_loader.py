"""Tenant-scoped document source loading and claim excerpt selection."""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypedDict
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.document import Document, ProcessingStatus

MAX_EXCERPT_CHARS = 12_000
WINDOW_STEP_CHARS = MAX_EXCERPT_CHARS // 2

_CLAIM_TERM_PATTERN = re.compile(r"\w{3,}", re.UNICODE)


class ClassifierSource(TypedDict):
    source_id: UUID
    excerpt: str
    content_hash: str


@dataclass(frozen=True)
class EvidenceSource:
    source_id: UUID
    title: str
    excerpt: str
    content_hash: str

    @property
    def revision(self) -> str:
        return f"{self.source_id}:{self.content_hash}"

    def classifier_input(self) -> ClassifierSource:
        return {
            "source_id": self.source_id,
            "excerpt": self.excerpt,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class EvidenceSourceSet:
    sources: tuple[EvidenceSource, ...]
    withdrawn_source_ids: tuple[str, ...]

    @property
    def revisions(self) -> list[str]:
        active = [source.revision for source in self.sources]
        withdrawn = [
            f"{source_id}:withdrawn" for source_id in self.withdrawn_source_ids
        ]
        return active + withdrawn


class ClaimExcerptSelector:
    """Select the highest-scoring bounded source window for a claim."""

    def select(self, claim: str, content: str) -> str:
        terms = _CLAIM_TERM_PATTERN.findall(claim.casefold())
        best_start = 0
        best_score = -1

        for start in range(0, len(content), WINDOW_STEP_CHARS):
            window = content[start : start + MAX_EXCERPT_CHARS]
            folded_window = window.casefold()
            score = sum(term in folded_window for term in terms)
            if score > best_score:
                best_start = start
                best_score = score

        return content[best_start : best_start + MAX_EXCERPT_CHARS]


class EvidenceSourceError(ValueError):
    """Base error for source-boundary validation failures."""


class DuplicateSourceIdsError(EvidenceSourceError):
    """Raised when a caller repeats a source ID."""


class SourceSetNotFoundError(EvidenceSourceError):
    """Raised when the requested source set is not visible to the tenant."""


class SourceNotReadyError(EvidenceSourceError):
    """Raised when an active source has not produced usable content."""


class NoActiveSourcesError(EvidenceSourceError):
    """Raised when every requested source has been withdrawn."""


class EvidenceSourceLoader:
    """Load caller-selected documents within one organization boundary."""

    def __init__(self, selector: ClaimExcerptSelector | None = None) -> None:
        self._selector = selector or ClaimExcerptSelector()

    def load(
        self,
        db: Session,
        *,
        organization_id: UUID | None,
        source_ids: Sequence[UUID],
        claim: str,
    ) -> EvidenceSourceSet:
        if organization_id is None:
            raise SourceSetNotFoundError("Requested source set was not found")

        requested_ids = tuple(source_ids)
        if len(set(requested_ids)) != len(requested_ids):
            raise DuplicateSourceIdsError("Source IDs must be unique")

        documents = (
            db.query(Document)
            .filter(
                Document.id.in_(requested_ids),
                Document.organization_id == organization_id,
            )
            .all()
        )
        requested_id_set = set(requested_ids)
        returned_id_set = {document.id for document in documents}
        if returned_id_set != requested_id_set or any(
            document.organization_id != organization_id for document in documents
        ):
            raise SourceSetNotFoundError("Requested source set was not found")

        documents_by_id = {document.id: document for document in documents}
        withdrawn_source_ids = tuple(
            str(source_id)
            for source_id in requested_ids
            if documents_by_id[source_id].is_deleted
        )
        active_documents = [
            documents_by_id[source_id]
            for source_id in requested_ids
            if not documents_by_id[source_id].is_deleted
        ]

        for document in active_documents:
            if (
                document.processing_status != ProcessingStatus.COMPLETED
                or not document.content_text
                or not document.content_text.strip()
            ):
                raise SourceNotReadyError("One or more sources are not ready")

        if not active_documents:
            raise NoActiveSourcesError("No active sources remain")

        sources = tuple(
            self._build_source(document, claim) for document in active_documents
        )
        return EvidenceSourceSet(
            sources=sources,
            withdrawn_source_ids=withdrawn_source_ids,
        )

    def _build_source(self, document: Document, claim: str) -> EvidenceSource:
        content = document.content_text
        content_hash = document.checksum_sha256
        if not content_hash or not content_hash.strip():
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        return EvidenceSource(
            source_id=document.id,
            title=document.title,
            excerpt=self._selector.select(claim, content),
            content_hash=content_hash,
        )
