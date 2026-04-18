"""
Enhanced Document Upload API endpoints with multipart file upload, validation,
security scanning, and real-time processing status updates
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, BinaryIO, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_organization, get_current_user
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.organization import Organization
from src.models.processing import JobPriority, JobStatus, JobType, ProcessingJob
from src.models.user import User, UserRole
from src.services.documents.document_quality_service import (
    DocumentQualityService,
    get_document_quality_service,
)
from src.services.documents.enhanced_file_service import (
    EnhancedFileService,
    get_enhanced_file_service,
)
from src.services.processing.multimodal_processing_service import (
    MultimodalProcessingService,
    get_multimodal_processing_service,
)
from src.tasks.document_processing_tasks import process_document_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2/documents/upload", tags=["enhanced-document-upload"])


# Request/Response Models
class DocumentUploadRequest(BaseModel):
    """Enhanced document upload request"""

    title: str = Field(..., min_length=1, max_length=500, description="Document title")
    description: Optional[str] = Field(
        None, max_length=2000, description="Document description"
    )
    tags: List[str] = Field(default_factory=list, description="Document tags")
    is_public: bool = Field(
        default=False, description="Whether document is publicly accessible"
    )
    processing_priority: str = Field(
        "normal", regex="^(low|normal|high|urgent)$", description="Processing priority"
    )
    enable_quality_check: bool = Field(
        default=True, description="Enable quality assessment"
    )
    custom_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata"
    )


class DocumentUploadResponse(BaseModel):
    """Enhanced document upload response"""

    document_id: str
    upload_id: str
    title: str
    filename: str
    document_type: str
    file_size_bytes: int
    file_size_mb: float
    mime_type: str
    processing_status: str
    job_id: Optional[str] = None
    estimated_processing_time: Optional[int] = None
    quality_score: Optional[float] = None
    security_scan_result: Optional[Dict[str, Any]] = None
    upload_progress: float = 100.0
    message: str
    created_at: datetime


class BatchUploadRequest(BaseModel):
    """Batch upload request"""

    documents: List[DocumentUploadRequest] = Field(..., min_items=1, max_items=50)
    processing_mode: str = Field(
        "parallel", regex="^(parallel|sequential)$", description="Processing mode"
    )
    enable_deduplication: bool = Field(
        default=True, description="Enable duplicate detection"
    )


class UploadProgressResponse(BaseModel):
    """Upload progress response"""

    upload_id: str
    progress_percentage: float
    current_step: str
    total_steps: int
    completed_steps: int
    estimated_remaining_seconds: Optional[int] = None
    error_message: Optional[str] = None


class QualityAssessmentResponse(BaseModel):
    """Quality assessment response"""

    document_id: str
    overall_score: float
    readability_score: float
    content_quality_score: float
    technical_quality_score: float
    recommendations: List[str]
    issues: List[Dict[str, Any]]
    processing_time_ms: float


class SecurityScanResult(BaseModel):
    """Security scan result"""

    scan_status: str  # passed, failed, warning
    virus_detected: bool
    suspicious_content: bool
    file_integrity: str
    scan_timestamp: datetime
    threats: List[Dict[str, Any]] = []
    warnings: List[str] = []


# WebSocket connection manager for real-time updates
class UploadManager:
    """WebSocket connection manager for upload progress updates"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.upload_progress: Dict[str, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, upload_id: str):
        """Connect WebSocket for upload progress"""
        await websocket.accept()
        self.active_connections[upload_id] = websocket
        self.upload_progress[upload_id] = {
            "progress": 0.0,
            "current_step": "Initializing",
            "total_steps": 10,
            "completed_steps": 0,
            "error_message": None,
        }

    def disconnect(self, upload_id: str):
        """Disconnect WebSocket"""
        if upload_id in self.active_connections:
            del self.active_connections[upload_id]
        if upload_id in self.upload_progress:
            del self.upload_progress[upload_id]

    async def update_progress(
        self,
        upload_id: str,
        progress: float,
        current_step: str = None,
        error_message: str = None,
    ):
        """Update upload progress"""
        if upload_id in self.upload_progress:
            self.upload_progress[upload_id]["progress"] = progress
            if current_step:
                self.upload_progress[upload_id]["current_step"] = current_step
            if error_message:
                self.upload_progress[upload_id]["error_message"] = error_message

            # Send update via WebSocket
            if upload_id in self.active_connections:
                try:
                    await self.active_connections[upload_id].send_json(
                        {
                            "type": "progress_update",
                            "upload_id": upload_id,
                            **self.upload_progress[upload_id],
                        }
                    )
                except:
                    # Connection might be closed
                    pass

    async def send_completion(self, upload_id: str, result: Dict[str, Any]):
        """Send completion notification"""
        if upload_id in self.active_connections:
            try:
                await self.active_connections[upload_id].send_json(
                    {
                        "type": "upload_complete",
                        "upload_id": upload_id,
                        "result": result,
                    }
                )
            except:
                pass


