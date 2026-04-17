"""Unit tests for citations API route behavior."""

import sys
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

backend_root = Path(__file__).resolve().parents[3]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

# Temporarily stub heavy modules so spec_from_file_location can load the
# route module without pulling in the full dependency tree.  We save any
# pre-existing entries and restore them immediately after loading.
_STUB_KEYS = [
    "src.core.database",
    "src.services.research.bibliography_service",
    "src.services.research.citation_extraction_service",
    "src.services.security.user_management",
]
_saved = {k: sys.modules.pop(k) for k in _STUB_KEYS if k in sys.modules}

database_stub = ModuleType("src.core.database")
database_stub.get_db = AsyncMock()
sys.modules["src.core.database"] = database_stub

bibliography_stub = ModuleType("src.services.research.bibliography_service")
bibliography_stub.BibliographyService = object
sys.modules["src.services.research.bibliography_service"] = bibliography_stub

extraction_stub = ModuleType("src.services.research.citation_extraction_service")
extraction_stub.CitationExtractionService = object
extraction_stub.SemanticScholarClient = object
extraction_stub.CrossRefClient = object
sys.modules["src.services.research.citation_extraction_service"] = extraction_stub

user_management_stub = ModuleType("src.services.security.user_management")
user_management_stub.get_current_user = AsyncMock()
sys.modules["src.services.security.user_management"] = user_management_stub

from src.models.citation import Citation
from src.shared.research_schemas import CitationCreate

citations_spec = spec_from_file_location(
    "test_citations_module",
    backend_root / "src/api/research/citations.py",
)
assert citations_spec is not None and citations_spec.loader is not None
citations_module = module_from_spec(citations_spec)
citations_spec.loader.exec_module(citations_module)

CitationExtractRequest = citations_module.CitationExtractRequest
extract_citation = citations_module.extract_citation

# Restore original modules so other test files get the real implementations.
for k in _STUB_KEYS:
    if k in _saved:
        sys.modules[k] = _saved[k]
    else:
        sys.modules.pop(k, None)


def _make_existing_citation(*, document_id, doi=None, arxiv_id=None) -> Citation:
    citation = Citation(
        id=uuid4(),
        document_id=document_id,
        document_title="Existing Citation",
        doi=doi,
        arxiv_id=arxiv_id,
        authors=["Existing Author"],
        year=2024,
        venue="Existing Venue",
        metadata_source="manual",
        needs_review=True,
    )
    citation.created_at = datetime.now(timezone.utc)
    citation.updated_at = datetime.now(timezone.utc)
    return citation


async def _populate_persisted_fields(citation: Citation) -> None:
    """Simulate ORM-populated fields that would normally appear after refresh."""
    if citation.id is None:
        citation.id = uuid4()
    now = datetime.now(timezone.utc)
    citation.created_at = citation.created_at or now
    citation.updated_at = citation.updated_at or now


@pytest.mark.asyncio
@pytest.mark.regression
async def test_extract_citation_reuses_existing_citation_for_same_document_and_doi() -> None:
    """Repeated extraction for the same document should update the existing citation."""
    document_id = uuid4()
    existing_citation = _make_existing_citation(
        document_id=document_id,
        doi="10.1234/existing-doi",
    )

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = existing_citation

    db = AsyncMock()
    db.execute = AsyncMock(return_value=query_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    extracted = CitationCreate(
        document_id=document_id,
        document_title="Updated Citation",
        doi="10.1234/existing-doi",
        authors=["Updated Author"],
        year=2025,
        venue="Updated Venue",
        metadata_source="crossref",
        needs_review=False,
    )

    with patch.object(citations_module, "CitationExtractionService") as service_cls:
        service = service_cls.return_value
        service.extract_for_document = AsyncMock(return_value=(extracted, "crossref"))

        response = await extract_citation(
            request=CitationExtractRequest(document_id=document_id, strategy="auto"),
            current_user=MagicMock(id=uuid4()),
            db=db,
        )

    assert response.id == existing_citation.id
    assert response.documentTitle == "Updated Citation"
    assert response.authors == ["Updated Author"]
    assert response.venue == "Updated Venue"
    assert response.metadataSource == "crossref"
    assert response.needsReview is False
    db.add.assert_not_called()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(existing_citation)


@pytest.mark.asyncio
async def test_extract_citation_creates_new_citation_for_same_doi_on_different_document() -> None:
    """Duplicate identifiers should only be deduped within the same document."""
    existing_document_id = uuid4()
    current_document_id = uuid4()

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=query_result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=_populate_persisted_fields)

    extracted = CitationCreate(
        document_id=current_document_id,
        document_title="Current Document Citation",
        doi="10.5678/shared-doi",
        authors=["New Author"],
        metadata_source="crossref",
    )

    with patch.object(citations_module, "CitationExtractionService") as service_cls:
        service = service_cls.return_value
        service.extract_for_document = AsyncMock(return_value=(extracted, "crossref"))

        await extract_citation(
            request=CitationExtractRequest(document_id=current_document_id, strategy="auto"),
            current_user=MagicMock(id=uuid4()),
            db=db,
        )

    db.execute.assert_awaited_once()
    db.add.assert_called_once()
    inserted_citation = db.add.call_args.args[0]
    assert isinstance(inserted_citation, Citation)
    assert inserted_citation.document_id == current_document_id
    assert inserted_citation.doi == "10.5678/shared-doi"
    assert inserted_citation.document_id != existing_document_id


