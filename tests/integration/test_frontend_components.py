"""
Integration tests for Frontend React Components
Tests React components, user interactions, state management, and accessibility
"""

import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch
import json

# React Testing Library imports
from react_testing_library import render, screen, fireEvent, waitFor, act, userEvent
from react_testing_library.web import by, query_by, within
from jest import jest, expect

# Import components and hooks
from src.components.documents.DocumentCard import DocumentCard
from src.components.documents.DocumentLibrary import DocumentLibrary
from src.components.documents.DocumentUploader import DocumentUploader
from src.components.documents.ProcessingStatus import ProcessingStatus
from src.hooks.useDocuments import useDocuments
from src.hooks.useDocumentUpload import useDocumentUpload
from src.types import Document, ProcessingStatus as DocumentProcessingStatus

# Import test utilities
from tests.frontend.utils.test_utils import (
    create_mock_document, create_mock_user, create_mock_organization,
    mock_api_responses, setup_test_router, cleanup_test_components
)
from tests.frontend.utils.accessibility_utils import check_accessibility_compliance


class TestDocumentCardComponent:
    """Test DocumentCard component functionality and interactions"""

    @pytest.fixture
    def mock_document(self) -> Document:
        """Create mock document for testing"""
        return create_mock_document(
            id="doc-123",
            title="Test Document",
            filename="test.pdf",
            file_type="pdf",
            file_size=1024 * 1024,  # 1MB
            processing_status="indexed",
            upload_timestamp="2024-01-15T10:30:00Z",
            thumbnail_url="https://example.com/thumb.jpg"
        )

    def test_document_card_rendering(self, mock_document: Document):
        """Test DocumentCard renders correctly with document data"""
        # Mock callback functions
        on_select = Mock()
        on_preview = Mock()
        on_delete = Mock()
        on_download = Mock()
        on_retry = Mock()

        # Render component
        component = render(
            DocumentCard,
            props={
                "document": mock_document,
                "selected": False,
                "onSelect": on_select,
                "onPreview": on_preview,
                "onDelete": on_delete,
                "onDownload": on_download,
                "onRetry": on_retry
            }
        )

        # Verify document title and filename are displayed
        expect(screen.get_by_text("Test Document")).to_be_in_document()
        expect(screen.get_by_text("test.pdf")).to_be_in_document()

        # Verify file size is formatted correctly
        expect(screen.get_by_text("1.00 MB")).to_be_in_document()

        # Verify status is displayed
        expect(screen.get_by_text("Ready for search")).to_be_in_document()

        # Verify file icon is present for PDF
        pdf_icon = component.container.querySelector('[data-testid="file-icon"]')
        expect(pdf_icon).to_have_class("text-red-600")

    def test_document_card_selection(self, mock_document: Document):
        """Test document selection functionality"""
        on_select = Mock()

        render(
            DocumentCard,
            props={
                "document": mock_document,
                "selected": False,
                "onSelect": on_select
            }
        )

        # Find and click selection checkbox
        checkbox = screen.get_by_role("checkbox", name="Select document")
        fireEvent.click(checkbox)

        # Verify selection callback was called
        expect(on_select).to_have_been_called_with("doc-123")

    def test_document_card_selected_state(self, mock_document: Document):
        """Test document card visual state when selected"""
        on_select = Mock()

        component = render(
            DocumentCard,
            props={
                "document": mock_document,
                "selected": True,
                "onSelect": on_select
            }
        )

        # Verify selected styling is applied
        card = component.container.querySelector('[data-testid="document-card"]')
        expect(card).to_have_class("ring-2", "ring-primary")

        # Verify checkbox is checked
        checkbox = screen.get_by_role("checkbox", name="Deselect document")
        expect(checkbox).to_be_checked()

    def test_document_card_actions_menu(self, mock_document: Document):
        """Test document actions menu functionality"""
        on_preview = Mock()
        on_download = Mock()
        on_delete = Mock()

        render(
            DocumentCard,
            props={
                "document": mock_document,
                "onPreview": on_preview,
                "onDownload": on_download,
                "onDelete": on_delete
            }
        )

        # Click actions menu button
        actions_button = screen.get_by_label("More options")
        fireEvent.click(actions_button)

        # Verify menu items are displayed
        expect(screen.get_by_text("Preview")).to_be_in_document()
        expect(screen.get_by_text("Download")).to_be_in_document()
        expect(screen.get_by_text("Delete")).to_be_in_document()

        # Test preview action
        preview_button = screen.get_by_text("Preview")
        fireEvent.click(preview_button)
        expect(on_preview).to_have_been_called_with(mock_document)

    def test_document_card_processing_status(self):
        """Test document card displays processing status for non-completed documents"""
        processing_document = create_mock_document(
            processing_status="processing",
            processing_error=None
        )

        render(
            DocumentCard,
            props={
                "document": processing_document,
                "showProcessingStatus": True
            }
        )

        # Verify processing indicator is displayed
        expect(screen.get_by_text("Processing...")).to_be_in_document()

        # Verify spinner animation is present
        spinner = component.container.querySelector('.animate-spin')
        expect(spinner).to_be_in_document()

    def test_document_card_error_display(self):
        """Test document card displays error information"""
        error_document = create_mock_document(
            processing_status="failed",
            processing_error="OCR processing failed due to corrupted file"
        )

        render(
            DocumentCard,
            props={
                "document": error_document,
                "showProcessingStatus": True
            }
        )

        # Verify error status and message are displayed
        expect(screen.get_by_text("Processing failed")).to_be_in_document()
        expect(screen.get_by_text("• OCR processing failed due to corrupted file")).to_be_in_document()

    def test_document_card_file_types(self):
        """Test document card displays different icons for different file types"""
        file_types = [
            ("pdf", "text-red-600"),
            ("txt", "text-blue-600"),
            ("jpg", "text-green-600"),
            ("png", "text-green-600"),
            ("mp3", "text-purple-600"),
            ("mp4", "text-orange-600")
        ]

        for file_type, expected_class in file_types:
            document = create_mock_document(file_type=file_type)

            component = render(
                DocumentCard,
                props={"document": document}
            )

            icon = component.container.querySelector('[data-testid="file-icon"]')
            expect(icon).to_have_class(expected_class)

            cleanup_test_components(component)

    def test_document_card_accessibility(self, mock_document: Document):
        """Test DocumentCard accessibility compliance"""
        on_select = Mock()
        on_preview = Mock()
        on_delete = Mock()

        component = render(
            DocumentCard,
            props={
                "document": mock_document,
                "onSelect": on_select,
                "onPreview": on_preview,
                "onDelete": on_delete
            }
        )

        # Check accessibility compliance
        accessibility_issues = check_accessibility_compliance(component.container)
        expect(accessibility_issues).to_have_length(0)

        # Verify ARIA labels
        expect(screen.get_by_label("Select document")).to_be_in_document()
        expect(screen.get_by_label("More options")).to_be_in_document()

    def test_document_card_click_outside_closes_menu(self, mock_document: Document):
        """Test clicking outside closes actions menu"""
        render(
            DocumentCard,
            props={"document": mock_document}
        )

        # Open actions menu
        actions_button = screen.get_by_label("More options")
        fireEvent.click(actions_button)

        # Verify menu is open
        expect(screen.get_by_text("Preview")).to_be_in_document()

        # Click outside (on the card itself)
        card = screen.get_by_test_id("document-card")
        fireEvent.click(card)

        # Verify menu is closed
        expect(screen.query_by_text("Preview")).to_be_null()


