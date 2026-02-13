"""Projects API endpoints for Research Assistant feature.

Handles research project CRUD operations, document management,
notes, and bibliography generation.

User Story 4: Organize Documents into Research Projects
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from src.core.database import get_db
from src.models import Collection, CollectionDocument, Document, ProjectNote, User
from src.services.research.bibliography_service import BibliographyService
from src.services.research.project_service import ProjectService
from src.services.security.user_management import get_current_user
from src.shared.research_schemas import (
    NoteCreate,
    NoteListResponse,
    NoteResponse,
    NoteUpdate,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)

logger = get_logger()
router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


# =========================================================================
# Project CRUD (T061)
# =========================================================================


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    workspace_id: Optional[UUID] = Query(None, description="Filter by workspace"),
    project_status: Optional[str] = Query(None, description="Filter by status"),
    project_type: Optional[str] = Query(None, description="Filter by type"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search by name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's research projects with filtering.

    Args:
        workspace_id: Optional workspace filter
        project_status: Filter by research_status (active/paused/completed/archived)
        project_type: Filter by project_type (research/literature_review/thesis/paper)
        tag: Filter by tag
        search: Search by project name
        skip: Pagination offset
        limit: Pagination limit
        current_user: Authenticated user
        db: Database session

    Returns:
        Paginated list of projects
    """
    try:
        service = ProjectService(db)
        result = await service.list_projects(
            user_id=current_user.id,
            workspace_id=workspace_id,
            project_status=project_status,
            project_type=project_type,
            tag=tag,
            search=search,
            skip=skip,
            limit=limit,
        )

        return ProjectListResponse(
            projects=[_to_project_response(p) for p in result["projects"]],
            total=result["total"],
            page=result["page"],
            size=result["size"],
            has_next=result["has_next"],
            has_prev=result["has_prev"],
        )

    except Exception as e:
        logger.error("list_projects_failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list projects: {str(e)}",
        )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new research project.

    Args:
        project_data: Project creation data
        current_user: Authenticated user
        db: Database session

    Returns:
        Created project
    """
    try:
        service = ProjectService(db)
        project = await service.create_project(
            user_id=current_user.id,
            project_data=project_data,
        )

        logger.info(
            "project_created",
            project_id=str(project.id),
            name=project.name,
            user_id=str(current_user.id),
        )

        return _to_project_response(project)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(
            "create_project_failed", error=str(e), user_id=str(current_user.id)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}",
        )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get project details with documents and notes.

    Args:
        project_id: Project ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Project details with associated data
    """
    try:
        service = ProjectService(db)
        project = await service.get_project_for_user(
            project_id=project_id,
            user_id=current_user.id,
        )

        # Get documents
        doc_query = (
            select(CollectionDocument)
            .where(CollectionDocument.collection_id == project_id)
            .options(selectinload(CollectionDocument.document))
            .order_by(CollectionDocument.sort_order)
        )
        doc_result = await db.execute(doc_query)
        collection_docs = doc_result.scalars().all()

        # Get notes
        note_query = (
            select(ProjectNote)
            .where(ProjectNote.project_id == project_id)
            .order_by(ProjectNote.is_pinned.desc(), ProjectNote.updated_at.desc())
        )
        note_result = await db.execute(note_query)
        notes = note_result.scalars().all()

        return ProjectDetailResponse(
            **_to_project_response(project).model_dump(),
            documents=[
                {
                    "id": str(cd.document.id),
                    "filename": cd.document.filename,
                    "file_type": cd.document.file_type,
                    "status": cd.document.status,
                    "created_at": cd.document.created_at.isoformat(),
                    "sort_order": cd.sort_order,
                }
                for cd in collection_docs
                if cd.document
            ],
            notes=[_to_note_response(n) for n in notes],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_project_failed", error=str(e), project_id=str(project_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get project: {str(e)}",
        )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update project details.

    Args:
        project_id: Project ID
        project_data: Update data (partial)
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated project
    """
    try:
        service = ProjectService(db)
        project = await service.update_project(
            user_id=current_user.id,
            project_id=project_id,
            project_data=project_data,
        )

        logger.info("project_updated", project_id=str(project_id))

        return _to_project_response(project)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("update_project_failed", error=str(e), project_id=str(project_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project: {str(e)}",
        )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project.

    Args:
        project_id: Project ID
        current_user: Authenticated user
        db: Database session
    """
    try:
        service = ProjectService(db)
        await service.delete_project(
            user_id=current_user.id,
            project_id=project_id,
        )

        logger.info("project_deleted", project_id=str(project_id))

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("delete_project_failed", error=str(e), project_id=str(project_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}",
        )


