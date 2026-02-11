"""
Integration tests for Drafts API (T121)

Tests the DraftGenerationService methods with mocked DB and LLM calls.
Covers generation, status lifecycle, CRUD operations, citations,
comparison, and export functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

from src.services.research.draft_generation_service import (
    DraftGenerationService,
    DraftGenerationStatus,
    _generation_status,
)

# Mark all async tests for pytest-asyncio (needed when running from norecursedirs path)
pytestmark = pytest.mark.asyncio


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def clear_generation_status():
    """Reset the in-memory status store between tests."""
    _generation_status.clear()
    yield
    _generation_status.clear()


@pytest.fixture
def mock_db():
    """Create a mocked AsyncSession for service instantiation."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = Mock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def service(mock_db):
    """Create a DraftGenerationService with LLM init disabled."""
    with patch.object(
        DraftGenerationService, "_initialize_llm", return_value=None
    ):
        svc = DraftGenerationService(db=mock_db)
    svc.llm = None
    svc._openai_client = None
    svc._anthropic_client = None
    return svc


@pytest.fixture
def project_id():
    return uuid4()


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def sample_documents():
    """Create mock Document objects for testing."""
    docs = []
    for i in range(3):
        doc = Mock()
        doc.id = uuid4()
        doc.title = f"Paper {i + 1}: Research on Topic {i + 1}"
        doc.filename = f"paper_{i + 1}.pdf"
        doc.content_text = (
            f"This paper examines topic {i + 1} in depth. "
            f"We present findings on subtopic A and subtopic B. "
            f"Our methodology involves approach {i + 1}. "
            f"Results show significant progress in the field."
        )
        doc.content_summary = (
            f"Summary of paper {i + 1} covering topic {i + 1}."
        )
        docs.append(doc)
    return docs


@pytest.fixture
def doc_context(sample_documents):
    """Build a document context map from sample documents."""
    context = {}
    for idx, doc in enumerate(sample_documents, start=1):
        context[idx] = {
            "id": doc.id,
            "title": doc.title,
            "content": doc.content_text,
            "summary": doc.content_summary,
        }
    return context


@pytest.fixture
def sample_draft_content():
    """Content with [Doc N] citation references for extraction tests."""
    return (
        "## 1. Introduction\n\n"
        "Machine learning has transformed healthcare [Doc 1]. "
        "Recent advances in NLP have enabled new diagnostic tools [Doc 2]. "
        "Computer vision applications in radiology are growing [Doc 3].\n\n"
        "## 2. Methodology\n\n"
        "We surveyed the literature following guidelines from [Doc 1] "
        "and validated our framework using data from [Doc 2].\n\n"
        "## 3. Conclusion\n\n"
        "The intersection of these fields shows promise [Doc 1] [Doc 3]."
    )


# ============================================================================
# TestDraftGenerationService - Unit tests for service methods
# ============================================================================


