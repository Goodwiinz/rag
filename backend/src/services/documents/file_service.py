"""
File handling and storage service
"""

import hashlib
import logging
import mimetypes
import os
import time
import uuid
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional

import aiofiles
import magic
from fastapi import Depends, HTTPException, UploadFile, status
from PIL import Image
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Optional pandas import for spreadsheet processing
try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    PANDAS_AVAILABLE = False

from src.core.config import settings
from src.core.database import get_db
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.organization import Organization
from src.models.processing import JobPriority, JobStatus, JobType, ProcessingJob
from src.models.user import User, UserRole

logger = logging.getLogger(__name__)


class FileValidationError(Exception):
    """File validation related errors"""

    pass


class FileStorageError(Exception):
    """File storage related errors"""

    pass


class FileService:
    """Service for handling file uploads, validation, and storage"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for different file types
        self.create_subdirectories()

    def create_subdirectories(self):
        """Create subdirectories for different file types"""
        subdirs = ["documents", "images", "audio", "video", "temp", "processed"]

        for subdir in subdirs:
            (self.upload_dir / subdir).mkdir(parents=True, exist_ok=True)

    def get_file_type(self, filename: str, content: bytes = None) -> DocumentType:
        """Determine document type based on file extension and content"""
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(filename)

        # Use python-magic for more accurate detection if content is available
        if content:
            try:
                mime_type = magic.from_buffer(content, mime=True)
            except (OSError, ValueError) as e:
                logger.debug(f"Magic MIME detection failed: {e}")

        # Map MIME types to document types
        if mime_type:
            if mime_type.startswith("text/"):
                return DocumentType.TEXT
            elif mime_type.startswith("image/"):
                return DocumentType.IMAGE
            elif mime_type.startswith("audio/"):
                return DocumentType.AUDIO
            elif mime_type.startswith("video/"):
                return DocumentType.VIDEO
            elif mime_type == "application/pdf":
                return DocumentType.PDF
            elif mime_type in [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
            ]:
                return DocumentType.SPREADSHEET
            elif mime_type in [
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "application/vnd.ms-powerpoint",
            ]:
                return DocumentType.PRESENTATION
            elif mime_type in [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
            ]:
                return DocumentType.TEXT

        # Fallback to extension-based detection
        ext = Path(filename).suffix.lower()

        if ext in [".txt", ".md", ".rst", ".log"]:
            return DocumentType.TEXT
        elif ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]:
            return DocumentType.IMAGE
        elif ext in [".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"]:
            return DocumentType.AUDIO
        elif ext in [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"]:
            return DocumentType.VIDEO
        elif ext == ".pdf":
            return DocumentType.PDF
        elif ext in [".xlsx", ".xls", ".csv"]:
            return DocumentType.SPREADSHEET
        elif ext in [".pptx", ".ppt"]:
            return DocumentType.PRESENTATION
        elif ext in [".docx", ".doc"]:
            return DocumentType.TEXT

        return DocumentType.MULTIMODAL  # Default for unknown types

    def validate_file(
        self, file: UploadFile, user: User, organization: Organization
    ) -> Dict[str, Any]:
        """Validate uploaded file"""
        # Check file size
        if hasattr(file, "size") and file.size:
            file_size = file.size
        else:
            # Read content to get size if not available
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset position

        if file_size > organization.max_file_size_bytes:
            raise FileValidationError(
                f"File size ({file_size} bytes) exceeds maximum allowed size "
                f"({organization.max_file_size_bytes} bytes)"
            )

        # Check storage quota
        if not organization.can_upload_file(file_size):
            raise FileValidationError(
                f"Insufficient storage quota. Available: "
                f"{organization.storage_available_gb:.2f}GB"
            )

        # Check file extension
        allowed_extensions = [
            ".txt",
            ".md",
            ".pdf",
            ".docx",
            ".doc",
            ".xlsx",
            ".xls",
            ".csv",
            ".pptx",
            ".ppt",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".tiff",
            ".mp3",
            ".wav",
            ".ogg",
            ".flac",
            ".aac",
            ".m4a",
            ".mp4",
            ".avi",
            ".mkv",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".zip",
            ".rar",
        ]

        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise FileValidationError(f"File extension '{file_ext}' is not allowed")

        # Read content for type detection
        file_content = file.file.read(min(file_size, 8192))  # Read first 8KB
        file.file.seek(0)  # Reset position

        # Determine document type
        document_type = self.get_file_type(file.filename, file_content)

        return {
            "file_size": file_size,
            "document_type": document_type,
            "mime_type": mimetypes.guess_type(file.filename)[0],
        }

    def generate_file_path(
        self, document_type: DocumentType, organization_id: str
    ) -> str:
        """Generate unique file path for uploaded file"""
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())

        type_dir = {
            DocumentType.TEXT: "documents",
            DocumentType.PDF: "documents",
            DocumentType.SPREADSHEET: "documents",
            DocumentType.PRESENTATION: "documents",
            DocumentType.IMAGE: "images",
            DocumentType.AUDIO: "audio",
            DocumentType.VIDEO: "video",
            DocumentType.MULTIMODAL: "documents",
        }

        directory = type_dir.get(document_type, "documents")
        filename = f"{timestamp}_{unique_id}"

        return str(self.upload_dir / directory / f"{organization_id}" / filename)

    async def save_file(self, file: UploadFile, file_path: str) -> str:
        """Save uploaded file to disk"""
        try:
            # Ensure directory exists
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

            # Save file asynchronously
            async with aiofiles.open(file_path, "wb") as f:
                content = await file.read()
                await f.write(content)

            return file_path

        except Exception as e:
            # Clean up on failure
            if os.path.exists(file_path):
                os.remove(file_path)
            raise FileStorageError(f"Failed to save file: {str(e)}")

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    async def upload_file(
        self,
        file: UploadFile,
        title: str,
        user: User,
        organization: Organization,
        tags: List[str] = None,
        is_public: bool = False,
    ) -> Document:
        """Process and store uploaded file"""
        try:
            # Validate file
            validation_result = self.validate_file(file, user, organization)

            # Generate file path
            file_path = self.generate_file_path(
                validation_result["document_type"], str(organization.id)
            )

            # Add original extension to file path
            original_ext = Path(file.filename).suffix
            file_path_with_ext = f"{file_path}{original_ext}"

            # Save file
            saved_path = await self.save_file(file, file_path_with_ext)

            # Calculate file hash
            file_hash = self.calculate_file_hash(saved_path)

            # Create document record
            document = Document(
                title=title,
                filename=file.filename,
                file_path=saved_path,
                file_size_bytes=validation_result["file_size"],
                mime_type=validation_result["mime_type"],
                document_type=validation_result["document_type"],
                processing_status=ProcessingStatus.PENDING,
                is_public=is_public,
                tags=tags or [],
                organization_id=organization.id,
                uploaded_by_user_id=user.id,
            )

            # Add file hash as metadata
            document.add_metadata("file_hash", file_hash)
            document.add_metadata("original_filename", file.filename)

            self.db.add(document)
            await self.db.commit()
            await self.db.refresh(document)

            # Update organization storage usage
            organization.update_storage_usage(validation_result["file_size"])
            await self.db.commit()

            # Create processing job for document ingestion
            processing_job = ProcessingJob(
                job_type=JobType.DOCUMENT_INGESTION,
                status=JobStatus.PENDING,
                priority=JobPriority.NORMAL,
                document_id=document.id,
                organization_id=organization.id,
                created_by_user_id=user.id,
                parameters={
                    "document_id": str(document.id),
                    "file_path": document.file_path,
                    "document_type": document.document_type.value,
                    "mime_type": document.mime_type,
                },
                config={"max_retries": 3, "timeout_seconds": 300},
                total_steps=5,  # Text extraction, entity extraction, embedding, indexing, quality check
                queue_name="document_processing",
            )

            self.db.add(processing_job)
            await self.db.commit()
            await self.db.refresh(processing_job)

            # Queue the job for processing
            from src.tasks.processing_tasks import process_document_ingestion

            process_document_ingestion.delay(str(processing_job.id))

            return document

        except Exception as e:
            await self.db.rollback()
            raise FileStorageError(f"Failed to upload file: {str(e)}")

    def extract_text_content(self, document: Document) -> str:
        """Extract text content from document"""
        try:
            file_path = document.file_path

            if document.document_type == DocumentType.TEXT:
                # Simple text file
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()

            elif document.document_type == DocumentType.PDF:
                # PDF file
                text = []
                with open(file_path, "rb") as file:
                    pdf_reader = PdfReader(file)
                    for page in pdf_reader.pages:
                        text.append(page.extract_text())
                return "\n".join(text)

            elif document.document_type in [DocumentType.SPREADSHEET]:
                # Excel file - process if pandas is available
                if not PANDAS_AVAILABLE:
                    logger.warning(
                        "Pandas not available, skipping spreadsheet processing"
                    )
                    return "Spreadsheet processing not available"
                try:
                    if file_path.endswith(".csv"):
                        df = pd.read_csv(file_path)
                    else:
                        df = pd.read_excel(file_path)
                    return df.to_string()
                except Exception as e:
                    logger.warning(f"Spreadsheet processing failed: {str(e)}")
                    return ""

            elif document.document_type == DocumentType.PRESENTATION:
                # PowerPoint file (basic extraction)
                try:
                    from pptx import Presentation

                    prs = Presentation(file_path)
                    text = []
                    for slide in prs.slides:
                        for shape in slide.shapes:
                            if hasattr(shape, "text"):
                                text.append(shape.text)
                    return "\n".join(text)
                except (ImportError, ValueError, IOError) as e:
                    logger.warning(f"Failed to extract text from PowerPoint: {e}")
                    return ""

            elif document.document_type == DocumentType.IMAGE:
                # For images, we could use OCR here (integrate with Tesseract)
                return ""

            else:
                return ""

        except Exception as e:
            return f"Error extracting text: {str(e)}"

    def extract_metadata(self, document: Document) -> Dict[str, Any]:
        """Extract metadata from document"""
        metadata = {}

        try:
            file_path = document.file_path

            if document.document_type == DocumentType.IMAGE:
                # Image metadata
                with Image.open(file_path) as img:
                    metadata.update(
                        {
                            "width": img.width,
                            "height": img.height,
                            "format": img.format,
                            "mode": img.mode,
                        }
                    )

            elif document.document_type == DocumentType.PDF:
                # PDF metadata
                with open(file_path, "rb") as file:
                    pdf_reader = PdfReader(file)
                    if pdf_reader.metadata:
                        metadata.update(
                            {
                                "title": pdf_reader.metadata.get("/Title", ""),
                                "author": pdf_reader.metadata.get("/Author", ""),
                                "subject": pdf_reader.metadata.get("/Subject", ""),
                                "creator": pdf_reader.metadata.get("/Creator", ""),
                                "producer": pdf_reader.metadata.get("/Producer", ""),
                                "creation_date": str(
                                    pdf_reader.metadata.get("/CreationDate", "")
                                ),
                                "modification_date": str(
                                    pdf_reader.metadata.get("/ModDate", "")
                                ),
                            }
                        )
                    metadata["page_count"] = len(pdf_reader.pages)

            elif document.document_type in [
                DocumentType.SPREADSHEET,
                DocumentType.PRESENTATION,
            ]:
                # Excel/PowerPoint metadata (basic)
                file_stat = os.stat(file_path)
                metadata.update(
                    {
                        "size": file_stat.st_size,
                        "created": file_stat.st_ctime,
                        "modified": file_stat.st_mtime,
                    }
                )

        except Exception as e:
            metadata["extraction_error"] = str(e)

        return metadata

    async def delete_file(self, document: Document, user: User) -> bool:
        """Delete file and update storage"""
        try:
            # Check permissions
            if document.uploaded_by_user_id != user.id and not user.has_permission(
                UserRole.ADMIN
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Can only delete your own files or require admin role",
                )

            # Delete physical file
            if os.path.exists(document.file_path):
                os.remove(document.file_path)

            # Soft delete document record
            document.soft_delete()

            # Update organization storage usage
            organization = document.organization
            organization.update_storage_usage(-document.file_size_bytes)
            await self.db.commit()

            return True

        except Exception as e:
            await self.db.rollback()
            raise FileStorageError(f"Failed to delete file: {str(e)}")

    async def get_file_stats(self, organization_id: str) -> Dict[str, Any]:
        """Get file statistics for organization"""
        from sqlalchemy import func

        # Total files by type
        files_by_type_stmt = (
            select(
                Document.document_type,
                func.count(Document.id).label("count"),
                func.sum(Document.file_size_bytes).label("total_size"),
            )
            .where(
                Document.organization_id == organization_id,
                Document.is_deleted == False,
            )
            .group_by(Document.document_type)
        )
        files_by_type_result = await self.db.execute(files_by_type_stmt)
        files_by_type = files_by_type_result.all()

        # Processing status distribution
        processing_stats_stmt = (
            select(Document.processing_status, func.count(Document.id).label("count"))
            .where(
                Document.organization_id == organization_id,
                Document.is_deleted == False,
            )
            .group_by(Document.processing_status)
        )
        processing_stats_result = await self.db.execute(processing_stats_stmt)
        processing_stats = processing_stats_result.all()

        return {
            "files_by_type": [
                {
                    "type": stat.document_type.value,
                    "count": stat.count,
                    "total_size_mb": stat.total_size / (1024 * 1024)
                    if stat.total_size
                    else 0,
                }
                for stat in files_by_type
            ],
            "processing_stats": [
                {"status": stat.processing_status.value, "count": stat.count}
                for stat in processing_stats
            ],
        }


def get_file_service(db: AsyncSession = Depends(get_db)) -> FileService:
    """Get file service instance"""
    return FileService(db)
