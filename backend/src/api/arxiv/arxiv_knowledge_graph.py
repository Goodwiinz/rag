"""
ArXiv Knowledge Graph API endpoints
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.core.dependencies import get_current_user
from src.services.arxiv.arxiv_kg_integration import ArXivKnowledgeGraphIntegration
from src.services.arxiv.arxiv_service import ArXivIngestionService

logger = logging.getLogger(__name__)
router = APIRouter()


class KnowledgeGraphRequest(BaseModel):
    paper_id: str = Field(..., description="ArXiv paper ID")
    depth: int = Field(default=2, description="Depth of subgraph exploration")


class AuthorNetworkRequest(BaseModel):
    author_name: str = Field(..., description="Author name")
    max_depth: int = Field(default=2, description="Depth of collaboration network")


class TrendAnalysisRequest(BaseModel):
    category: str = Field(..., description="ArXiv category (e.g., cs.LG)")
    days: int = Field(default=30, description="Number of recent days to analyze")


class BulkIngestionRequest(BaseModel):
    query: str = Field(..., description="Search query for papers")
    max_results: int = Field(default=100, description="Maximum papers to process")
    categories: Optional[List[str]] = Field(
        default=None, description="Filter by categories"
    )
    create_kg_entries: bool = Field(
        default=True, description="Create knowledge graph entries"
    )


# Dependency injection
async def get_kg_integration():
    """Get knowledge graph integration service"""
    try:
        return ArXivKnowledgeGraphIntegration()
    except Exception as e:
        logger.error(f"Failed to initialize KG integration: {e}")
        raise HTTPException(
            status_code=503, detail="Knowledge graph service unavailable"
        )


async def get_arxiv_service():
    """Get ArXiv service"""
    try:
        return ArXivIngestionService()
    except Exception as e:
        logger.error(f"Failed to initialize ArXiv service: {e}")
        raise HTTPException(status_code=503, detail="ArXiv service unavailable")


@router.post("/subgraph")
async def create_paper_subgraph(
    request: KnowledgeGraphRequest,
    current_user: dict = Depends(get_current_user),
    kg_integration: ArXivKnowledgeGraphIntegration = Depends(get_kg_integration),
):
    """
    Create a knowledge graph subgraph for a specific paper

    This endpoint extracts entities and relationships from an arXiv paper
    and creates a knowledge graph subgraph showing connections to concepts,
    authors, and cited works.
    """
    try:
        logger.info(f"Creating KG subgraph for paper {request.paper_id}")

        result = await kg_integration.create_paper_kg_subgraph(
            paper_id=request.paper_id, depth=request.depth
        )

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return {
            "status": "success",
            "paper_id": request.paper_id,
            "depth": request.depth,
            "subgraph": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create subgraph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/author-network")
async def get_author_collaboration_network(
    request: AuthorNetworkRequest,
    current_user: dict = Depends(get_current_user),
    kg_integration: ArXivKnowledgeGraphIntegration = Depends(get_kg_integration),
):
    """
    Build collaboration network for an author

    This endpoint searches for papers by the specified author and builds
    a collaboration network showing co-authors and collaboration strength.
    """
    try:
        logger.info(f"Building collaboration network for {request.author_name}")

        network = await kg_integration.get_author_collaboration_network(
            author_name=request.author_name, max_depth=request.max_depth
        )

        if "error" in network:
            raise HTTPException(status_code=404, detail=network["error"])

        return {
            "status": "success",
            "author": request.author_name,
            "max_depth": request.max_depth,
            "network": network,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to build collaboration network: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-trends")
async def analyze_research_trends(
    request: TrendAnalysisRequest,
    current_user: dict = Depends(get_current_user),
    kg_integration: ArXivKnowledgeGraphIntegration = Depends(get_kg_integration),
):
    """
    Analyze trends in a research area

    This endpoint analyzes recent papers in a specific arXiv category
    to identify trending topics, author collaborations, and citation patterns.
    """
    try:
        logger.info(
            f"Analyzing trends for category {request.category} over {request.days} days"
        )

        analysis = await kg_integration.analyze_research_area_trends(
            category=request.category, days=request.days
        )

        if "error" in analysis:
            raise HTTPException(status_code=400, detail=analysis["error"])

        return {
            "status": "success",
            "category": request.category,
            "period_days": request.days,
            "analysis": analysis,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-ingest")
async def bulk_ingest_with_kg(
    request: BulkIngestionRequest,
    current_user: dict = Depends(get_current_user),
    arxiv_service: ArXivIngestionService = Depends(get_arxiv_service),
    kg_integration: ArXivKnowledgeGraphIntegration = Depends(get_kg_integration),
):
    """
    Bulk ingest arXiv papers with knowledge graph integration

    This endpoint searches for arXiv papers matching the query and optionally
    creates knowledge graph entries for extracted entities and relationships.
    """
    try:
        logger.info(f"Bulk ingesting papers for query: {request.query}")

        # Search for papers
        papers = await arxiv_service.search_papers(
            query=request.query,
            max_results=request.max_results,
            categories=request.categories,
        )

        if not papers:
            return {
                "status": "success",
                "message": "No papers found matching the query",
                "papers_found": 0,
                "kg_entries_created": 0,
            }

        # Ingest papers
        ingested_count = await arxiv_service.ingest_papers(
            papers=papers, extract_entities=request.create_kg_entries
        )

        # Create knowledge graph entries if requested
        kg_entries_count = 0
        if request.create_kg_entries:
            for paper in papers:
                try:
                    await kg_integration.process_paper_kg_integration(paper)
                    kg_entries_count += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to process KG for paper {paper.get('id')}: {e}"
                    )

        return {
            "status": "success",
            "query": request.query,
            "papers_found": len(papers),
            "papers_ingested": ingested_count,
            "kg_entries_created": kg_entries_count,
            "categories_filter": request.categories,
        }

    except Exception as e:
        logger.error(f"Failed to bulk ingest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_name}")
async def get_entity_details(
    entity_name: str,
    entity_type: Optional[str] = Query(None, description="Entity type filter"),
    current_user: dict = Depends(get_current_user),
    kg_integration: ArXivKnowledgeGraphIntegration = Depends(get_kg_integration),
):
    """
    Get details about a specific entity in the knowledge graph

    This endpoint retrieves information about an entity including related papers,
    connected entities, and relationship patterns.
    """
    try:
        logger.info(f"Getting details for entity {entity_name}")

        if not kg_integration.kg_service:
            raise HTTPException(
                status_code=503, detail="Knowledge graph service unavailable"
            )

        # Get entity from knowledge graph
        entity_details = await kg_integration.kg_service.get_entity_details(
            entity_name=entity_name, entity_type=entity_type
        )

        if not entity_details:
            raise HTTPException(
                status_code=404, detail=f"Entity {entity_name} not found"
            )

        return {"status": "success", "entity": entity_details}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get entity details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/path/{source}/{target}")
async def find_entity_path(
    source: str,
    target: str,
    max_depth: int = Query(default=3, description="Maximum path depth"),
    current_user: dict = Depends(get_current_user),
    kg_integration: ArXivKnowledgeGraphIntegration = Depends(get_kg_integration),
):
    """
    Find shortest path between two entities in the knowledge graph

    This endpoint finds the shortest path between two entities, showing
    the chain of relationships that connect them.
    """
    try:
        logger.info(f"Finding path from {source} to {target}")

        if not kg_integration.kg_service:
            raise HTTPException(
                status_code=503, detail="Knowledge graph service unavailable"
            )

        # Find path in knowledge graph
        path = await kg_integration.kg_service.find_shortest_path(
            source_entity=source, target_entity=target, max_depth=max_depth
        )

        if not path:
            return {
                "status": "success",
                "source": source,
                "target": target,
                "path_found": False,
                "message": "No path found within specified depth",
            }

        return {
            "status": "success",
            "source": source,
            "target": target,
            "path_found": True,
            "path_length": len(path),
            "path": path,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find path: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_knowledge_graph_stats(
    current_user: dict = Depends(get_current_user),
    kg_integration: ArXivKnowledgeGraphIntegration = Depends(get_kg_integration),
):
    """
    Get statistics about the arXiv knowledge graph

    This endpoint returns statistics about the knowledge graph including
    entity counts, relationship types, and growth metrics.
    """
    try:
        if not kg_integration.kg_service:
            raise HTTPException(
                status_code=503, detail="Knowledge graph service unavailable"
            )

        # Get stats from knowledge graph
        stats = await kg_integration.kg_service.get_graph_statistics()

        # Add arXiv-specific stats
        arxiv_stats = {
            "arxiv_papers_processed": stats.get("total_entities", {}).get("paper", 0),
            "unique_authors": stats.get("total_entities", {}).get("author", 0),
            "research_concepts": stats.get("total_entities", {}).get("concept", 0),
            "total_relationships": sum(stats.get("total_relationships", {}).values()),
            "relationship_types": stats.get("total_relationships", {}),
            "last_updated": stats.get("last_updated"),
        }

        return {"status": "success", "statistics": arxiv_stats}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
