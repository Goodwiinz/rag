"""
Collection endpoints, nested and standalone (Task 4.2 split of the former
monolithic ``backend/src/api/threads/workspaces.py``).
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.collection import Collection, CollectionDocument
from src.models.user import User
from src.schemas.chat import (
    CollectionCreate,
    CollectionDetailResponse,
    CollectionDocumentAdd,
    CollectionDocumentRemove,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdate,
)

from .dependencies import (
    _get_accessible_document_or_none,
    _get_collection_or_404,
    _get_workspace_or_404,
)
from .presenters import _collection_to_detail_response, _collection_to_response

router = APIRouter(prefix="/api/v2/workspaces", tags=["workspaces"])

# Standalone router for flat API paths (used by frontend)
standalone_router = APIRouter(prefix="/api/v2", tags=["workspaces-flat"])

# ============================================================================
# Collection Endpoints
# ============================================================================


@router.post(
    "/{workspace_id}/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_collection(
    workspace_id: UUID,
    request: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new collection in a workspace"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    collection = Collection(
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon,
    )
    db.add(collection)

    # Add initial documents if provided
    if request.document_ids:
        for i, doc_id in enumerate(request.document_ids):
            doc = await _get_accessible_document_or_none(db, doc_id, current_user)
            if doc:
                collection_doc = CollectionDocument(
                    collection=collection, document_id=doc_id, sort_order=i
                )
                db.add(collection_doc)

    await db.commit()
    await db.refresh(collection)

    return _collection_to_response(collection)


@router.get("/{workspace_id}/collections", response_model=CollectionListResponse)
async def list_collections(
    workspace_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List collections in a workspace"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    base_conditions = [
        Collection.workspace_id == workspace_id,
        Collection.is_deleted == False,
    ]

    # Count total
    count_stmt = select(func.count(Collection.id)).where(*base_conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Fetch collections with eager-loaded documents for document_count property
    offset = (page - 1) * limit
    stmt = (
        select(Collection)
        .options(selectinload(Collection.documents))
        .where(*base_conditions)
        .order_by(Collection.name)
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    collections = result.scalars().all()

    return CollectionListResponse(
        collections=[_collection_to_response(c) for c in collections],
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(collections)) < total,
    )


@router.get(
    "/{workspace_id}/collections/{collection_id}",
    response_model=CollectionDetailResponse,
)
async def get_collection(
    workspace_id: UUID,
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get collection details with documents"""
    collection = await _get_collection_or_404(
        db, workspace_id, collection_id, current_user
    )

    return _collection_to_detail_response(collection)


