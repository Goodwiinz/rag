"""REST API for external database connectors.

Provides endpoints to list available connectors, search across them,
and fetch individual records.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.connectors import connector_registry
from src.services.connectors.base import ConnectorDomain

router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])


# ---- Request / Response models ----


class ConnectorSummary(BaseModel):
    name: str
    display_name: str
    description: str
    domains: List[str]
    capabilities: List[str]
    requires_api_key: bool
    available: bool


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    connectors: Optional[List[str]] = Field(
        None, description="Connector names to search. None = all available."
    )
    domain: Optional[str] = Field(
        None, description="Filter connectors by domain."
    )
    max_results: int = Field(10, ge=1, le=50)
    filters: Optional[Dict[str, Any]] = None


class SearchResultItem(BaseModel):
    id: str
    title: str
    source: str
    url: str
    content: str = ""
    authors: List[str] = []
    published_date: Optional[str] = None
    metadata: Dict[str, Any] = {}
    document_type: str = "article"


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResultItem]
    connectors_searched: List[str]


# ---- Endpoints ----


@router.get("/", response_model=List[ConnectorSummary])
async def list_connectors(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    available_only: bool = Query(True, description="Only show available connectors"),
):
    """List all registered external database connectors."""
    if domain:
        try:
            d = ConnectorDomain(domain)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid domain: {domain}. Valid: {[d.value for d in ConnectorDomain]}",
            )
        connectors = connector_registry.search_by_domain(d)
    elif available_only:
        connectors = connector_registry.list_available()
    else:
        connectors = connector_registry.list_all()

    return [
        ConnectorSummary(
            name=c.info.name,
            display_name=c.info.display_name,
            description=c.info.description,
            domains=[d.value for d in c.info.domains],
            capabilities=[cap.value for cap in c.info.capabilities],
            requires_api_key=c.info.requires_api_key,
            available=c.is_available(),
        )
        for c in connectors
    ]


@router.post("/search", response_model=SearchResponse)
async def search_connectors(body: SearchRequest):
    """Search across one or more external database connectors."""
    import asyncio

    # Determine which connectors to search
    if body.connectors:
        targets = []
        for name in body.connectors:
            c = connector_registry.get(name)
            if c is None:
                raise HTTPException(
                    status_code=404, detail=f"Connector not found: {name}"
                )
            if not c.is_available():
                raise HTTPException(
                    status_code=503,
                    detail=f"Connector '{name}' is not available (API key missing?)",
                )
            targets.append(c)
    elif body.domain:
        try:
            d = ConnectorDomain(body.domain)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid domain: {body.domain}")
        targets = connector_registry.search_by_domain(d)
    else:
        targets = connector_registry.list_available()

    if not targets:
        return SearchResponse(
            query=body.query,
            total_results=0,
            results=[],
            connectors_searched=[],
        )

    # Search all targets concurrently
    tasks = [
        c.search(body.query, max_results=body.max_results, filters=body.filters)
        for c in targets
    ]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    merged: List[SearchResultItem] = []
    searched: List[str] = []
    for connector, result in zip(targets, all_results):
        searched.append(connector.info.name)
        if isinstance(result, Exception):
            continue  # skip failed connectors silently
        for r in result:
            merged.append(
                SearchResultItem(
                    id=r.id,
                    title=r.title,
                    source=r.source,
                    url=r.url,
                    content=r.content[:500],
                    authors=r.authors,
                    published_date=r.published_date,
                    metadata=r.metadata,
                    document_type=r.document_type,
                )
            )

    return SearchResponse(
        query=body.query,
        total_results=len(merged),
        results=merged,
        connectors_searched=searched,
    )


@router.get("/{connector_name}/{record_id}")
async def fetch_record(connector_name: str, record_id: str):
    """Fetch a single record from a specific connector by ID."""
    connector = connector_registry.get(connector_name)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"Connector not found: {connector_name}")
    if not connector.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"Connector '{connector_name}' is not available",
        )

    result = await connector.fetch_by_id(record_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Record '{record_id}' not found in {connector_name}",
        )

    return {
        "id": result.id,
        "title": result.title,
        "source": result.source,
        "url": result.url,
        "content": result.content,
        "authors": result.authors,
        "published_date": result.published_date,
        "metadata": result.metadata,
        "document_type": result.document_type,
    }