@pytest.mark.asyncio
async def test_extract_citation_integrity_error_reuses_accessible_existing_citation() -> None:
    """When a race-condition IntegrityError fires, the handler should return the
    winning citation if the current user can access it."""
    from sqlalchemy.exc import IntegrityError

    document_id = uuid4()
    user_id = uuid4()
    existing = _make_existing_citation(document_id=document_id, doi="10.1/race")
    # Simulate the access check passing by setting up document ownership
    existing.document = MagicMock()
    existing.document.is_public = False
    existing.document.uploaded_by_user_id = user_id
    existing.message = None

    # First execute returns None (no existing, triggers new insert), second
    # returns the existing after rollback in the IntegrityError handler.
    none_result = MagicMock()
    none_result.scalar_one_or_none.return_value = None
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[none_result, existing_result])
    db.add = MagicMock()
    db.commit = AsyncMock(side_effect=IntegrityError("", {}, Exception()))
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()

    extracted = CitationCreate(
        document_id=document_id,
        document_title="Race Citation",
        doi="10.1/race",
        metadata_source="crossref",
    )

    current_user = MagicMock()
    current_user.id = user_id

    with patch.object(citations_module, "CitationExtractionService") as service_cls:
        service = service_cls.return_value
        service.extract_for_document = AsyncMock(return_value=(extracted, "crossref"))

        response = await extract_citation(
            request=CitationExtractRequest(document_id=document_id, strategy="auto"),
            current_user=current_user,
            db=db,
        )

    db.rollback.assert_awaited_once()
    assert response.id == existing.id


@pytest.mark.asyncio
async def test_extract_citation_integrity_error_raises_conflict_for_inaccessible_citation() -> None:
    """When the IntegrityError recovery finds a citation owned by a different user,
    a 409 Conflict should be returned instead of leaking the other user's data."""
    from http import HTTPStatus

    from fastapi import HTTPException
    from sqlalchemy.exc import IntegrityError

    document_id = uuid4()
    other_user_id = uuid4()
    existing = _make_existing_citation(document_id=uuid4(), doi="10.1/other-owner")
    # Belong to a different user
    existing.document = MagicMock()
    existing.document.is_public = False
    existing.document.uploaded_by_user_id = other_user_id
    existing.message = None

    none_result = MagicMock()
    none_result.scalar_one_or_none.return_value = None
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[none_result, existing_result])
    db.add = MagicMock()
    db.commit = AsyncMock(side_effect=IntegrityError("", {}, Exception()))
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()

    extracted = CitationCreate(
        document_id=document_id,
        document_title="Race Citation",
        doi="10.1/other-owner",
        metadata_source="crossref",
    )

    current_user = MagicMock()
    current_user.id = uuid4()  # different user

    with patch.object(citations_module, "CitationExtractionService") as service_cls:
        service = service_cls.return_value
        service.extract_for_document = AsyncMock(return_value=(extracted, "crossref"))

        with pytest.raises(HTTPException) as exc_info:
            await extract_citation(
                request=CitationExtractRequest(document_id=document_id, strategy="auto"),
                current_user=current_user,
                db=db,
            )

    assert exc_info.value.status_code == HTTPStatus.CONFLICT
