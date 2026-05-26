"""Lightweight application-level exception handlers."""

import logging

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.core.config import settings


logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    logger.error(f"Validation error on {request.url.path}: {exc.errors()}")
    safe_errors = []
    for err in exc.errors():
        safe = {k: v for k, v in err.items() if k != "ctx"}
        if "ctx" in err and isinstance(err["ctx"], dict):
            safe["ctx"] = {k: str(v) for k, v in err["ctx"].items()}
        safe_errors.append(safe)
    first_msg = (
        safe_errors[0].get("msg", "Validation error")
        if safe_errors
        else "Validation error"
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "message": first_msg,
                "status_code": 422,
                "type": "validation_error",
                "details": safe_errors,
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
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
        headers=dict(exc.headers) if exc.headers else None,
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)

    message = "Internal server error"
    if settings.ENVIRONMENT not in ("production",):
        message = f"{type(exc).__name__}: {exc}"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": message,
                "status_code": 500,
                "type": "internal_error",
            }
        },
    )