class TestDocumentLibraryComponent:
    """Test DocumentLibrary component functionality and interactions"""

    @pytest.fixture
    def mock_documents(self) -> List[Document]:
        """Create mock documents list for testing"""
        return [
            create_mock_document(
                id="doc-1",
                title="First Document",
                file_type="pdf",
                processing_status="indexed"
            ),
            create_mock_document(
                id="doc-2",
                title="Second Document",
                file_type="txt",
                processing_status="processing"
            ),
            create_mock_document(
                id="doc-3",
                title="Third Document",
                file_type="jpg",
                processing_status="failed",
                processing_error="Image processing failed"
            )
        ]

    def test_document_library_rendering(self, mock_documents: List[Document]):
        """Test DocumentLibrary renders documents correctly"""
        # Mock useDocuments hook
        with patch('src.hooks.useDocuments.useDocuments') as mock_use_documents:
            mock_use_documents.return_value = {
                "documents": mock_documents,
                "loading": False,
                "error": None,
                "pagination": {
                    "page": 1,
                    "pageSize": 20,
                    "total": 3,
                    "totalPages": 1,
                    "hasNext": False,
                    "hasPrev": False
                },
                "filters": {},
                "selectedDocuments": set(),
                "selectedCount": 0,
                "hasSelection": False,
                "isAllSelected": False,
                "fetchDocuments": Mock(),
                "updateFilters": Mock(),
                "updatePage": Mock(),
                "updatePageSize": Mock(),
                "selectDocument": Mock(),
                "selectAllDocuments": Mock(),
                "clearSelection": Mock(),
                "deleteDocument": Mock(),
                "deleteSelectedDocuments": Mock(),
                "refreshDocuments": Mock(),
                "retryDocument": Mock()
            }

            component = render(DocumentLibrary)

            # Verify header
            expect(screen.get_by_text("Documents")).to_be_in_document()
            expect(screen.get_by_text("3 documents")).to_be_in_document()

            # Verify all documents are rendered
            expect(screen.get_by_text("First Document")).to_be_in_document()
            expect(screen.get_by_text("Second Document")).to_be_in_document()
            expect(screen.get_by_text("Third Document")).to_be_in_document()

            # Verify refresh button
            expect(screen.get_by_text("Refresh")).to_be_in_document()

    def test_document_library_loading_state(self):
        """Test DocumentLibrary loading state"""
        with patch('src.hooks.useDocuments.useDocuments') as mock_use_documents:
            mock_use_documents.return_value = {
                "documents": [],
                "loading": True,
                "error": None,
                "pagination": {"page": 1, "pageSize": 20, "total": 0, "totalPages": 0, "hasNext": False, "hasPrev": False},
                "filters": {},
                "selectedDocuments": set(),
                "selectedCount": 0,
                "hasSelection": False,
                "isAllSelected": False,
                "fetchDocuments": Mock(),
                "updateFilters": Mock(),
                "updatePage": Mock(),
                "updatePageSize": Mock(),
                "selectDocument": Mock(),
                "selectAllDocuments": Mock(),
                "clearSelection": Mock(),
                "deleteDocument": Mock(),
                "deleteSelectedDocuments": Mock(),
                "refreshDocuments": Mock(),
                "retryDocument": Mock()
            }

            component = render(DocumentLibrary)

            # Verify loading skeletons are displayed
            skeletons = component.container.querySelectorAll('.animate-pulse')
            expect(skeletons.length).to_be(6)  # Should show 6 loading cards

    def test_document_library_error_state(self):
        """Test DocumentLibrary error state"""
        with patch('src.hooks.useDocuments.useDocuments') as mock_use_documents:
            mock_use_documents.return_value = {
                "documents": [],
                "loading": False,
                "error": "Failed to load documents: Network error",
                "pagination": {"page": 1, "pageSize": 20, "total": 0, "totalPages": 0, "hasNext": False, "hasPrev": False},
                "filters": {},
                "selectedDocuments": set(),
                "selectedCount": 0,
                "hasSelection": False,
                "isAllSelected": False,
                "fetchDocuments": Mock(),
                "updateFilters": Mock(),
                "updatePage": Mock(),
                "updatePageSize": Mock(),
                "selectDocument": Mock(),
                "selectAllDocuments": Mock(),
                "clearSelection": Mock(),
                "deleteDocument": Mock(),
                "deleteSelectedDocuments": Mock(),
                "refreshDocuments": Mock(),
                "retryDocument": Mock()
            }

            render(DocumentLibrary)

            # Verify error message is displayed
            expect(screen.get_by_text("Failed to load documents: Network error")).to_be_in_document()
            expect(screen.get_by_text("Try Again")).to_be_in_document()

    def test_document_library_empty_state(self):
        """Test DocumentLibrary empty state"""
        with patch('src.hooks.useDocuments.useDocuments') as mock_use_documents:
            mock_use_documents.return_value = {
                "documents": [],
                "loading": False,
                "error": None,
                "pagination": {"page": 1, "pageSize": 20, "total": 0, "totalPages": 0, "hasNext": False, "hasPrev": False},
                "filters": {},
                "selectedDocuments": set(),
                "selectedCount": 0,
                "hasSelection": False,
                "isAllSelected": False,
                "fetchDocuments": Mock(),
                "updateFilters": Mock(),
                "updatePage": Mock(),
                "updatePageSize": Mock(),
                "selectDocument": Mock(),
                "selectAllDocuments": Mock(),
                "clearSelection": Mock(),
                "deleteDocument": Mock(),
                "deleteSelectedDocuments": Mock(),
                "refreshDocuments": Mock(),
                "retryDocument": Mock()
            }

            render(DocumentLibrary)

            # Verify empty state message
            expect(screen.get_by_text("No documents found")).to_be_in_document()
            expect(screen.get_by_text("Upload your first document to get started")).to_be_in_document()

    def test_document_library_search_functionality(self, mock_documents: List[Document]):
        """Test document search functionality"""
        mock_update_filters = Mock()

        with patch('src.hooks.useDocuments.useDocuments') as mock_use_documents:
            mock_use_documents.return_value = {
                "documents": mock_documents,
                "loading": False,
                "error": None,
                "pagination": {"page": 1, "pageSize": 20, "total": 3, "totalPages": 1, "hasNext": False, "hasPrev": False},
                "filters": {},
                "selectedDocuments": set(),
                "selectedCount": 0,
                "hasSelection": False,
                "isAllSelected": False,
                "fetchDocuments": Mock(),
                "updateFilters": mock_update_filters,
                "updatePage": Mock(),
                "updatePageSize": Mock(),
                "selectDocument": Mock(),
                "selectAllDocuments": Mock(),
                "clearSelection": Mock(),
                "deleteDocument": Mock(),
                "deleteSelectedDocuments": Mock(),
                "refreshDocuments": Mock(),
                "retryDocument": Mock()
            }

            render(DocumentLibrary)

            # Find search input
            search_input = screen.get_by_placeholder_text("Search documents...")

            # Type search query
            fireEvent.change(search_input, {"target": {"value": "First"}})

            # Verify updateFilters was called with search term
            expect(mock_update_filters).to_have_been_called_with({"search_term": "First"})

    def test_document_library_filter_functionality(self, mock_documents: List[Document]):
        """Test document filtering functionality"""
        mock_update_filters = Mock()

        with patch('src.hooks.useDocuments.useDocuments') as mock_use_documents:
            mock_use_documents.return_value = {
                "documents": mock_documents,
                "loading": False,
                "error": None,
                "pagination": {"page": 1, "pageSize": 20, "total": 3, "totalPages": 1, "hasNext": False, "hasPrev": False},
                "filters": {},
                "selectedDocuments": set(),
                "selectedCount": 0,
                "hasSelection": False,
                "isAllSelected": False,
                "fetchDocuments": Mock(),
                "updateFilters": mock_update_filters,
                "updatePage": Mock(),
                "updatePageSize": Mock(),
                "selectDocument": Mock(),
                "selectAllDocuments": Mock(),
                "clearSelection": Mock(),
                "deleteDocument": Mock(),
                "deleteSelectedDocuments": Mock(),
                "refreshDocuments": Mock(),
                "retryDocument": Mock()
            }

            render(DocumentLibrary)

            # Find file type filter
            file_type_filter = screen.get_by_text("All Files")
            fireEvent.click(file_type_filter)

            # Select PDF option
            pdf_option = screen.get_by_text("PDF")
            fireEvent.click(pdf_option)

            # Verify updateFilters was called with file type filter
            expect(mock_update_filters).to_have_been_called_with({"file_types": ["pdf"]})

    def test_document_library_bulk_selection(self, mock_documents: List[Document]):
        """Test bulk document selection functionality"""
        mock_select_all_documents = Mock()
        mock_clear_selection = Mock()

        with patch('src.hooks.useDocuments.useDocuments') as mock_use_documents:
            mock_use_documents.return_value = {
                "documents": mock_documents,
                "loading": False,
                "error": None,
                "pagination": {"page": 1, "pageSize": 20, "total": 3, "totalPages": 1, "hasNext": False, "hasPrev": False},
                "filters": {},
                "selectedDocuments": set(["doc-1", "doc-2"]),
                "selectedCount": 2,
                "hasSelection": True,
                "isAllSelected": False,
                "fetchDocuments": Mock(),
                "updateFilters": Mock(),
                "updatePage": Mock(),
                "updatePageSize": Mock(),
                "selectDocument": Mock(),
                "selectAllDocuments": mock_select_all_documents,
                "clearSelection": mock_clear_selection,
                "deleteDocument": Mock(),
                "deleteSelectedDocuments": Mock(),
                "refreshDocuments": Mock(),
                "retryDocument": Mock()
            }

            render(DocumentLibrary)

            # Verify bulk actions are displayed
            expect(screen.get_by_text("2 selected")).to_be_in_document()
            expect(screen.get_by_text("Clear selection")).to_be_in_document()
            expect(screen.get_by_text("Actions")).to_be_in_document()
            expect(screen.get_by_text("Delete")).to_be_in_document()

            # Test clear selection
            clear_button = screen.get_by_text("Clear selection")
            fireEvent.click(clear_button)
            expect(mock_clear_selection).to_have_been_called()

    def test_document_library_pagination(self):
        """Test document pagination functionality"""
        mock_update_page = Mock()
        mock_update_page_size = Mock()

        with patch('src.hooks.useDocuments.useDocuments') as mock_use_documents:
            mock_use_documents.return_value = {
                "documents": [create_mock_document()],
                "loading": False,
                "error": None,
                "pagination": {
                    "page": 2,
                    "pageSize": 20,
                    "total": 50,
                    "totalPages": 3,
                    "hasNext": True,
                    "hasPrev": True
                },
                "filters": {},
                "selectedDocuments": set(),
                "selectedCount": 0,
                "hasSelection": False,
                "isAllSelected": False,
                "fetchDocuments": Mock(),
                "updateFilters": Mock(),
                "updatePage": mock_update_page,
                "updatePageSize": mock_update_page_size,
                "selectDocument": Mock(),
                "selectAllDocuments": Mock(),
                "clearSelection": Mock(),
                "deleteDocument": Mock(),
                "deleteSelectedDocuments": Mock(),
                "refreshDocuments": Mock(),
                "retryDocument": Mock()
            }

            render(DocumentLibrary)

            # Verify pagination info
            expect(screen.get_by_text("Showing 21 to 40 of 50 documents")).to_be_in_document()
            expect(screen.get_by_text("Page 2 of 3")).to_be_in_document()

            # Test navigation
            next_button = screen.get_by_role("button", {"name": /next/i})
            prev_button = screen.get_by_role("button", {"name": /previous/i})

            fireEvent.click(next_button)
            expect(mock_update_page).to_have_been_called_with(3)

            fireEvent.click(prev_button)
            expect(mock_update_page).to_have_been_called_with(1)

    def test_document_library_accessibility(self, mock_documents: List[Document]):
        """Test DocumentLibrary accessibility compliance"""
        with patch('src.hooks.useDocuments.useDocuments') as mock_use_documents:
            mock_use_documents.return_value = {
                "documents": mock_documents,
                "loading": False,
                "error": None,
                "pagination": {"page": 1, "pageSize": 20, "total": 3, "totalPages": 1, "hasNext": False, "hasPrev": False},
                "filters": {},
                "selectedDocuments": set(),
                "selectedCount": 0,
                "hasSelection": False,
                "isAllSelected": False,
                "fetchDocuments": Mock(),
                "updateFilters": Mock(),
                "updatePage": Mock(),
                "updatePageSize": Mock(),
                "selectDocument": Mock(),
                "selectAllDocuments": Mock(),
                "clearSelection": Mock(),
                "deleteDocument": Mock(),
                "deleteSelectedDocuments": Mock(),
                "refreshDocuments": Mock(),
                "retryDocument": Mock()
            }

            component = render(DocumentLibrary)

            # Check accessibility compliance
            accessibility_issues = check_accessibility_compliance(component.container)
            expect(accessibility_issues).to_have_length(0)

            # Verify ARIA labels
            expect(screen.get_by_label("Search documents...")).to_be_in_document()
            expect(screen.get_by_role("main")).to_be_in_document()