class TestDraftGenerationService:
    """Unit tests for DraftGenerationService methods."""

    async def test_generate_draft_returns_task_id(
        self, service, project_id, user_id
    ):
        """generate_draft should return a dict with task_id and pending status."""
        with patch.object(
            service,
            "_generate_draft_async",
            new_callable=AsyncMock,
        ) as mock_gen:
            result = await service.generate_draft(
                project_id=project_id,
                user_id=user_id,
                themes=["machine learning", "healthcare"],
            )

        assert "task_id" in result
        assert result["status"] == DraftGenerationStatus.PENDING
        assert result["message"] == "Draft generation started"

        task_id = result["task_id"]
        assert isinstance(task_id, str)
        assert len(task_id) == 12

        stored = _generation_status.get(task_id)
        assert stored is not None
        assert stored["status"] == DraftGenerationStatus.PENDING
        assert stored["progress"] == 0
        assert stored["project_id"] == str(project_id)
        assert stored["user_id"] == str(user_id)

    async def test_get_status_returns_status(self, service, project_id):
        """get_status should return the stored status dict for a task."""
        task_id = "test_task_01"
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.GENERATING,
            "progress": 45,
            "current_step": "Building sections",
            "project_id": str(project_id),
        }

        status = DraftGenerationService.get_status(task_id)

        assert status is not None
        assert status["status"] == DraftGenerationStatus.GENERATING
        assert status["progress"] == 45
        assert status["current_step"] == "Building sections"

    async def test_get_status_returns_none_for_unknown(self):
        """get_status should return None for an unknown task_id."""
        status = DraftGenerationService.get_status("nonexistent_task")
        assert status is None

    async def test_cancel_generation_cancels(self, service):
        """cancel_generation should mark an active task as cancelled."""
        task_id = "cancel_test"
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.GENERATING,
            "progress": 50,
            "current_step": "Generating content",
        }

        result = DraftGenerationService.cancel_generation(task_id)

        assert result is True
        assert (
            _generation_status[task_id]["status"]
            == DraftGenerationStatus.CANCELLED
        )
        assert (
            _generation_status[task_id]["current_step"]
            == "Cancelled by user"
        )

    async def test_cancel_generation_returns_false_for_completed(self):
        """cancel_generation should return False for already-completed tasks."""
        task_id = "done_task"
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.COMPLETED,
            "progress": 100,
            "current_step": "Done",
        }

        result = DraftGenerationService.cancel_generation(task_id)
        assert result is False
        assert (
            _generation_status[task_id]["status"]
            == DraftGenerationStatus.COMPLETED
        )

    async def test_cancel_generation_returns_false_for_unknown(self):
        """cancel_generation should return False for unknown task_id."""
        result = DraftGenerationService.cancel_generation("no_such_task")
        assert result is False

    async def test_extract_citations_from_content(
        self, service, doc_context, sample_draft_content
    ):
        """_extract_citations_from_content should find unique [Doc N] refs."""
        citations = service._extract_citations_from_content(
            sample_draft_content, doc_context
        )

        assert len(citations) == 3

        doc_ids_found = {c["document_id"] for c in citations}
        expected_ids = {doc_context[i]["id"] for i in [1, 2, 3]}
        assert doc_ids_found == expected_ids

        for citation in citations:
            assert "document_id" in citation
            assert "snippet" in citation
            assert "context" in citation
            assert citation["citation_id"] is None

    async def test_extract_citations_skips_invalid_doc_nums(
        self, service, doc_context
    ):
        """Citations referencing non-existent doc numbers should be skipped."""
        content = "Refer to [Doc 1] and [Doc 99] for details."
        citations = service._extract_citations_from_content(
            content, doc_context
        )

        assert len(citations) == 1
        assert citations[0]["document_id"] == doc_context[1]["id"]

    async def test_extract_citations_deduplicates(
        self, service, doc_context
    ):
        """Multiple references to the same [Doc N] yield one citation."""
        content = (
            "First reference [Doc 1]. "
            "Second reference [Doc 1]. "
            "Third reference [Doc 1]."
        )
        citations = service._extract_citations_from_content(
            content, doc_context
        )
        assert len(citations) == 1

    async def test_build_document_context(self, service, sample_documents):
        """_build_document_context should build a numbered dict of docs."""
        context = service._build_document_context(sample_documents)

        assert len(context) == 3
        assert 1 in context
        assert 2 in context
        assert 3 in context

        for idx in range(1, 4):
            entry = context[idx]
            assert "id" in entry
            assert "title" in entry
            assert "content" in entry
            assert "summary" in entry
            assert isinstance(entry["id"], UUID)

    async def test_build_document_context_truncates_long_content(
        self, service
    ):
        """Long content should be truncated to 4000 chars."""
        doc = Mock()
        doc.id = uuid4()
        doc.title = "Long Paper"
        doc.filename = "long.pdf"
        doc.content_text = "x" * 10000
        doc.content_summary = "Short summary."

        context = service._build_document_context([doc])

        assert len(context[1]["content"]) == 4003  # 4000 + "..."
        assert context[1]["content"].endswith("...")

    async def test_build_document_context_empty_list(self, service):
        """Empty document list should return empty context."""
        context = service._build_document_context([])
        assert context == {}

    async def test_template_fallback_content(self, service, doc_context):
        """_build_template_content should produce markdown with sections."""
        themes = ["deep learning", "NLP", "computer vision"]
        content = service._build_template_content(
            doc_context=doc_context,
            themes=themes,
            style="academic",
            max_sections=5,
            include_abstract=True,
        )

        assert "## Abstract" in content
        assert "## 1. Introduction" in content
        assert "deep learning" in content.lower() or "Deep Learning" in content
        assert "Conclusion" in content
        assert "[Doc 1]" in content

    async def test_template_fallback_no_abstract(self, service, doc_context):
        """Template without abstract should skip the Abstract section."""
        content = service._build_template_content(
            doc_context=doc_context,
            themes=["topic"],
            style="academic",
            max_sections=3,
            include_abstract=False,
        )

        assert "## Abstract" not in content
        assert "## 1. Introduction" in content

    async def test_template_fallback_empty_themes(self, service, doc_context):
        """Template with empty themes should still produce valid content."""
        content = service._build_template_content(
            doc_context=doc_context,
            themes=[],
            style="academic",
            max_sections=3,
            include_abstract=False,
        )

        assert "## 1. Introduction" in content
        assert "Conclusion" in content


# ============================================================================
# TestDraftStatusLifecycle - Test the status tracking
# ============================================================================


class TestDraftStatusLifecycle:
    """Tests for status transitions in the generation lifecycle."""

    async def test_status_transitions(self, service):
        """_update_status should correctly update fields for each phase."""
        task_id = "lifecycle_01"
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.PENDING,
            "progress": 0,
            "current_step": "Initializing",
            "started_at": datetime.utcnow().isoformat(),
        }

        transitions = [
            (DraftGenerationStatus.ANALYZING, 10, "Retrieving documents"),
            (DraftGenerationStatus.ANALYZING, 20, "Analyzing 5 documents"),
            (DraftGenerationStatus.GENERATING, 30, "Generating review"),
            (DraftGenerationStatus.GENERATING, 60, "Building sections"),
            (DraftGenerationStatus.CITING, 80, "Validating citations"),
            (DraftGenerationStatus.FINALIZING, 90, "Saving draft"),
            (DraftGenerationStatus.COMPLETED, 100, "Draft completed"),
        ]

        for status, progress, step in transitions:
            service._update_status(task_id, status, progress, step)

            current = _generation_status[task_id]
            assert current["status"] == status
            assert current["progress"] == progress
            assert current["current_step"] == step
            assert "updated_at" in current

    async def test_update_status_with_extra_kwargs(self, service):
        """_update_status should accept and store extra keyword arguments."""
        task_id = "extra_kw"
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.PENDING,
            "progress": 0,
            "current_step": "Init",
        }

        draft_id = str(uuid4())
        service._update_status(
            task_id,
            DraftGenerationStatus.COMPLETED,
            100,
            "Done",
            draft_id=draft_id,
            duration=12.5,
        )

        current = _generation_status[task_id]
        assert current["draft_id"] == draft_id
        assert current["duration"] == 12.5

    async def test_update_status_ignores_unknown_task(self, service):
        """_update_status should silently ignore unknown task IDs."""
        service._update_status(
            "no_such_task",
            DraftGenerationStatus.COMPLETED,
            100,
            "Done",
        )
        assert "no_such_task" not in _generation_status

    async def test_cancel_while_generating(self, service):
        """Cancelling during GENERATING phase should set CANCELLED status."""
        task_id = "cancel_gen"
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.GENERATING,
            "progress": 45,
            "current_step": "Building sections",
        }

        cancelled = DraftGenerationService.cancel_generation(task_id)
        assert cancelled is True

        current = _generation_status[task_id]
        assert current["status"] == DraftGenerationStatus.CANCELLED
        assert current["current_step"] == "Cancelled by user"

        is_cancelled = service._is_cancelled(task_id)
        assert is_cancelled is True

    async def test_cancel_while_analyzing(self, service):
        """Cancelling during ANALYZING phase should set CANCELLED status."""
        task_id = "cancel_analyze"
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.ANALYZING,
            "progress": 15,
            "current_step": "Analyzing 3 documents",
        }

        cancelled = DraftGenerationService.cancel_generation(task_id)
        assert cancelled is True
        assert (
            _generation_status[task_id]["status"]
            == DraftGenerationStatus.CANCELLED
        )

    async def test_cancel_while_citing(self, service):
        """Cancelling during CITING phase should set CANCELLED status."""
        task_id = "cancel_cite"
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.CITING,
            "progress": 80,
            "current_step": "Validating citations",
        }

        cancelled = DraftGenerationService.cancel_generation(task_id)
        assert cancelled is True
        assert (
            _generation_status[task_id]["status"]
            == DraftGenerationStatus.CANCELLED
        )

    async def test_is_cancelled_returns_false_for_active(self, service):
        """_is_cancelled should return False for non-cancelled tasks."""
        task_id = "active_task"
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.GENERATING,
            "progress": 50,
            "current_step": "Working",
        }

        assert service._is_cancelled(task_id) is False

    async def test_cannot_cancel_failed_task(self):
        """cancel_generation should return False for a FAILED task."""
        task_id = "fail_task"
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.FAILED,
            "progress": 0,
            "current_step": "Error: something broke",
        }

        result = DraftGenerationService.cancel_generation(task_id)
        assert result is False
        assert (
            _generation_status[task_id]["status"]
            == DraftGenerationStatus.FAILED
        )

    async def test_cannot_cancel_already_cancelled(self):
        """cancel_generation should return False for an already CANCELLED task."""
        task_id = "already_cancelled"
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.CANCELLED,
            "progress": 0,
            "current_step": "Cancelled by user",
        }

        result = DraftGenerationService.cancel_generation(task_id)
        assert result is False


