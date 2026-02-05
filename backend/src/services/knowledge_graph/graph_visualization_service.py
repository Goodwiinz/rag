"""
Graph Visualization API Service (Port 8010)
Standalone microservice for graph data preparation and layout computation
"""

import asyncio
import logging
import math
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession as SQLAsyncSession

from .config.visualization_config import GraphVisualizationConfig
from .core.auth import get_current_user
from .core.cache import cache_get, cache_set
from .core.database import get_async_db
from .models.visualization_models import (
    FilterRequest,
    GraphLayout,
    GraphSizeCategory,
    GraphVisualizationRequest,
    GraphVisualizationResponse,
    InteractiveFilterRequest,
    LayoutAlgorithm,
    ProgressiveLoadRequest,
    VisualizationEdge,
    VisualizationNode,
)
from .services.data_preprocessor import DataPreprocessor
from .services.layout_algorithms import LayoutAlgorithms
from .services.performance_optimizer import PerformanceOptimizer

logger = logging.getLogger(__name__)
config = GraphVisualizationConfig()

# Global services
layout_algorithms = LayoutAlgorithms()
data_preprocessor = DataPreprocessor()
performance_optimizer = PerformanceOptimizer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Graph Visualization API Service on port 8010...")

    # Initialize Neo4j connection
    app.state.neo4j_driver = AsyncGraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        max_connection_lifetime=3600,
        max_connection_pool_size=50,
    )

    # Initialize Redis
    app.state.redis_client = redis.from_url(config.REDIS_URL)

    # Test connections
    await test_connections(app)

    logger.info("Graph Visualization API Service startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Graph Visualization API Service...")
    await app.state.neo4j_driver.close()
    await app.state.redis_client.close()
    logger.info("Graph Visualization API Service shutdown complete")


async def test_connections(app):
    """Test database connections"""
    try:
        # Test Neo4j
        async with app.state.neo4j_driver.session() as session:
            await session.run("RETURN 1")
        logger.info("Neo4j connection successful")

        # Test Redis
        await app.state.redis_client.ping()
        logger.info("Redis connection successful")

    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        raise