# Global upload manager
upload_manager = UploadManager()


@router.post("/single", response_model=DocumentUploadResponse)
async def upload_single_document(
    file: UploadFile = File(..., description="Document file to upload"),
    title: str = Form(..., description="Document title"),
    description: Optional[str] = Form(None, description="Document description"),
    tags: str = Form("", description="Comma-separated tags"),
    is_public: bool = Form(
        False, description="Whether document is publicly accessible"
    ),
    processing_priority: str = Form("normal", description="Processing priority"),
    enable_quality_check: bool = Form(True, description="Enable quality assessment"),
    custom_metadata: str = Form("{}", description="Custom metadata as JSON string"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
    file_service: EnhancedFileService = Depends(get_enhanced_file_service),
    processing_service: MultimodalProcessingService = Depends(
        get_multimodal_processing_service
    ),
    quality_service: DocumentQualityService = Depends(get_document_quality_service),
):
    """
    Enhanced single document upload with validation, security scanning, and quality assessment
    """
    # Generate upload ID for tracking
    upload_id = str(uuid.uuid4())

    try:
        # Parse form inputs
        tag_list = (
            [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
        )

        # Safe JSON parsing for custom metadata
        try:
            metadata_dict = json.loads(custom_metadata) if custom_metadata else {}
        except json.JSONDecodeError:
            metadata_dict = {}

        # Initialize upload progress
        await upload_manager.update_progress(upload_id, 10.0, "Validating file")

        # Enhanced file validation and security scanning
        validation_result = await file_service.validate_and_scan_file(
            file=file, user=current_user, organization=organization
        )

        await upload_manager.update_progress(
            upload_id, 25.0, "Security scanning completed"
        )

        # Check security scan results
        if validation_result["security_scan"]["virus_detected"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File contains malware and cannot be uploaded",
            )

        # Generate file path and save
        await upload_manager.update_progress(upload_id, 40.0, "Saving file")

        document = await file_service.upload_file(
            file=file,
            title=title,
            description=description,
            user=current_user,
            organization=organization,
            tags=tag_list,
            is_public=is_public,
            custom_metadata=metadata_dict,
            validation_result=validation_result,
        )

        await upload_manager.update_progress(upload_id, 60.0, "File saved successfully")

        # Create processing job with enhanced configuration
        job_priority = JobPriority[processing_priority.upper()]
        processing_job = ProcessingJob(
            job_type=JobType.DOCUMENT_INGESTION,
            status=JobStatus.PENDING,
            priority=job_priority,
            document_id=document.id,
            organization_id=organization.id,
            created_by_user_id=current_user.id,
            parameters={
                "document_id": str(document.id),
                "file_path": document.file_path,
                "document_type": document.document_type.value,
                "mime_type": document.mime_type,
                "enable_quality_check": enable_quality_check,
                "upload_id": upload_id,
            },
            config={
                "max_retries": 3,
                "timeout_seconds": 600,
                "enable_ocr": True,
                "enable_entity_extraction": True,
                "enable_embedding_generation": True,
            },
            total_steps=8,  # Enhanced processing pipeline
            queue_name="document_processing",
        )

        db.add(processing_job)
        await db.commit()
        await db.refresh(processing_job)

        await upload_manager.update_progress(upload_id, 75.0, "Queuing for processing")

        # Queue background processing
        background_tasks.add_task(
            process_document_upload, str(processing_job.id), upload_id
        )

        await upload_manager.update_progress(upload_id, 90.0, "Processing queued")

        # Estimate processing time based on file size and type
        estimated_time = processing_service.estimate_processing_time(
            document.document_type, document.file_size_bytes
        )

        # Perform initial quality assessment if enabled
        quality_score = None
        if enable_quality_check:
            quick_quality = await quality_service.quick_quality_assessment(document)
            quality_score = quick_quality.get("overall_score")

        await upload_manager.update_progress(upload_id, 100.0, "Upload completed")

        # Invalidate search cache so new document appears in results
        try:
            from src.services.search.search_service import cache

            await cache.delete_pattern("search:*")
            await cache.delete_pattern("suggestions:*")
        except Exception:
            pass  # Cache invalidation is best-effort

        # Send completion notification
        await upload_manager.send_completion(
            upload_id,
            {
                "document_id": str(document.id),
                "job_id": str(processing_job.id),
                "status": "success",
            },
        )

        return DocumentUploadResponse(
            document_id=str(document.id),
            upload_id=upload_id,
            title=document.title,
            filename=document.filename,
            document_type=document.document_type.value,
            file_size_bytes=document.file_size_bytes,
            file_size_mb=document.file_size_mb,
            mime_type=document.mime_type,
            processing_status=document.processing_status.value,
            job_id=str(processing_job.id),
            estimated_processing_time=estimated_time,
            quality_score=quality_score,
            security_scan_result=validation_result["security_scan"],
            upload_progress=100.0,
            message="Document uploaded successfully and queued for processing",
            created_at=document.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {str(e)}")
        await upload_manager.update_progress(
            upload_id, 0.0, error_message=f"Upload failed: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}",
        )


@router.post("/batch")
async def upload_batch_documents(
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
    file_service: EnhancedFileService = Depends(get_enhanced_file_service),
    processing_service: MultimodalProcessingService = Depends(
        get_multimodal_processing_service
    ),
):
    """
    Batch upload multiple documents with parallel processing
    """
    # Implementation for batch upload
    pass


@router.get("/progress/{upload_id}", response_model=UploadProgressResponse)
async def get_upload_progress(
    upload_id: str, current_user: User = Depends(get_current_user)
):
    """Get upload progress for a specific upload"""
    if upload_id not in upload_manager.upload_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found"
        )

    progress_data = upload_manager.upload_progress[upload_id]

    return UploadProgressResponse(
        upload_id=upload_id,
        progress_percentage=progress_data["progress"],
        current_step=progress_data["current_step"],
        total_steps=progress_data["total_steps"],
        completed_steps=progress_data["completed_steps"],
        estimated_remaining_seconds=progress_data.get("estimated_remaining_seconds"),
        error_message=progress_data.get("error_message"),
    )


@router.websocket("/progress/{upload_id}/ws")
async def websocket_upload_progress(websocket: WebSocket, upload_id: str):
    """WebSocket endpoint for real-time upload progress updates"""
    # Authenticate via Sec-WebSocket-Protocol header
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    token = None
    for protocol in protocols.split(","):
        protocol = protocol.strip()
        if protocol.startswith("access_token."):
            token = protocol.replace("access_token.", "", 1)

    try:
        if not token:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Missing authentication token",
            )
            return

        from src.core.security import verify_token

        token_data = verify_token(token)
        if not token_data or not token_data.user_id:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid or expired token",
            )
            return
    except Exception as e:
        logger.error(f"WebSocket upload progress auth error: {e}")
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Authentication error",
        )
        return

    await upload_manager.connect(websocket, upload_id)

    try:
        while True:
            # Keep connection alive and handle disconnects
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        upload_manager.disconnect(upload_id)


