"""
File upload and management API endpoints
"""

from typing import Optional, List
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.core.database import get_db
from src.core.dependencies import get_current_user, get_current_organization, can_upload_documents, has_storage_quota
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.document import Document, DocumentType, ProcessingStatus
from src.services.file_service import FileService, get_file_service

router = APIRouter(prefix="/files", tags=["files"])

# Request/Response Models
class FileUploadResponse(BaseModel):
    document_id: str
    upload_id: str  # Same as document_id for v1 API compatibility
    id: str  # Deprecated, use document_id
    title: str
    filename: str
    document_type: str
    file_size_bytes: int
    file_size_mb: float
    mime_type: str
    processing_status: str
    upload_timestamp: str
    created_at: str
    message: str
    upload_progress: int = 100  # v1 API doesn't support progress tracking

class FileListResponse(BaseModel):
    files: List[dict]
    total: int
    page: int
    size: int

class FileStatsResponse(BaseModel):
    files_by_type: List[dict]
    processing_stats: List[dict]

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    is_public: bool = Form(False),
    processing_priority: Optional[str] = Form('normal'),
    enable_quality_check: bool = Form(True),
    custom_metadata: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),  # Temporarily reduced permission check
    db: Session = Depends(get_db),
    file_service: FileService = Depends(get_file_service)
):
    """Upload a file to the system"""

    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"📤 Upload Request Debug:")
    logger.info(f"  - User ID: {current_user.id}")
    logger.info(f"  - User Email: {current_user.email}")
    logger.info(f"  - User Role: {current_user.role.value if current_user.role else 'None'}")
    logger.info(f"  - User Active: {current_user.is_active}")
    logger.info(f"  - Can Upload: {current_user.can_upload_documents()}")
    logger.info(f"  - Title: {title}")
    logger.info(f"  - Description: {description}")
    logger.info(f"  - Tags: {tags}")
    logger.info(f"  - Processing Priority: {processing_priority}")
    logger.info(f"  - Enable Quality Check: {enable_quality_check}")

    try:
        # Get user's organization
        from src.core.dependencies import get_current_organization
        organization = get_current_organization(current_user)
        logger.info(f"  - Organization ID: {organization.id if organization else 'None'}")
        logger.info(f"  - Organization Name: {organization.name if organization else 'None'}")

        # Manual permission check for debugging
        if not current_user.can_upload_documents():
            logger.error(f"❌ Permission check failed! User {current_user.email} cannot upload documents")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. User role: {current_user.role.value if current_user.role else 'None'}, Required: USER or higher"
            )

        logger.info(f"✅ Permission check passed!")

        # Get file size for quota check
        if hasattr(file, 'size') and file.size:
            file_size = file.size
        else:
            # Read content to get size if not available
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset position

        # Check storage quota
        if not organization.can_upload_file(file_size):
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Insufficient storage quota. Available: {organization.storage_available_gb:.2f}GB"
            )

        # Parse tags from comma-separated string
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Upload file
        document = await file_service.upload_file(
            file=file,
            title=title,
            user=current_user,
            organization=organization,
            tags=tag_list,
            is_public=is_public
        )

        # Map backend status to frontend expected status
        status_mapping = {
            'PENDING': 'queued',
            'PROCESSING': 'processing',
            'COMPLETED': 'indexed',
            'FAILED': 'failed'
        }
        frontend_status = status_mapping.get(document.processing_status.value, 'queued')

        return FileUploadResponse(
            document_id=str(document.id),
            upload_id=str(document.id),  # Same as document_id for v1 API
            id=str(document.id),  # Deprecated, maintain compatibility
            title=document.title,
            filename=document.filename,
            document_type=document.document_type.value,
            file_size_bytes=document.file_size_bytes,
            file_size_mb=document.file_size_mb,
            mime_type=document.mime_type or "application/octet-stream",
            processing_status=frontend_status,  # Use frontend-compatible lowercase status
            upload_timestamp=document.created_at.isoformat(),
            created_at=document.created_at.isoformat(),
            message="File uploaded successfully",
            upload_progress=100
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/", response_model=FileListResponse)
async def list_files(
    page: int = 1,
    size: int = 20,
    document_type: Optional[DocumentType] = None,
    processing_status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """List files in the organization"""
    try:
        # Build query
        query = db.query(Document).filter(
            Document.organization_id == organization.id,
            Document.is_deleted == False
        )

        # Apply filters
        if document_type:
            query = query.filter(Document.document_type == document_type)

        if processing_status:
            query = query.filter(Document.processing_status == processing_status)

        if search:
            query = query.filter(
                Document.title.ilike(f"%{search}%") |
                Document.filename.ilike(f"%{search}%")
            )

        # Count total results
        total = query.count()

        # Apply pagination
        offset = (page - 1) * size
        documents = query.offset(offset).limit(size).all()

        return FileListResponse(
            files=[doc.to_dict() for doc in documents],
            total=total,
            page=page,
            size=size
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/{file_id}")
async def get_file_info(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific file"""
    document = db.query(Document).filter(
        Document.id == file_id,
        Document.is_deleted == False
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Check permissions
    if (document.organization_id != current_user.organization_id or
        (not document.is_public and not current_user.has_permission(UserRole.USER))):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this file"
        )

    return {
        "file": document.to_dict(include_content=True)
    }

@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download a file"""
    document = db.query(Document).filter(
        Document.id == file_id,
        Document.is_deleted == False
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Check permissions
    if (document.organization_id != current_user.organization_id or
        (not document.is_public and not current_user.has_permission(UserRole.USER))):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this file"
        )

    # Check if file exists
    if not os.path.exists(document.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk"
        )

    return FileResponse(
        path=document.file_path,
        filename=document.filename,
        media_type=document.mime_type
    )

@router.put("/{file_id}")
async def update_file_metadata(
    file_id: str,
    title: Optional[str] = None,
    tags: Optional[List[str]] = None,
    is_public: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update file metadata"""
    document = db.query(Document).filter(
        Document.id == file_id,
        Document.is_deleted == False
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Check permissions (owner or admin)
    if (document.uploaded_by_user_id != current_user.id and
        not current_user.has_permission(UserRole.ADMIN)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update your own files or require admin role"
        )

    try:
        # Update fields
        if title is not None:
            document.title = title

        if tags is not None:
            document.tags = tags

        if is_public is not None:
            document.is_public = is_public

        db.commit()
        db.refresh(document)

        return {
            "message": "File metadata updated successfully",
            "file": document.to_dict()
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
):
    """Delete a file"""
    # Get document
    from src.models.document import Document
    document = file_service.db.query(Document).filter(
        Document.id == file_id,
        Document.is_deleted == False
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    try:
        success = await file_service.delete_file(document, current_user)

        if success:
            return {"message": "File deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete file"
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{file_id}/content")
async def get_file_content(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get extracted text content of a file"""
    document = db.query(Document).filter(
        Document.id == file_id,
        Document.is_deleted == False
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Check permissions
    if (document.organization_id != current_user.organization_id or
        (not document.is_public and not current_user.has_permission(UserRole.USER))):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this file"
        )

    return {
        "content": document.content_text,
        "summary": document.content_summary,
        "content_preview": document.get_content_preview(500)
    }

@router.get("/{file_id}/metadata")
async def get_file_metadata(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get file metadata"""
    document = db.query(Document).filter(
        Document.id == file_id,
        Document.is_deleted == False
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Check permissions
    if (document.organization_id != current_user.organization_id or
        (not document.is_public and not current_user.has_permission(UserRole.USER))):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this file"
        )

    return {
        "metadata": document.metadata,
        "file_info": {
            "id": str(document.id),
            "title": document.title,
            "filename": document.filename,
            "file_size_mb": document.file_size_mb,
            "mime_type": document.mime_type,
            "document_type": document.document_type.value,
            "processing_status": document.processing_status.value,
            "tags": document.tags,
            "is_public": document.is_public,
            "created_at": document.created_at,
            "updated_at": document.updated_at
        }
    }

@router.delete("/cancel/{upload_id}")
async def cancel_upload(
    upload_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel an ongoing upload or delete a recently uploaded document"""
    try:
        # Validate upload_id format
        import uuid
        try:
            uuid.UUID(upload_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid upload ID format. Must be a valid UUID."
            )

        # First, check if upload_id exists in processing jobs
        from src.models.processing import ProcessingJob

        processing_job = db.query(ProcessingJob).filter(
            ProcessingJob.celery_task_id == upload_id,
            ProcessingJob.is_deleted == False
        ).first()

        if processing_job:
            # Handle processing job cancellation
            # Check if user owns this job
            if processing_job.created_by_user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only cancel your own uploads"
                )

            # Check if job can be cancelled (only pending or running jobs)
            if processing_job.status not in ["pending", "running"]:
                return {
                    "message": f"Cannot cancel job in {processing_job.status} state",
                    "upload_id": upload_id,
                    "job_status": processing_job.status
                }

            # Update job status to cancelled
            processing_job.status = "cancelled"
            processing_job.completed_at = datetime.utcnow()
            processing_job.error_message = "Upload cancelled by user"
            db.commit()

            return {
                "message": "Upload cancelled successfully",
                "upload_id": upload_id,
                "job_id": processing_job.id
            }

        # If no processing job found, check if it's a document ID
        document = db.query(Document).filter(
            Document.id == upload_id,
            Document.uploaded_by_user_id == current_user.id,
            Document.is_deleted == False
        ).first()

        if document:
            # Handle document deletion (for recently uploaded documents)
            # Allow cancellation/deletion of documents that are still in processing state
            if document.processing_status.value in ["pending", "processing"]:
                document.soft_delete()
                db.commit()

                return {
                    "message": "Document upload cancelled successfully",
                    "upload_id": upload_id,
                    "document_id": document.id
                }
            else:
                return {
                    "message": f"Cannot cancel document in {document.processing_status.value} state",
                    "upload_id": upload_id,
                    "document_status": document.processing_status.value
                }

        # If neither processing job nor document found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload job or document not found"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel upload: {str(e)}"
        )

@router.get("/debug-auth")
async def debug_auth(
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization)
):
    """Debug endpoint to check authentication state"""
    return {
        "user_id": str(current_user.id),
        "user_email": current_user.email,
        "user_role": current_user.role.value if current_user.role else None,
        "user_active": current_user.is_active,
        "organization_id": str(organization.id) if organization else None,
        "organization_name": organization.name if organization else None,
        "can_upload_documents": current_user.can_upload_documents(),
        "user_permissions": {
            "has_user_role": current_user.has_permission(UserRole.USER),
            "has_admin_role": current_user.has_permission(UserRole.ADMIN),
            "has_content_manager_role": current_user.has_permission(UserRole.CONTENT_MANAGER),
            "has_analyst_role": current_user.has_permission(UserRole.ANALYST),
        }
    }

@router.get("/stats", response_model=FileStatsResponse)
async def get_file_statistics(
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    file_service: FileService = Depends(get_file_service)
):
    """Get file statistics for the organization"""
    try:
        stats = file_service.get_file_stats(str(organization.id))
        return FileStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/{file_id}/reprocess")
async def reprocess_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Trigger reprocessing of a file"""
    document = db.query(Document).filter(
        Document.id == file_id,
        Document.is_deleted == False
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Check permissions
    if (document.uploaded_by_user_id != current_user.id and
        not current_user.has_permission(UserRole.ADMIN)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only reprocess your own files or require admin role"
        )

    try:
        # Reset processing status
        document.processing_status = ProcessingStatus.PENDING
        document.processing_error = None
        document.processing_retry_count = 0
        document.processing_started_at = None
        document.processing_completed_at = None

        db.commit()

        return {
            "message": "File queued for reprocessing",
            "processing_status": document.processing_status.value
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )