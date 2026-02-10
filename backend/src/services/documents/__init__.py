"""Document management and processing services.

This package intentionally uses lazy imports to avoid circular import chains
between document upload and processing modules during app/test startup.
"""

from importlib import import_module
from typing import Dict, Tuple

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

_EXPORTS: Dict[str, Tuple[str, str]] = {
    # File service
    "FileService": ("src.services.documents.file_service", "FileService"),
    "FileValidationError": ("src.services.documents.file_service", "FileValidationError"),
    "FileStorageErrorBase": ("src.services.documents.file_service", "FileStorageError"),
    # Enhanced file service
    "EnhancedFileService": ("src.services.documents.enhanced_file_service", "EnhancedFileService"),
    "EnhancedFileValidationError": (
        "src.services.documents.enhanced_file_service",
        "EnhancedFileValidationError",
    ),
    "SecurityScanError": ("src.services.documents.enhanced_file_service", "SecurityScanError"),
    "EnhancedFileStorageError": ("src.services.documents.enhanced_file_service", "FileStorageError"),
    "FileIntegrityError": ("src.services.documents.enhanced_file_service", "FileIntegrityError"),
    "SecurityThreat": ("src.services.documents.enhanced_file_service", "SecurityThreat"),
    # Document management
    "DocumentUploadRequest": ("src.services.documents.document_management", "DocumentUploadRequest"),
    "DocumentUpdateRequest": ("src.services.documents.document_management", "DocumentUpdateRequest"),
    "DocumentListRequest": ("src.services.documents.document_management", "DocumentListRequest"),
    # Document quality
    "DocumentQualityService": ("src.services.documents.document_quality_service", "DocumentQualityService"),
    "QualityIssue": ("src.services.documents.document_quality_service", "QualityIssue"),
    # Document realtime
    "DocumentRealtimeService": ("src.services.documents.document_realtime_service", "DocumentRealtimeService"),
    "ProcessingEventType": ("src.services.documents.document_realtime_service", "ProcessingEventType"),
    "ProcessingEvent": ("src.services.documents.document_realtime_service", "ProcessingEvent"),
    # Document upload
    "DocumentUploadService": ("src.services.documents.document_upload_service", "DocumentUploadService"),
    # Enhanced processing
    "EnhancedDocumentProcessingService": (
        "src.services.documents.enhanced_document_processing_service",
        "EnhancedDocumentProcessingService",
    ),
    "ProcessingResult": ("src.services.documents.enhanced_document_processing_service", "ProcessingResult"),
    "MultimodalProcessor": ("src.services.documents.enhanced_document_processing_service", "MultimodalProcessor"),
    "EntityExtractor": ("src.services.documents.enhanced_document_processing_service", "EntityExtractor"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_path, attr_name = _EXPORTS[name]
    module = import_module(module_path)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
