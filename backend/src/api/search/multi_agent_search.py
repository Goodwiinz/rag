"""
Multi-Agent Search API endpoints

This module provides RESTful API endpoints for multi-agent search orchestration,
allowing users to benefit from AI-powered agent collaboration for improved search results.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.core.database import get_db, get_db_sync
from src.core.dependencies import get_current_user
from src.models.search_schemas import SearchQuery, SearchType
from src.models.user import User
from src.services.search.multi_agent_search_service import (
    AgentExecution,
    AgentType,
    MultiAgentSearchResult,
    multi_agent_search_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/multi-agent-search", tags=["multi-agent-search"])


class MultiAgentSearchRequest(BaseModel):
    """Request for multi-agent search"""

    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    max_agents: int = Field(
        default=4, ge=1, le=6, description="Maximum number of agents to use"
    )
    timeout: float = Field(
        default=120.0,
        ge=30.0,
        le=300.0,
        description="Maximum execution time in seconds",
    )
    include_agent_details: bool = Field(
        default=True, description="Include detailed agent execution information"
    )
    enable_quality_check: bool = Field(
        default=True, description="Enable quality assurance agent"
    )
    enable_graph_navigation: bool = Field(
        default=True, description="Enable knowledge graph navigation"
    )


class MultiAgentSearchResponse(BaseModel):
    """Response from multi-agent search"""

    original_query: str
    refined_query: str
    synthesized_answer: str
    confidence_score: float
    execution_time: float
    search_results_count: int
    quality_metrics: Dict[str, float]
    recommendations: List[str]
    agent_executions: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any]


class AgentStatusResponse(BaseModel):
    """Response for agent status"""

    crewai_available: bool
    agents_configured: List[str]
    tools_available: List[str]
    llm_configured: bool
    supported_agent_types: List[str]


class AgentBenchmarkRequest(BaseModel):
    """Request for agent performance benchmark"""

    test_queries: List[str] = Field(
        ..., min_items=1, max_items=10, description="Test queries for benchmarking"
    )
    agent_configurations: List[Dict[str, Any]] = Field(
        default_factory=list, description="Different agent configurations to test"
    )
    timeout_per_query: float = Field(
        default=60.0, ge=30.0, le=180.0, description="Timeout per query"
    )


class AgentBenchmarkResponse(BaseModel):
    """Response from agent benchmark"""

    benchmark_id: str
    test_queries: List[str]
    configuration_results: Dict[str, Dict[str, Any]]
    summary: Dict[str, Any]
    timestamp: datetime


@router.post("/search", response_model=MultiAgentSearchResponse)
async def multi_agent_search(
    request: MultiAgentSearchRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
):
    """
    Perform multi-agent search with AI-powered collaboration

    This endpoint orchestrates multiple specialized agents to provide comprehensive
    and accurate search results through intelligent collaboration.

    The agents work together to:
    - Understand and refine the query
    - Retrieve relevant content from multiple sources
    - Navigate knowledge graphs for related concepts
    - Validate result quality and accuracy
    - Synthesize comprehensive answers
    """
    try:
        # Log the multi-agent search request
        logger.info(
            f"Multi-agent search request: query='{request.query}', user_id={current_user.id}, max_agents={request.max_agents}"
        )

        # Execute multi-agent search
        result = await multi_agent_search_service.orchestrate_search(
            query=request.query,
            user_id=str(current_user.id),
            organization_id=str(current_user.organization_id),
            max_agents=request.max_agents,
            timeout=request.timeout,
        )

        # Prepare agent executions for response
        agent_executions = None
        if request.include_agent_details:
            agent_executions = []
            for execution in result.agent_executions:
                agent_executions.append(
                    {
                        "task_id": execution.task_id,
                        "agent_type": execution.agent_type.value,
                        "execution_time": execution.execution_time,
                        "success": execution.success,
                        "result": execution.result,
                        "error_message": execution.error_message,
                        "metadata": execution.metadata,
                    }
                )

        # Log successful completion
        background_tasks.add_task(
            logger.info,
            f"Multi-agent search completed: query='{request.query}', "
            f"results={len(result.search_results)}, confidence={result.confidence_score:.2f}, "
            f"time={result.execution_time:.2f}s, agents={len(result.agent_executions)}",
        )

        return MultiAgentSearchResponse(
            original_query=result.original_query,
            refined_query=result.refined_query,
            synthesized_answer=result.synthesized_answer,
            confidence_score=result.confidence_score,
            execution_time=result.execution_time,
            search_results_count=len(result.search_results),
            quality_metrics=result.quality_metrics,
            recommendations=result.recommendations,
            agent_executions=agent_executions,
            metadata=result.metadata,
        )

    except Exception as e:
        logger.error(f"Multi-agent search failed: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status(current_user: User = Depends(get_current_user)):
    """
    Get status of multi-agent search system

    Returns information about available agents, tools, and system configuration.
    """
    try:
        status = multi_agent_search_service.get_agent_status()

        return AgentStatusResponse(
            crewai_available=status["crewai_available"],
            agents_configured=status["agents_configured"],
            tools_available=status["tools_available"],
            llm_configured=status["llm_configured"],
            supported_agent_types=[agent_type.value for agent_type in AgentType],
        )

    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/benchmark", response_model=AgentBenchmarkResponse)
async def run_agent_benchmark(
    request: AgentBenchmarkRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Run performance benchmark for multi-agent search

    Tests different agent configurations and query types to evaluate performance
    and identify optimal settings.
    """
    try:
        benchmark_id = f"benchmark_{int(datetime.utcnow().timestamp())}"
        configuration_results = {}
        summary_stats = {}

        # Default configurations to test
        default_configs = [
            {"name": "minimal", "max_agents": 2, "description": "Minimal agent set"},
            {"name": "balanced", "max_agents": 4, "description": "Balanced agent set"},
            {
                "name": "comprehensive",
                "max_agents": 6,
                "description": "Comprehensive agent set",
            },
        ]

        configurations = (
            request.agent_configurations
            if request.agent_configurations
            else default_configs
        )

        # Run benchmark for each configuration
        for config in configurations:
            config_name = config.get("name", f"config_{len(configuration_results)}")
            max_agents = config.get("max_agents", 4)

            config_results = {
                "queries_tested": len(request.test_queries),
                "successful_queries": 0,
                "failed_queries": 0,
                "total_execution_time": 0.0,
                "average_execution_time": 0.0,
                "average_confidence": 0.0,
                "agent_success_rate": 0.0,
                "errors": [],
            }

            total_time = 0.0
            total_confidence = 0.0
            successful_queries = 0

            # Test each query
            for query in request.test_queries:
                try:
                    result = await multi_agent_search_service.orchestrate_search(
                        query=query,
                        user_id=str(current_user.id),
                        organization_id=str(current_user.organization_id),
                        max_agents=max_agents,
                        timeout=request.timeout_per_query,
                    )

                    if result.confidence_score > 0:
                        successful_queries += 1
                        total_time += result.execution_time
                        total_confidence += result.confidence_score
                    else:
                        config_results["failed_queries"] += 1

                except Exception as e:
                    config_results["failed_queries"] += 1
                    config_results["errors"].append(
                        f"Query '{query[:50]}...': {str(e)}"
                    )
                    logger.error(f"Benchmark query failed: {e}")

            # Calculate statistics
            config_results["successful_queries"] = successful_queries
            config_results["total_execution_time"] = total_time
            config_results["average_execution_time"] = (
                total_time / successful_queries if successful_queries > 0 else 0
            )
            config_results["average_confidence"] = (
                total_confidence / successful_queries if successful_queries > 0 else 0
            )

            # Agent success rate (simplified - would need more detailed tracking)
            config_results["agent_success_rate"] = successful_queries / len(
                request.test_queries
            )

            configuration_results[config_name] = config_results

        # Generate summary
        if configuration_results:
            best_config = max(
                configuration_results.items(), key=lambda x: x[1]["average_confidence"]
            )
            fastest_config = min(
                configuration_results.items(),
                key=lambda x: x[1]["average_execution_time"],
            )

            summary_stats = {
                "total_configurations": len(configuration_results),
                "best_performing_config": best_config[0],
                "best_confidence_score": best_config[1]["average_confidence"],
                "fastest_config": fastest_config[0],
                "fastest_avg_time": fastest_config[1]["average_execution_time"],
                "overall_success_rate": sum(
                    r["successful_queries"] for r in configuration_results.values()
                )
                / (len(request.test_queries) * len(configuration_results)),
            }

        # Log benchmark completion
        background_tasks.add_task(
            logger.info,
            f"Agent benchmark completed: benchmark_id={benchmark_id}, "
            f"configs={len(configuration_results)}, queries={len(request.test_queries)}, "
            f"user={current_user.id}",
        )

        return AgentBenchmarkResponse(
            benchmark_id=benchmark_id,
            test_queries=request.test_queries,
            configuration_results=configuration_results,
            summary=summary_stats,
            timestamp=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Agent benchmark failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/agents/types")
async def get_supported_agent_types():
    """
    Get information about supported agent types

    Returns descriptions of each agent type and their capabilities.
    """
    agent_descriptions = {
        "retrieval": {
            "name": "Content Retrieval Specialist",
            "description": "Finds the most relevant and comprehensive content for user queries",
            "capabilities": [
                "Hybrid search",
                "Document retrieval",
                "Relevance ranking",
                "Source diversity",
            ],
            "tools": ["hybrid_search"],
            "estimated_duration": 20.0,
        },
        "graph_navigation": {
            "name": "Knowledge Graph Navigator",
            "description": "Discovers related entities and concepts through graph traversal",
            "capabilities": [
                "Entity relationship discovery",
                "Concept mapping",
                "Multi-hop relationships",
                "Graph traversal",
            ],
            "tools": ["knowledge_graph"],
            "estimated_duration": 25.0,
        },
        "quality_assurance": {
            "name": "Search Quality Assurance Specialist",
            "description": "Validates search result accuracy, relevance, and completeness",
            "capabilities": [
                "Result validation",
                "Quality assessment",
                "Gap identification",
                "Accuracy checking",
            ],
            "tools": [],
            "estimated_duration": 20.0,
        },
        "answer_synthesis": {
            "name": "Answer Synthesis Expert",
            "description": "Synthesizes search results into coherent, comprehensive responses",
            "capabilities": [
                "Information synthesis",
                "Answer generation",
                "Coherence checking",
                "Response formatting",
            ],
            "tools": [],
            "estimated_duration": 30.0,
        },
        "query_understanding": {
            "name": "Query Understanding Specialist",
            "description": "Analyzes, refines, and expands user queries for better search results",
            "capabilities": [
                "Intent analysis",
                "Query refinement",
                "Entity extraction",
                "Query expansion",
            ],
            "tools": [],
            "estimated_duration": 15.0,
        },
        "result_enrichment": {
            "name": "Search Result Enrichment Specialist",
            "description": "Enhances search results with additional context and metadata",
            "capabilities": [
                "Context addition",
                "Metadata enrichment",
                "Categorization",
                "Summarization",
            ],
            "tools": ["hybrid_search"],
            "estimated_duration": 15.0,
        },
    }

    return {
        "agent_types": agent_descriptions,
        "total_types": len(agent_descriptions),
        "collaboration_benefits": [
            "Improved result accuracy through multiple perspectives",
            "Comprehensive coverage of different aspects of the query",
            "Quality validation reduces errors and improves reliability",
            "Intelligent result synthesis provides coherent answers",
            "Agent collaboration identifies gaps and additional relevant information",
        ],
    }


@router.get("/health")
async def health_check():
    """
    Health check for multi-agent search service

    Returns the status of the multi-agent search system and its components.
    """
    try:
        status = multi_agent_search_service.get_agent_status()

        # Basic health indicators
        is_healthy = (
            status["crewai_available"]
            or len(status["agents_configured"]) > 0  # Can work in fallback mode
            or len(status["tools_available"]) > 0
        )

        health_status = {
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "multi_agent_search",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "crewai_available": status["crewai_available"],
                "agents_configured": len(status["agents_configured"]),
                "tools_available": len(status["tools_available"]),
                "llm_configured": status["llm_configured"],
            },
            "capabilities": {
                "multi_agent_orchestration": status["crewai_available"],
                "fallback_mode": True,  # Always available
                "agent_collaboration": status["crewai_available"]
                and len(status["agents_configured"]) > 1,
            },
        }

        if not is_healthy:
            return JSONResponse(status_code=503, content=health_status)

        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "multi_agent_search",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


@router.get("/performance")
async def get_performance_metrics(
    days: int = Query(default=7, ge=1, le=30, description="Number of days for metrics"),
    current_user: User = Depends(get_current_user),
):
    """
    Get performance metrics for multi-agent search

    Returns analytics about agent performance, execution times, success rates,
    and collaboration effectiveness.
    """
    try:
        # This would typically query a metrics database
        # For now, return mock data that demonstrates the expected structure
        mock_metrics = {
            "period_days": days,
            "total_searches": 45,
            "average_execution_time": 28.5,
            "average_confidence_score": 0.78,
            "agent_success_rates": {
                "retrieval": 0.92,
                "graph_navigation": 0.85,
                "quality_assurance": 0.88,
                "answer_synthesis": 0.90,
                "query_understanding": 0.95,
                "result_enrichment": 0.87,
            },
            "collaboration_effectiveness": 0.82,
            "most_used_configurations": [
                {"name": "balanced", "usage_count": 25, "avg_confidence": 0.78},
                {"name": "comprehensive", "usage_count": 15, "avg_confidence": 0.85},
                {"name": "minimal", "usage_count": 5, "avg_confidence": 0.65},
            ],
            "query_complexity_distribution": {
                "simple": 15,
                "moderate": 20,
                "complex": 10,
            },
            "recommendations": [
                "Consider using comprehensive configuration for complex queries",
                "Graph navigation agent shows high success rate - enable for entity-rich queries",
                "Query understanding agent has excellent success rate - always include for better results",
            ],
        }

        return mock_metrics

    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/compare")