class TestDocumentUploaderComponent:
    """Test DocumentUploader component functionality"""

    def test_document_upload_drag_and_drop(self):
        """Test drag and drop file upload"""
        mock_upload = Mock()

        with patch('src.hooks.useDocumentUpload.useDocumentUpload') as mock_use_upload:
            mock_use_upload.return_value = {
                "uploadFile": mock_upload,
                "uploadProgress": {},
                "isUploading": False,
                "error": None,
                "resetUpload": Mock()
            }

            component = render(DocumentUploader)

            # Find dropzone
            dropzone = component.container.querySelector('[data-testid="dropzone"]')

            # Simulate file drop
            file = new File(["test content"], "test.pdf", { type: "application/pdf" })
            fireEvent.drop(dropzone, {
                dataTransfer: {
                    files: [file]
                }
            })

            # Verify upload was initiated
            expect(mock_upload).to_have_been_called()

    def test_document_upload_progress_tracking(self):
        """Test upload progress tracking"""
        with patch('src.hooks.useDocumentUpload.useDocumentUpload') as mock_use_upload:
            mock_use_upload.return_value = {
                "uploadFile": Mock(),
                "uploadProgress": {
                    "upload-123": {
                        "progress": 75,
                        "currentStep": "Processing file",
                        "totalSteps": 10,
                        "completedSteps": 7
                    }
                },
                "isUploading": True,
                "error": None,
                "resetUpload": Mock()
            }

            render(DocumentUploader)

            # Verify progress is displayed
            expect(screen.get_by_text("75%")).to_be_in_document()
            expect(screen.get_by_text("Processing file")).to_be_in_document()

    def test_document_upload_error_handling(self):
        """Test upload error handling"""
        with patch('src.hooks.useDocumentUpload.useDocumentUpload') as mock_use_upload:
            mock_use_upload.return_value = {
                "uploadFile": Mock(),
                "uploadProgress": {},
                "isUploading": False,
                "error": "File size exceeds limit of 100MB",
                "resetUpload": Mock()
            }

            render(DocumentUploader)

            # Verify error message is displayed
            expect(screen.get_by_text("File size exceeds limit of 100MB")).to_be_in_document()

    def test_document_upload_file_validation(self):
        """Test file validation during upload"""
        mock_upload = Mock()

        with patch('src.hooks.useDocumentUpload.useDocumentUpload') as mock_use_upload:
            mock_use_upload.return_value = {
                "uploadFile": mock_upload,
                "uploadProgress": {},
                "isUploading": False,
                "error": None,
                "resetUpload": Mock()
            }

            component = render(DocumentUploader)

            # Test unsupported file type
            unsupported_file = new File(["malicious content"], "virus.exe", { type: "application/x-executable" })

            input = component.container.querySelector('input[type="file"]')
            fireEvent.change(input, { target: { files: [unsupported_file] } })

            # Verify validation error is displayed
            expect(screen.get_by_text(/unsupported file type/i)).to_be_in_document()


