"""Regression tests for research project and citation API bugs."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.api.research import citations as citations_api
from src.api.research import projects as projects_api


def _result(*, scalar=None, scalars=None, rows=None):
    """Create a lightweight SQLAlchemy-like result mock."""
    result = Mock()
    scalar_items = list(scalars or [])
    result.scalar_one_or_none = Mock(return_value=scalar)
    result.scalar = Mock(return_value=scalar)
    result.all = Mock(return_value=list(rows or []))
    result.scalars = Mock(
        return_value=SimpleNamespace(
            all=lambda: scalar_items,
            first=lambda: scalar_items[0] if scalar_items else None,
        )
    )
    return result


def _make_user():
    return SimpleNamespace(id=uuid4(), email="owner@example.com")


def _make_document(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid4(),
        "title": "Test Document",
        "filename": "test.pdf",
        "document_type": "pdf",
        "processing_status": "completed",
        "created_at": now,
        "uploaded_by_user_id": uuid4(),
        "is_public": False,
        "content_text": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_citation(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid4(),
        "message_id": None,
        "document_id": uuid4(),
        "external_reference_id": None,
        "document_title": "Test Paper",
        "document_type": "paper",
        "chunk_index": None,
        "chunk_id": None,
        "snippet": "Snippet",
        "page_number": 1,
        "score": 0.9,
        "rerank_score": None,
        "authors": ["Author One"],
        "year": 2024,
        "venue": "Journal",
        "doi": None,
        "arxiv_id": None,
        "abstract": None,
        "metadata_source": "manual",
        "needs_review": False,
        "created_at": now,
        "updated_at": now,
        "document": None,
        "message": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_project(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid4(),
        "workspace_id": uuid4(),
        "name": "Research Project",
        "description": "Project description",
        "project_type": "research",
        "research_status": "active",
        "research_goals": None,
        "deadline": None,
        "tags": [],
        "is_private": True,
        "created_at": now,
        "updated_at": now,
        "documents": [],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_note(project_id, user_id, **overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid4(),
        "project_id": project_id,
        "user_id": user_id,
        "title": "Note title",
        "content": "Full note content",
        "content_preview": "Full note content",
        "linked_document_ids": [],
        "tags": [],
        "is_pinned": False,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_get_citation_rejects_inaccessible_private_document():
    current_user = _make_user()
    private_doc = _make_document(uploaded_by_user_id=uuid4(), is_public=False)
    citation = _make_citation(document_id=private_doc.id, document=private_doc)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_result(scalar=citation))

    with pytest.raises(HTTPException) as exc_info:
        await citations_api.get_citation(
            citation_id=citation.id,
            current_user=current_user,
            db=db,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_list_citations_excludes_inaccessible_private_document_rows():
    current_user = _make_user()
    owned_doc = _make_document(uploaded_by_user_id=current_user.id, is_public=False)
    other_private_doc = _make_document(uploaded_by_user_id=uuid4(), is_public=False)
    visible_citation = _make_citation(document_id=owned_doc.id, document=owned_doc)
    hidden_citation = _make_citation(
        document_id=other_private_doc.id,
        document=other_private_doc,
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _result(rows=[(visible_citation.id,), (hidden_citation.id,)]),
            _result(scalars=[visible_citation, hidden_citation]),
        ]
    )

    response = await citations_api.list_citations(
        skip=0,
        limit=50,
        current_user=current_user,
        db=db,
    )

    assert response.total == 1
    assert len(response.citations) == 1
    assert response.citations[0].id == visible_citation.id


@pytest.mark.asyncio
async def test_export_bibliography_rejects_inaccessible_project():
    current_user = _make_user()
    project_id = uuid4()
    doc_id = uuid4()
    citation = _make_citation(document_id=doc_id)

    db = AsyncMock()

    async def execute_side_effect(statement):
        sql = str(statement).lower()
        if "workspaces.owner_id" in sql or "join workspaces" in sql:
            return _result(scalar=None)
        if "collection_documents.document_id" in sql:
            return _result(rows=[(doc_id,)])
        return _result(scalars=[citation])

    db.execute = AsyncMock(side_effect=execute_side_effect)

    with patch.object(
        citations_api.BibliographyService,
        "format_bibliography",
        return_value="@article{test}",
    ):
        with pytest.raises(HTTPException) as exc_info:
            await citations_api.export_bibliography(
                request=None,
                format="bibtex",
                citation_ids=None,
                project_id=project_id,
                current_user=current_user,
                db=db,
            )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_add_document_to_project_rejects_unowned_private_document():
    current_user = _make_user()
    project_id = uuid4()
    private_doc = _make_document(uploaded_by_user_id=uuid4(), is_public=False)

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _result(scalar=private_doc),
            _result(scalar=None),
        ]
    )
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = Mock()

    with patch.object(
        projects_api,
        "_get_project_with_auth",
        AsyncMock(return_value=SimpleNamespace(id=project_id)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await projects_api.add_document_to_project(
                project_id=project_id,
                document_id=private_doc.id,
                current_user=current_user,
                db=db,
            )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_project_response_includes_notes_field():
    current_user = _make_user()
    project = _make_project()
    note = _make_note(project_id=project.id, user_id=current_user.id)
    collection_doc = SimpleNamespace(
        document=SimpleNamespace(
            id=uuid4(),
            filename="paper.pdf",
            document_type="pdf",
            processing_status="completed",
            created_at=datetime.now(timezone.utc),
        ),
        sort_order=0,
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _result(scalars=[collection_doc]),
            _result(scalars=[note]),
        ]
    )

    with patch.object(projects_api, "ProjectService") as mock_service_cls:
        mock_service = mock_service_cls.return_value
        mock_service.get_project_for_user = AsyncMock(return_value=project)

        response = await projects_api.get_project(
            project_id=project.id,
            current_user=current_user,
            db=db,
        )

    assert hasattr(response, "notes")
    assert len(response.notes) == 1
    assert response.notes[0].title == "Note title"