# ============================================================================
# TestDraftCRUD - Test CRUD with mocked DB
# ============================================================================


class TestDraftCRUD:
    """Test CRUD operations with mocked database."""

    async def test_get_draft_by_id(self, service, mock_db, project_id):
        """get_draft with a draft_id should query by id and project_id."""
        draft_id = uuid4()
        mock_draft = Mock()
        mock_draft.id = draft_id
        mock_draft.project_id = project_id
        mock_draft.title = "Test Draft"

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_draft
        mock_db.execute.return_value = mock_result

        result = await service.get_draft(project_id, draft_id=draft_id)

        assert result is not None
        assert result.id == draft_id
        assert result.title == "Test Draft"
        mock_db.execute.assert_called_once()

    async def test_get_draft_current_only(self, service, mock_db, project_id):
        """get_draft with current_only=True should filter by is_current."""
        mock_draft = Mock()
        mock_draft.project_id = project_id
        mock_draft.is_current = True
        mock_draft.version = 3

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_draft
        mock_db.execute.return_value = mock_result

        result = await service.get_draft(project_id, current_only=True)

        assert result is not None
        assert result.is_current is True
        mock_db.execute.assert_called_once()

    async def test_get_draft_returns_none_no_params(
        self, service, mock_db, project_id
    ):
        """get_draft without draft_id or current_only should return None."""
        result = await service.get_draft(project_id)
        assert result is None

    async def test_list_drafts_returns_ordered(
        self, service, mock_db, project_id
    ):
        """list_drafts should return drafts sorted by version desc."""
        mock_drafts = []
        for v in [3, 2, 1]:
            d = Mock()
            d.version = v
            d.project_id = project_id
            d.is_current = v == 3
            mock_drafts.append(d)

        count_result = Mock()
        count_result.scalar.return_value = 3

        drafts_result = Mock()
        drafts_result.scalars.return_value = Mock(all=Mock(return_value=mock_drafts))

        mock_db.execute.side_effect = [count_result, drafts_result]

        result = await service.list_drafts(project_id)

        assert result["total"] == 3
        assert result["skip"] == 0
        assert result["limit"] == 20

        drafts = result["drafts"]
        assert len(drafts) == 3
        versions = [d.version for d in drafts]
        assert versions == [3, 2, 1]

    async def test_list_drafts_with_pagination(
        self, service, mock_db, project_id
    ):
        """list_drafts should respect skip and limit parameters."""
        mock_draft = Mock()
        mock_draft.version = 2
        mock_draft.project_id = project_id

        count_result = Mock()
        count_result.scalar.return_value = 5

        drafts_result = Mock()
        drafts_result.scalars.return_value = Mock(
            all=Mock(return_value=[mock_draft])
        )

        mock_db.execute.side_effect = [count_result, drafts_result]

        result = await service.list_drafts(
            project_id, skip=2, limit=1
        )

        assert result["total"] == 5
        assert result["skip"] == 2
        assert result["limit"] == 1
        assert len(result["drafts"]) == 1

    async def test_list_drafts_empty_project(
        self, service, mock_db, project_id
    ):
        """list_drafts for a project with no drafts should return empty."""
        count_result = Mock()
        count_result.scalar.return_value = 0

        drafts_result = Mock()
        drafts_result.scalars.return_value = Mock(all=Mock(return_value=[]))

        mock_db.execute.side_effect = [count_result, drafts_result]

        result = await service.list_drafts(project_id)

        assert result["total"] == 0
        assert result["drafts"] == []

    async def test_delete_draft_success(
        self, service, mock_db, project_id
    ):
        """delete_draft should delete an existing draft and return True."""
        draft_id = uuid4()
        mock_draft = Mock()
        mock_draft.id = draft_id

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_draft
        mock_db.execute.return_value = mock_result

        result = await service.delete_draft(project_id, draft_id)

        assert result is True
        mock_db.delete.assert_called_once_with(mock_draft)
        mock_db.commit.assert_called_once()

    async def test_delete_draft_not_found(
        self, service, mock_db, project_id
    ):
        """delete_draft should return False when draft is not found."""
        draft_id = uuid4()

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.delete_draft(project_id, draft_id)

        assert result is False
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()

    async def test_get_draft_citations(
        self, service, mock_db, project_id
    ):
        """get_draft_citations should return citations ordered by index."""
        draft_id = uuid4()
        mock_citations = []
        for i in range(1, 4):
            c = Mock()
            c.citation_index = i
            c.draft_id = draft_id
            c.snippet = f"Citation snippet {i}"
            c.context = f"Context for citation {i}"
            mock_citations.append(c)

        mock_result = Mock()
        mock_result.scalars.return_value = Mock(
            all=Mock(return_value=mock_citations)
        )
        mock_db.execute.return_value = mock_result

        result = await service.get_draft_citations(project_id, draft_id)

        assert len(result) == 3
        assert result[0].citation_index == 1
        assert result[1].citation_index == 2
        assert result[2].citation_index == 3

    async def test_compare_drafts_calculates_similarity(
        self, service, mock_db, project_id
    ):
        """compare_drafts should compute Jaccard similarity between versions."""
        draft_a = Mock()
        draft_a.version = 1
        draft_a.content = "the quick brown fox jumps over the lazy dog"
        draft_a.word_count = 9
        draft_a.citation_count = 3
        draft_a.created_at = datetime(2024, 1, 1)

        draft_b = Mock()
        draft_b.version = 2
        draft_b.content = "the quick brown fox leaps over the lazy cat"
        draft_b.word_count = 9
        draft_b.citation_count = 5
        draft_b.created_at = datetime(2024, 1, 2)

        result_a = Mock()
        result_a.scalar_one_or_none.return_value = draft_a
        result_b = Mock()
        result_b.scalar_one_or_none.return_value = draft_b

        mock_db.execute.side_effect = [result_a, result_b]

        comparison = await service.compare_drafts(project_id, 1, 2)

        assert "version_a" in comparison
        assert "version_b" in comparison
        assert comparison["version_a"]["version"] == 1
        assert comparison["version_b"]["version"] == 2
        assert comparison["word_count_diff"] == 0
        assert comparison["citation_count_diff"] == 2

        # Jaccard similarity: shared words / total unique words
        words_a = set(draft_a.content.lower().split())
        words_b = set(draft_b.content.lower().split())
        expected_similarity = round(
            len(words_a & words_b) / len(words_a | words_b), 3
        )
        assert comparison["similarity_score"] == expected_similarity
        assert 0 < comparison["similarity_score"] < 1

    async def test_compare_drafts_identical_content(
        self, service, mock_db, project_id
    ):
        """compare_drafts with identical content should return similarity 1.0."""
        content = "identical content for both drafts"
        draft_a = Mock()
        draft_a.version = 1
        draft_a.content = content
        draft_a.word_count = 5
        draft_a.citation_count = 0
        draft_a.created_at = datetime(2024, 1, 1)

        draft_b = Mock()
        draft_b.version = 2
        draft_b.content = content
        draft_b.word_count = 5
        draft_b.citation_count = 0
        draft_b.created_at = datetime(2024, 1, 2)

        result_a = Mock()
        result_a.scalar_one_or_none.return_value = draft_a
        result_b = Mock()
        result_b.scalar_one_or_none.return_value = draft_b

        mock_db.execute.side_effect = [result_a, result_b]

        comparison = await service.compare_drafts(project_id, 1, 2)

        assert comparison["similarity_score"] == 1.0

    async def test_compare_drafts_not_found(
        self, service, mock_db, project_id
    ):
        """compare_drafts should return error when a draft is not found."""
        result_a = Mock()
        result_a.scalar_one_or_none.return_value = None
        result_b = Mock()
        result_b.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [result_a, result_b]

        comparison = await service.compare_drafts(project_id, 1, 2)

        assert "error" in comparison
        assert "not found" in comparison["error"]

    async def test_export_markdown(self, service, mock_db, project_id):
        """export_draft as markdown should include content and references."""
        draft_id = uuid4()
        mock_draft = Mock()
        mock_draft.id = draft_id
        mock_draft.project_id = project_id
        mock_draft.title = "ML Healthcare Review"
        mock_draft.content = (
            "## Introduction\n\nThis is a review [Doc 1].\n\n"
            "## Methods\n\nWe used approach X [Doc 2]."
        )

        mock_citations = []
        for i in range(1, 3):
            c = Mock()
            c.citation_index = i
            c.snippet = f"Paper {i} title"
            c.context = f"Context for [Doc {i}]"
            mock_citations.append(c)

        # get_draft call
        draft_result = Mock()
        draft_result.scalar_one_or_none.return_value = mock_draft

        # get_draft_citations call
        citations_result = Mock()
        citations_result.scalars.return_value = Mock(
            all=Mock(return_value=mock_citations)
        )

        mock_db.execute.side_effect = [draft_result, citations_result]

        result = await service.export_draft(
            project_id,
            draft_id,
            format="markdown",
            include_bibliography=True,
        )

        assert result["format"] == "markdown"
        assert result["mime_type"] == "text/markdown"
        assert result["filename"] == "ML_Healthcare_Review.md"
        assert "## References" in result["content"]
        assert "[Doc 1]" in result["content"]
        assert "Paper 1 title" in result["content"]
        assert "Paper 2 title" in result["content"]

    async def test_export_markdown_no_bibliography(
        self, service, mock_db, project_id
    ):
        """export_draft markdown without bibliography omits references."""
        draft_id = uuid4()
        mock_draft = Mock()
        mock_draft.id = draft_id
        mock_draft.project_id = project_id
        mock_draft.title = "Review"
        mock_draft.content = "## Introduction\n\nSome content."

        draft_result = Mock()
        draft_result.scalar_one_or_none.return_value = mock_draft
        mock_db.execute.return_value = draft_result

        result = await service.export_draft(
            project_id,
            draft_id,
            format="markdown",
            include_bibliography=False,
        )

        assert result["format"] == "markdown"
        assert "## References" not in result["content"]
        assert result["content"] == "## Introduction\n\nSome content."

    async def test_export_latex(self, service, mock_db, project_id):
        """export_draft as latex should produce .tex and .bib files."""
        draft_id = uuid4()
        mock_draft = Mock()
        mock_draft.id = draft_id
        mock_draft.project_id = project_id
        mock_draft.title = "Literature Review"
        mock_draft.content = (
            "## Introduction\n\n"
            "Machine learning is growing [Doc 1].\n\n"
            "## Methods\n\nApproach described in [Doc 2]."
        )

        mock_citations = []
        for i in range(1, 3):
            c = Mock()
            c.citation_index = i
            c.snippet = f"Citation {i} title text"
            c.context = f"Some context around [Doc {i}] reference"
            mock_citations.append(c)

        # get_draft call
        draft_result = Mock()
        draft_result.scalar_one_or_none.return_value = mock_draft

        # get_draft_citations call
        citations_result = Mock()
        citations_result.scalars.return_value = Mock(
            all=Mock(return_value=mock_citations)
        )

        mock_db.execute.side_effect = [draft_result, citations_result]

        result = await service.export_draft(
            project_id,
            draft_id,
            format="latex",
            include_bibliography=True,
        )

        assert result["format"] == "latex"
        assert len(result["files"]) == 2

        tex_file = result["files"][0]
        bib_file = result["files"][1]

        assert tex_file["filename"].endswith(".tex")
        assert tex_file["mime_type"] == "application/x-tex"
        assert "\\documentclass{article}" in tex_file["content"]
        assert "\\begin{document}" in tex_file["content"]
        assert "\\end{document}" in tex_file["content"]
        assert "\\section{" in tex_file["content"]
        assert "\\cite{doc1}" in tex_file["content"]
        assert "\\cite{doc2}" in tex_file["content"]

        assert bib_file["filename"] == "references.bib"
        assert bib_file["mime_type"] == "application/x-bibtex"
        assert "@misc{doc1," in bib_file["content"]
        assert "@misc{doc2," in bib_file["content"]
        assert "Citation 1 title" in bib_file["content"]

    async def test_export_latex_without_bibliography(
        self, service, mock_db, project_id
    ):
        """export_draft latex without bibliography should produce empty bib."""
        draft_id = uuid4()
        mock_draft = Mock()
        mock_draft.id = draft_id
        mock_draft.project_id = project_id
        mock_draft.title = "Review"
        mock_draft.content = "## Intro\n\nContent [Doc 1]."

        # Only get_draft is called; get_draft_citations is skipped
        # when include_bibliography=False for latex format
        draft_result = Mock()
        draft_result.scalar_one_or_none.return_value = mock_draft
        mock_db.execute.return_value = draft_result

        result = await service.export_draft(
            project_id,
            draft_id,
            format="latex",
            include_bibliography=False,
        )

        assert result["format"] == "latex"
        assert len(result["files"]) == 2
        bib_file = result["files"][1]
        assert bib_file["content"] == ""
        assert bib_file["filename"] == "references.bib"

    async def test_export_unsupported_format(
        self, service, mock_db, project_id
    ):
        """export_draft with unsupported format should return error."""
        draft_id = uuid4()
        mock_draft = Mock()
        mock_draft.id = draft_id
        mock_draft.project_id = project_id
        mock_draft.title = "Review"
        mock_draft.content = "Content."

        draft_result = Mock()
        draft_result.scalar_one_or_none.return_value = mock_draft
        mock_db.execute.return_value = draft_result

        result = await service.export_draft(
            project_id, draft_id, format="docx"
        )

        assert "error" in result
        assert "Unsupported format" in result["error"]

    async def test_export_draft_not_found(
        self, service, mock_db, project_id
    ):
        """export_draft should return error when draft does not exist."""
        draft_id = uuid4()

        draft_result = Mock()
        draft_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = draft_result

        result = await service.export_draft(
            project_id, draft_id, format="markdown"
        )

        assert "error" in result
        assert "not found" in result["error"]