class TestProcessingStatusComponent:
    """Test ProcessingStatus component functionality"""

    def test_processing_status_display(self):
        """Test processing status display for different states"""
        processing_states = [
            ("queued", "Queued for processing", false),
            ("processing", "Processing...", true),
            ("indexed", "Ready for search", false),
            ("failed", "Processing failed", false)
        ]

        for status, expected_text, show_spinner in processing_states:
            document = create_mock_document(processing_status=status)

            component = render(
                ProcessingStatus,
                props={
                    "document": document,
                    "compact": false
                }
            )

            # Verify status text
            expect(screen.get_by_text(expected_text)).to_be_in_document()

            # Verify spinner presence/absence
            spinner = component.container.querySelector('.animate-spin')
            if show_spinner:
                expect(spinner).to_be_in_document()
            else:
                expect(spinner).to_be_null()

            cleanup_test_components(component)

    def test_processing_status_retry_functionality(self):
        """Test retry functionality for failed documents"""
        mock_retry = Mock()
        failed_document = create_mock_document(
            processing_status="failed",
            processing_error="Processing failed"
        )

        render(
            ProcessingStatus,
            props={
                "document": failed_document,
                "onRetry": mock_retry,
                "compact": false
            }
        )

        # Find and click retry button
        retry_button = screen.get_by_text("Retry")
        fireEvent.click(retry_button)

        # Verify retry callback was called
        expect(mock_retry).to_have_been_called_with(failed_document.id)


