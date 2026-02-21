"""
Main FastAPI application for the multimodal RAG system
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import redis  # Added this line
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

# Setup basic logging
logger = logging.getLogger(__name__)

from src.api.arxiv import (
    arxiv_bulk_router,
    arxiv_change_router,
    arxiv_extraction_router,
    arxiv_kg_router,
    arxiv_llm_bulk_router,
    arxiv_local_router,
    arxiv_router,
)
from src.api.auth import auth_router
from src.api.auth.api_keys import router as api_keys_router
from src.api.documents import documents_router, files_router, integrity_router, processing_router, table_extraction_router
from src.api.evidence.router import router as evidence_router
from src.api.infrastructure import evaluation_router, workers_router
from src.api.quality import (
    performance_dashboard_router,
    quality_metrics_router,
    quality_recommendations_router,
    user_behavior_router,
)
from src.api.realtime import (
    realtime_quality_metrics_router,
    realtime_status_router,
    websocket_router,
    websocket_v2_router,
)
from src.api.research import (
    chat_router,
    citations_router,
    drafts_router,
    export_router,
    extraction_matrix_router,
    project_chat_router,
    projects_router,
    tone_engine_router,
)
from src.api.research_engine import (
    research_engine_blueprints_router,
    research_engine_projects_router,
    research_engine_runs_router,
    research_engine_steps_router,
)
from src.api.search import (
    knowledge_graph_router,
    multi_agent_search_router,
    multi_agent_search_v2_router,
    search_quality_router,
    search_router,
    vectors_router,
)
from src.api.diagnostics import diagnostics_router
from src.api.security import compliance_router, encryption_router, rbac_router
from src.api.threads import (
    stream_router,
    thread_search_router,
    threads_router,
    workspaces_router,
    workspaces_standalone_router,
)
from src.core.config import settings
from src.core.database import Base, engine
from src.middleware.rate_limiting import AnalyticsRateLimitMiddleware
from src.health.endpoints import router as health_router

# from src.services.documents.file_service import redis_client  # Not exported, not needed here

# Configure observability (optional)
try:
    from src.observability import (
        configure_logging,
        configure_metrics,
        configure_tracing,
        instrument_app,
        instrument_services,
    )

    configure_logging()
    configure_tracing()
    configure_metrics()
    OBSERVABILITY_ENABLED = True
except ImportError as e:
    print(f"Warning: Observability not available: {e}")
    OBSERVABILITY_ENABLED = False

    # Create dummy functions
    def instrument_app(app):
        return app

    def instrument_services():
        pass


# Global Redis client instance
redis_client: Optional[redis.Redis] = None

try:
    redis_client = redis.from_url(settings.REDIS_URL)
    # We don't ping here to avoid blocking startup if Redis is down,
    # but the client object is created so middleware can use it (and fail gracefully later).
except Exception as e:
    logger.warning(
        f"Failed to create Redis client: {e}. Rate limiting will use in-memory storage."
    )
    redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting up Multimodal RAG System...")

    # Create database tables
    # Note: With multiple Gunicorn workers, create_all may race on PostgreSQL
    # ENUM type creation. We catch IntegrityError from duplicate types and
    # retry, since the first worker will have created them successfully.
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        if "already exists" in str(e):
            logger.info("Database tables already created by another worker")
        else:
            logger.error(f"Failed to create database tables: {e}")
            raise

    # Check Redis connection
    if redis_client:
        try:
            redis_client.ping()  # Test connection
            logger.info("Redis client connected successfully")
        except redis.RedisError as e:
            logger.warning(
                f"Redis connection failed: {e}. Rate limiting may not persist across restarts."
            )

    # Initialize WebSocket services
    try:
        from src.services.websocket.websocket_service_initializer import (
            websocket_service_initializer,
        )

        await websocket_service_initializer.initialize()
        logger.info("WebSocket services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize WebSocket services: {e}")
        # Continue startup even if WebSocket services fail

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down Multimodal RAG System...")

    # Close Redis client
    if redis_client:
        try:
            redis_client.close()
            logger.info("Redis client closed successfully")
        except redis.RedisError as e:
            logger.error(f"Error closing Redis client: {e}")

    # Shutdown WebSocket services
    try:
        from src.services.websocket.websocket_service_initializer import (
            websocket_service_initializer,
        )

        await websocket_service_initializer.shutdown()
        logger.info("WebSocket services shutdown successfully")
    except Exception as e:
        logger.error(f"Error shutting down WebSocket services: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="A multimodal enterprise RAG system for intelligent document search and analysis",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    redirect_slashes=False,  # Prevent 307 redirects that strip Authorization headers
)

# Instrument application with observability
instrument_app(app)

# Instrument additional services
if OBSERVABILITY_ENABLED:
    try:
        from src.services.documents.file_service import redis_client

        instrument_services(sql_engine=engine, redis_client=redis_client)
    except ImportError:
        instrument_services(sql_engine=engine)

# Add CORS middleware
# SECURITY: Strict CORS configuration - only allow specified origins, headers, and methods
# Never use allow_origins=["*"] or allow_headers=["*"] in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=settings.cors_methods_list,
    allow_headers=settings.cors_headers_list,
    expose_headers=settings.cors_expose_list,
    max_age=settings.CORS_MAX_AGE,  # Cache preflight for 24 hours
)

# Add rate limiting middleware for analytics endpoints
app.add_middleware(AnalyticsRateLimitMiddleware, redis_client=redis_client)

# Add trusted host middleware for production
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.yourdomain.com"],
    )


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add response time header"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming requests"""
    start_time = time.time()

    # Log request
    logger.info(
        f"Request: {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'}"
    )

    response = await call_next(request)

    # Log response
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} in {process_time:.4f}s")

    return response


# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(processing_router, prefix="/api/v1")
app.include_router(vectors_router, prefix="/api/v1")
app.include_router(knowledge_graph_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(search_quality_router, prefix="/api/v1")
app.include_router(multi_agent_search_router, prefix="/api/v1")
app.include_router(multi_agent_search_v2_router)  # Enhanced v2 multi-agent search
app.include_router(evidence_router, prefix="/api/v1/evidence", tags=["evidence"])
app.include_router(quality_metrics_router, prefix="/api/v1/analytics/quality")
app.include_router(user_behavior_router, prefix="/api/v1/analytics/behavior")
app.include_router(performance_dashboard_router, prefix="/api/v1/analytics/performance")
app.include_router(
    quality_recommendations_router, prefix="/api/v1/analytics/recommendations"
)
app.include_router(workers_router, prefix="/api/v1")
app.include_router(encryption_router, prefix="/api/v1/security")
app.include_router(compliance_router, prefix="/api/v1/security")
app.include_router(rbac_router, prefix="/api/v1/rbac")
app.include_router(evaluation_router, prefix="/api/v1")
app.include_router(diagnostics_router, prefix="/api/v1")  # Retrieval diagnostics endpoints
app.include_router(websocket_router)  # Legacy WebSocket routes
app.include_router(websocket_v2_router)  # Enhanced WebSocket v2 routes
app.include_router(realtime_status_router)  # Real-time document status API
app.include_router(
    realtime_quality_metrics_router, prefix="/api/v2"
)  # Real-time quality metrics API
app.include_router(arxiv_router)  # ArXiv integration endpoints
app.include_router(
    arxiv_kg_router, prefix="/api/v1/arxiv/kg"
)  # ArXiv Knowledge Graph endpoints
app.include_router(
    arxiv_change_router, prefix="/api/v1/arxiv/tracking"
)  # ArXiv Change Tracking endpoints
app.include_router(
    arxiv_extraction_router, prefix="/api/v1/arxiv/extraction"
)  # ArXiv Feature Extraction endpoints
app.include_router(
    arxiv_local_router, prefix="/api/v1/arxiv/local"
)  # Local ArXiv PDF processing endpoints
# app.include_router(arxiv_batch_router, prefix="/api/v1/arxiv/batch")  # Temporarily disabled due to import error
app.include_router(
    arxiv_bulk_router, prefix="/api/v1"
)  # Kaggle bulk ingestion endpoints
app.include_router(
    arxiv_llm_bulk_router, prefix="/api/v1"
)  # LLM-powered bulk ingestion with embeddings
app.include_router(chat_router, prefix="/api/v1")  # Chat completion endpoints
app.include_router(
    workspaces_router
)  # Thread-centric workspace/conversation/thread/message API
# IMPORTANT: threads_router MUST be included BEFORE workspaces_standalone_router
# because threads_router has /bulk/* routes that need to match before /{thread_id}
app.include_router(
    threads_router, prefix="/api/v2"
)  # Thread management endpoints (includes bulk operations)
app.include_router(
    stream_router, prefix="/api/v2"
)  # SSE streaming chat endpoint
app.include_router(
    workspaces_standalone_router
)  # Flat API routes for workspaces (used by frontend)
app.include_router(export_router, prefix="/api/v1")  # Thread export endpoints
app.include_router(citations_router)  # Research Assistant citations endpoints
app.include_router(projects_router)  # Research Assistant projects endpoints
app.include_router(project_chat_router)  # Project-Chat integration endpoints
app.include_router(drafts_router)  # Research Assistant drafts endpoints
app.include_router(tone_engine_router)  # Scholarly Tone Engine endpoints
app.include_router(extraction_matrix_router)  # Extraction Matrix endpoints
app.include_router(integrity_router)  # AI Integrity Detector endpoints
app.include_router(table_extraction_router)  # Table & math extraction endpoints
app.include_router(research_engine_projects_router, prefix="/api/v1")  # Research Engine projects
app.include_router(research_engine_blueprints_router, prefix="/api/v1")  # Research Engine blueprints
app.include_router(research_engine_runs_router, prefix="/api/v1")  # Research Engine runs
app.include_router(research_engine_steps_router, prefix="/api/v1")  # Research Engine steps
app.include_router(
    thread_search_router, prefix="/api/v2"
)  # Thread and message full-text search

# Include health endpoints
app.include_router(health_router)  # Comprehensive health check endpoints

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time(),
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.VERSION,
        "docs_url": "/docs"
        if settings.DEBUG
        else "Documentation not available in production",
        "health_check": "/health",
    }