# =========================================================================
# Project Documents (T062)
# =========================================================================


@router.get("/{project_id}/documents")
async def list_project_documents(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List documents in a project.

    Args:
        project_id: Project ID
        current_user: Authenticated user
        db: Database session

    Returns:
        List of documents
    """
    try:
        await _get_project_with_auth(project_id, current_user, db)

        query = (
            select(CollectionDocument)
            .where(CollectionDocument.collection_id == project_id)
            .options(selectinload(CollectionDocument.document))
            .order_by(CollectionDocument.sort_order)
        )
        result = await db.execute(query)
        collection_docs = result.scalars().all()

        documents = []
        for cd in collection_docs:
            if not cd.document:
                continue
            documents.append(
                {
                    "id": str(cd.id),
                    "project_id": str(project_id),
                    "document_id": str(cd.document_id),
                    "added_at": cd.created_at.isoformat() if cd.created_at else None,
                    "sort_order": cd.sort_order,
                    "document": {
                        "id": str(cd.document.id),
                        "title": cd.document.title or cd.document.filename,
                        "filename": cd.document.filename,
                        "status": cd.document.status,
                        "created_at": cd.document.created_at.isoformat()
                        if cd.document.created_at
                        else None,
                    },
                }
            )

        return {
            "documents": documents,
            "total": len(documents),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_project_documents_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}",
        )


@router.post("/{project_id}/documents", status_code=status.HTTP_201_CREATED)
async def add_document_to_project(
    project_id: UUID,
    document_id: UUID,
    sort_order: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a document to a project.

    Args:
        project_id: Project ID
        document_id: Document ID to add
        sort_order: Optional sort order
        current_user: Authenticated user
        db: Database session

    Returns:
        Created association
    """
    try:
        await _get_project_with_auth(project_id, current_user, db)

        # Verify document exists
        doc_query = select(Document).where(Document.id == document_id)
        doc_result = await db.execute(doc_query)
        document = doc_result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )

        # Check if already in project
        existing_query = select(CollectionDocument).where(
            and_(
                CollectionDocument.collection_id == project_id,
                CollectionDocument.document_id == document_id,
            )
        )
        existing_result = await db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document already in project",
            )

        # Add document to project
        collection_doc = CollectionDocument(
            collection_id=project_id,
            document_id=document_id,
            sort_order=sort_order,
        )
        db.add(collection_doc)
        await db.commit()
        await db.refresh(collection_doc)

        logger.info(
            "document_added_to_project",
            project_id=str(project_id),
            document_id=str(document_id),
        )

        return {
            "id": str(collection_doc.id),
            "project_id": str(project_id),
            "document_id": str(document_id),
            "added_at": collection_doc.created_at.isoformat()
            if collection_doc.created_at
            else None,
            "sort_order": sort_order,
            "document": {
                "id": str(document.id),
                "title": document.title or document.filename,
                "filename": document.filename,
                "status": document.status,
                "created_at": document.created_at.isoformat()
                if document.created_at
                else None,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("add_document_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add document: {str(e)}",
        )


@router.delete(
    "/{project_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_document_from_project(
    project_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a document from a project.

    Args:
        project_id: Project ID
        document_id: Document ID to remove
        current_user: Authenticated user
        db: Database session
    """
    try:
        await _get_project_with_auth(project_id, current_user, db)

        # Find and delete the association
        query = select(CollectionDocument).where(
            and_(
                CollectionDocument.collection_id == project_id,
                CollectionDocument.document_id == document_id,
            )
        )
        result = await db.execute(query)
        collection_doc = result.scalar_one_or_none()

        if not collection_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found in project",
            )

        await db.delete(collection_doc)
        await db.commit()

        logger.info(
            "document_removed_from_project",
            project_id=str(project_id),
            document_id=str(document_id),
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("remove_document_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove document: {str(e)}",
        )


# =========================================================================
# Project Notes (T063)
# =========================================================================


@router.get("/{project_id}/notes", response_model=NoteListResponse)
async def list_project_notes(
    project_id: UUID,
    tag: Optional[str] = Query(None, description="Filter by tag"),
    pinned_only: bool = Query(False, description="Show only pinned notes"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List notes in a project.

    Args:
        project_id: Project ID
        tag: Optional tag filter
        pinned_only: Only return pinned notes
        skip: Pagination offset
        limit: Pagination limit
        current_user: Authenticated user
        db: Database session

    Returns:
        Paginated list of notes
    """
    try:
        await _get_project_with_auth(project_id, current_user, db)

        query = select(ProjectNote).where(ProjectNote.project_id == project_id)

        filters = []
        if tag:
            filters.append(ProjectNote.tags.contains([tag]))
        if pinned_only:
            filters.append(ProjectNote.is_pinned == True)

        if filters:
            query = query.where(and_(*filters))

        # Get total count
        count_query = select(func.count(ProjectNote.id)).where(
            ProjectNote.project_id == project_id
        )
        if filters:
            count_query = count_query.where(and_(*filters))
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        query = (
            query.order_by(ProjectNote.is_pinned.desc(), ProjectNote.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(query)
        notes = result.scalars().all()

        # Calculate pagination values
        page = (skip // limit) + 1 if limit > 0 else 1

        return NoteListResponse(
            notes=[_to_note_response(n) for n in notes],
            total=total,
            page=page,
            size=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_notes_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list notes: {str(e)}",
        )


@router.post(
    "/{project_id}/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_note(
    project_id: UUID,
    note_data: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a note in a project.

    Args:
        project_id: Project ID
        note_data: Note creation data
        current_user: Authenticated user
        db: Database session

    Returns:
        Created note
    """
    try:
        await _get_project_with_auth(project_id, current_user, db)

        note = ProjectNote(
            project_id=project_id,
            user_id=current_user.id,
            title=note_data.title,
            content=note_data.content,
            linked_document_ids=note_data.linked_document_ids or [],
            tags=note_data.tags or [],
            is_pinned=note_data.is_pinned or False,
        )

        db.add(note)
        await db.commit()
        await db.refresh(note)

        logger.info(
            "note_created",
            note_id=str(note.id),
            project_id=str(project_id),
        )

        return _to_note_response(note)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("create_note_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create note: {str(e)}",
        )


@router.get("/{project_id}/notes/{note_id}", response_model=NoteResponse)
async def get_note(
    project_id: UUID,
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific note.

    Args:
        project_id: Project ID
        note_id: Note ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Note details
    """
    try:
        await _get_project_with_auth(project_id, current_user, db)

        note = await _get_note(project_id, note_id, db)
        return _to_note_response(note)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_note_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get note: {str(e)}",
        )


@router.patch("/{project_id}/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    project_id: UUID,
    note_id: UUID,
    note_data: NoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a note.

    Args:
        project_id: Project ID
        note_id: Note ID
        note_data: Update data (partial)
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated note
    """
    try:
        await _get_project_with_auth(project_id, current_user, db)
        note = await _get_note(project_id, note_id, db)

        # Update fields
        if note_data.title is not None:
            note.title = note_data.title
        if note_data.content is not None:
            note.content = note_data.content
        if note_data.linked_document_ids is not None:
            note.linked_document_ids = note_data.linked_document_ids
        if note_data.tags is not None:
            note.tags = note_data.tags
        if note_data.is_pinned is not None:
            note.is_pinned = note_data.is_pinned

        await db.commit()
        await db.refresh(note)

        logger.info("note_updated", note_id=str(note_id))

        return _to_note_response(note)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("update_note_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update note: {str(e)}",
        )


@router.delete("/{project_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    project_id: UUID,
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a note.

    Args:
        project_id: Project ID
        note_id: Note ID
        current_user: Authenticated user
        db: Database session
    """
    try:
        await _get_project_with_auth(project_id, current_user, db)
        note = await _get_note(project_id, note_id, db)

        await db.delete(note)
        await db.commit()

        logger.info("note_deleted", note_id=str(note_id))

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("delete_note_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete note: {str(e)}",
        )


@router.post("/{project_id}/notes/{note_id}/pin")
async def toggle_note_pin(
    project_id: UUID,
    note_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle note pinned status.

    Args:
        project_id: Project ID
        note_id: Note ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated pin status
    """
    try:
        await _get_project_with_auth(project_id, current_user, db)
        note = await _get_note(project_id, note_id, db)

        note.is_pinned = not note.is_pinned
        await db.commit()
        await db.refresh(note)

        logger.info("note_pin_toggled", note_id=str(note_id), is_pinned=note.is_pinned)

        return _to_note_response(note)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("toggle_pin_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle pin: {str(e)}",
        )


# =========================================================================
# Project Bibliography (T064)
# =========================================================================


@router.get("/{project_id}/bibliography")
async def get_project_bibliography(
    project_id: UUID,
    format: str = Query("bibtex", regex="^(bibtex|ieee|apa|mla)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate bibliography from all project documents.

    Args:
        project_id: Project ID
        format: Bibliography format (bibtex/ieee/apa/mla)
        current_user: Authenticated user
        db: Database session

    Returns:
        Formatted bibliography payload
    """
    from src.models import Citation

    try:
        project = await _get_project_with_auth(project_id, current_user, db)

        # Get all documents in project
        doc_query = select(CollectionDocument.document_id).where(
            CollectionDocument.collection_id == project_id
        )
        doc_result = await db.execute(doc_query)
        document_ids = [row[0] for row in doc_result.all()]

        if not document_ids:
            return {
                "project_id": str(project_id),
                "project_name": project.name,
                "content": "",
                "citation_count": 0,
                "format": format,
                "message": "No documents in project",
                "generated_at": datetime.utcnow().isoformat(),
            }

        # Get citations for these documents
        citation_query = select(Citation).where(Citation.document_id.in_(document_ids))
        citation_result = await db.execute(citation_query)
        citations = citation_result.scalars().all()

        if not citations:
            return {
                "project_id": str(project_id),
                "project_name": project.name,
                "content": "",
                "citation_count": 0,
                "format": format,
                "message": "No citations found for project documents",
                "generated_at": datetime.utcnow().isoformat(),
            }

        # Format bibliography
        bibliography = BibliographyService.format_bibliography(
            citations=list(citations),
            format_type=format,
        )

        logger.info(
            "project_bibliography_generated",
            project_id=str(project_id),
            format=format,
            citation_count=len(citations),
        )

        return {
            "project_id": str(project_id),
            "project_name": project.name,
            "format": format,
            "content": bibliography,
            "citation_count": len(citations),
            "generated_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("generate_bibliography_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate bibliography: {str(e)}",
        )


# =========================================================================
# Helper Functions
# =========================================================================


async def _get_project_with_auth(
    project_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> Collection:
    """Get project with authorization check.

    Args:
        project_id: Project ID
        current_user: Current user
        db: Database session

    Returns:
        Project if authorized

    Raises:
        HTTPException: If not found or not authorized
    """
    from src.models import Workspace

    query = (
        select(Collection)
        .options(selectinload(Collection.documents))
        .join(Workspace, Collection.workspace_id == Workspace.id)
        .where(
            and_(
                Collection.id == project_id,
                Workspace.owner_id == current_user.id,
            )
        )
    )
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found or access denied",
        )

    return project


async def _get_note(
    project_id: UUID,
    note_id: UUID,
    db: AsyncSession,
) -> ProjectNote:
    """Get note by ID within a project.

    Args:
        project_id: Project ID
        note_id: Note ID
        db: Database session

    Returns:
        Note if found

    Raises:
        HTTPException: If not found
    """
    query = select(ProjectNote).where(
        and_(
            ProjectNote.id == note_id,
            ProjectNote.project_id == project_id,
        )
    )
    result = await db.execute(query)
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )

    return note


def _to_project_response(project: Collection) -> ProjectResponse:
    """Convert Collection to ProjectResponse."""
    # Avoid async lazy-loading of relationship attributes in response serialization.
    # Accessing `project.documents` when it wasn't eagerly loaded can raise:
    # "greenlet_spawn has not been called; can't call await_only() here."
    documents = project.__dict__.get("documents")
    document_count = len(documents) if documents else 0

    return ProjectResponse(
        id=project.id,
        workspace_id=project.workspace_id,
        name=project.name,
        description=project.description,
        project_type=project.project_type,
        research_status=project.research_status,
        research_goals=project.research_goals,
        deadline=project.deadline,
        tags=project.tags or [],
        is_private=project.is_private,
        document_count=document_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _to_note_response(note: ProjectNote) -> NoteResponse:
    """Convert ProjectNote to NoteResponse."""
    linked_docs = note.linked_document_ids or []
    return NoteResponse(
        id=note.id,
        project_id=note.project_id,
        user_id=note.user_id,
        title=note.title,
        content=note.content,
        content_preview=note.content_preview,
        linked_document_ids=linked_docs,
        linked_document_count=len(linked_docs),
        tags=note.tags or [],
        is_pinned=note.is_pinned,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )
