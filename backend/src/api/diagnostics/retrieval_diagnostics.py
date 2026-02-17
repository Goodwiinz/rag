"""
REST API endpoints for retrieval diagnostics.

Provides access to diagnostic traces, aggregate statistics,
bottleneck analysis, and weight experimentation.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.core.dependencies import require_admin
from src.services.diagnostics.bottleneck_analyzer import BottleneckAnalyzer
from src.services.diagnostics.diagnostics_store import diagnostics_store

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/diagnostics",
    tags=["diagnostics"],
    dependencies=[Depends(require_admin)],
)


# --- Request/Response models ---


class WeightExperimentRequest(BaseModel):
    """Request to run the same query with different weight configurations."""

    query: str = Field(..., description="Search query to test")
    max_docs: int = Field(default=5, ge=1, le=10)
    configurations: List[Dict[str, float]] = Field(
        ...,
        description="List of weight configs, each a dict with fulltext/vector/knowledge_graph keys summing to 1.0",
        min_length=1,
        max_length=5,
    )


class WeightExperimentResult(BaseModel):
    """Result of a single weight configuration experiment."""

    weights: Dict[str, float]
    result_count: int
    top_scores: List[float]
    trace_id: str
    total_time_ms: float


class WeightExperimentResponse(BaseModel):
    """Response containing all experiment results."""

    query: str
    results: List[WeightExperimentResult]


# --- Endpoints ---


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> Dict[str, Any]:
    """Get full diagnostic trace by ID."""
    trace = await diagnostics_store.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    # Include bottleneck analysis
    analyzer = BottleneckAnalyzer()
    report = analyzer.analyze_trace(trace)

    return {
        "trace": trace.to_dict(),
        "bottleneck_report": report.to_dict(),
    }


@router.get("/traces")
async def get_recent_traces(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """Get recent trace summaries."""
    traces = await diagnostics_store.get_recent_traces(limit=limit, offset=offset)
    return {"traces": traces, "count": len(traces), "limit": limit, "offset": offset}


@router.get("/aggregate")
async def get_aggregate_stats(
    hours: int = Query(default=24, ge=1, le=168),
) -> Dict[str, Any]:
    """Get aggregate statistics over the specified time period."""
    stats = await diagnostics_store.get_aggregate_stats(hours=hours)
    return stats


@router.post("/weight-experiment", response_model=WeightExperimentResponse)
async def run_weight_experiment(request: WeightExperimentRequest) -> WeightExperimentResponse:
    """
    Run the same query with different weight configurations and compare results.

    Each configuration must have fulltext, vector, and knowledge_graph keys summing to 1.0.
    """
    import asyncio

    from src.models.search_schemas import SearchQuery
    from src.services.search.hybrid_search_service import hybrid_search_service

    # Validate weight configs
    for i, config in enumerate(request.configurations):
        total = sum(config.values())
        if abs(total - 1.0) > 0.01:
            raise HTTPException(
                status_code=422,
                detail=f"Configuration {i} weights must sum to 1.0 (got {total:.2f})",
            )

    results = []
    loop = asyncio.get_event_loop()

    for config in request.configurations:
        search_request = SearchQuery(
            query=request.query, limit=request.max_docs, search_type="hybrid"
        )

        response, trace = await loop.run_in_executor(
            None,
            lambda cfg=config: hybrid_search_service.search_with_diagnostics(
                search_request=search_request,
                weights_override=cfg,
            ),
        )

        # Store the trace
        await diagnostics_store.store_trace(trace)

        top_scores = sorted(
            [r.relevance_score for r in response.results], reverse=True
        )[:5]

        results.append(
            WeightExperimentResult(
                weights=config,
                result_count=len(response.results),
                top_scores=[round(s, 4) for s in top_scores],
                trace_id=trace.trace_id,
                total_time_ms=round(trace.total_time_ms, 2),
            )
        )

    return WeightExperimentResponse(query=request.query, results=results)
