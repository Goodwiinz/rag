"""
Documents API routes for document management, file handling, and processing
"""

from .documents import router as documents_router
from .files import router as files_router
from .integrity import router as integrity_router
from .processing import router as processing_router

# document_upload provides upload utilities, not a router

__all__ = ["documents_router", "files_router", "integrity_router", "processing_router"]
