"""Citations API endpoints for Research Assistant feature.

Handles:
- Citation persistence from chat messages
- Citation retrieval and filtering
- Citation metadata extraction
- Bibliography export
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from structlog import get_logger

from backend.src.core.database import get_db
from backend.src.core.security import get_current_user
from backend.src.models import User, Citation
from backend.src.shared.research_schemas import (
    CitationCreate,
    CitationUpdate,
    CitationResponse,
    CitationListResponse,
)
from backend.src.services.citation_extraction_service import CitationExtractionService
from backend.src.services.bibliography_service import BibliographyService

logger = get_logger()
router = APIRouter(prefix="/api/v1/citations", tags=["citations"])


@router.post("", response_model=CitationResponse, status_code=status.HTTP_201_CREATED)
async def create_citation(
    citation_data: CitationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new citation from chat message context.

    Args:
        citation_data: Citation creation data
        current_user: Authenticated user
        db: Database session

    Returns:
        Created citation
    """
    try:
        # Create citation instance
        citation = Citation(
            message_id=citation_data.message_id,
            document_id=citation_data.document_id,
            external_reference_id=citation_data.external_reference_id,
            document_title=citation_data.document_title,
            document_type=citation_data.document_type or "paper",
            authors=citation_data.authors,
            year=citation_data.year,
            venue=citation_data.venue,
            doi=citation_data.doi,
            arxiv_id=citation_data.arxiv_id,
            abstract=citation_data.abstract,
            snippet=citation_data.snippet,
            page_number=citation_data.page_number,
            score=citation_data.score or 0.0,
            metadata_source=citation_data.metadata_source or "manual",
            needs_review=citation_data.needs_review or False,
        )

        db.add(citation)
        await db.commit()
        await db.refresh(citation)

        logger.info(
            "citation_created",
            citation_id=str(citation.id),
            document_id=str(citation.document_id) if citation.document_id else None,
            message_id=str(citation.message_id) if citation.message_id else None,
            metadata_source=citation.metadata_source,
        )

        return CitationResponse.model_validate(citation)

    except Exception as e:
        await db.rollback()
        logger.error("citation_creation_failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create citation: {str(e)}",
        )