async def compare_search_methods(
    request_data: Dict[str, str], current_user: User = Depends(get_current_user)
):
    """
    Compare multi-agent search with standard hybrid search

    Executes the same query using both methods and provides comparative analysis.
    """
    try:
        query = request_data.get("query", "")
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")

        # Execute standard hybrid search
        from src.models.search_schemas import SearchQuery
        from src.services.search.hybrid_search_service import hybrid_search_service

        standard_search_query = SearchQuery(
            query=query, search_type=SearchType.HYBRID, limit=10
        )

        start_time = datetime.utcnow()
        standard_result = hybrid_search_service.search(
            search_request=standard_search_query,
            user_id=str(current_user.id),
            organization_id=str(current_user.organization_id),
        )
        standard_time = (datetime.utcnow() - start_time).total_seconds()

        # Execute multi-agent search
        start_time = datetime.utcnow()
        multi_agent_result = await multi_agent_search_service.orchestrate_search(
            query=query,
            user_id=str(current_user.id),
            organization_id=str(current_user.organization_id),
            max_agents=4,
            timeout=60.0,
        )
        multi_agent_time = (datetime.utcnow() - start_time).total_seconds()

        # Compare results
        comparison = {
            "query": query,
            "standard_search": {
                "results_count": len(standard_result.results),
                "execution_time": standard_time,
                "avg_relevance_score": sum(
                    r.relevance_score for r in standard_result.results
                )
                / len(standard_result.results)
                if standard_result.results
                else 0,
                "search_type": "hybrid",
            },
            "multi_agent_search": {
                "results_count": len(multi_agent_result.search_results),
                "execution_time": multi_agent_result.execution_time,
                "confidence_score": multi_agent_result.confidence_score,
                "agents_used": len(multi_agent_result.agent_executions),
                "synthesized_answer": multi_agent_result.synthesized_answer,
                "quality_metrics": multi_agent_result.quality_metrics,
            },
            "analysis": {
                "time_difference": multi_agent_result.execution_time - standard_time,
                "multi_agent_faster": multi_agent_result.execution_time < standard_time,
                "quality_improvement": multi_agent_result.confidence_score
                - 0.7,  # Assuming standard search has baseline 0.7
                "agent_benefits": multi_agent_result.recommendations,
                "recommended_usage": _get_recommendation(
                    multi_agent_result.confidence_score,
                    multi_agent_result.execution_time,
                    standard_time,
                ),
            },
        }

        return comparison

    except Exception as e:
        logger.error(f"Search comparison failed: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


def _get_recommendation(
    confidence_score: float, multi_agent_time: float, standard_time: float
) -> str:
    """Get recommendation based on performance comparison"""
    if confidence_score > 0.8 and multi_agent_time < standard_time * 1.5:
        return "Multi-agent search shows clear benefits - recommended for this type of query"
    elif confidence_score > 0.7:
        return (
            "Multi-agent search provides improved quality - use for important queries"
        )
    elif multi_agent_time > standard_time * 2:
        return "Standard search is faster - use multi-agent search for complex queries only"
    else:
        return "Both methods perform similarly - choose based on specific needs"