# ============================================================================
# TestConvertToLatex - LaTeX conversion helper
# ============================================================================


class TestConvertToLatex:
    """Tests for the _convert_to_latex helper method."""

    @pytest.fixture
    def service_instance(self, mock_db):
        """Standalone service for conversion tests."""
        with patch.object(
            DraftGenerationService, "_initialize_llm", return_value=None
        ):
            svc = DraftGenerationService(db=mock_db)
        return svc

    def test_converts_h2_to_section(self, service_instance):
        """## headers should become \\section{}."""
        md = "## Introduction\n\nSome text."
        latex = service_instance._convert_to_latex(md)
        assert "\\section{Introduction}" in latex

    def test_converts_h3_to_subsection(self, service_instance):
        """### headers should become \\subsection{}."""
        md = "### Background\n\nMore text."
        latex = service_instance._convert_to_latex(md)
        assert "\\subsection{Background}" in latex

    def test_converts_doc_citations(self, service_instance):
        """[Doc N] references should become \\cite{docN}."""
        md = "Findings from [Doc 1] and [Doc 3]."
        latex = service_instance._convert_to_latex(md)
        assert "\\cite{doc1}" in latex
        assert "\\cite{doc3}" in latex

    def test_wraps_in_document_structure(self, service_instance):
        """Output should include full LaTeX document structure."""
        md = "## Title\n\nBody text."
        latex = service_instance._convert_to_latex(md)
        assert "\\documentclass{article}" in latex
        assert "\\usepackage{natbib}" in latex
        assert "\\begin{document}" in latex
        assert "\\maketitle" in latex
        assert "\\end{document}" in latex
        assert "\\bibliographystyle{plain}" in latex