@router.get("", response_model=CitationListResponse)
async def list_citations(
    message_id: Optional[UUID] = Query(None, description="Filter by message ID"),
    document_id: Optional[UUID] = Query(None, description="Filter by document ID"),
    arxiv_id: Optional[str] = Query(None, description="Filter by ArXiv ID"),
    doi: Optional[str] = Query(None, description="Filter by DOI"),
    needs_review: Optional[bool] = Query(None, description="Filter by needs_review flag"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List citations with filtering.

    Args:
        message_id: Optional message ID filter
        document_id: Optional document ID filter
        arxiv_id: Optional ArXiv ID filter
        doi: Optional DOI filter
        needs_review: Optional needs_review filter
        skip: Pagination offset
        limit: Pagination limit
        current_user: Authenticated user
        db: Database session

    Returns:
        List of citations with pagination metadata
    """
    try:
        # Build query with filters
        query = select(Citation)
        
        filters = []
        if message_id:
            filters.append(Citation.message_id == message_id)
        if document_id:
            filters.append(Citation.document_id == document_id)
        if arxiv_id:
            filters.append(Citation.arxiv_id == arxiv_id)
        if doi:
            filters.append(Citation.doi == doi)
        if needs_review is not None:
            filters.append(Citation.needs_review == needs_review)

        if filters:
            query = query.where(and_(*filters))

        # Get total count
        count_query = select(Citation.id).where(and_(*filters)) if filters else select(Citation.id)
        total_result = await db.execute(count_query)
        total = len(total_result.all())

        # Execute paginated query
        query = query.offset(skip).limit(limit).order_by(Citation.created_at.desc())
        result = await db.execute(query)
        citations = result.scalars().all()

        return CitationListResponse(
            citations=[CitationResponse.model_validate(c) for c in citations],
            total=total,
            skip=skip,
            limit=limit,
        )

    except Exception as e:
        logger.error("citation_list_failed", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list citations: {str(e)}",
        )


@router.get("/{citation_id}", response_model=CitationResponse)
async def get_citation(
    citation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get single citation detail with full snippet.

    Args:
        citation_id: Citation ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Citation details
    """
    try:
        query = select(Citation).where(Citation.id == citation_id)
        result = await db.execute(query)
        citation = result.scalar_one_or_none()

        if not citation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Citation {citation_id} not found",
            )

        return CitationResponse.model_validate(citation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "citation_get_failed",
            error=str(e),
            citation_id=str(citation_id),
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get citation: {str(e)}",
        )


@router.post("/extract", response_model=CitationResponse, status_code=status.HTTP_201_CREATED)
async def extract_citation(
    arxiv_id: Optional[str] = None,
    doi: Optional[str] = None,
    title: Optional[str] = None,
    strategy: str = "auto",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Extract citation metadata using hybrid extraction pipeline.
    
    Args:
        arxiv_id: Optional ArXiv ID
        doi: Optional DOI
        title: Optional paper title
        strategy: Extraction strategy ("auto", "arxiv", "semantic_scholar", "crossref")
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Extracted citation
    """
    if not arxiv_id and not doi and not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide at least one of: arxiv_id, doi, or title"
        )
    
    try:
        extraction_service = CitationExtractionService(db)
        
        # Extract using hybrid strategy
        citation_data, source = await extraction_service.extract_hybrid(
            arxiv_id=arxiv_id,
            doi=doi,
            title=title,
        )
        
        if not citation_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Could not extract citation metadata from any source"
            )
        
        # Create citation in database
        citation = Citation(
            document_title=citation_data.documentTitle,
            authors=citation_data.authors,
            year=citation_data.year,
            venue=citation_data.venue,
            doi=citation_data.doi,
            arxiv_id=citation_data.arxivId,
            abstract=citation_data.abstract,
            metadata_source=source,
            needs_review=False,
        )
        
        db.add(citation)
        await db.commit()
        await db.refresh(citation)
        
        logger.info(
            "citation_extracted",
            citation_id=str(citation.id),
            source=source,
            arxiv_id=arxiv_id,
            doi=doi,
        )
        
        return CitationResponse.model_validate(citation)
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("citation_extraction_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract citation: {str(e)}"
        )


@router.post("/lookup", response_model=CitationResponse)
async def lookup_citation(
    arxiv_id: Optional[str] = None,
    doi: Optional[str] = None,
    title: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lookup citation by ArXiv ID, DOI, or title (no database persistence).
    
    Args:
        arxiv_id: Optional ArXiv ID
        doi: Optional DOI
        title: Optional paper title
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Citation metadata (not persisted)
    """
    if not arxiv_id and not doi and not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide at least one of: arxiv_id, doi, or title"
        )
    
    try:
        extraction_service = CitationExtractionService(db)
        
        citation_data, source = await extraction_service.extract_hybrid(
            arxiv_id=arxiv_id,
            doi=doi,
            title=title,
        )
        
        if not citation_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Citation not found"
            )
        
        # Return citation without persisting
        return CitationResponse(
            id="00000000-0000-0000-0000-000000000000",  # Placeholder ID
            documentTitle=citation_data.documentTitle,
            authors=citation_data.authors or [],
            year=citation_data.year,
            venue=citation_data.venue,
            doi=citation_data.doi,
            arxivId=citation_data.arxivId,
            abstract=citation_data.abstract,
            metadataSource=source,
            needsReview=False,
            createdAt=datetime.now().isoformat(),
            updatedAt=datetime.now().isoformat(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("citation_lookup_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to lookup citation: {str(e)}"
        )


@router.post("/export")
async def export_bibliography(
    format: str = "bibtex",
    citation_ids: Optional[List[UUID]] = None,
    project_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export bibliography in specified format.
    
    Args:
        format: Bibliography format ("bibtex", "ieee", "apa", "mla")
        citation_ids: Optional list of citation IDs to export
        project_id: Optional project ID to export all citations from
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Formatted bibliography as plain text
    """
    if not citation_ids and not project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either citation_ids or project_id"
        )
    
    try:
        # Fetch citations
        query = select(Citation)
        
        if citation_ids:
            query = query.where(Citation.id.in_(citation_ids))
        elif project_id:
            # TODO: Add project-citation relationship when projects are implemented
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Project-based export not yet implemented"
            )
        
        result = await db.execute(query)
        citations = result.scalars().all()
        
        if not citations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No citations found"
            )
        
        # Format bibliography
        bibliography = BibliographyService.format_bibliography(
            citations=list(citations),
            format_type=format
        )
        
        logger.info(
            "bibliography_exported",
            format=format,
            citation_count=len(citations),
            user_id=str(current_user.id),
        )
        
        # Return as plain text with appropriate content type
        from fastapi.responses import PlainTextResponse
        
        content_type = "text/plain"
        if format == "bibtex":
            content_type = "application/x-bibtex"
        
        return PlainTextResponse(
            content=bibliography,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="bibliography.{format}"'
            }
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("bibliography_export_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export bibliography: {str(e)}"
        )
