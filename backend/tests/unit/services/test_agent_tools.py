"""Unit tests for agent tool functions.

Covers the fresh-session pattern used by destructive tools
(_tool_add_document_to_project, _tool_ingest_arxiv) to ensure
DB writes are committed independently of the shared graph session.
"""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from tests.mocks.services import MockAsyncSession

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user(org_id=None):
    user = Mock()
    user.id = uuid4()
    user.organization_id = org_id or uuid4()
    return user


def _mock_document(title="Test Doc", doc_id=None):
    doc = Mock()
    doc.id = doc_id or uuid4()
    doc.title = title
    doc.filename = f"{title.lower().replace(' ', '_')}.pdf"
    return doc


def _mock_project(name="Test Project", proj_id=None):
    proj = Mock()
    proj.id = proj_id or uuid4()
    proj.name = name
    return proj


# ---------------------------------------------------------------------------
# _tool_add_document_to_project
# ---------------------------------------------------------------------------


class TestAddDocumentToProject:
    """Tests for _tool_add_document_to_project fresh-session behaviour."""

    async def test_success_uses_fresh_session(self):
        """Tool should commit via AsyncSessionLocal, not the passed-in db."""
        from src.api.agent.execute import _tool_add_document_to_project

        user = _mock_user()
        doc = _mock_document(title="Attention Paper")
        project = _mock_project(name="My Project")

        fresh_db = MockAsyncSession()
        # First execute → resolve document → found
        # Second execute → verify project → found
        # Third execute → check existing link → None (not linked)
        fresh_db._scalar_result = None  # default for "not already linked"

        with (
            patch(
                "src.core.database.AsyncSessionLocal",
                return_value=fresh_db,
            ),
            patch(
                "src.api.agent.tools_impl._resolve_document_id",
                new_callable=AsyncMock,
                return_value=doc,
            ),
            patch(
                "src.api.agent.tools_impl._verify_project_ownership",
                new_callable=AsyncMock,
                return_value=project,
            ),
        ):
            result = await _tool_add_document_to_project(
                args={"document_id": str(doc.id), "project_id": str(project.id)},
                db=AsyncMock(),  # shared graph db — should NOT be used
                current_user=user,
            )

        assert result["status"] == "success"
        assert "Attention Paper" in result["message"]
        fresh_db.assert_added(count=1)
        fresh_db.assert_committed()

    async def test_document_not_found_returns_error(self):
        """Tool should return a helpful error when document doesn't exist."""
        from src.api.agent.execute import _tool_add_document_to_project

        user = _mock_user()
        fresh_db = MockAsyncSession()

        with (
            patch(
                "src.core.database.AsyncSessionLocal",
                return_value=fresh_db,
            ),
            patch(
                "src.api.agent.tools_impl._resolve_document_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await _tool_add_document_to_project(
                args={"document_id": "fake-id", "project_id": str(uuid4())},
                db=AsyncMock(),
                current_user=user,
            )

        assert "error" in result
        assert "not found" in result["error"].lower()
        assert "ingest" in result["error"].lower()

    async def test_already_linked_returns_status(self):
        """Tool should detect and report already-linked documents."""
        from src.api.agent.execute import _tool_add_document_to_project

        user = _mock_user()
        doc = _mock_document()
        project = _mock_project()

        fresh_db = MockAsyncSession()
        # scalar_one_or_none returns a truthy value → already linked
        fresh_db.set_scalar_result(Mock())

        with (
            patch(
                "src.core.database.AsyncSessionLocal",
                return_value=fresh_db,
            ),
            patch(
                "src.api.agent.tools_impl._resolve_document_id",
                new_callable=AsyncMock,
                return_value=doc,
            ),
            patch(
                "src.api.agent.tools_impl._verify_project_ownership",
                new_callable=AsyncMock,
                return_value=project,
            ),
        ):
            result = await _tool_add_document_to_project(
                args={"document_id": str(doc.id), "project_id": str(project.id)},
                db=AsyncMock(),
                current_user=user,
            )

        assert result["status"] == "already_linked"

    async def test_missing_document_id_returns_error(self):
        """Tool should reject calls without document_id."""
        from src.api.agent.execute import _tool_add_document_to_project

        result = await _tool_add_document_to_project(
            args={"project_id": str(uuid4())},
            db=AsyncMock(),
            current_user=_mock_user(),
        )

        assert "error" in result

    async def test_no_auth_returns_error(self):
        """Tool should reject unauthenticated calls."""
        from src.api.agent.execute import _tool_add_document_to_project

        result = await _tool_add_document_to_project(
            args={"document_id": str(uuid4()), "project_id": str(uuid4())},
            db=AsyncMock(),
            current_user=None,
        )

        assert "error" in result
        assert "authentication" in result["error"].lower()


# ---------------------------------------------------------------------------
# _tool_ingest_arxiv
# ---------------------------------------------------------------------------


class TestIngestArxiv:
    """Tests for _tool_ingest_arxiv fresh-session behaviour."""

    async def test_ingested_papers_use_fresh_session(self):
        """Ingest should persist documents via AsyncSessionLocal, not shared db."""
        from src.api.agent.execute import _tool_ingest_arxiv

        user = _mock_user()
        paper_ids = ["2301.00001v1", "2301.00002v1"]

        mock_paper = Mock()
        mock_paper.title = "Test Paper"
        mock_paper.filename = "test.pdf"
        mock_paper.file_path = "/tmp/test.pdf"
        mock_paper.file_size_bytes = 1024
        mock_paper.mime_type = "application/pdf"
        mock_paper.content_text = "Some content"
        mock_paper.content_summary = "Summary"
        mock_paper.document_metadata = {"arxiv_id": "2301.00001v1"}

        fresh_db = MockAsyncSession()

        mock_service = AsyncMock()
        mock_service.search_papers = AsyncMock(
            return_value=[{"id": "2301.00001v1", "title": "Test Paper"}]
        )
        mock_service.ingest_papers = AsyncMock(return_value=[mock_paper, mock_paper])

        mock_service_ctx = AsyncMock()
        mock_service_ctx.__aenter__ = AsyncMock(return_value=mock_service)
        mock_service_ctx.__aexit__ = AsyncMock(return_value=False)

        shared_db = AsyncMock()  # graph session — should NOT be used for writes

        with (
            patch(
                "src.services.arxiv.arxiv_service.ArXivIngestionService",
                return_value=mock_service_ctx,
            ),
            patch(
                "src.core.database.AsyncSessionLocal",
                return_value=fresh_db,
            ),
        ):
            result = await _tool_ingest_arxiv(
                args={"paper_ids": paper_ids},
                user_id=str(user.id),
                db=shared_db,
                current_user=user,
            )

        assert result["status"] == "ingestion_complete"
        assert len(result["document_ids"]) == 2
        fresh_db.assert_added(count=2)
        fresh_db.assert_committed()

        # Verify shared db was NOT used for writes
        shared_db.add.assert_not_called()
        shared_db.commit.assert_not_called()

    async def test_ingest_no_papers_returns_error(self):
        """Should reject empty paper_ids list."""
        from src.api.agent.execute import _tool_ingest_arxiv

        result = await _tool_ingest_arxiv(
            args={"paper_ids": []},
            user_id="user-1",
            db=AsyncMock(),
            current_user=_mock_user(),
        )

        assert "error" in result

    async def test_ingest_too_many_papers_returns_error(self):
        """Should reject more than 10 papers."""
        from src.api.agent.execute import _tool_ingest_arxiv

        result = await _tool_ingest_arxiv(
            args={"paper_ids": [f"id-{i}" for i in range(11)]},
            user_id="user-1",
            db=AsyncMock(),
            current_user=_mock_user(),
        )

        assert "error" in result
        assert "10" in result["error"]

    async def test_ingest_service_failure_returns_error(self):
        """Should catch service exceptions and return an error dict."""
        from src.api.agent.execute import _tool_ingest_arxiv

        mock_service_ctx = AsyncMock()
        mock_service_ctx.__aenter__ = AsyncMock(
            side_effect=RuntimeError("ArXiv API down")
        )
        mock_service_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.services.arxiv.arxiv_service.ArXivIngestionService",
            return_value=mock_service_ctx,
        ):
            result = await _tool_ingest_arxiv(
                args={"paper_ids": ["2301.00001v1"]},
                user_id="user-1",
                db=AsyncMock(),
                current_user=_mock_user(),
            )

        assert "error" in result

    async def test_ingest_without_user_skips_db_persist(self):
        """Without current_user, should return paper_ids only (no DB writes)."""
        from src.api.agent.execute import _tool_ingest_arxiv

        mock_paper = Mock()
        mock_paper.id = "arxiv-id-1"
        mock_paper.title = "Fallback Paper"

        mock_service = AsyncMock()
        mock_service.search_papers = AsyncMock(return_value=[{"id": "id1"}])
        mock_service.ingest_papers = AsyncMock(return_value=[mock_paper])

        mock_service_ctx = AsyncMock()
        mock_service_ctx.__aenter__ = AsyncMock(return_value=mock_service)
        mock_service_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.services.arxiv.arxiv_service.ArXivIngestionService",
            return_value=mock_service_ctx,
        ):
            result = await _tool_ingest_arxiv(
                args={"paper_ids": ["2301.00001v1"]},
                user_id="",
                db=AsyncMock(),
                current_user=None,
            )

        assert result["status"] == "ingestion_complete"
        assert "arxiv-id-1" in result["document_ids"]