@router.get("/{document_id}/quality", response_model=QualityAssessmentResponse)
async def get_document_quality(
    document_id: str,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
    quality_service: DocumentQualityService = Depends(get_document_quality_service),
):
    """Get comprehensive quality assessment for a document"""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization.id,
            Document.is_deleted == False,
        )
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # Check permissions
    if not document.is_public and not current_user.has_permission(UserRole.USER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this document",
        )

    try:
        quality_result = await quality_service.comprehensive_quality_assessment(
            document
        )

        return QualityAssessmentResponse(
            document_id=document_id,
            overall_score=quality_result["overall_score"],
            readability_score=quality_result["readability_score"],
            content_quality_score=quality_result["content_quality_score"],
            technical_quality_score=quality_result["technical_quality_score"],
            recommendations=quality_result["recommendations"],
            issues=quality_result["issues"],
            processing_time_ms=quality_result["processing_time_ms"],
        )

    except Exception as e:
        logger.error(f"Quality assessment failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assess document quality: {str(e)}",
        )


@router.post("/{document_id}/rescan")
async def rescan_document_security(
    document_id: str,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
    file_service: EnhancedFileService = Depends(get_enhanced_file_service),
):
    """Rescan document for security threats"""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization.id,
            Document.is_deleted == False,
        )
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # Check permissions (owner or admin)
    if (
        document.uploaded_by_user_id != current_user.id
        and not current_user.has_permission(UserRole.ADMIN)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only rescan your own documents or require admin role",
        )

    try:
        # Perform security rescan
        scan_result = await file_service.rescan_file_security(document)

        return {
            "message": "Security scan completed",
            "document_id": document_id,
            "scan_result": scan_result,
            "scanned_at": datetime.utcnow(),
        }

    except Exception as e:
        logger.error(f"Security rescan failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rescan document: {str(e)}",
        )


@router.delete("/cancel/{upload_id}")
async def cancel_upload(upload_id: str, current_user: User = Depends(get_current_user)):
    """Cancel an ongoing upload"""
    if upload_id not in upload_manager.upload_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found"
        )

    try:
        # Update progress to cancelled
        await upload_manager.update_progress(
            upload_id, 0.0, error_message="Upload cancelled by user"
        )

        # Disconnect WebSocket
        upload_manager.disconnect(upload_id)

        return {"message": "Upload cancelled successfully", "upload_id": upload_id}

    except Exception as e:
        logger.error(f"Failed to cancel upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel upload: {str(e)}",
        )
