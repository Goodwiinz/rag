"""
Document Management Service - Port 8001
Handles file upload, metadata management, storage quota enforcement, and document lifecycle
"""

import asyncio
import hashlib
import json
import mimetypes
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional

import aiofiles
import redis.asyncio as redis
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.models.document import Document
from src.models.document import DocumentType as DocType
from src.models.document import ProcessingStatus as ProcStatus
from src.models.organization import Organization, StorageTier
from src.shared.exceptions import (
    BaseCustomException,
    ConflictError,
    FileUploadError,
    NotFoundError,
    StorageQuotaError,
    ValidationError,
    handle_exceptions,
)
from src.shared.schemas import (
    BaseResponse,
    DocumentDetailResponse,
    DocumentMetadata,
    DocumentResponse,
    DocumentType,
    ErrorResponse,
    HealthCheckResponse,
    PaginatedResponse,
    PaginationRequest,
    ProcessingStatus,
    ProcessingStatusResponse,
)
from src.shared.utils import (
    CorrelationIdMiddleware,
    EventLogger,
    HealthChecker,
    MetricsCollector,
    format_file_size,
    paginate_query,
    sanitize_filename,
    validate_mime_type,
)

# Configuration
DOCUMENT_SERVICE_CONFIG = {
    "service_name": "document-management",
    "version": "1.0.0",
    "port": 8001,
    "host": "0.0.0.0",  # nosec B104 - containerized deployment
    "upload_dir": settings.UPLOAD_DIR,
    "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
    "allowed_mime_types": {
        # Text documents
        DocumentType.TEXT: ["text/plain", "text/csv", "text/markdown"],
        DocumentType.PDF: ["application/pdf"],
        DocumentType.SPREADSHEET: [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv",
        ],
        DocumentType.PRESENTATION: [
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ],
        # Images
        DocumentType.IMAGE: [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/gif",
            "image/bmp",
            "image/tiff",
            "image/webp",
            "image/svg+xml",
        ],
        # Audio
        DocumentType.AUDIO: [
            "audio/mpeg",
            "audio/mp3",
            "audio/wav",
            "audio/ogg",
            "audio/m4a",
            "audio/flac",
            "audio/aac",
        ],
        # Video
        DocumentType.VIDEO: [
            "video/mp4",
            "video/avi",
            "video/mov",
            "video/wmv",
            "video/flv",
            "video/webm",
            "video/mkv",
            "video/3gp",
        ],
    },
}

# Initialize FastAPI app
app = FastAPI(
    title="Document Management Service",
    version=DOCUMENT_SERVICE_CONFIG["version"],
    description="Service for managing document upload, storage, and metadata",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(CorrelationIdMiddleware)

# Initialize components
event_logger = EventLogger(DOCUMENT_SERVICE_CONFIG["service_name"])
health_checker = HealthChecker(DOCUMENT_SERVICE_CONFIG["service_name"])
metrics = MetricsCollector(DOCUMENT_SERVICE_CONFIG["service_name"])

# Initialize Redis for caching
cache = redis.from_url(settings.REDIS_URL, decode_responses=True)

# Ensure upload directory exists
os.makedirs(DOCUMENT_SERVICE_CONFIG["upload_dir"], exist_ok=True)


class DocumentUploadRequest(BaseModel):
    """Document upload request"""

    title: str = Field(..., min_length=1, max_length=500)
    tags: List[str] = Field(default_factory=list)
    is_public: bool = False
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentUpdateRequest(BaseModel):
    """Document update request"""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    custom_metadata: Optional[Dict[str, Any]] = None


class DocumentListRequest(PaginationRequest):
    """Document list request with filters"""

    document_type: Optional[DocumentType] = None
    processing_status: Optional[ProcessingStatus] = None
    tags: Optional[List[str]] = None
    search: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    is_public: Optional[bool] = None


def get_document_type_from_mime(mime_type: str) -> DocumentType:
    """Get document type from MIME type"""
    for doc_type, allowed_mimes in DOCUMENT_SERVICE_CONFIG[
        "allowed_mime_types"
    ].items():
        if mime_type in allowed_mimes:
            return doc_type
    return DocumentType.MULTIMODAL


def validate_file_upload(file: UploadFile) -> tuple[DocumentType, bool]:
    """Validate uploaded file"""
    # Check file size
    if (
        file.size
        and file.size > DOCUMENT_SERVICE_CONFIG["max_file_size_mb"] * 1024 * 1024
    ):
        raise FileUploadError(
            message=f"File size exceeds maximum limit of {DOCUMENT_SERVICE_CONFIG['max_file_size_mb']}MB",
            filename=file.filename,
            file_size=file.size,
        )

    # Get MIME type
    mime_type = (
        file.content_type
        or mimetypes.guess_type(file.filename)[0]
        or "application/octet-stream"
    )

    # Determine document type
    document_type = get_document_type_from_mime(mime_type)

    return document_type, mime_type


async def calculate_file_hash(file_content: bytes) -> str:
    """Calculate SHA-256 hash of file content"""
    return hashlib.sha256(file_content).hexdigest()


async def check_storage_quota(
    db: AsyncSession, organization_id: uuid.UUID, additional_size: int
) -> tuple[bool, int, int]:
    """Check if organization has sufficient storage quota"""
    # Get organization info
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()

    if not organization:
        raise NotFoundError("Organization not found", resource_type="organization")

    # Calculate current storage usage
    result = await db.execute(
        select(func.coalesce(func.sum(Document.file_size_bytes), 0)).where(
            and_(
                Document.organization_id == organization_id,
                Document.is_deleted == False,
            )
        )
    )
    current_usage = result.scalar() or 0

    # Check quota
    quota_limit = organization.storage_limit_bytes
    new_usage = current_usage + additional_size

    has_quota = new_usage <= quota_limit

    return has_quota, current_usage, quota_limit


async def save_uploaded_file(
    file: UploadFile, organization_id: uuid.UUID, document_id: uuid.UUID
) -> str:
    """Save uploaded file to storage"""
    # Create organization-specific directory
    org_dir = Path(DOCUMENT_SERVICE_CONFIG["upload_dir"]) / str(organization_id)
    org_dir.mkdir(exist_ok=True)

    # Sanitize filename
    safe_filename = sanitize_filename(file.filename or "uploaded_file")

    # Add document ID to prevent conflicts
    file_extension = Path(safe_filename).suffix
    storage_filename = f"{document_id}{file_extension}"
    file_path = org_dir / storage_filename

    # Save file
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    return str(file_path)


async def delete_file_from_storage(file_path: str) -> bool:
    """Delete file from storage"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception:
        return False


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await event_logger.log_event(
        event_type="service_startup",
        event_data={"version": DOCUMENT_SERVICE_CONFIG["version"]},
    )

    # Add health checks
    health_checker.add_check(
        "storage", lambda: os.access(DOCUMENT_SERVICE_CONFIG["upload_dir"], os.W_OK)
    )
    health_checker.add_check(
        "database", lambda: True
    )  # Would check actual DB connection
    health_checker.add_check("redis", lambda: True)  # Would check Redis connection


@app.post("/documents/upload", response_model=DocumentResponse)
@handle_exceptions
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    tags: str = Form(default="[]"),
    is_public: bool = Form(default=False),
    custom_metadata: str = Form(default="{}"),
    organization_id: uuid.UUID = Form(...),
    uploaded_by_user_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new document"""
    start_time = datetime.now(timezone.utc)

    try:
        # Parse form data safely using JSON
        try:
            tags_list = json.loads(tags) if tags else []
            metadata_dict = json.loads(custom_metadata) if custom_metadata else {}
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON in form data: {e}")

        # Validate file
        document_type, mime_type = validate_file_upload(file)

        # Read file content for hashing and size calculation
        file_content = await file.read()
        file_size = len(file_content)
        file_hash = await calculate_file_hash(file_content)

        # Check for duplicate file by hash
        existing_doc = await db.execute(
            select(Document).where(
                and_(
                    Document.organization_id == organization_id,
                    Document.file_hash == file_hash,
                    Document.is_deleted == False,
                )
            )
        )
        if existing_doc.scalar_one_or_none():
            raise ConflictError(
                message="Duplicate file detected",
                conflict_details={"file_hash": file_hash},
            )

        # Check storage quota
        has_quota, current_usage, quota_limit = await check_storage_quota(
            db, organization_id, file_size
        )

        if not has_quota:
            raise StorageQuotaError(
                current_usage_mb=current_usage / (1024 * 1024),
                quota_limit_mb=quota_limit / (1024 * 1024),
            )

        # Reset file position for saving
        await file.seek(0)

        # Create document record
        document = Document(
            title=title,
            filename=file.filename or "uploaded_file",
            file_path="",  # Will be set after saving
            file_size_bytes=file_size,
            mime_type=mime_type,
            document_type=DocType(document_type.value),
            processing_status=ProcStatus.QUEUED,
            is_public=is_public,
            tags=tags_list,
            document_metadata=metadata_dict,
            organization_id=organization_id,
            uploaded_by_user_id=uploaded_by_user_id,
            file_hash=file_hash,
        )

        db.add(document)
        await db.flush()  # Get the document ID

        # Save file to storage
        file_path = await save_uploaded_file(file, organization_id, document.id)
        document.file_path = file_path

        await db.commit()

        # Schedule processing job
        background_tasks.add_task(
            schedule_document_processing,
            str(document.id),
            organization_id,
            uploaded_by_user_id,
        )

        # Log successful upload
        await event_logger.log_event(
            event_type="document_uploaded",
            event_data={
                "document_id": str(document.id),
                "filename": file.filename,
                "file_size": file_size,
                "document_type": document_type.value,
                "processing_status": document.processing_status.value,
            },
            user_id=str(uploaded_by_user_id),
            organization_id=str(organization_id),
        )

        # Record metrics
        metrics.increment_counter(
            "documents_uploaded", labels={"document_type": document_type.value}
        )
        metrics.set_gauge(
            "storage_usage_bytes",
            current_usage + file_size,
            {"organization_id": str(organization_id)},
        )

        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()

        return DocumentResponse(
            id=document.id,
            title=document.title,
            filename=document.filename,
            document_type=DocumentType(document.document_type.value),
            file_size_bytes=document.file_size_bytes,
            file_size_mb=document.file_size_mb,
            mime_type=document.mime_type,
            processing_status=ProcessingStatus(document.processing_status.value),
            tags=document.tags or [],
            is_public=document.is_public,
            created_at=document.created_at,
            updated_at=document.updated_at,
            processing_started_at=document.processing_started_at,
            processing_completed_at=document.processing_completed_at,
            content_preview=document.get_content_preview(),
        )

    except Exception as e:
        await db.rollback()
        # Clean up uploaded file if it exists
        if "document" in locals() and document.file_path:
            await delete_file_from_storage(document.file_path)
        raise


async def schedule_document_processing(
    document_id: str, organization_id: uuid.UUID, user_id: uuid.UUID
):
    """Schedule document processing job"""
    try:
        # This would send a message to the processing pipeline service
        # For now, we'll just log the event
        await event_logger.log_event(
            event_type="processing_scheduled",
            event_data={
                "document_id": document_id,
                "organization_id": str(organization_id),
                "user_id": str(user_id),
            },
        )
    except Exception as e:
        await event_logger.log_error(e, {"document_id": document_id})


@app.get("/documents", response_model=PaginatedResponse)
@handle_exceptions
async def list_documents(
    request: DocumentListRequest = Depends(),
    organization_id: uuid.UUID = Query(...),
    user_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List documents with pagination and filters"""
    # Build base query
    query = select(Document).where(
        and_(Document.organization_id == organization_id, Document.is_deleted == False)
    )

    # Apply filters
    if request.document_type:
        query = query.where(
            Document.document_type == DocType(request.document_type.value)
        )

    if request.processing_status:
        query = query.where(
            Document.processing_status == ProcStatus(request.processing_status.value)
        )

    if request.tags:
        # Filter by tags (PostgreSQL array contains)
        for tag in request.tags:
            query = query.where(Document.tags.any(tag))

    if request.is_public is not None:
        query = query.where(Document.is_public == request.is_public)

    if request.search:
        # Full-text search
        search_term = f"%{request.search}%"
        query = query.where(
            or_(
                Document.title.ilike(search_term),
                Document.filename.ilike(search_term),
                Document.content_text.ilike(search_term),
            )
        )

    if request.date_from:
        query = query.where(Document.created_at >= request.date_from)

    if request.date_to:
        query = query.where(Document.created_at <= request.date_to)

    # If not admin, filter by user
    if user_id:
        query = query.where(
            or_(Document.uploaded_by_user_id == user_id, Document.is_public == True)
        )

    # Order by creation date (newest first)
    query = query.order_by(desc(Document.created_at))

    # Paginate
    documents, pagination_info = await paginate_query(
        query, request.page, request.limit, db
    )

    # Convert to response models
    document_responses = []
    for doc in documents:
        document_responses.append(
            DocumentResponse(
                id=doc.id,
                title=doc.title,
                filename=doc.filename,
                document_type=DocumentType(doc.document_type.value),
                file_size_bytes=doc.file_size_bytes,
                file_size_mb=doc.file_size_mb,
                mime_type=doc.mime_type,
                processing_status=ProcessingStatus(doc.processing_status.value),
                tags=doc.tags or [],
                is_public=doc.is_public,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                processing_started_at=doc.processing_started_at,
                processing_completed_at=doc.processing_completed_at,
                content_preview=doc.get_content_preview(),
            )
        )

    return PaginatedResponse(
        success=True, data=document_responses, pagination=pagination_info
    )


@app.get("/documents/{document_id}", response_model=DocumentDetailResponse)
@handle_exceptions
async def get_document(
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Query(...),
    user_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get document details"""
    # Get document
    result = await db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.organization_id == organization_id,
                Document.is_deleted == False,
            )
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise NotFoundError(
            "Document not found", resource_type="document", resource_id=str(document_id)
        )

    # Check access permissions
    if user_id and not document.is_public and document.uploaded_by_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this document",
        )

    return DocumentDetailResponse(
        id=document.id,
        title=document.title,
        filename=document.filename,
        document_type=DocumentType(document.document_type.value),
        file_size_bytes=document.file_size_bytes,
        file_size_mb=document.file_size_mb,
        mime_type=document.mime_type,
        processing_status=ProcessingStatus(document.processing_status.value),
        tags=document.tags or [],
        is_public=document.is_public,
        created_at=document.created_at,
        updated_at=document.updated_at,
        processing_started_at=document.processing_started_at,
        processing_completed_at=document.processing_completed_at,
        content_preview=document.get_content_preview(),
        content_text=document.content_text,
        metadata=document.get_metadata(),
        processing_error=document.processing_error,
        processing_retry_count=document.processing_retry_count,
    )


