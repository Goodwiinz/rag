"""
Document management and processing services
"""

from .file_service import FileService, FileValidationError
from .file_service import FileStorageError as FileStorageErrorBase
from .enhanced_file_service import (
    EnhancedFileService,
    EnhancedFileValidationError,
    SecurityScanError,
    FileIntegrityError,
    SecurityThreat,
)
from .enhanced_file_service import FileStorageError as EnhancedFileStorageError
from .document_management import DocumentUploadRequest, DocumentUpdateRequest, DocumentListRequest
from .document_quality_service import DocumentQualityService, QualityIssue
from .document_realtime_service import DocumentRealtimeService, ProcessingEventType, ProcessingEvent
from .document_upload_service import DocumentUploadService
from .enhanced_document_processing_service import (
    EnhancedDocumentProcessingService,
    ProcessingResult,
    MultimodalProcessor,
    EntityExtractor,
)

__all__ = [
    # File service
    "FileService",
    "FileValidationError",
    "FileStorageErrorBase",
    # Enhanced file service
    "EnhancedFileService",
    "EnhancedFileValidationError",
    "SecurityScanError",
    "EnhancedFileStorageError",
    "FileIntegrityError",
    "SecurityThreat",
    # Document management
    "DocumentUploadRequest",
    "DocumentUpdateRequest",
    "DocumentListRequest",
    # Document quality
    "DocumentQualityService",
    "QualityIssue",
    # Document realtime
    "DocumentRealtimeService",
    "ProcessingEventType",
    "ProcessingEvent",
    # Document upload
    "DocumentUploadService",
    # Enhanced processing
    "EnhancedDocumentProcessingService",
    "ProcessingResult",
    "MultimodalProcessor",
    "EntityExtractor",
]