# ============================================================================
# TestGenerateBibEntries - BibTeX generation helper
# ============================================================================


class TestGenerateBibEntries:
    """Tests for the _generate_bib_entries helper method."""

    @pytest.fixture
    def service_instance(self, mock_db):
        with patch.object(
            DraftGenerationService, "_initialize_llm", return_value=None
        ):
            svc = DraftGenerationService(db=mock_db)
        return svc

    def test_generates_bib_entries(self, service_instance):
        """Should produce @misc entries for each citation."""
        citations = []
        for i in range(1, 3):
            c = Mock()
            c.citation_index = i
            c.snippet = f"Title of paper {i}"
            c.context = f"Context for paper {i} reference"
            citations.append(c)

        bib = service_instance._generate_bib_entries(citations)

        assert "@misc{doc1," in bib
        assert "@misc{doc2," in bib
        assert "Title of paper 1" in bib
        assert "Title of paper 2" in bib
        assert "title = {" in bib
        assert "note = {" in bib

    def test_empty_citations_returns_empty(self, service_instance):
        """No citations should produce empty string."""
        bib = service_instance._generate_bib_entries([])
        assert bib == ""

    def test_truncates_long_snippet(self, service_instance):
        """Snippets longer than 100 chars should be truncated in title."""
        c = Mock()
        c.citation_index = 1
        c.snippet = "A" * 200
        c.context = "Some context"

        bib = service_instance._generate_bib_entries([c])

        # Title field should contain at most 100 chars of snippet
        assert "title = {" + "A" * 100 + "}" in bib

    def test_handles_none_context(self, service_instance):
        """Citation with None context should produce empty note."""
        c = Mock()
        c.citation_index = 1
        c.snippet = "Title"
        c.context = None

        bib = service_instance._generate_bib_entries([c])

        assert "note = {}" in bib