app = FastAPI(
    title="Graph Visualization API Service",
    version="1.0.0",
    description="Graph data preparation and layout computation service",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_neo4j_session(app) -> AsyncSession:
    """Get Neo4j session"""
    return app.state.neo4j_driver.session()


async def get_redis_client(app):
    """Get Redis client"""
    return app.state.redis_client


# Main Visualization Endpoints
@app.post("/visualization/prepare", response_model=GraphVisualizationResponse)
async def prepare_graph_visualization(
    request: GraphVisualizationRequest,
    current_user=Depends(get_current_user),
    neo4j_session=Depends(get_neo4j_session),
    redis_client=Depends(get_redis_client),
):
    """Prepare graph data for visualization"""
    try:
        # Verify tenant access
        await verify_tenant_access(current_user.tenant_id, "visualization:prepare")

        # Check cache first
        cache_key = generate_cache_key("visualization", request, current_user.tenant_id)
        cached_result = await cache_get(redis_client, cache_key)
        if cached_result and not request.force_recompute:
            return GraphVisualizationResponse(**cached_result)

        # Estimate graph size and apply optimizations
        estimated_size = await estimate_graph_size(
            neo4j_session, request.filters, current_user.tenant_id
        )
        size_category = categorize_graph_size(estimated_size)

        # Apply performance optimizations based on graph size
        optimizations = performance_optimizer.get_optimizations(size_category)
        request = apply_optimizations_to_request(request, optimizations)

        # Extract graph data from Neo4j
        raw_nodes, raw_edges = await extract_graph_data(
            neo4j_session, request, current_user.tenant_id
        )

        # Preprocess data
        processed_nodes, processed_edges = await data_preprocessor.process(
            raw_nodes, raw_edges, request.preprocessing_options
        )

        # Compute layout
        layout_data = await compute_layout(
            processed_nodes, processed_edges, request.layout_algorithm
        )

        # Apply visual styling
        styled_nodes, styled_edges = apply_visual_styling(
            processed_nodes, processed_edges, request.style_options
        )

        # Create response
        response = GraphVisualizationResponse(
            visualization_id=str(uuid.uuid4()),
            nodes=styled_nodes,
            edges=styled_edges,
            layout=layout_data,
            metadata={
                "graph_size": len(styled_nodes),
                "edge_count": len(styled_edges),
                "layout_algorithm": request.layout_algorithm,
                "processing_time": 0.0,  # Would track actual time
                "size_category": size_category.value,
                "optimizations_applied": optimizations,
                "tenant_id": current_user.tenant_id,
            },
        )

        # Cache result
        cache_ttl = get_cache_ttl(size_category)
        await cache_set(redis_client, cache_key, response.dict(), ttl=cache_ttl)

        return response

    except Exception as e:
        logger.error(f"Error preparing graph visualization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/visualization/{entity_id}/neighborhood", response_model=GraphVisualizationResponse
)
async def get_entity_neighborhood(
    entity_id: str,
    depth: int = Query(default=2, ge=1, le=5),
    max_nodes: int = Query(default=100, ge=1, le=1000),
    layout_algorithm: LayoutAlgorithm = Query(default=LayoutAlgorithm.FORCE_DIRECTED),
    include_relationships: bool = Query(default=True),
    current_user=Depends(get_current_user),
    neo4j_session=Depends(get_neo4j_session),
    redis_client=Depends(get_redis_client),
):
    """Get neighborhood visualization for a specific entity"""
    try:
        await verify_tenant_access(current_user.tenant_id, "visualization:neighborhood")

        # Check cache
        cache_key = f"neighborhood:{entity_id}:{depth}:{max_nodes}:{layout_algorithm}:{current_user.tenant_id}"
        cached_result = await cache_get(redis_client, cache_key)
        if cached_result:
            return GraphVisualizationResponse(**cached_result)

        # Get central entity
        central_entity = await get_entity_by_id(
            neo4j_session, entity_id, current_user.tenant_id
        )
        if not central_entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        # Get neighborhood data
        neighborhood_nodes, neighborhood_edges = await get_entity_neighborhood_data(
            neo4j_session, entity_id, depth, max_nodes, current_user.tenant_id
        )

        # Add central entity if not included
        central_node_id = str(uuid.uuid4())
        central_node = VisualizationNode(
            id=central_node_id,
            label=central_entity["name"],
            type=central_entity["type"],
            x=0,
            y=0,  # Will be positioned by layout algorithm
            size=20,  # Central node is larger
            color="#ff6b6b",
            properties=central_entity,
            is_central=True,
        )

        # Update edges to use central node ID
        updated_edges = []
        for edge in neighborhood_edges:
            if edge["source"] == entity_id:
                edge["source"] = central_node_id
            if edge["target"] == entity_id:
                edge["target"] = central_node_id
            updated_edges.append(VisualizationEdge(**edge))

        # Compute layout
        all_nodes = [central_node] + [
            VisualizationNode(**node) for node in neighborhood_nodes
        ]
        layout_data = await compute_layout(all_nodes, updated_edges, layout_algorithm)

        response = GraphVisualizationResponse(
            visualization_id=str(uuid.uuid4()),
            nodes=all_nodes,
            edges=updated_edges,
            layout=layout_data,
            metadata={
                "central_entity_id": entity_id,
                "depth": depth,
                "total_nodes": len(all_nodes),
                "total_edges": len(updated_edges),
                "layout_algorithm": layout_algorithm,
                "tenant_id": current_user.tenant_id,
            },
        )

        # Cache result
        await cache_set(redis_client, cache_key, response.dict(), ttl=1800)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting entity neighborhood: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/visualization/progressive-load", response_model=GraphVisualizationResponse)
async def progressive_graph_load(
    request: ProgressiveLoadRequest,
    current_user=Depends(get_current_user),
    neo4j_session=Depends(get_neo4j_session),
    redis_client=Depends(get_redis_client),
):
    """Progressively load graph data for large graphs"""
    try:
        await verify_tenant_access(current_user.tenant_id, "visualization:progressive")

        # Check if we have cached data for this session
        session_cache_key = f"progressive:{request.session_id}:{current_user.tenant_id}"
        cached_session = await cache_get(redis_client, session_cache_key)

        if not cached_session:
            # Initialize session
            cached_session = {
                "loaded_nodes": [],
                "loaded_edges": [],
                "total_nodes": 0,
                "total_edges": 0,
                "loaded_batches": [],
            }

        # Load next batch
        batch_nodes, batch_edges, has_more = await load_graph_batch(
            neo4j_session, request, cached_session, current_user.tenant_id
        )

        # Update session data
        cached_session["loaded_nodes"].extend(batch_nodes)
        cached_session["loaded_edges"].extend(batch_edges)
        cached_session["loaded_batches"].append(request.batch_number)

        # Compute layout for new nodes
        all_nodes = [
            VisualizationNode(**node) for node in cached_session["loaded_nodes"]
        ]
        all_edges = [
            VisualizationEdge(**edge) for edge in cached_session["loaded_edges"]
        ]

        # Use incremental layout for progressive loading
        layout_data = await compute_incremental_layout(
            all_nodes, all_edges, request.layout_algorithm, request.batch_number > 1
        )

        response = GraphVisualizationResponse(
            visualization_id=f"progressive_{request.session_id}",
            nodes=all_nodes,
            edges=all_edges,
            layout=layout_data,
            metadata={
                "batch_number": request.batch_number,
                "batch_size": len(batch_nodes),
                "total_loaded_nodes": len(cached_session["loaded_nodes"]),
                "total_loaded_edges": len(cached_session["loaded_edges"]),
                "has_more": has_more,
                "progressive_load": True,
                "session_id": request.session_id,
                "tenant_id": current_user.tenant_id,
            },
        )

        # Update session cache
        if has_more:
            await cache_set(redis_client, session_cache_key, cached_session, ttl=3600)
        else:
            # Clean up session cache when complete
            await cache_delete(redis_client, session_cache_key)

        return response

    except Exception as e:
        logger.error(f"Error in progressive graph load: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/visualization/interactive-filter", response_model=GraphVisualizationResponse
)
async def interactive_filter(
    request: InteractiveFilterRequest,
    current_user=Depends(get_current_user),
    neo4j_session=Depends(get_neo4j_session),
    redis_client=Depends(get_redis_client),
):
    """Apply interactive filters to graph visualization"""
    try:
        await verify_tenant_access(current_user.tenant_id, "visualization:filter")

        # Get base visualization data
        base_cache_key = f"base_visualization:{request.base_visualization_id}:{current_user.tenant_id}"
        base_data = await cache_get(redis_client, base_cache_key)

        if not base_data:
            raise HTTPException(status_code=404, detail="Base visualization not found")

        # Apply filters
        filtered_nodes, filtered_edges = apply_interactive_filters(
            base_data["nodes"], base_data["edges"], request.filters
        )

        # Recompute layout for filtered subgraph
        nodes = [VisualizationNode(**node) for node in filtered_nodes]
        edges = [VisualizationEdge(**edge) for edge in filtered_edges]

        layout_data = await compute_layout(nodes, edges, request.layout_algorithm)

        response = GraphVisualizationResponse(
            visualization_id=str(uuid.uuid4()),
            nodes=nodes,
            edges=edges,
            layout=layout_data,
            metadata={
                "base_visualization_id": request.base_visualization_id,
                "filters_applied": request.filters,
                "original_nodes": len(base_data["nodes"]),
                "original_edges": len(base_data["edges"]),
                "filtered_nodes": len(filtered_nodes),
                "filtered_edges": len(filtered_edges),
                "interactive_filter": True,
                "tenant_id": current_user.tenant_id,
            },
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying interactive filters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Layout Computation Endpoints
@app.post("/layout/compute")
async def compute_layout_only(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    algorithm: LayoutAlgorithm = LayoutAlgorithm.FORCE_DIRECTED,
    current_user=Depends(get_current_user),
    redis_client=Depends(get_redis_client),
):
    """Compute layout for provided nodes and edges"""
    try:
        await verify_tenant_access(current_user.tenant_id, "layout:compute")

        # Convert to visualization objects
        viz_nodes = [VisualizationNode(**node) for node in nodes]
        viz_edges = [VisualizationEdge(**edge) for edge in edges]

        # Compute layout
        layout_data = await compute_layout(viz_nodes, viz_edges, algorithm)

        return {
            "layout": layout_data,
            "algorithm": algorithm,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    except Exception as e:
        logger.error(f"Error computing layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/layout/algorithms")
async def get_available_layouts(current_user=Depends(get_current_user)):
    """Get available layout algorithms"""
    return {
        "algorithms": [
            {
                "id": LayoutAlgorithm.FORCE_DIRECTED,
                "name": "Force Directed",
                "description": "Physics-based force-directed layout",
                "suitable_for": ["small", "medium"],
                "performance": "medium",
            },
            {
                "id": LayoutAlgorithm.CIRCULAR,
                "name": "Circular",
                "description": "Circular arrangement of nodes",
                "suitable_for": ["small", "medium"],
                "performance": "fast",
            },
            {
                "id": LayoutAlgorithm.HIERARCHICAL,
                "name": "Hierarchical",
                "description": "Top-down hierarchical layout",
                "suitable_for": ["small", "medium", "large"],
                "performance": "medium",
            },
            {
                "id": LayoutAlgorithm.GRID,
                "name": "Grid",
                "description": "Grid-based layout",
                "suitable_for": ["all"],
                "performance": "fast",
            },
            {
                "id": LayoutAlgorithm.RANDOM,
                "name": "Random",
                "description": "Random positioning",
                "suitable_for": ["all"],
                "performance": "fast",
            },
        ]
    }


# Utility Functions
async def verify_tenant_access(tenant_id: str, resource: str):
    """Verify tenant access (placeholder)"""
    # This would integrate with tenant service
    return True


def generate_cache_key(prefix: str, request, tenant_id: str) -> str:
    """Generate cache key for request"""
    import hashlib

    request_str = str(request.dict()) + str(tenant_id)
    hash_obj = hashlib.md5(request_str.encode(), usedforsecurity=False)
    return f"{prefix}:{hash_obj.hexdigest()}"


async def estimate_graph_size(
    session: AsyncSession, filters: Dict[str, Any], tenant_id: str
) -> int:
    """Estimate the size of the graph based on filters"""
    try:
        # Simple estimation query
        where_clauses = ["e.tenant_id = $tenant_id"]
        params = {"tenant_id": tenant_id}

        if filters.get("entity_types"):
            type_filter = " OR ".join(
                [f"e.type = '{etype}'" for etype in filters["entity_types"]]
            )
            where_clauses.append(f"({type_filter})")

        where_clause = " AND ".join(where_clauses)

        query = f"""
        MATCH (e:Entity)
        WHERE {where_clause}
        RETURN count(e) as node_count
        """

        result = await session.run(query, params)
        record = await result.single()
        return record["node_count"] if record else 0

    except Exception as e:
        logger.error(f"Error estimating graph size: {e}")
        return 1000  # Default estimate


def categorize_graph_size(node_count: int) -> GraphSizeCategory:
    """Categorize graph size for performance optimization"""
    if node_count <= 100:
        return GraphSizeCategory.SMALL
    elif node_count <= 1000:
        return GraphSizeCategory.MEDIUM
    elif node_count <= 10000:
        return GraphSizeCategory.LARGE
    else:
        return GraphSizeCategory.EXTRA_LARGE


def apply_optimizations_to_request(request, optimizations: Dict[str, Any]):
    """Apply performance optimizations to request"""
    # Apply node sampling for large graphs
    if optimizations.get("sample_nodes"):
        request.max_nodes = min(
            request.max_nodes or 1000, optimizations["sample_nodes"]
        )

    # Apply edge filtering for large graphs
    if optimizations.get("filter_edges"):
        request.edge_filters = request.edge_filters or {}
        request.edge_filters.update(optimizations["filter_edges"])

    # Apply simpler layout for very large graphs
    if optimizations.get("simple_layout"):
        request.layout_algorithm = LayoutAlgorithm.GRID

    return request


async def extract_graph_data(
    session: AsyncSession, request: GraphVisualizationRequest, tenant_id: str
) -> Tuple[List[Dict], List[Dict]]:
    """Extract graph data from Neo4j"""
    try:
        # Build query conditions
        where_clauses = ["e.tenant_id = $tenant_id"]
        params = {"tenant_id": tenant_id, "limit": request.max_nodes or 1000}

        if request.filters and request.filters.get("entity_types"):
            type_filter = " OR ".join(
                [f"e.type = '{etype}'" for etype in request.filters["entity_types"]]
            )
            where_clauses.append(f"({type_filter})")

        where_clause = " AND ".join(where_clauses)

        # Query nodes
        node_query = f"""
        MATCH (e:Entity)
        WHERE {where_clause}
        OPTIONAL MATCH (e)-[r:RELATED_TO]-()
        WITH e, count(r) as degree
        ORDER BY degree DESC
        LIMIT $limit
        RETURN e.id AS id, e.name AS label, e.type AS type,
               properties(e) AS properties, degree
        """

        node_result = await session.run(node_query, params)
        nodes = []
        async for record in node_result:
            nodes.append(
                {
                    "id": record["id"],
                    "label": record["label"],
                    "type": record["type"],
                    "properties": record["properties"],
                    "degree": record["degree"],
                }
            )

        if not nodes:
            return [], []

        # Query relationships between the selected nodes
        node_ids = [node["id"] for node in nodes]
        edge_query = """
        MATCH (source:Entity)-[r:RELATED_TO]-(target:Entity)
        WHERE source.id IN $node_ids AND target.id IN $node_ids
        RETURN r.id AS id, source.id AS source, target.id AS target,
               r.type AS type, properties(r) AS properties
        LIMIT $limit
        """

        edge_result = await session.run(
            edge_query, {"node_ids": node_ids, "limit": request.max_edges or 2000}
        )

        edges = []
        async for record in edge_result:
            edges.append(
                {
                    "id": record["id"],
                    "source": record["source"],
                    "target": record["target"],
                    "type": record["type"],
                    "properties": record["properties"],
                }
            )

        return nodes, edges

    except Exception as e:
        logger.error(f"Error extracting graph data: {e}")
        return [], []


async def compute_layout(
    nodes: List[VisualizationNode],
    edges: List[VisualizationEdge],
    algorithm: LayoutAlgorithm,
) -> GraphLayout:
    """Compute graph layout using specified algorithm"""
    try:
        if algorithm == LayoutAlgorithm.FORCE_DIRECTED:
            return await layout_algorithms.force_directed_layout(nodes, edges)
        elif algorithm == LayoutAlgorithm.CIRCULAR:
            return await layout_algorithms.circular_layout(nodes, edges)
        elif algorithm == LayoutAlgorithm.HIERARCHICAL:
            return await layout_algorithms.hierarchical_layout(nodes, edges)
        elif algorithm == LayoutAlgorithm.GRID:
            return await layout_algorithms.grid_layout(nodes, edges)
        elif algorithm == LayoutAlgorithm.RANDOM:
            return await layout_algorithms.random_layout(nodes, edges)
        else:
            # Default to force directed
            return await layout_algorithms.force_directed_layout(nodes, edges)

    except Exception as e:
        logger.error(f"Error computing layout: {e}")
        # Fallback to simple layout
        return await layout_algorithms.random_layout(nodes, edges)


def apply_visual_styling(
    nodes: List[Dict], edges: List[Dict], style_options: Dict[str, Any]
) -> Tuple[List[VisualizationNode], List[VisualizationEdge]]:
    """Apply visual styling to nodes and edges"""
    # Node styling
    node_color_map = style_options.get("node_colors", {})
    default_node_color = style_options.get("default_node_color", "#4ecdc4")
    node_size_range = style_options.get("node_size_range", [5, 20])

    styled_nodes = []
    for node_data in nodes:
        color = node_color_map.get(node_data["type"], default_node_color)

        # Size based on degree if available
        if "degree" in node_data:
            # Normalize degree to size range
            max_degree = max([n.get("degree", 1) for n in nodes])
            normalized_degree = (
                node_data["degree"] / max_degree if max_degree > 0 else 0
            )
            size = node_size_range[0] + normalized_degree * (
                node_size_range[1] - node_size_range[0]
            )
        else:
            size = (node_size_range[0] + node_size_range[1]) / 2

        styled_node = VisualizationNode(
            id=node_data["id"],
            label=node_data["label"],
            type=node_data["type"],
            x=0,
            y=0,  # Will be set by layout algorithm
            size=size,
            color=color,
            properties=node_data.get("properties", {}),
        )
        styled_nodes.append(styled_node)

    # Edge styling
    edge_color_map = style_options.get("edge_colors", {})
    default_edge_color = style_options.get("default_edge_color", "#636e72")
    edge_width_range = style_options.get("edge_width_range", [1, 5])

    styled_edges = []
    for edge_data in edges:
        color = edge_color_map.get(edge_data["type"], default_edge_color)

        # Width based on strength if available
        strength = edge_data.get("properties", {}).get("strength", 1.0)
        width = edge_width_range[0] + strength * (
            edge_width_range[1] - edge_width_range[0]
        )

        styled_edge = VisualizationEdge(
            id=edge_data["id"],
            source=edge_data["source"],
            target=edge_data["target"],
            type=edge_data["type"],
            weight=edge_data.get("properties", {}).get("strength", 1.0),
            width=width,
            color=color,
            properties=edge_data.get("properties", {}),
        )
        styled_edges.append(styled_edge)

    return styled_nodes, styled_edges


def get_cache_ttl(size_category: GraphSizeCategory) -> int:
    """Get cache TTL based on graph size"""
    ttl_map = {
        GraphSizeCategory.SMALL: 1800,  # 30 minutes
        GraphSizeCategory.MEDIUM: 3600,  # 1 hour
        GraphSizeCategory.LARGE: 7200,  # 2 hours
        GraphSizeCategory.EXTRA_LARGE: 14400,  # 4 hours
    }
    return ttl_map.get(size_category, 1800)


# Health check endpoint
@app.get("/health")
async def health_check(app):
    """Health check endpoint"""
    try:
        # Test Neo4j
        async with app.state.neo4j_driver.session() as session:
            await session.run("RETURN 1")

        # Test Redis
        await app.state.redis_client.ping()

        return {
            "status": "healthy",
            "service": "graph-visualization",
            "port": 8010,
            "neo4j": "connected",
            "redis": "connected",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "graph-visualization",
            "port": 8010,
            "error": str(e),
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "graph_visualization_service:app",
        host="0.0.0.0",  # nosec B104
        port=8010,
        reload=config.DEBUG,
        log_level="info",
    )
