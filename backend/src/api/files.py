"""
File upload and management API endpoints
"""

from typing import Optional, List
import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.core.database import get_db
from src.core.dependencies import get_current_user, get_current_organization, can_upload_documents, has_storage_quota
from src.models.user import User
from src.models.organization import Organization
from src.models.document import Document, DocumentType
from src.services.file_service import FileService, get_file_service

router = APIRouter(prefix="/files", tags=["files"])

# Request/Response Models
class FileUploadResponse(BaseModel):
    id: str
    title: str
    filename: str
    document_type: str
    file_size_bytes: int
    processing_status: str
    upload_timestamp: str

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
    tags: Optional[str] = Form(None),
    is_public: bool = Form(False),
    current_user: User = Depends(can_upload_documents),
    db: Session = Depends(get_db),
    file_service: FileService = Depends(get_file_service)
):
    """Upload a file to the system"""
    try:
        # Get user's organization
        from src.core.dependencies import get_current_organization
        organization = get_current_organization(current_user)

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

        return FileUploadResponse(
            id=str(document.id),
            title=document.title,
            filename=document.filename,
            document_type=document.document_type.value,
            file_size_bytes=document.file_size_bytes,
            processing_status=document.processing_status.value,
            upload_timestamp=document.created_at.isoformat()
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