# ============================================================================
# TestFormatDocSummaries - Document formatting helper
# ============================================================================


class TestFormatDocSummaries:
    """Tests for the _format_doc_summaries helper method."""

    @pytest.fixture
    def service_instance(self, mock_db):
        with patch.object(
            DraftGenerationService, "_initialize_llm", return_value=None
        ):
            svc = DraftGenerationService(db=mock_db)
        return svc

    def test_formats_doc_summaries(self, service_instance, doc_context):
        """Should format each doc as [Doc N] Title\\nContent."""
        formatted = service_instance._format_doc_summaries(doc_context)

        assert "[Doc 1]" in formatted
        assert "[Doc 2]" in formatted
        assert "[Doc 3]" in formatted
        assert "---" in formatted

        for idx in doc_context:
            assert doc_context[idx]["title"] in formatted

    def test_uses_summary_over_content(self, service_instance):
        """Should prefer summary when available."""
        context = {
            1: {
                "id": uuid4(),
                "title": "Doc Title",
                "content": "Full content here",
                "summary": "Brief summary",
            }
        }

        formatted = service_instance._format_doc_summaries(context)
        assert "Brief summary" in formatted

    def test_truncates_long_text(self, service_instance):
        """Text longer than 2000 chars should be truncated."""
        context = {
            1: {
                "id": uuid4(),
                "title": "Long Doc",
                "content": "",
                "summary": "x" * 3000,
            }
        }

        formatted = service_instance._format_doc_summaries(context)
        # Summary was 3000 chars, should be truncated to 2000 + "..."
        assert formatted.count("x") == 2000
        assert "..." in formatted