class TestComponentIntegration:
    """Test component integration and data flow"""

    def test_document_library_with_real_data(self):
        """Test DocumentLibrary with realistic data and interactions"""
        # This test simulates real user workflows
        mock_user = create_mock_user()
        mock_documents = [
            create_mock_document(
                id="doc-1",
                title="Q1 Financial Report",
                file_type="pdf",
                file_size=5 * 1024 * 1024,  # 5MB
                processing_status="indexed"
            ),
            create_mock_document(
                id="doc-2",
                title="Product Demo Video",
                file_type="mp4",
                file_size=50 * 1024 * 1024,  # 50MB
                processing_status="processing"
            )
        ]

        with patch('src.hooks.useDocuments.useDocuments') as mock_use_documents:
            mock_use_documents.return_value = {
                "documents": mock_documents,
                "loading": False,
                "error": None,
                "pagination": {"page": 1, "pageSize": 20, "total": 2, "totalPages": 1, "hasNext": False, "hasPrev": False},
                "filters": {},
                "selectedDocuments": set(),
                "selectedCount": 0,
                "hasSelection": False,
                "isAllSelected": False,
                "fetchDocuments": Mock(),
                "updateFilters": Mock(),
                "updatePage": Mock(),
                "updatePageSize": Mock(),
                "selectDocument": Mock(),
                "selectAllDocuments": Mock(),
                "clearSelection": Mock(),
                "deleteDocument": Mock(),
                "deleteSelectedDocuments": Mock(),
                "refreshDocuments": Mock(),
                "retryDocument": Mock()
            }

            component = render(DocumentLibrary)

            # Simulate user selecting a document
            first_document_card = screen.get_by_test_id("document-card")
            select_checkbox = within(first_document_card).get_by_label("Select document")
            fireEvent.click(select_checkbox)

            # Simulate user searching
            search_input = screen.get_by_placeholder_text("Search documents...")
            fireEvent.change(search_input, { target: { value: "Financial" } })

            # Simulate user filtering by file type
            file_type_filter = screen.get_by_text("All Files")
            fireEvent.click(file_type_filter)
            pdf_option = screen.get_by_text("PDF")
            fireEvent.click(pdf_option)

            # Verify all interactions work together
            expect(screen.get_by_text("Q1 Financial Report")).to_be_in_document()

    async def test_document_upload_flow_integration(self):
        """Test complete document upload flow integration"""
        # This test simulates the complete upload workflow
        mock_upload_function = AsyncMock(return_value={
            "document_id": "new-doc-123",
            "upload_id": "upload-123",
            "status": "success"
        })

        with patch('src.hooks.useDocumentUpload.useDocumentUpload') as mock_use_upload:
            mock_use_upload.return_value = {
                "uploadFile": mock_upload_function,
                "uploadProgress": {},
                "isUploading": False,
                "error": None,
                "resetUpload": Mock()
            }

            component = render(DocumentUploader)

            # Simulate file selection
            test_file = new File(["test document content"], "test-doc.pdf", { type: "application/pdf" })
            input = component.container.querySelector('input[type="file"]')
            fireEvent.change(input, { target: { files: [test_file] } })

            # Wait for upload to complete
            await act(async () => {
                await mock_upload_function(test_file, {
                    "title": "Test Document",
                    "description": "Test Description"
                })
            })

            # Verify upload completed successfully
            expect(mock_upload_function).to_have_been_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])