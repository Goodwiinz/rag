"""Diagnostics API endpoints for retrieval pipeline instrumentation."""

from .retrieval_diagnostics import router as diagnostics_router

__all__ = ["diagnostics_router"]