@app.put("/documents/{document_id}", response_model=DocumentResponse)
@handle_exceptions
async def update_document(
    document_id: uuid.UUID,
    update_data: DocumentUpdateRequest,
    organization_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Update document metadata"""
    # Get document
    result = await db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.organization_id == organization_id,
                Document.uploaded_by_user_id == user_id,
                Document.is_deleted == False,
            )
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise NotFoundError(
            "Document not found", resource_type="document", resource_id=str(document_id)
        )

    # Update fields
    if update_data.title is not None:
        document.title = update_data.title

    if update_data.tags is not None:
        document.tags = update_data.tags

    if update_data.is_public is not None:
        document.is_public = update_data.is_public

    if update_data.custom_metadata is not None:
        document.set_metadata(update_data.custom_metadata)

    await db.commit()

    # Log update
    await event_logger.log_event(
        event_type="document_updated",
        event_data={
            "document_id": str(document_id),
            "updated_fields": update_data.dict(exclude_unset=True),
        },
        user_id=str(user_id),
        organization_id=str(organization_id),
    )

    return DocumentResponse(
        id=document.id,
        title=document.title,
        filename=document.filename,
        document_type=DocumentType(document.document_type.value),
        file_size_bytes=document.file_size_bytes,
        file_size_mb=document.file_size_mb,
        mime_type=document.mime_type,
        processing_status=ProcessingStatus(document.processing_status.value),
        tags=document.tags or [],
        is_public=document.is_public,
        created_at=document.created_at,
        updated_at=document.updated_at,
        processing_started_at=document.processing_started_at,
        processing_completed_at=document.processing_completed_at,
        content_preview=document.get_content_preview(),
    )


@app.delete("/documents/{document_id}")
@handle_exceptions
async def delete_document(
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Delete document (soft delete)"""
    # Get document
    result = await db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.organization_id == organization_id,
                Document.uploaded_by_user_id == user_id,
                Document.is_deleted == False,
            )
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise NotFoundError(
            "Document not found", resource_type="document", resource_id=str(document_id)
        )

    # Soft delete
    document.soft_delete()
    await db.commit()

    # Schedule file cleanup (could be done in background)
    # await delete_file_from_storage(document.file_path)

    # Log deletion
    await event_logger.log_event(
        event_type="document_deleted",
        event_data={
            "document_id": str(document_id),
            "filename": document.filename,
            "file_size_bytes": document.file_size_bytes,
        },
        user_id=str(user_id),
        organization_id=str(organization_id),
    )

    return BaseResponse(success=True, message="Document deleted successfully")