@router.patch(
    "/{workspace_id}/collections/{collection_id}", response_model=CollectionResponse
)
async def update_collection(
    workspace_id: UUID,
    collection_id: UUID,
    request: CollectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update collection details"""
    collection = await _get_collection_or_404(
        db, workspace_id, collection_id, current_user
    )
    workspace = collection.workspace

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if request.name is not None:
        collection.name = request.name
    if request.description is not None:
        collection.description = request.description
    if request.color is not None:
        collection.color = request.color
    if request.icon is not None:
        collection.icon = request.icon

    collection.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(collection)

    return _collection_to_response(collection)


@router.delete(
    "/{workspace_id}/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_collection(
    workspace_id: UUID,
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a collection"""
    collection = await _get_collection_or_404(
        db, workspace_id, collection_id, current_user
    )

    if not collection.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    collection.is_deleted = True
    collection.deleted_at = datetime.utcnow()
    await db.commit()


@router.post(
    "/{workspace_id}/collections/{collection_id}/documents",
    response_model=CollectionDetailResponse,
)
async def add_documents_to_collection(
    workspace_id: UUID,
    collection_id: UUID,
    request: CollectionDocumentAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add documents to a collection"""
    collection = await _get_collection_or_404(
        db, workspace_id, collection_id, current_user
    )

    if not collection.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Get current max sort order
    max_order_stmt = select(func.max(CollectionDocument.sort_order)).where(
        CollectionDocument.collection_id == collection_id
    )
    max_order_result = await db.execute(max_order_stmt)
    max_order = max_order_result.scalar() or 0

    for i, doc_id in enumerate(request.document_ids):
        # Check if document exists
        doc = await _get_accessible_document_or_none(db, doc_id, current_user)
        if not doc:
            continue

        # Check if already in collection
        existing_stmt = select(CollectionDocument).where(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == doc_id,
            CollectionDocument.is_deleted == False,
        )
        existing_result = await db.execute(existing_stmt)
        existing = existing_result.scalars().first()

        if not existing:
            collection_doc = CollectionDocument(
                collection_id=collection_id,
                document_id=doc_id,
                sort_order=max_order + i + 1,
            )
            db.add(collection_doc)

    await db.commit()
    await db.refresh(collection)

    return _collection_to_detail_response(collection)


@router.delete(
    "/{workspace_id}/collections/{collection_id}/documents",
    response_model=CollectionDetailResponse,
)
async def remove_documents_from_collection(
    workspace_id: UUID,
    collection_id: UUID,
    request: CollectionDocumentRemove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove documents from a collection"""
    collection = await _get_collection_or_404(
        db, workspace_id, collection_id, current_user
    )

    if not collection.workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    for doc_id in request.document_ids:
        collection_doc_stmt = select(CollectionDocument).where(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == doc_id,
            CollectionDocument.is_deleted == False,
        )
        collection_doc_result = await db.execute(collection_doc_stmt)
        collection_doc = collection_doc_result.scalars().first()

        if collection_doc:
            collection_doc.is_deleted = True
            collection_doc.deleted_at = datetime.utcnow()

    await db.commit()
    await db.refresh(collection)

    return _collection_to_detail_response(collection)


# ============================================================================
# Standalone (Flat) Collection Routes
# These routes allow direct access without full path hierarchy
# ============================================================================


@standalone_router.post(
    "/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_collection_standalone(
    request: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new collection (standalone route - uses workspace_id from request body)"""
    workspace = await _get_workspace_or_404(db, request.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    collection = Collection(
        workspace_id=request.workspace_id,
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon,
    )
    db.add(collection)

    # Add initial documents if provided
    if request.document_ids:
        for i, doc_id in enumerate(request.document_ids):
            doc = await _get_accessible_document_or_none(db, doc_id, current_user)
            if doc:
                collection_doc = CollectionDocument(
                    collection=collection, document_id=doc_id, sort_order=i
                )
                db.add(collection_doc)

    await db.commit()
    await db.refresh(collection)

    return _collection_to_response(collection)


@standalone_router.get(
    "/collections/{collection_id}", response_model=CollectionDetailResponse
)
async def get_collection_standalone(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get collection details with documents (standalone route)"""
    coll_stmt = (
        select(Collection)
        .options(selectinload(Collection.documents))
        .where(Collection.id == collection_id, Collection.is_deleted == False)
    )
    coll_result = await db.execute(coll_stmt)
    collection = coll_result.scalars().first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    workspace = await _get_workspace_or_404(db, collection.workspace_id, current_user)

    return _collection_to_detail_response(collection)


@standalone_router.patch(
    "/collections/{collection_id}", response_model=CollectionResponse
)
async def update_collection_standalone(
    collection_id: UUID,
    request: CollectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update collection details (standalone route)"""
    coll_stmt = select(Collection).where(
        Collection.id == collection_id, Collection.is_deleted == False
    )
    coll_result = await db.execute(coll_stmt)
    collection = coll_result.scalars().first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    workspace = await _get_workspace_or_404(db, collection.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if request.name is not None:
        collection.name = request.name
    if request.description is not None:
        collection.description = request.description
    if request.color is not None:
        collection.color = request.color
    if request.icon is not None:
        collection.icon = request.icon

    collection.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(collection)

    return _collection_to_response(collection)


@standalone_router.delete(
    "/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_collection_standalone(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a collection (standalone route)"""
    coll_stmt = select(Collection).where(
        Collection.id == collection_id, Collection.is_deleted == False
    )
    coll_result = await db.execute(coll_stmt)
    collection = coll_result.scalars().first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    workspace = await _get_workspace_or_404(db, collection.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    collection.is_deleted = True
    collection.deleted_at = datetime.utcnow()
    await db.commit()


@standalone_router.post(
    "/collections/{collection_id}/documents", response_model=CollectionDetailResponse
)
async def add_documents_to_collection_standalone(
    collection_id: UUID,
    request: CollectionDocumentAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add documents to a collection (standalone route)"""
    coll_stmt = (
        select(Collection)
        .options(selectinload(Collection.documents))
        .where(Collection.id == collection_id, Collection.is_deleted == False)
    )
    coll_result = await db.execute(coll_stmt)
    collection = coll_result.scalars().first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    workspace = await _get_workspace_or_404(db, collection.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Get current max sort order
    max_order_stmt = select(func.max(CollectionDocument.sort_order)).where(
        CollectionDocument.collection_id == collection_id
    )
    max_order_result = await db.execute(max_order_stmt)
    max_order = max_order_result.scalar() or 0

    for i, doc_id in enumerate(request.document_ids):
        doc = await _get_accessible_document_or_none(db, doc_id, current_user)
        if not doc:
            continue

        existing_stmt = select(CollectionDocument).where(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == doc_id,
            CollectionDocument.is_deleted == False,
        )
        existing_result = await db.execute(existing_stmt)
        existing = existing_result.scalars().first()

        if not existing:
            collection_doc = CollectionDocument(
                collection_id=collection_id,
                document_id=doc_id,
                sort_order=max_order + i + 1,
            )
            db.add(collection_doc)

    await db.commit()
    await db.refresh(collection)

    return _collection_to_detail_response(collection)


@standalone_router.delete(
    "/collections/{collection_id}/documents", response_model=CollectionDetailResponse
)
async def remove_documents_from_collection_standalone(
    collection_id: UUID,
    request: CollectionDocumentRemove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove documents from a collection (standalone route)"""
    coll_stmt = (
        select(Collection)
        .options(selectinload(Collection.documents))
        .where(Collection.id == collection_id, Collection.is_deleted == False)
    )
    coll_result = await db.execute(coll_stmt)
    collection = coll_result.scalars().first()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    workspace = await _get_workspace_or_404(db, collection.workspace_id, current_user)

    if not workspace.can_user_edit(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    for doc_id in request.document_ids:
        collection_doc_stmt = select(CollectionDocument).where(
            CollectionDocument.collection_id == collection_id,
            CollectionDocument.document_id == doc_id,
            CollectionDocument.is_deleted == False,
        )
        collection_doc_result = await db.execute(collection_doc_stmt)
        collection_doc = collection_doc_result.scalars().first()

        if collection_doc:
            collection_doc.is_deleted = True
            collection_doc.deleted_at = datetime.utcnow()

    await db.commit()
    await db.refresh(collection)

    return _collection_to_detail_response(collection)