# ---------------------------------------------------------------------------
# execute_tool dispatch
# ---------------------------------------------------------------------------


class TestExecuteToolDispatch:
    """Test that execute_tool routes to the correct tool function."""

    async def test_unknown_tool_returns_error(self):
        """Unrecognised tool names should return an error, not crash."""
        from src.api.agent.execute import execute_tool

        result = await execute_tool(
            tool_name="nonexistent_tool",
            args={},
            user_id="user-1",
            db=AsyncMock(),
            current_user=_mock_user(),
        )

        assert "error" in result

    async def test_add_document_dispatches_correctly(self):
        """execute_tool should route add_document_to_project to its handler."""
        from src.api.agent.execute import execute_tool

        with patch(
            "src.api.agent.tools_impl._tool_add_document_to_project",
            new_callable=AsyncMock,
            return_value={"status": "success"},
        ) as mock_handler:
            result = await execute_tool(
                tool_name="add_document_to_project",
                args={"document_id": "d1", "project_id": "p1"},
                user_id="user-1",
                db=AsyncMock(),
                current_user=_mock_user(),
            )

        mock_handler.assert_awaited_once()
        assert result["status"] == "success"

    async def test_create_project_dispatches_correctly(self):
        """execute_tool should route create_project to its handler."""
        from src.api.agent.execute import execute_tool

        with patch(
            "src.api.agent.tools_impl._tool_create_project",
            new_callable=AsyncMock,
            return_value={"status": "success", "project_id": "p1"},
        ) as mock_handler:
            result = await execute_tool(
                tool_name="create_project",
                args={"name": "Diffusion Transformers"},
                user_id="user-1",
                db=AsyncMock(),
                current_user=_mock_user(),
            )

        mock_handler.assert_awaited_once()
        assert result["status"] == "success"


class TestCreateProject:
    """Tests for _tool_create_project."""

    async def test_missing_user_returns_error(self):
        from src.api.agent.execute import _tool_create_project

        result = await _tool_create_project(
            {"name": "Diffusion Transformers"}, None, None
        )
        assert "error" in result
        assert "Authentication" in result["error"]

    async def test_missing_name_returns_error(self):
        from src.api.agent.execute import _tool_create_project

        result = await _tool_create_project({"name": "  "}, None, _mock_user())
        assert "error" in result
        assert "name is required" in result["error"]

    async def test_invalid_workspace_id_returns_error(self):
        from src.api.agent.execute import _tool_create_project

        result = await _tool_create_project(
            {"name": "X", "workspace_id": "not-a-uuid"},
            None,
            _mock_user(),
        )
        assert "error" in result
        assert "UUID" in result["error"]

    async def test_success_uses_first_workspace_when_omitted(self):
        """When workspace_id is omitted, the user's first workspace is used."""
        from src.api.agent.execute import _tool_create_project

        user = _mock_user()
        workspace_id = uuid4()
        project = _mock_project(name="Diffusion Transformers")
        project.workspace_id = workspace_id

        service = MagicMock()
        service._get_workspace_ids_for_user = AsyncMock(return_value=[workspace_id])
        service.create_project = AsyncMock(return_value=project)

        fresh_db = MockAsyncSession()

        with (
            patch(
                "src.core.database.AsyncSessionLocal",
                return_value=fresh_db,
            ),
            patch(
                "src.services.research.project_service.ProjectService",
                return_value=service,
            ),
        ):
            result = await _tool_create_project(
                {"name": "Diffusion Transformers", "tags": ["ml"]}, None, user
            )

        assert result["status"] == "success"
        assert result["project_id"] == str(project.id)
        assert result["workspace_id"] == str(workspace_id)
        service._get_workspace_ids_for_user.assert_awaited_once_with(user.id)
        service.create_project.assert_awaited_once()

    async def test_success_no_workspace_returns_error(self):
        """If the user has no workspace, the tool returns a clear error."""
        from src.api.agent.execute import _tool_create_project

        user = _mock_user()
        service = MagicMock()
        service._get_workspace_ids_for_user = AsyncMock(return_value=[])

        fresh_db = MockAsyncSession()

        with (
            patch(
                "src.core.database.AsyncSessionLocal",
                return_value=fresh_db,
            ),
            patch(
                "src.services.research.project_service.ProjectService",
                return_value=service,
            ),
        ):
            result = await _tool_create_project({"name": "X"}, None, user)

        assert "error" in result
        assert "workspace" in result["error"].lower()