# ============================================================================
# TestGetProviderName - Provider detection helper
# ============================================================================


class TestGetProviderName:
    """Tests for the _get_provider_name helper method."""

    def test_azure_provider(self, mock_db):
        with patch.object(
            DraftGenerationService, "_initialize_llm", return_value=None
        ):
            svc = DraftGenerationService(db=mock_db)
        svc.llm = "azure/gpt-4o"
        svc._openai_client = None
        svc._anthropic_client = None
        assert svc._get_provider_name() == "azure_openai"

    def test_openai_provider(self, mock_db):
        with patch.object(
            DraftGenerationService, "_initialize_llm", return_value=None
        ):
            svc = DraftGenerationService(db=mock_db)
        svc.llm = "gpt-4o-mini"
        svc._openai_client = Mock()
        svc._anthropic_client = None
        assert svc._get_provider_name() == "openai"

    def test_anthropic_provider(self, mock_db):
        with patch.object(
            DraftGenerationService, "_initialize_llm", return_value=None
        ):
            svc = DraftGenerationService(db=mock_db)
        svc.llm = None
        svc._openai_client = None
        svc._anthropic_client = Mock()
        assert svc._get_provider_name() == "anthropic"

    def test_template_provider(self, mock_db):
        with patch.object(
            DraftGenerationService, "_initialize_llm", return_value=None
        ):
            svc = DraftGenerationService(db=mock_db)
        svc.llm = None
        svc._openai_client = None
        svc._anthropic_client = None
        assert svc._get_provider_name() == "template"
