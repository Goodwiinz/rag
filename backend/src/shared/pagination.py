"""Shared pagination primitives.

Audit finding C10: every router hand-rolls its own pagination — offset/limit
here, page/size (often unvalidated) there, limit-only elsewhere — and each one
re-derives its own ``total`` and ``has_more``. That divergence is the root of
the count-filter-drift bug class: a count query that applies different filters
than its result query over-reports ``total`` and yields phantom "next" pages.

This module provides two reusable pieces to converge on:

* :class:`PaginationParams` — a FastAPI dependency that validates ``page``/``size``
  once (``page >= 1``, ``1 <= size <= 100``) and exposes a computed ``offset``.
* :class:`Page` — a generic response envelope whose ``has_more`` is *derived*
  from the true total and the actual slice returned, so it can never claim a
  page that doesn't exist.

Pilot adoption: ``backend/src/api/documents/files.py``. Remaining routers are
adopt-on-touch.
"""

from __future__ import annotations

from typing import Generic, List, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams:
    """Validated page/size pagination, injected as a FastAPI dependency.

    Usage::

        @router.get("/")
        async def list_things(pagination: PaginationParams = Depends()):
            ...
            stmt = select(Thing).offset(pagination.offset).limit(pagination.size)

    ``page`` and ``size`` are validated by FastAPI *before* the handler runs, so
    out-of-range values fail closed with a 422 instead of reaching a raw
    ``.offset()/.limit()`` with a negative offset or an unbounded page size.
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="1-indexed page number"),
        size: int = Query(20, ge=1, le=100, description="Items per page (1-100)"),
    ) -> None:
        self.page = page
        self.size = size

    @property
    def offset(self) -> int:
        """Zero-based row offset for the current page."""
        return (self.page - 1) * self.size


class Page(BaseModel, Generic[T]):
    """Generic paginated response envelope.

    ``has_more`` is computed from ``total`` and the actual page slice — never
    passed in — so a drifted or stale count cannot manufacture a phantom next
    page. Prefer :meth:`create` over constructing this directly.
    """

    items: List[T]
    total: int = Field(..., ge=0, description="Total rows matching the filters")
    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1)
    has_more: bool = Field(
        ..., description="True when rows exist beyond the current page"
    )

    @classmethod
    def create(
        cls,
        items: Sequence[T],
        total: int,
        params: PaginationParams,
    ) -> "Page[T]":
        """Build a page from a slice, its true total, and the request params.

        ``has_more`` is derived as ``offset + len(items) < total``. Using the
        length of the returned slice (rather than the requested ``size``) keeps
        it honest even on a short final page.
        """
        consumed = params.offset + len(items)
        return cls(
            items=list(items),
            total=total,
            page=params.page,
            size=params.size,
            has_more=consumed < total,
        )
