"""
Global error handlers for RAG system exceptions
Provides consistent error responses across the application
"""

import logging
from typing import Any, Dict

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.exceptions import RAGException
from src.exceptions.analytics_exceptions import (
    AnalyticsException,
    AnalyticsServiceException,
    AnalyticsTimeoutException,
    ConfigurationException,
    DataRetentionException,
    DataValidationException,
    ExportFailedException,
    InsufficientDataException,
    PermissionDeniedException,
    RateLimitExceededException,
)

logger = logging.getLogger(__name__)


async def rag_exception_handler(request: Request, exc: RAGException) -> JSONResponse:
    """
    Handle all RAG system exceptions with consistent error responses.

    Logs errors appropriately based on severity and returns
    a structured error response without leaking internal details.
    """
    # Log with appropriate level based on status code
    if exc.status_code >= 500:
        logger.error(
            f"RAG exception: {exc.error_code} - {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "details": exc.details,
                "path": str(request.url),
                "method": request.method,
                "user_id": getattr(request.state, "user_id", None),
                "organization_id": getattr(request.state, "organization_id", None),
            },
            exc_info=exc.cause if exc.cause else True,
        )
    else:
        logger.warning(
            f"RAG exception: {exc.error_code} - {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "details": exc.details,
                "path": str(request.url),
                "method": request.method,
            },
        )

    # Build error response
    error_response = {
        "error": {
            "code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "path": str(request.url.path),
            "method": request.method,
        }
    }

    # Add request ID if available
    if hasattr(request.state, "request_id"):
        error_response["error"]["request_id"] = request.state.request_id

    return JSONResponse(status_code=exc.status_code, content=error_response)


async def analytics_exception_handler(
    request: Request, exc: AnalyticsException
) -> JSONResponse:
    """
    Handle all analytics exceptions with consistent error responses
    """
    # Determine appropriate HTTP status code based on exception type
    status_code_map = {
        PermissionDeniedException: 403,
        RateLimitExceededException: 429,
        DataValidationException: 422,
        InsufficientDataException: 422,
        AnalyticsTimeoutException: 408,
        ExportFailedException: 500,
        ConfigurationException: 500,
        DataRetentionException: 403,
        AnalyticsServiceException: 503,
        AnalyticsException: 500,
    }

    status_code = status_code_map.get(type(exc), 500)

    # Log the error with context
    logger.error(
        f"Analytics exception: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "path": str(request.url),
            "method": request.method,
            "user_id": getattr(request.state, "user_id", None),
            "organization_id": getattr(request.state, "organization_id", None),
        },
        exc_info=True,
    )

    # Build error response
    error_response = {
        "error": {
            "code": exc.error_code,
            "message": exc.user_friendly_message,
            "details": exc.details,
            "timestamp": exc.timestamp.isoformat() if exc.timestamp else None,
            "path": str(request.url.path),
            "method": request.method,
        }
    }

    # Add request ID if available
    if hasattr(request.state, "request_id"):
        error_response["error"]["request_id"] = request.state.request_id

    # Set appropriate headers for rate limiting
    headers = {}
    if isinstance(exc, RateLimitExceededException) and exc.details.get("retry_after"):
        headers["Retry-After"] = str(exc.details["retry_after"])

    return JSONResponse(
        status_code=status_code, content=error_response, headers=headers
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTP exceptions with consistent format
    """
    # Log HTTP exceptions
    logger.warning(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": str(request.url),
            "method": request.method,
            "user_id": getattr(request.state, "user_id", None),
        },
    )

    # Build error response in consistent format
    error_response = {
        "error": {
            "code": f"HTTP_{exc.status_code}",
            "message": exc.detail,
            "details": getattr(exc, "details", {}),
            "timestamp": None,
            "path": str(request.url.path),
            "method": request.method,
        }
    }

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response,
        headers=getattr(exc, "headers", {}),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle request validation errors
    """
    # Log validation errors
    logger.warning(
        f"Request validation error: {exc.errors()}",
        extra={
            "validation_errors": exc.errors(),
            "path": str(request.url),
            "method": request.method,
            "user_id": getattr(request.state, "user_id", None),
        },
    )

    # Format validation errors for user-friendly response
    formatted_errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        formatted_errors.append(
            {"field": field_path, "message": error["msg"], "type": error["type"]}
        )

    error_response = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed. Please check your input.",
            "details": {"validation_errors": formatted_errors},
            "timestamp": None,
            "path": str(request.url.path),
            "method": request.method,
        }
    }

    return JSONResponse(status_code=422, content=error_response)


async def database_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """
    Handle database errors
    """
    # Log database errors (without exposing sensitive details)
    logger.error(
        f"Database error: {str(exc)}",
        extra={
            "error_type": type(exc).__name__,
            "path": str(request.url),
            "method": request.method,
            "user_id": getattr(request.state, "user_id", None),
        },
        exc_info=True,
    )

    error_response = {
        "error": {
            "code": "DATABASE_ERROR",
            "message": "A database error occurred. Please try again later.",
            "details": {"error_type": "DatabaseError"},
            "timestamp": None,
            "path": str(request.url.path),
            "method": request.method,
        }
    }

    return JSONResponse(status_code=500, content=error_response)


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle any unhandled exceptions
    """
    # Log unexpected errors
    logger.error(
        f"Unhandled exception: {type(exc).__name__} - {str(exc)}",
        extra={
            "error_type": type(exc).__name__,
            "message": str(exc),
            "path": str(request.url),
            "method": request.method,
            "user_id": getattr(request.state, "user_id", None),
        },
        exc_info=True,
    )

    error_response = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Please try again later.",
            "details": {"error_type": type(exc).__name__},
            "timestamp": None,
            "path": str(request.url.path),
            "method": request.method,
        }
    }

    return JSONResponse(status_code=500, content=error_response)


def setup_error_handlers(app):
    """
    Register all error handlers with the FastAPI application
    """
    # RAG system exceptions (base class catches all)
    app.add_exception_handler(RAGException, rag_exception_handler)

    # Analytics-specific exceptions
    app.add_exception_handler(AnalyticsException, analytics_exception_handler)
    app.add_exception_handler(PermissionDeniedException, analytics_exception_handler)
    app.add_exception_handler(RateLimitExceededException, analytics_exception_handler)
    app.add_exception_handler(DataValidationException, analytics_exception_handler)
    app.add_exception_handler(InsufficientDataException, analytics_exception_handler)
    app.add_exception_handler(AnalyticsTimeoutException, analytics_exception_handler)
    app.add_exception_handler(ExportFailedException, analytics_exception_handler)
    app.add_exception_handler(ConfigurationException, analytics_exception_handler)
    app.add_exception_handler(DataRetentionException, analytics_exception_handler)
    app.add_exception_handler(AnalyticsServiceException, analytics_exception_handler)

    # General HTTP and framework exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Database and system exceptions
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Error handlers registered successfully")