# Global exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    logger.error(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "message": "Validation error",
                "status_code": 422,
                "type": "validation_error",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP {exc.status_code} error on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "status_code": exc.status_code,
                "type": "http_error",
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "Internal server error" if not settings.DEBUG else str(exc),
                "status_code": 500,
                "type": "internal_error",
            }
        },
    )


# Development server info
if settings.DEBUG:

    @app.get("/debug/info")
    async def debug_info():
        """Debug information endpoint (development only)"""
        return {
            "settings": {
                "database_url": settings.DATABASE_URL,
                "environment": settings.ENVIRONMENT,
                "log_level": settings.LOG_LEVEL,
                "enable_metrics": settings.ENABLE_METRICS,
                "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
                "free_tier_storage_gb": settings.FREE_TIER_STORAGE_GB,
            },
            "environment_variables": {
                "NEO4J_URI": settings.NEO4J_URI,
                "QDRANT_URL": settings.QDRANT_URL,
                "REDIS_URL": settings.REDIS_URL,
            },
        }


# Debug: Inspect middleware stack
print("Inspecting middleware stack:", flush=True)
for i, m in enumerate(app.user_middleware):
    try:
        print(f"Middleware {i}: {m} (type: {type(m)})", flush=True)
        # specific check for unpacking
        try:
            items = list(m)
            print(f"  Unpacks to {len(items)} items: {items}", flush=True)
        except Exception as e:
            print(f"  Cannot unpack middleware {i}: {e}", flush=True)
    except Exception as e:
        print(f"  Error inspecting middleware {i}: {e}", flush=True)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
