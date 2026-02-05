"""
Monitoring Service Main Application

FastAPI application that combines all monitoring and observability services
into a comprehensive monitoring solution.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.monitoring_endpoints import router as monitoring_router
from .api.websocket_handlers import websocket_manager
from .config.monitoring_config import get_monitoring_config
from .middleware.observability_middleware import ObservabilityMiddleware
from .services.observability_manager import (
    ObservabilityManager,
    get_observability_manager,
)
from .utils.sentry_integration import init_sentry
from src.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    config = get_monitoring_config()
    observability_manager = get_observability_manager()

    logger.info("🚀 Starting Monitoring Service...")

    try:
        # Initialize Sentry
        if os.getenv("SENTRY_DSN"):
            init_sentry()
            logger.info("✅ Sentry initialized")

        # Initialize observability manager
        await observability_manager.initialize()
        await observability_manager.start()

        # Add monitoring service info to app state
        app.state.observability_manager = observability_manager
        app.state.config = config

        logger.info("✅ Monitoring Service started successfully")

        yield

    except Exception as e:
        logger.error(f"❌ Failed to start Monitoring Service: {e}")
        raise

    finally:
        logger.info("🛑 Stopping Monitoring Service...")

        # Cleanup
        await observability_manager.shutdown()
        await websocket_manager.stop_broadcasting()

        logger.info("✅ Monitoring Service stopped successfully")


# Create FastAPI application
app = FastAPI(
    title="RAG System Monitoring Service",
    description="Comprehensive monitoring and observability for the Multimodal Enterprise RAG System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
# SECURITY: Restrict allow_headers to specific values instead of "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# Add observability middleware
config = get_monitoring_config()
app.add_middleware(ObservabilityMiddleware)

# Include API routers
app.include_router(monitoring_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "RAG System Monitoring Service",
        "version": "1.0.0",
        "status": "running",
        "timestamp": "2024-01-01T00:00:00Z",
    }


@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    try:
        observability_manager = get_observability_manager()
        health_status = await observability_manager.health_check()

        return JSONResponse(
            status_code=200 if health_status["manager"]["status"] == "healthy" else 503,
            content={
                "status": health_status["manager"]["status"],
                "service": "monitoring",
                "version": "1.0.0",
                "checks": health_status,
            },
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "service": "monitoring", "error": str(e)},
        )


@app.get("/info")
async def service_info():
    """Get service information"""
    config = get_monitoring_config()

    return {
        "service": "RAG System Monitoring Service",
        "version": "1.0.0",
        "environment": config.environment,
        "debug": config.debug,
        "components": {
            "metrics": {
                "enabled": config.metrics.custom_metrics_enabled,
                "prometheus": config.metrics.prometheus_enabled,
            },
            "tracing": {
                "enabled": config.tracing.enabled,
                "jaeger": config.tracing.jaeger_enabled,
                "otlp": config.tracing.otlp_enabled,
            },
            "logging": {
                "enabled": config.logging.structured_logging,
                "level": config.logging.level,
            },
            "alerting": {"enabled": config.alerting.enabled},
            "health_checks": {"enabled": config.health_check.enabled},
        },
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    # Capture in Sentry if available
    try:
        observability_manager = get_observability_manager()
        # Sentry integration would capture this automatically
    except:
        pass

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "request_id": getattr(request.state, "request_id", None),
            "correlation_id": getattr(request.state, "correlation_id", None),
        },
    )


@app.on_event("startup")
async def startup_event():
    """Additional startup tasks"""
    logger.info("Monitoring Service startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Additional shutdown tasks"""
    logger.info("Monitoring Service shutdown complete")


# Development server startup
if __name__ == "__main__":
    import uvicorn

    config = get_monitoring_config()
    port = int(os.getenv("MONITORING_PORT", 8001))

    uvicorn.run(
        "main:app",
        host=os.getenv("MONITORING_HOST", "0.0.0.0"),
        port=port,
        reload=config.debug,
        log_level="info",
    )
