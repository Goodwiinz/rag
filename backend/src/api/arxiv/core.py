"""
ArXiv API Endpoints for RAG System

Provides REST API endpoints for:
- Searching arXiv papers
- Ingesting arXiv papers into the system
- Creating evaluation datasets
- Managing arXiv-specific features
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.database import get_db

# from src.services.search.search_service import SearchService  # Not used
from src.core.dependencies import get_current_user
from src.models.document import Document, DocumentType, ProcessingStatus
from src.services.arxiv.arxiv_service import ArXivIngestionService
from src.services.documents.file_service import FileService
from src.shared.schemas import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/arxiv", tags=["arxiv"])
settings = get_settings()


# Pydantic models
class ArXivSearchRequest(BaseModel):
    query: str = Field(..., description="Search query for arXiv papers")
    max_results: int = Field(
        100, ge=1, le=1000, description="Maximum number of results"
    )
    date_from: Optional[datetime] = Field(None, description="Start date for filtering")
    date_to: Optional[datetime] = Field(None, description="End date for filtering")
    categories: Optional[List[str]] = Field(None, description="Categories to filter by")
    sort_by: str = Field("submittedDate", description="Sort field")
    sort_order: str = Field("descending", description="Sort order")


class ArXivIngestRequest(BaseModel):
    paper_ids: List[str] = Field(..., description="List of arXiv paper IDs to ingest")
    download_pdfs: bool = Field(True, description="Whether to download PDFs")
    extract_content: bool = Field(
        True, description="Whether to extract full text content"
    )
    batch_size: int = Field(10, ge=1, le=50, description="Batch size for processing")


class ArXivPaperResponse(BaseModel):
    id: str
    title: str
    authors: List[str]
    abstract: str
    published: datetime
    updated: datetime
    categories: List[str]
    primary_category: Optional[str]
    comment: Optional[str]
    journal_ref: Optional[str]
    pdf_url: Optional[str]
    doi: Optional[str]


class EvaluationDatasetRequest(BaseModel):
    query: str = Field(
        "machine learning", description="Query to find papers for dataset"
    )
    num_papers: int = Field(50, ge=1, le=200, description="Number of papers to include")
    questions_per_paper: int = Field(5, ge=1, le=10, description="Questions per paper")
    difficulty_levels: List[str] = Field(
        ["easy", "medium", "hard"], description="Difficulty levels"
    )


# Dependency injection
async def get_arxiv_service() -> ArXivIngestionService:
    """Get arXiv service instance"""
    config = {
        "arxiv_download_dir": settings.get("arxiv_download_dir", "data/arxiv"),
        "max_concurrent_downloads": settings.get("arxiv_max_downloads", 10),
    }
    return ArXivIngestionService(config)


# Endpoints
@router.post("/search", response_model=List[ArXivPaperResponse])
async def search_arxiv_papers(
    request: ArXivSearchRequest,
):
    """
    Search for papers on arXiv

    This endpoint allows searching the arXiv database for papers
    matching specific criteria.
    """
    try:
        async with ArXivIngestionService() as arxiv_service:
            papers = await arxiv_service.search_papers(
                query=request.query,
                max_results=request.max_results,
                date_from=request.date_from,
                date_to=request.date_to,
                categories=request.categories,
                sort_by=request.sort_by,
                sort_order=request.sort_order,
            )

            # Convert to response model
            response = []
            for paper in papers:
                response.append(
                    ArXivPaperResponse(
                        id=paper["id"],
                        title=paper["title"],
                        authors=paper["authors"],
                        abstract=paper["abstract"],
                        published=datetime.fromisoformat(
                            paper["published"].replace("Z", "+00:00")
                        ),
                        updated=datetime.fromisoformat(
                            paper["updated"].replace("Z", "+00:00")
                        ),
                        categories=paper["categories"],
                        primary_category=paper.get("primary_category"),
                        comment=paper.get("comment"),
                        journal_ref=paper.get("journal_ref"),
                        pdf_url=paper["links"].get("pdf"),
                        doi=paper["links"].get("doi"),
                    )
                )

            return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest", response_model=Dict[str, Any])
async def ingest_arxiv_papers(
    request: ArXivIngestRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Ingest arXiv papers into the RAG system

    Starts a background task to download and process the specified papers.
    """
    try:
        # Add to background tasks
        background_tasks.add_task(
            _process_arxiv_ingestion,
            paper_ids=request.paper_ids,
            user_id=current_user.id,
            download_pdfs=request.download_pdfs,
            extract_content=request.extract_content,
            batch_size=request.batch_size,
        )

        return {
            "message": "ArXiv paper ingestion started",
            "paper_count": len(request.paper_ids),
            "status": "processing",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-dataset", response_model=Dict[str, Any])
async def create_evaluation_dataset(
    request: EvaluationDatasetRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Create an evaluation dataset from arXiv papers

    Generates questions and evaluation data for testing the RAG system.
    """
    try:
        # Start dataset creation in background
        task_id = f"arxiv_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        background_tasks.add_task(
            _create_arxiv_dataset,
            task_id=task_id,
            query=request.query,
            num_papers=request.num_papers,
            questions_per_paper=request.questions_per_paper,
            difficulty_levels=request.difficulty_levels,
            user_id=current_user.id,
        )

        return {
            "message": "Evaluation dataset creation started",
            "task_id": task_id,
            "status": "processing",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", response_model=Dict[str, Any])
async def get_arxiv_categories(current_user: UserResponse = Depends(get_current_user)):
    """
    Get available arXiv categories and their descriptions
    """
    categories = {
        "computer_science": {
            "description": "Computer Science",
            "subcategories": {
                "cs.AI": "Artificial Intelligence",
                "cs.CL": "Computation and Language",
                "cs.CV": "Computer Vision and Pattern Recognition",
                "cs.LG": "Machine Learning",
                "cs.NE": "Neural and Evolutionary Computing",
                "cs.CR": "Cryptography and Security",
                "cs.DB": "Databases",
                "cs.IR": "Information Retrieval",
                "cs.MM": "Multimedia",
                "cs.NI": "Networking and Internet Architecture",
                "cs.RO": "Robotics",
                "cs.SY": "Systems and Control",
            },
        },
        "mathematics": {
            "description": "Mathematics",
            "subcategories": {
                "math.AG": "Algebraic Geometry",
                "math.AT": "Algebraic Topology",
                "math.CA": "Classical Analysis and ODEs",
                "math.CO": "Combinatorics",
                "math.NA": "Numerical Analysis",
                "math.PR": "Probability",
                "math.ST": "Statistics Theory",
            },
        },
        "physics": {
            "description": "Physics",
            "subcategories": {
                "astro-ph": "Astrophysics",
                "cond-mat": "Condensed Matter",
                "quant-ph": "Quantum Physics",
                "physics.app-ph": "Applied Physics",
                "physics.comp-ph": "Computational Physics",
            },
        },
        "quantitative_biology": {
            "description": "Quantitative Biology",
            "subcategories": {
                "q-bio.BM": "Biomolecules",
                "q-bio.CB": "Cell Behavior",
                "q-bio.GN": "Genomics",
                "q-bio.NC": "Neurons and Cognition",
                "q-bio.QM": "Quantitative Methods",
                "q-bio.TO": "Tissues and Organs",
            },
        },
        "statistics": {
            "description": "Statistics",
            "subcategories": {
                "stat.ML": "Machine Learning",
                "stat.ME": "Methodology",
                "stat.TH": "Statistics Theory",
            },
        },
    }

    return {
        "categories": categories,
        "total_categories": sum(
            len(cat["subcategories"]) for cat in categories.values()
        ),
    }


@router.get("/download/{paper_id}")
async def download_paper(
    paper_id: str, current_user: UserResponse = Depends(get_current_user)
):
    """
    Download PDF for a specific arXiv paper
    """
    try:
        async with ArXivIngestionService() as arxiv_service:
            pdf_content = await arxiv_service.download_paper_pdf(paper_id)

            if pdf_content:
                # Return PDF file
                return JSONResponse(
                    content={
                        "message": "PDF downloaded successfully",
                        "paper_id": paper_id,
                        "size_bytes": len(pdf_content),
                    }
                )
            else:
                raise HTTPException(status_code=404, detail="PDF not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_arxiv_statistics(
    query: Optional[str] = Query(None, description="Query to filter papers"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Get statistics about arXiv papers in the system
    """
    try:
        # Calculate date range
        date_to = datetime.now()
        date_from = date_to - timedelta(days=days)

        # Search for papers in the date range
        search_query = query or "all"
        search_query += f" AND submittedDate:[{date_from.strftime('%Y%m%d')}0000 TO {date_to.strftime('%Y%m%d')}2359]"

        async with ArXivIngestionService() as arxiv_service:
            papers = await arxiv_service.search_papers(
                query=search_query,
                max_results=1000,
                date_from=date_from,
                date_to=date_to,
            )

            # Get category statistics
            stats = arxiv_service.get_category_statistics(papers)

            # Add additional statistics
            stats["date_range"] = {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
                "days": days,
            }
            stats["query"] = query

            return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Background task functions
async def _process_arxiv_ingestion(
    paper_ids: List[str],
    user_id: str,
    download_pdfs: bool,
    extract_content: bool,
    batch_size: int,
):
    """Background task to process arXiv paper ingestion"""
    try:
        # Get database session
        from src.core.database import get_db_session

        async for db in get_db_session():
            async with ArXivIngestionService() as arxiv_service:
                # First, get paper metadata
                papers = []
                for paper_id in paper_ids:
                    # Search for specific paper ID
                    search_results = await arxiv_service.search_papers(
                        query=f"id:{paper_id}", max_results=1
                    )
                    if search_results:
                        papers.extend(search_results)

                if papers:
                    # Ingest papers
                    documents = await arxiv_service.ingest_papers(
                        papers=papers,
                        download_pdfs=download_pdfs,
                        extract_content=extract_content,
                        batch_size=batch_size,
                    )

                    # Save documents to database
                    for doc in documents:
                        # Create document instance
                        document = Document(
                            title=doc.get("title", ""),
                            filename=doc.get("filename", ""),
                            file_path=doc.get("file_path", ""),
                            file_size_bytes=doc.get("file_size_bytes", 0),
                            mime_type=doc.get("mime_type", "application/pdf"),
                            document_type=DocumentType.PDF,
                            content_text=doc.get("content_text"),
                            content_summary=doc.get("content_summary"),
                            document_metadata=doc.get("metadata", {}),
                            processing_status=ProcessingStatus.COMPLETED,
                            uploaded_by_user_id=user_id,
                            organization_id=doc.get("organization_id", ""),
                            is_public=doc.get("is_public", False),
                        )
                        db.add(document)

                    await db.commit()

    except Exception as e:
        logger.error(f"Background arXiv ingestion failed: {e}")


async def _create_arxiv_dataset(
    task_id: str,
    query: str,
    num_papers: int,
    questions_per_paper: int,
    difficulty_levels: List[str],
    user_id: str,
):
    """Background task to create evaluation dataset"""
    try:
        async with ArXivIngestionService() as arxiv_service:
            # Search for papers
            papers = await arxiv_service.search_papers(
                query=query, max_results=num_papers
            )

            if papers:
                # Create evaluation dataset
                dataset = await arxiv_service.create_evaluation_dataset(
                    papers=papers,
                    num_questions=questions_per_paper,
                    difficulty_levels=difficulty_levels,
                )

                # Store dataset metadata
                # This could be saved to a database or file system
                logger.info(
                    f"Created evaluation dataset {task_id} with {len(dataset['test_cases'])} test cases"
                )

    except Exception as e:
        logger.error(f"Background dataset creation failed: {e}")