@app.get(
    "/documents/{document_id}/processing-status",
    response_model=ProcessingStatusResponse,
)
@handle_exceptions
async def get_processing_status(
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get document processing status"""
    # Get document
    result = await db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.organization_id == organization_id,
                Document.is_deleted == False,
            )
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise NotFoundError(
            "Document not found", resource_type="document", resource_id=str(document_id)
        )

    # Calculate progress percentage based on status
    progress_map = {
        ProcStatus.QUEUED: 0,
        ProcStatus.PROCESSING: 50,
        ProcStatus.COMPLETED: 100,
        ProcStatus.FAILED: 0,
    }

    # Estimate completion time (simplified)
    estimated_completion = None
    if (
        document.processing_status == ProcStatus.PROCESSING
        and document.processing_started_at
    ):
        # Assume average processing time of 2 minutes
        avg_processing_time = 120  # seconds
        elapsed = (
            datetime.now(timezone.utc) - document.processing_started_at
        ).total_seconds()
        remaining = max(0, avg_processing_time - elapsed)
        estimated_completion = datetime.now(timezone.utc) + timedelta(seconds=remaining)

    return ProcessingStatusResponse(
        document_id=document.id,
        processing_status=ProcessingStatus(document.processing_status.value),
        current_stage=document.processing_status.value,
        progress_percentage=progress_map.get(document.processing_status, 0),
        estimated_completion=estimated_completion,
        error_message=document.processing_error,
        retry_count=document.processing_retry_count,
    )


@app.get("/documents/{document_id}/download")
@handle_exceptions
async def download_document(
    document_id: uuid.UUID,
    organization_id: uuid.UUID = Query(...),
    user_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Download document file"""
    # Get document
    result = await db.execute(
        select(Document).where(
            and_(
                Document.id == document_id,
                Document.organization_id == organization_id,
                Document.is_deleted == False,
            )
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise NotFoundError(
            "Document not found", resource_type="document", resource_id=str(document_id)
        )

    # Check access permissions
    if user_id and not document.is_public and document.uploaded_by_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this document",
        )

    # Check if file exists
    if not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found on storage"
        )

    # Stream file
    async def file_generator():
        async with aiofiles.open(document.file_path, "rb") as f:
            while chunk := await f.read(8192):
                yield chunk

    # Log download
    await event_logger.log_event(
        event_type="document_downloaded",
        event_data={
            "document_id": str(document_id),
            "filename": document.filename,
            "file_size_bytes": document.file_size_bytes,
        },
        user_id=str(user_id) if user_id else None,
        organization_id=str(organization_id),
    )

    headers = {"Content-Disposition": f'attachment; filename="{document.filename}"'}

    return StreamingResponse(
        file_generator(), media_type=document.mime_type, headers=headers
    )


@app.get("/storage/quota", response_model=Dict[str, Any])
@handle_exceptions
async def get_storage_quota(
    organization_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)
):
    """Get storage quota information"""
    # Get organization info
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()

    if not organization:
        raise NotFoundError("Organization not found", resource_type="organization")

    # Calculate current usage
    result = await db.execute(
        select(func.coalesce(func.sum(Document.file_size_bytes), 0)).where(
            and_(
                Document.organization_id == organization_id,
                Document.is_deleted == False,
            )
        )
    )
    current_usage = result.scalar() or 0

    return {
        "organization_id": str(organization_id),
        "storage_tier": organization.storage_tier.value,
        "quota_limit_bytes": organization.storage_limit_bytes,
        "quota_limit_mb": organization.storage_limit_bytes / (1024 * 1024),
        "current_usage_bytes": current_usage,
        "current_usage_mb": current_usage / (1024 * 1024),
        "usage_percentage": (current_usage / organization.storage_limit_bytes) * 100,
        "available_bytes": organization.storage_limit_bytes - current_usage,
        "available_mb": (organization.storage_limit_bytes - current_usage)
        / (1024 * 1024),
    }


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Service health check"""
    health_data = await health_checker.check_health()

    return HealthCheckResponse(
        status=health_data["status"],
        version=DOCUMENT_SERVICE_CONFIG["version"],
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        services=health_data["checks"],
        uptime_seconds=0,  # Would track actual uptime
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await cache.close()
    await event_logger.log_event(event_type="service_shutdown", event_data={})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.services.document_management:app",
        host=DOCUMENT_SERVICE_CONFIG["host"],
        port=DOCUMENT_SERVICE_CONFIG["port"],
        log_level=settings.LOG_LEVEL.lower(),
    )
