"""
Document management API endpoints
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload, selectinload

from src.core.database import get_db
from src.core.dependencies import get_current_organization, get_current_user
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.entity import Entity
from src.models.organization import Organization
from src.models.processing import JobStatus, ProcessingJob
from src.models.user import User, UserRole
from src.services.file_service import FileService, get_file_service
from src.shared.enums import DocumentSortField, SortOrder

router = APIRouter(prefix="/documents", tags=["documents"], redirect_slashes=False)


# Request/Response Models
class DocumentResponse(BaseModel):
    id: str
    title: str
    filename: str
    document_type: str
    file_size_bytes: int
    file_size_mb: float
    mime_type: str
    processing_status: str
    tags: Optional[List[str]] = Field(default_factory=list)
    is_public: bool
    content_preview: Optional[str] = None
    content_summary: Optional[str] = None
    created_at: str
    updated_at: str
    uploaded_by_user_id: str
    organization_id: str


class DocumentDetailResponse(DocumentResponse):
    content_text: Optional[str] = None
    metadata: Optional[dict] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    processing_retry_count: int = 0


class PaginationInfo(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    pagination: PaginationInfo


class DocumentEntityResponse(BaseModel):
    id: str
    name: str
    entity_type: str
    confidence_score: float
    extraction_method: str
    metadata: Optional[dict] = None


class DocumentEntitiesResponse(BaseModel):
    document_id: str
    entities: List[DocumentEntityResponse]
    total_entities: int


class DocumentSearchResponse(BaseModel):
    documents: List[DocumentResponse]
    pagination: PaginationInfo
    search_query: str
    search_filters: dict


class DocumentStatusResponse(BaseModel):
    document_id: str
    processing_status: str
    progress_percentage: float
    current_step: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None


class BulkDocumentRequest(BaseModel):
    document_ids: List[str] = Field(..., min_items=1, max_items=100)


class BulkDocumentResponse(BaseModel):
    successful: List[str]
    failed: List[dict]
    total_processed: int
    success_count: int
    failure_count: int


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents with filtering and pagination",
    description="""
    Retrieve a paginated list of documents for the current user's organization.
    
    ## Filtering Options
    - **document_type**: Filter by type (pdf, txt, jpg, png, mp3, mp4)
    - **processing_status**: Filter by status (pending, processing, completed, failed)
    - **search**: Full-text search in title, filename, and content
    - **tags**: Comma-separated list of tags to filter by
    - **is_public**: Filter by public/private visibility
    - **date_from/date_to**: Date range filtering
    
    ## Sorting
    - **sort_by**: created_at, updated_at, title, filename, file_size_bytes
    - **sort_order**: asc or desc (default: desc)
    
    ## Pagination
    - **page**: 1-indexed page number
    - **size**: Items per page (1-100, default 20)
    
    ## Security
    - Requires authentication
    - Returns only documents belonging to user's organization
    - Uses validated enums for sort fields (SQL injection protected)
    """,
    responses={
        200: {
            "description": "Successfully retrieved documents",
            "content": {
                "application/json": {
                    "example": {
                        "documents": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440001",
                                "title": "Research Paper on ML",
                                "filename": "ml-research.pdf",
                                "document_type": "pdf",
                                "file_size_bytes": 1048576,
                                "file_size_mb": 1.0,
                                "mime_type": "application/pdf",
                                "processing_status": "indexed",
                                "tags": ["research", "machine-learning"],
                                "is_public": False,
                                "content_preview": "This paper explores...",
                                "created_at": "2024-01-15T10:30:00Z",
                                "updated_at": "2024-01-15T10:35:00Z",
                            }
                        ],
                        "pagination": {
                            "page": 1,
                            "page_size": 20,
                            "total": 42,
                            "total_pages": 3,
                            "has_next": True,
                            "has_prev": False,
                        },
                    }
                }
            },
        },
        401: {"description": "Not authenticated - missing or invalid token"},
        403: {"description": "Not authorized to access this organization's documents"},
        500: {"description": "Internal server error"},
    },
)
@router.get("/", response_model=DocumentListResponse, include_in_schema=False)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    document_type: Optional[DocumentType] = Query(
        None, description="Filter by document type"
    ),
    processing_status: Optional[ProcessingStatus] = Query(
        None, description="Filter by processing status"
    ),
    search: Optional[str] = Query(None, description="Search in title and filename"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    is_public: Optional[bool] = Query(None, description="Filter by public status"),
    date_from: Optional[datetime] = Query(
        None, description="Filter documents from date"
    ),
    date_to: Optional[datetime] = Query(None, description="Filter documents to date"),
    sort_by: DocumentSortField = Query(
        DocumentSortField.CREATED_AT,
        description="Sort field (created_at, updated_at, title, filename, file_size_bytes, processing_status, document_type)",
    ),
    sort_order: SortOrder = Query(
        SortOrder.DESC, description="Sort order: asc or desc"
    ),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    List documents with pagination and comprehensive filtering
    """
    try:
        # Build query with eager loading to prevent N+1 queries
        query = (
            db.query(Document)
            .options(
                # Eager load relationships that might be accessed
                joinedload(Document.uploaded_by_user),
                joinedload(Document.organization),
            )
            .filter(
                Document.organization_id == organization.id,
                Document.is_deleted == False,
            )
        )

        # Apply filters
        if document_type:
            query = query.filter(Document.document_type == document_type)

        if processing_status:
            query = query.filter(Document.processing_status == processing_status)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                Document.title.ilike(search_pattern)
                | Document.filename.ilike(search_pattern)
                | Document.content_text.ilike(search_pattern)
            )

        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            for tag in tag_list:
                query = query.filter(Document.tags.contains([tag]))

        if is_public is not None:
            query = query.filter(Document.is_public == is_public)

        if date_from:
            query = query.filter(Document.created_at >= date_from)

        if date_to:
            query = query.filter(Document.created_at <= date_to)

        # Apply sorting - sort_by is now a validated enum, preventing SQL injection
        sort_column = getattr(Document, sort_by.value, Document.created_at)
        if sort_order == SortOrder.DESC:
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Count total results
        total = query.count()

        # Apply pagination
        offset = (page - 1) * size
        documents = query.offset(offset).limit(size).all()

        # Convert to response format
        document_responses = []
        for doc in documents:
            document_responses.append(
                DocumentResponse(
                    id=str(doc.id),
                    title=doc.title,
                    filename=doc.filename,
                    document_type=doc.document_type.value,
                    file_size_bytes=doc.file_size_bytes,
                    file_size_mb=doc.file_size_mb,
                    mime_type=doc.mime_type,
                    processing_status=doc.get_mapped_status(),
                    tags=doc.tags,
                    is_public=doc.is_public,
                    content_preview=doc.get_content_preview(200),
                    content_summary=doc.content_summary,
                    created_at=doc.created_at.isoformat(),
                    updated_at=doc.updated_at.isoformat(),
                    uploaded_by_user_id=str(doc.uploaded_by_user_id),
                    organization_id=str(doc.organization_id),
                )
            )

        total_pages = (total + size - 1) // size
        has_next = page < total_pages
        has_prev = page > 1

        return DocumentListResponse(
            documents=document_responses,
            pagination=PaginationInfo(
                page=page,
                page_size=size,
                total=total,
                total_pages=total_pages,
                has_next=has_next,
                has_prev=has_prev,
            ),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}",
        )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: str,
    include_content: bool = Query(False, description="Include full text content"),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific document
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == organization.id,
            Document.is_deleted == False,
        )
        .first()
    )

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

    return DocumentDetailResponse(
        id=str(document.id),
        title=document.title,
        filename=document.filename,
        document_type=document.document_type.value,
        file_size_bytes=document.file_size_bytes,
        file_size_mb=document.file_size_mb,
        mime_type=document.mime_type,
        processing_status=document.to_dict()["processing_status"],
        tags=document.tags,
        is_public=document.is_public,
        content_preview=document.get_content_preview(500),
        content_summary=document.content_summary,
        content_text=document.content_text if include_content else None,
        metadata=document.get_metadata(),
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
        uploaded_by_user_id=str(document.uploaded_by_user_id),
        organization_id=str(document.organization_id),
        processing_started_at=document.processing_started_at,
        processing_completed_at=document.processing_completed_at,
        processing_error=document.processing_error,
        processing_retry_count=document.processing_retry_count,
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    cascade: bool = Query(True, description="Cascade delete related entities and jobs"),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
    file_service: FileService = Depends(get_file_service),
):
    """
    Delete a document with optional cascade deletion
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == organization.id,
            Document.is_deleted == False,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # Check permissions (owner or admin)
    from src.models.user import UserRole

    if (
        document.uploaded_by_user_id != current_user.id
        and not current_user.has_permission(UserRole.ADMIN)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only delete your own documents or require admin role",
        )

    try:
        # Start transaction
        db.begin()

        if cascade:
            # Delete related entities
            db.query(Entity).filter(
                Entity.document_id == document_id, Entity.is_deleted == False
            ).update({"is_deleted": True, "deleted_at": datetime.utcnow()})

            # Delete related processing jobs
            db.query(ProcessingJob).filter(
                ProcessingJob.document_id == document_id,
                ProcessingJob.is_deleted == False,
            ).update({"is_deleted": True, "deleted_at": datetime.utcnow()})

        # Delete physical file
        import os

        if os.path.exists(document.file_path):
            os.remove(document.file_path)

        # Soft delete document
        document.soft_delete()

        # Update organization storage usage
        organization = document.organization
        organization.update_storage_usage(-document.file_size_bytes)

        db.commit()

        return {
            "message": "Document deleted successfully",
            "document_id": str(document.id),
            "cascade_deleted": cascade,
            "file_size_freed": document.file_size_bytes,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}",
        )


@router.get("/{document_id}/entities", response_model=DocumentEntitiesResponse)
async def get_document_entities(
    document_id: str,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    min_confidence: Optional[float] = Query(
        0.0, ge=0.0, le=1.0, description="Minimum confidence score"
    ),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Get entities extracted from a specific document
    """
    # Verify document exists and user has access
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == organization.id,
            Document.is_deleted == False,
        )
        .first()
    )

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
        # Build entities query
        query = db.query(Entity).filter(
            Entity.document_id == document_id, Entity.is_deleted == False
        )

        if entity_type:
            query = query.filter(Entity.entity_type == entity_type)

        if min_confidence > 0:
            query = query.filter(Entity.confidence_score >= min_confidence)

        # Count total entities
        total = query.count()

        # Apply pagination
        offset = (page - 1) * size
        entities = query.offset(offset).limit(size).all()

        # Convert to response format
        entity_responses = []
        for entity in entities:
            entity_responses.append(
                DocumentEntityResponse(
                    id=str(entity.id),
                    name=entity.name,
                    entity_type=entity.entity_type.value,
                    confidence_score=entity.confidence_score,
                    extraction_method=entity.extraction_method.value,
                    metadata=entity.metadata,
                )
            )

        return DocumentEntitiesResponse(
            document_id=document_id, entities=entity_responses, total_entities=total
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document entities: {str(e)}",
        )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Get real-time processing status of a document
    """
    # Verify document exists and user has access
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == organization.id,
            Document.is_deleted == False,
        )
        .first()
    )

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

    # Get latest processing job
    processing_job = (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.document_id == document_id, ProcessingJob.is_deleted == False
        )
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )

    # Calculate estimated completion
    estimated_completion = None
    if (
        processing_job
        and processing_job.started_at
        and processing_job.progress_percentage < 100
    ):
        # Simple estimation based on current progress
        elapsed_time = (datetime.utcnow() - processing_job.started_at).total_seconds()
        if processing_job.progress_percentage > 0:
            estimated_total_time = elapsed_time / (
                processing_job.progress_percentage / 100
            )
            estimated_completion = processing_job.started_at + timedelta(
                seconds=estimated_total_time
            )

    return DocumentStatusResponse(
        document_id=document_id,
        processing_status=document.to_dict()["processing_status"],
        progress_percentage=(
            processing_job.progress_percentage if processing_job else 0.0
        ),
        current_step=processing_job.current_step if processing_job else None,
        processing_started_at=document.processing_started_at,
        estimated_completion=estimated_completion,
        error_message=document.processing_error
        or (processing_job.error_message if processing_job else None),
    )


@router.post(
    "/search",
    response_model=DocumentSearchResponse,
    summary="Search documents with hybrid search",
    description="""
    Perform full-text search across document titles, filenames, and content.
    
    ## Search Behavior
    - Searches title, filename, content_text, and content_summary fields
    - Results are ordered by relevance (title matches prioritized)
    - Returns matching documents with highlighted preview
    
    ## Filtering Options
    - **document_types**: List of document types to include
    - **tags**: List of tags to filter by (AND logic)
    - **date_range**: Quick date filters (last_week, last_month, last_year)
    
    ## Performance Notes
    - Uses eager loading to prevent N+1 query issues
    - Optimized for organizations with up to 100k documents
    """,
    responses={
        200: {
            "description": "Search results",
            "content": {
                "application/json": {
                    "example": {
                        "documents": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440001",
                                "title": "Machine Learning Guide",
                                "filename": "ml-guide.pdf",
                                "document_type": "pdf",
                                "processing_status": "indexed",
                                "content_preview": "...comprehensive guide to machine learning...",
                            }
                        ],
                        "pagination": {"page": 1, "total": 15, "has_next": False},
                        "search_query": "machine learning",
                        "search_filters": {
                            "document_types": ["pdf"],
                            "date_range": "last_month",
                        },
                    }
                }
            },
        },
        400: {"description": "Invalid query parameters"},
        401: {"description": "Not authenticated"},
    },
)
async def search_documents(
    query: str = Query(..., description="Search query"),
    document_types: Optional[List[DocumentType]] = Query(
        None, description="Filter by document types"
    ),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    date_range: Optional[str] = Query(
        None, description="Date range filter (e.g., 'last_week', 'last_month')"
    ),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Advanced document search with multiple filters
    """
    try:
        # Build base query with eager loading to prevent N+1 queries
        db_query = (
            db.query(Document)
            .options(
                joinedload(Document.uploaded_by_user),
                joinedload(Document.organization),
            )
            .filter(
                Document.organization_id == organization.id,
                Document.is_deleted == False,
            )
        )

        # Apply text search
        search_pattern = f"%{query}%"
        db_query = db_query.filter(
            Document.title.ilike(search_pattern)
            | Document.filename.ilike(search_pattern)
            | Document.content_text.ilike(search_pattern)
            | Document.content_summary.ilike(search_pattern)
        )

        # Apply document type filter
        if document_types:
            db_query = db_query.filter(Document.document_type.in_(document_types))

        # Apply tags filter
        if tags:
            for tag in tags:
                db_query = db_query.filter(Document.tags.contains([tag]))

        # Apply date range filter
        if date_range:
            now = datetime.utcnow()
            if date_range == "last_week":
                date_from = now - timedelta(days=7)
                db_query = db_query.filter(Document.created_at >= date_from)
            elif date_range == "last_month":
                date_from = now - timedelta(days=30)
                db_query = db_query.filter(Document.created_at >= date_from)
            elif date_range == "last_year":
                date_from = now - timedelta(days=365)
                db_query = db_query.filter(Document.created_at >= date_from)

        # Order by relevance (simple implementation - prioritize title matches)
        db_query = db_query.order_by(
            Document.title.ilike(search_pattern).desc(), Document.created_at.desc()
        )

        # Count total results
        total = db_query.count()

        # Apply pagination
        offset = (page - 1) * size
        documents = db_query.offset(offset).limit(size).all()

        # Convert to response format
        document_responses = []
        for doc in documents:
            document_responses.append(
                DocumentResponse(
                    id=str(doc.id),
                    title=doc.title,
                    filename=doc.filename,
                    document_type=doc.document_type.value,
                    file_size_bytes=doc.file_size_bytes,
                    file_size_mb=doc.file_size_mb,
                    mime_type=doc.mime_type,
                    processing_status=doc.get_mapped_status(),
                    tags=doc.tags,
                    is_public=doc.is_public,
                    content_preview=doc.get_content_preview(200),
                    content_summary=doc.content_summary,
                    created_at=doc.created_at.isoformat(),
                    updated_at=doc.updated_at.isoformat(),
                    uploaded_by_user_id=str(doc.uploaded_by_user_id),
                    organization_id=str(doc.organization_id),
                )
            )

        total_pages = (total + size - 1) // size
        has_next = page < total_pages
        has_prev = page > 1

        return DocumentSearchResponse(
            documents=document_responses,
            pagination=PaginationInfo(
                page=page,
                page_size=size,
                total=total,
                total_pages=total_pages,
                has_next=has_next,
                has_prev=has_prev,
            ),
            search_query=query,
            search_filters={
                "document_types": (
                    [dt.value for dt in document_types] if document_types else None
                ),
                "tags": tags,
                "date_range": date_range,
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document search failed: {str(e)}",
        )


@router.post("/bulk-delete", response_model=BulkDocumentResponse)
async def bulk_delete_documents(
    request: BulkDocumentRequest,
    cascade: bool = Query(True, description="Cascade delete related data"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
    file_service: FileService = Depends(get_file_service),
):
    """
    Bulk delete multiple documents
    """
    if current_user.has_permission(UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bulk delete requires admin privileges",
        )

    successful = []
    failed = []

    for document_id in request.document_ids:
        try:
            document = (
                db.query(Document)
                .filter(
                    Document.id == document_id,
                    Document.organization_id == organization.id,
                    Document.is_deleted == False,
                )
                .first()
            )

            if not document:
                failed.append(
                    {"document_id": document_id, "error": "Document not found"}
                )
                continue

            # Perform deletion
            if cascade:
                # Delete related entities
                db.query(Entity).filter(
                    Entity.document_id == document_id, Entity.is_deleted == False
                ).update({"is_deleted": True, "deleted_at": datetime.utcnow()})

                # Delete related processing jobs
                db.query(ProcessingJob).filter(
                    ProcessingJob.document_id == document_id,
                    ProcessingJob.is_deleted == False,
                ).update({"is_deleted": True, "deleted_at": datetime.utcnow()})

            # Delete physical file
            import os

            if os.path.exists(document.file_path):
                os.remove(document.file_path)

            # Soft delete document
            document.soft_delete()

            # Update organization storage usage
            org = document.organization
            org.update_storage_usage(-document.file_size_bytes)

            successful.append(document_id)

        except Exception as e:
            failed.append({"document_id": document_id, "error": str(e)})

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to commit bulk delete: {str(e)}",
        )

    return BulkDocumentResponse(
        successful=successful,
        failed=failed,
        total_processed=len(request.document_ids),
        success_count=len(successful),
        failure_count=len(failed),
    )


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: str,
    force_reprocess: bool = Query(
        False, description="Force reprocess even if already completed"
    ),
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
):
    """
    Trigger reprocessing of a document
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == organization.id,
            Document.is_deleted == False,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # Check permissions
    if document.uploaded_by_user_id != current_user.id and current_user.has_permission(
        UserRole.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only reprocess your own documents or require admin role",
        )

    # Check if reprocessing is needed
    if document.processing_status == ProcessingStatus.COMPLETED and not force_reprocess:
        return {
            "message": "Document already processed successfully. Use force_reprocess=true to override.",
            "processing_status": document.processing_status.value,
        }

    try:
        # Reset processing status
        document.processing_status = ProcessingStatus.PENDING
        document.processing_error = None
        document.processing_retry_count = 0
        document.processing_started_at = None
        document.processing_completed_at = None

        db.commit()

        # Create new processing job
        processing_job = ProcessingJob(
            job_type="document_reprocessing",
            status=JobStatus.PENDING,
            priority="normal",
            document_id=document.id,
            organization_id=organization.id,
            created_by_user_id=current_user.id,
            parameters={
                "document_id": str(document.id),
                "file_path": document.file_path,
                "document_type": document.document_type.value,
                "mime_type": document.mime_type,
                "force_reprocess": force_reprocess,
            },
            config={"max_retries": 3, "timeout_seconds": 300},
            total_steps=5,
            queue_name="document_processing",
        )

        db.add(processing_job)
        db.commit()

        # Queue the job for processing
        from src.tasks.processing_tasks import process_document_ingestion

        process_document_ingestion.delay(str(processing_job.id))

        return {
            "message": "Document queued for reprocessing",
            "document_id": str(document.id),
            "processing_status": document.processing_status.value,
            "job_id": str(processing_job.id),
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue document for reprocessing: {str(e)}",
        )
