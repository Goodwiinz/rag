"""
Graph Analytics Service (Port 8009)
Standalone microservice for graph algorithms and background processing
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession as SQLAsyncSession
from celery import Celery

from .config.analytics_config import GraphAnalyticsConfig
from .models.analytics_models import (
    CentralityRequest, CentralityResponse, PathRequest, PathResponse,
    CommunityRequest, CommunityResponse, AnalyticsJobRequest, AnalyticsJobResponse,
    GraphInsightsRequest, GraphInsightsResponse
)
from .core.database import get_async_db
from .core.auth import get_current_user
from .core.cache import analytics_cache, cache_get, cache_set
from .services.graph_algorithms import GraphAlgorithms
from .services.background_job_processor import BackgroundJobProcessor
from .services.analytics_scheduler import AnalyticsScheduler
from .services.tenant_service import TenantService

logger = logging.getLogger(__name__)
config = GraphAnalyticsConfig()

# Initialize Celery for background processing
celery_app = Celery(
    'graph_analytics',
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND
)

# Global services
graph_algorithms = GraphAlgorithms()
job_processor = BackgroundJobProcessor()
analytics_scheduler = AnalyticsScheduler()
tenant_service = TenantService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Graph Analytics Service on port 8009...")

    # Initialize Neo4j connection
    app.state.neo4j_driver = AsyncGraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        max_connection_lifetime=3600,
        max_connection_pool_size=50
    )

    # Initialize Redis
    app.state.redis_client = redis.from_url(config.REDIS_URL)

    # Test connections
    await test_connections(app)

    # Start background services
    await job_processor.start()
    await analytics_scheduler.start()

    logger.info("Graph Analytics Service startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Graph Analytics Service...")
    await job_processor.stop()
    await analytics_scheduler.stop()
    await app.state.neo4j_driver.close()
    await app.state.redis_client.close()
    logger.info("Graph Analytics Service shutdown complete")

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
    title="Graph Analytics Service",
    version="1.0.0",
    description="Graph algorithms and analytics processing service",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
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

# Centrality Analysis Endpoints
@app.post("/analytics/centrality", response_model=CentralityResponse)
async def compute_centrality(
    request: CentralityRequest,
    current_user = Depends(get_current_user),
    neo4j_session = Depends(get_neo4j_session),
    redis_client = Depends(get_redis_client)
):
    """Compute centrality metrics for nodes"""
    try:
        # Verify tenant access
        await tenant_service.verify_tenant_access(current_user.tenant_id, "analytics:centrality")

        # Check cache first
        cache_key = f"centrality:{request.algorithm}:{request.entity_types}:{current_user.tenant_id}"
        cached_result = await cache_get(redis_client, cache_key)
        if cached_result and not request.force_recompute:
            return CentralityResponse(**cached_result)

        # Compute centrality based on algorithm
        if request.algorithm == "pagerank":
            results = await graph_algorithms.compute_pagerank(
                neo4j_session,
                entity_types=request.entity_types,
                tenant_id=current_user.tenant_id,
                limit=request.limit
            )
        elif request.algorithm == "betweenness":
            results = await graph_algorithms.compute_betweenness_centrality(
                neo4j_session,
                entity_types=request.entity_types,
                tenant_id=current_user.tenant_id,
                limit=request.limit
            )
        elif request.algorithm == "closeness":
            results = await graph_algorithms.compute_closeness_centrality(
                neo4j_session,
                entity_types=request.entity_types,
                tenant_id=current_user.tenant_id,
                limit=request.limit
            )
        elif request.algorithm == "degree":
            results = await graph_algorithms.compute_degree_centrality(
                neo4j_session,
                entity_types=request.entity_types,
                tenant_id=current_user.tenant_id,
                limit=request.limit
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown centrality algorithm: {request.algorithm}")

        response = CentralityResponse(
            algorithm=request.algorithm,
            results=results,
            computation_time=results.get("computation_time", 0.0),
            node_count=results.get("node_count", 0),
            timestamp=datetime.utcnow()
        )

        # Cache results
        await cache_set(redis_client, cache_key, response.dict(), ttl=3600)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing centrality: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analytics/paths", response_model=PathResponse)
async def find_shortest_paths(
    request: PathRequest,
    current_user = Depends(get_current_user),
    neo4j_session = Depends(get_neo4j_session),
    redis_client = Depends(get_redis_client)
):
    """Find shortest paths between entities"""
    try:
        await tenant_service.verify_tenant_access(current_user.tenant_id, "analytics:paths")

        # Check cache
        cache_key = f"paths:{request.source_entity_id}:{request.target_entity_id}:{request.algorithm}:{current_user.tenant_id}"
        cached_result = await cache_get(redis_client, cache_key)
        if cached_result and not request.force_recompute:
            return PathResponse(**cached_result)

        # Find paths based on algorithm
        if request.algorithm == "dijkstra":
            paths = await graph_algorithms.find_shortest_path_dijkstra(
                neo4j_session,
                request.source_entity_id,
                request.target_entity_id,
                current_user.tenant_id,
                weight_property=request.weight_property,
                max_paths=request.max_paths
            )
        elif request.algorithm == "bfs":
            paths = await graph_algorithms.find_shortest_path_bfs(
                neo4j_session,
                request.source_entity_id,
                request.target_entity_id,
                current_user.tenant_id,
                max_depth=request.max_depth,
                max_paths=request.max_paths
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown path algorithm: {request.algorithm}")

        response = PathResponse(
            source_entity_id=request.source_entity_id,
            target_entity_id=request.target_entity_id,
            algorithm=request.algorithm,
            paths=paths,
            computation_time=paths.get("computation_time", 0.0),
            path_count=len(paths.get("paths", [])),
            timestamp=datetime.utcnow()
        )

        # Cache results
        await cache_set(redis_client, cache_key, response.dict(), ttl=1800)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding shortest paths: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analytics/communities", response_model=CommunityResponse)
async def detect_communities(
    request: CommunityRequest,
    current_user = Depends(get_current_user),
    neo4j_session = Depends(get_neo4j_session),
    redis_client = Depends(get_redis_client)
):
    """Detect communities in the graph"""
    try:
        await tenant_service.verify_tenant_access(current_user.tenant_id, "analytics:communities")

        # Check cache
        cache_key = f"communities:{request.algorithm}:{request.entity_types}:{current_user.tenant_id}"
        cached_result = await cache_get(redis_client, cache_key)
        if cached_result and not request.force_recompute:
            return CommunityResponse(**cached_result)

        # Detect communities based on algorithm
        if request.algorithm == "louvain":
            communities = await graph_algorithms.detect_communities_louvain(
                neo4j_session,
                entity_types=request.entity_types,
                tenant_id=current_user.tenant_id,
                resolution=request.resolution
            )
        elif request.algorithm == "label_propagation":
            communities = await graph_algorithms.detect_communities_label_propagation(
                neo4j_session,
                entity_types=request.entity_types,
                tenant_id=current_user.tenant_id,
                max_iterations=request.max_iterations
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown community detection algorithm: {request.algorithm}")

        response = CommunityResponse(
            algorithm=request.algorithm,
            communities=communities,
            computation_time=communities.get("computation_time", 0.0),
            community_count=communities.get("community_count", 0),
            modularity_score=communities.get("modularity_score", 0.0),
            timestamp=datetime.utcnow()
        )

        # Cache results
        await cache_set(redis_client, cache_key, response.dict(), ttl=7200)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detecting communities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background Job Processing
@app.post("/analytics/jobs", response_model=AnalyticsJobResponse)
async def submit_analytics_job(
    request: AnalyticsJobRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    db: SQLAsyncSession = Depends(get_async_db)
):
    """Submit analytics job for background processing"""
    try:
        await tenant_service.verify_tenant_access(current_user.tenant_id, "analytics:jobs")

        job_id = str(uuid.uuid4())

        # Create job record
        job_response = AnalyticsJobResponse(
            job_id=job_id,
            job_type=request.job_type,
            status="queued",
            parameters=request.parameters,
            tenant_id=current_user.tenant_id,
            created_at=datetime.utcnow()
        )

        # Submit background task
        background_tasks.add_task(
            job_processor.process_job,
            job_id,
            request.job_type,
            request.parameters,
            current_user.tenant_id
        )

        return job_response

    except Exception as e:
        logger.error(f"Error submitting analytics job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/jobs/{job_id}", response_model=AnalyticsJobResponse)
async def get_job_status(
    job_id: str,
    current_user = Depends(get_current_user),
    redis_client = Depends(get_redis_client)
):
    """Get status of analytics job"""
    try:
        cache_key = f"job:{job_id}:{current_user.tenant_id}"
        job_data = await cache_get(redis_client, cache_key)

        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")

        return AnalyticsJobResponse(**job_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/jobs", response_model=List[AnalyticsJobResponse])
async def list_jobs(
    current_user = Depends(get_current_user),
    redis_client = Depends(get_redis_client),
    limit: int = 50,
    status: Optional[str] = None
):
    """List analytics jobs for tenant"""
    try:
        # Get jobs from Redis or database
        # For now, return empty list (implementation would query job storage)
        return []

    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Graph Insights
@app.post("/analytics/insights", response_model=GraphInsightsResponse)
async def generate_graph_insights(
    request: GraphInsightsRequest,
    current_user = Depends(get_current_user),
    neo4j_session = Depends(get_neo4j_session),
    redis_client = Depends(get_redis_client)
):
    """Generate comprehensive graph insights"""
    try:
        await tenant_service.verify_tenant_access(current_user.tenant_id, "analytics:insights")

        # Check cache
        cache_key = f"insights:{request.insight_types}:{current_user.tenant_id}"
        cached_result = await cache_get(redis_client, cache_key)
        if cached_result and not request.force_recompute:
            return GraphInsightsResponse(**cached_result)

        insights = {}

        # Generate requested insights
        for insight_type in request.insight_types:
            if insight_type == "key_entities":
                insights["key_entities"] = await graph_algorithms.find_key_entities(
                    neo4j_session, current_user.tenant_id
                )
            elif insight_type == "bridge_entities":
                insights["bridge_entities"] = await graph_algorithms.find_bridge_entities(
                    neo4j_session, current_user.tenant_id
                )
            elif insight_type == "clusters":
                insights["clusters"] = await graph_algorithms.identify_graph_clusters(
                    neo4j_session, current_user.tenant_id
                )
            elif insight_type == "anomalies":
                insights["anomalies"] = await graph_algorithms.detect_graph_anomalies(
                    neo4j_session, current_user.tenant_id
                )
            elif insight_type == "growth_trends":
                insights["growth_trends"] = await graph_algorithms.analyze_growth_trends(
                    neo4j_session, current_user.tenant_id
                )

        response = GraphInsightsResponse(
            insights=insights,
            insight_types=request.insight_types,
            computation_time=insights.get("computation_time", 0.0),
            timestamp=datetime.utcnow()
        )

        # Cache results
        await cache_set(redis_client, cache_key, response.dict(), ttl=3600)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating graph insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Scheduled Analytics
@app.post("/analytics/schedule")
async def schedule_recurring_analytics(
    job_type: str,
    schedule: str,  # Cron expression
    parameters: Dict[str, Any],
    current_user = Depends(get_current_user)
):
    """Schedule recurring analytics job"""
    try:
        await tenant_service.verify_tenant_access(current_user.tenant_id, "analytics:schedule")

        schedule_id = await analytics_scheduler.schedule_job(
            job_type,
            schedule,
            parameters,
            current_user.tenant_id
        )

        return {
            "schedule_id": schedule_id,
            "job_type": job_type,
            "schedule": schedule,
            "status": "scheduled"
        }

    except Exception as e:
        logger.error(f"Error scheduling analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/analytics/schedule/{schedule_id}")
async def cancel_scheduled_analytics(
    schedule_id: str,
    current_user = Depends(get_current_user)
):
    """Cancel scheduled analytics job"""
    try:
        await tenant_service.verify_tenant_access(current_user.tenant_id, "analytics:schedule")

        success = await analytics_scheduler.cancel_job(schedule_id, current_user.tenant_id)

        if success:
            return {"message": "Schedule cancelled successfully"}
        else:
            raise HTTPException(status_code=404, detail="Schedule not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling scheduled analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

        # Check Celery
        inspect = celery_app.control.inspect()
        stats = inspect.stats()

        return {
            "status": "healthy",
            "service": "graph-analytics",
            "port": 8009,
            "neo4j": "connected",
            "redis": "connected",
            "celery": "active" if stats else "inactive",
            "active_workers": len(stats) if stats else 0
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "graph-analytics",
            "port": 8009,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "graph_analytics_service:app",
        host="0.0.0.0",
        port=8009,
        reload=config.DEBUG,
        log_level="info"
    )