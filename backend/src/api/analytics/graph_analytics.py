"""
Graph Analytics API routes
"""

import logging
import uuid
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks

from ...services.analytics.graph_analytics_service import graph_analytics_service
from ...models.analytics.graph_analytics import (
    GraphAnalysisRequest, GraphAnalysisResponse, PathAnalysisRequest, PathAnalysisResponse,
    GraphStatistics, CentralityAnalysis
)
from ...auth.dependencies import get_current_user
from ...models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph-analytics", tags=["analytics-graph"])


@router.post("/analyze", response_model=GraphAnalysisResponse)
async def run_graph_analysis(
    request: GraphAnalysisRequest,
    current_user: User = Depends(get_current_user)
):
    """Run graph analysis with specified algorithm"""
    try:
        result = await graph_analytics_service.run_graph_analysis(
            request=request,
            user_id=current_user.id
        )
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph analytics service unavailable"
        )
    except Exception as e:
        logger.error(f"Error running graph analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run graph analysis"
        )


@router.post("/paths", response_model=PathAnalysisResponse)
async def run_path_analysis(
    request: PathAnalysisRequest,
    current_user: User = Depends(get_current_user)
):
    """Run path analysis between nodes"""
    try:
        result = await graph_analytics_service.run_path_analysis(
            request=request,
            user_id=current_user.id
        )
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph analytics service unavailable"
        )
    except Exception as e:
        logger.error(f"Error running path analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run path analysis"
        )


@router.get("/statistics", response_model=GraphStatistics)
async def get_graph_statistics(
    current_user: User = Depends(get_current_user)
):
    """Get overall graph statistics"""
    try:
        stats = await graph_analytics_service.get_graph_statistics()
        return stats

    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph analytics service unavailable"
        )
    except Exception as e:
        logger.error(f"Error getting graph statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get graph statistics"
        )


@router.get("/centrality/{algorithm}", response_model=CentralityAnalysis)
async def get_centrality_analysis(
    algorithm: str,
    top_k: int = Query(100, ge=1, le=1000, description="Number of top nodes to return"),
    current_user: User = Depends(get_current_user)
):
    """Get centrality analysis for the graph"""
    try:
        valid_algorithms = ["pagerank", "betweenness", "degree"]
        if algorithm not in valid_algorithms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid algorithm. Must be one of: {valid_algorithms}"
            )

        analysis = await graph_analytics_service.get_centrality_analysis(
            algorithm=algorithm,
            top_k=top_k
        )
        return analysis

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph analytics service unavailable"
        )
    except Exception as e:
        logger.error(f"Error getting centrality analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get centrality analysis"
        )


@router.get("/algorithms", response_model=Dict[str, Any])
async def get_available_algorithms(
    current_user: User = Depends(get_current_user)
):
    """Get available graph algorithms"""
    try:
        from ...models.analytics.graph_analytics import GraphAlgorithmType

        algorithms = {
            "pagerank": {
                "name": "PageRank",
                "description": "Measures the importance of nodes in the graph",
                "parameters": {
                    "damping_factor": {
                        "type": "float",
                        "default": 0.85,
                        "min": 0.0,
                        "max": 1.0,
                        "description": "Probability of following a random link"
                    },
                    "max_iterations": {
                        "type": "integer",
                        "default": 20,
                        "min": 1,
                        "max": 100,
                        "description": "Maximum number of iterations"
                    }
                },
                "output": ["node_rankings"]
            },
            "betweenness_centrality": {
                "name": "Betweenness Centrality",
                "description": "Measures how often a node appears on shortest paths",
                "parameters": {},
                "output": ["node_rankings"]
            },
            "community_detection": {
                "name": "Community Detection",
                "description": "Detects communities or clusters in the graph",
                "parameters": {
                    "resolution": {
                        "type": "float",
                        "default": 1.0,
                        "min": 0.1,
                        "max": 10.0,
                        "description": "Resolution parameter for community detection"
                    }
                },
                "output": ["community_assignments", "community_metrics"]
            },
            "connected_components": {
                "name": "Connected Components",
                "description": "Finds connected components in the graph",
                "parameters": {},
                "output": ["component_assignments", "component_count"]
            },
            "shortest_path": {
                "name": "Shortest Path",
                "description": "Finds shortest path between two nodes",
                "parameters": {
                    "source_node_id": {
                        "type": "string",
                        "required": True,
                        "description": "ID of source node"
                    },
                    "target_node_id": {
                        "type": "string",
                        "required": True,
                        "description": "ID of target node"
                    }
                },
                "output": ["path", "path_length"]
            },
            "triangle_count": {
                "name": "Triangle Count",
                "description": "Counts triangles in the graph",
                "parameters": {},
                "output": ["triangle_count", "triangles"]
            },
            "clustering_coefficient": {
                "name": "Clustering Coefficient",
                "description": "Calculates clustering coefficient for nodes",
                "parameters": {},
                "output": ["node_coefficients", "average_coefficient"]
            }
        }

        return {
            "algorithms": algorithms,
            "path_analysis_types": {
                "shortest": "Find shortest paths",
                "all": "Find all paths up to a maximum depth",
                "k_shortest": "Find k shortest paths"
            },
            "node_types": ["entity", "document", "concept", "person", "organization", "location", "event", "topic", "keyword"],
            "edge_types": ["mentions", "contains", "related_to", "similar_to", "part_of", "references", "cites", "works_with"]
        }

    except Exception as e:
        logger.error(f"Error getting available algorithms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get available algorithms"
        )


@router.get("/health", response_model=Dict[str, Any])
async def check_graph_health(
    current_user: User = Depends(get_current_user)
):
    """Check graph analytics service health"""
    try:
        if not graph_analytics_service.initialized:
            return {
                "status": "unhealthy",
                "message": "Graph analytics service not initialized",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Test basic connectivity
        stats = await graph_analytics_service.get_graph_statistics()

        return {
            "status": "healthy",
            "neo4j_connected": True,
            "total_nodes": stats.total_nodes,
            "total_edges": stats.total_edges,
            "last_updated": stats.last_updated.isoformat(),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error checking graph health: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }