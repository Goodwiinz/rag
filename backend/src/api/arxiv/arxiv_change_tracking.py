"""
ArXiv Change Tracking API endpoints
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.core.dependencies import get_current_user
from src.services.arxiv.arxiv_change_tracker import change_tracker, track_arxiv_changes
from src.services.arxiv.arxiv_service import IngestionError

logger = logging.getLogger(__name__)
router = APIRouter()

ARXIV_TRACKING_RETRY_MESSAGE = (
    "ArXiv is temporarily rate limiting category scans. Retry in about a minute "
    "or scan fewer categories."
)


class CategoryTrackingRequest(BaseModel):
    categories: List[str] = Field(..., description="ArXiv categories to track")
    days_back: int = Field(default=1, description="Number of days to look back")
    update_database: bool = Field(
        default=True, description="Whether to apply changes to database"
    )


class ChangeHistoryResponse(BaseModel):
    paper_id: str
    current_hash: str
    last_seen: str
    deleted: bool
    metadata: Dict[str, Any]


@router.post("/track-categories")
async def track_category_changes(
    request: CategoryTrackingRequest, current_user: dict = Depends(get_current_user)
):
    """
    Track changes in specific arXiv categories

    This endpoint searches for recent papers in the specified categories,
    detects changes (new, updated, deleted papers), and optionally updates
    the database and knowledge graph with the changes.
    """
    try:
        logger.info(f"Tracking changes for categories: {request.categories}")

        result = await change_tracker.track_category_changes(
            categories=request.categories,
            days_back=request.days_back,
            update_db=request.update_database,
        )

        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "result": result,
        }

    except IngestionError as e:
        logger.warning(f"ArXiv category scan unavailable: {e}")
        detail = str(e).lower()

        if "rate limit" in detail or "timed out" in detail:
            raise HTTPException(
                status_code=503,
                detail=ARXIV_TRACKING_RETRY_MESSAGE,
                headers={"Retry-After": "60"},
            )

        raise HTTPException(
            status_code=502,
            detail="Unable to complete the arXiv category scan right now. Retry shortly.",
        )
    except Exception as e:
        logger.error(f"Failed to track category changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/track-all")
async def track_all_changes(
    days_back: int = Query(default=1, description="Days to look back"),
    current_user: dict = Depends(get_current_user),
):
    """
    Track changes across all popular arXiv categories

    This is a convenience endpoint that tracks changes across a predefined
    list of popular arXiv categories.
    """
    try:
        logger.info(f"Tracking all arXiv changes for last {days_back} days")

        result = await track_arxiv_changes(days_back=days_back)

        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "result": result,
        }

    except Exception as e:
        logger.error(f"Failed to track all changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_change_history(
    paper_id: Optional[str] = Query(
        None, description="Specific paper ID to get history for"
    ),
    limit: int = Query(default=100, description="Maximum number of records to return"),
    current_user: dict = Depends(get_current_user),
):
    """
    Get change history for arXiv papers

    Returns a history of all tracked changes, optionally filtered by paper ID.
    """
    try:
        logger.info(f"Getting change history for paper_id: {paper_id}")

        history = await change_tracker.get_change_history(paper_id=paper_id)

        # Apply limit
        if limit and len(history) > limit:
            history = history[:limit]

        return {"status": "success", "total_records": len(history), "history": history}

    except Exception as e:
        logger.error(f"Failed to get change history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_tracking_statistics():
    """
    Get statistics about the change tracking system (public endpoint)

    Returns information about tracked papers, change patterns, etc.
    This endpoint is public and returns cached data only for fast response.
    """
    try:
        # Get all tracking data from local cache
        history = await change_tracker.get_change_history()

        # Calculate statistics
        total_tracked = len(history)
        deleted_count = sum(1 for h in history if h["deleted"])
        active_count = total_tracked - deleted_count

        # Group by categories
        category_counts = {}
        for h in history:
            cat = h["metadata"].get("primary_category", "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "statistics": {
                "total_papers_tracked": total_tracked,
                "active_papers": active_count,
                "deleted_papers": deleted_count,
                "categories_tracked": len(category_counts),
                "top_categories": sorted(
                    category_counts.items(), key=lambda x: x[1], reverse=True
                )[:10],
                "recent_changes_week": {},  # Removed slow arXiv API call
                "state_file_path": str(change_tracker.state_file),
            },
        }

    except Exception as e:
        logger.error(f"Failed to get tracking statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_old_state(
    days: int = Body(default=90, embed=True, description="Days to keep state for"),
    current_user: dict = Depends(get_current_user),
):
    """
    Clean up old tracking state

    Removes tracking records for papers not seen in the specified number of days.
    """
    try:
        logger.info(f"Cleaning up state older than {days} days")

        removed_count = await change_tracker.cleanup_old_state(days=days)

        return {
            "status": "success",
            "removed_records": removed_count,
            "message": f"Removed {removed_count} stale state records",
        }

    except Exception as e:
        logger.error(f"Failed to cleanup old state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/force-sync")
async def force_sync_paper(
    paper_id: str = Body(..., embed=True, description="arXiv paper ID to sync"),
    current_user: dict = Depends(get_current_user),
):
    """
    Force synchronization of a specific paper

    Fetches the latest version of the paper from arXiv and updates the database
    and knowledge graph regardless of whether changes are detected.
    """
    try:
        logger.info(f"Force syncing paper: {paper_id}")

        # Fetch paper details
        paper = await change_tracker._fetch_paper_details(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")

        # Apply changes as if it were new/updated
        async with change_tracker.get_db_session() as db:
            # Check if exists
            from sqlalchemy import select

            from src.models.document import Document

            stmt = select(Document).where(Document.external_id == paper_id)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                await change_tracker._update_existing_paper(db, paper, ["force_update"])
                await change_tracker._update_knowledge_graph(paper)
                action = "updated"
            else:
                # Create new
                await change_tracker._ingest_new_paper(db, paper, update_kg=True)
                action = "created"

            # Update tracking state
            paper_hash = change_tracker.compute_paper_hash(paper)
            change_tracker.state[paper_id] = {
                "hash": paper_hash,
                "last_seen": datetime.utcnow().isoformat(),
                "paper_metadata": {
                    "title": paper.get("title", ""),
                    "authors": paper.get("authors", [])[:5],
                    "primary_category": paper.get("primary_category"),
                },
            }
            change_tracker.save_state()

        return {
            "status": "success",
            "action": action,
            "paper_id": paper_id,
            "title": paper.get("title", ""),
            "message": f"Successfully {action} paper {paper_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to force sync paper {paper_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
