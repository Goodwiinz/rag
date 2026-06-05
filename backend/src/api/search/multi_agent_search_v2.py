"""
API endpoints for the enhanced multi-agent search service v2.
Provides improved orchestration, monitoring, and benchmarking capabilities.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.core.dependencies import get_current_user
from src.models.user import User
from src.services.search.multi_agent_search_service_v2 import (
    AgentType,
    WorkflowType,
    multi_agent_search_service_v2,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/multi-agent-search", tags=["multi-agent-search-v2"])


# Request/Response Models
class MultiAgentSearchRequest(BaseModel):
    """Enhanced request model for multi-agent search"""

    query: str = Field(..., description="Search query", min_length=1, max_length=1000)
    workflow_type: WorkflowType = Field(
        default=WorkflowType.FACTUAL_LOOKUP, description="Type of search workflow"
    )
    max_agents: int = Field(
        default=4, ge=1, le=7, description="Maximum number of agents to use"
    )
    timeout: float = Field(
        default=180.0,
        ge=30.0,
        le=600.0,
        description="Maximum execution time in seconds",
    )
    enable_learning: bool = Field(default=True, description="Enable query learning")
    user_preferences: Optional[Dict[str, Any]] = Field(
        default=None, description="User-specific preferences"
    )


class WorkflowRecommendationRequest(BaseModel):
    """Request for workflow recommendations"""

    query: str = Field(
        ..., description="Query to analyze", min_length=1, max_length=1000
    )


class AgentBenchmarkRequest(BaseModel):
    """Request for agent benchmarking"""

    queries: List[str] = Field(
        ..., description="List of test queries", min_items=1, max_items=100
    )
    workflow_types: List[WorkflowType] = Field(
        default=[WorkflowType.FACTUAL_LOOKUP], description="Workflow types to test"
    )
    iterations: int = Field(
        default=3, ge=1, le=10, description="Number of iterations per query"
    )
    parallel: bool = Field(default=False, description="Run tests in parallel")


class MultiAgentSearchResponse(BaseModel):
    """Enhanced response model for multi-agent search"""

    success: bool
    query: str
    workflow_type: str
    results: Dict[str, Any]
    execution_time: float
    confidence_score: float
    agent_performance: Dict[str, Any]
    recommendations: List[str]
    metadata: Dict[str, Any]


# API Endpoints
@router.post("/search", response_model=MultiAgentSearchResponse)
async def enhanced_multi_agent_search(
    request: MultiAgentSearchRequest,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
):
    """
    Execute enhanced multi-agent search with improved orchestration and monitoring.

    Features:
    - Workflow-specific optimization
    - Intelligent agent selection
    - Real-time performance tracking
    - Query learning
    - Enhanced error handling
    """
    try:
        # Log search request for analytics
        logger.info(
            f"Enhanced multi-agent search request from user {current_user.id}: {request.query}"
        )

        # Apply user preferences if provided
        if request.user_preferences:
            # Adjust parameters based on user preferences
            max_agents = request.user_preferences.get("max_agents", request.max_agents)
            timeout = request.user_preferences.get("timeout", request.timeout)
        else:
            max_agents = request.max_agents
            timeout = request.timeout

        # Execute search
        start_time = datetime.now(timezone.utc)
        result = await multi_agent_search_service_v2.orchestrate_search(
            query=request.query,
            user_id=str(current_user.id),
            organization_id=current_user.organization_id,
            workflow_type=request.workflow_type,
            max_agents=max_agents,
            timeout=timeout,
            enable_learning=request.enable_learning,
        )
        end_time = datetime.now(timezone.utc)

        # Format response
        response = MultiAgentSearchResponse(
            success=True,
            query=result.original_query,
            workflow_type=result.workflow_type.value,
            results={
                "refined_query": result.refined_query,
                "expanded_queries": result.expanded_queries,
                "search_results": [
                    {
                        "id": r.id,
                        "title": r.title,
                        "content_preview": r.content_preview,
                        "relevance_score": r.relevance_score,
                        "source_type": r.source_type.value
                        if hasattr(r.source_type, "value")
                        else str(r.source_type),
                        "metadata": r.metadata,
                    }
                    for r in result.search_results
                ],
                "synthesized_answer": result.synthesized_answer,
            },
            execution_time=result.execution_time,
            confidence_score=result.confidence_score,
            agent_performance={
                agent_type: {
                    "executions": metrics.total_executions,
                    "success_rate": metrics.successful_executions
                    / metrics.total_executions
                    if metrics.total_executions > 0
                    else 0,
                    "avg_time": metrics.average_execution_time,
                    "confidence": metrics.confidence_score,
                }
                for agent_type, metrics in result.agent_metrics.items()
            },
            recommendations=result.recommendations,
            metadata={
                **result.metadata,
                "user_id": str(current_user.id),
                "timestamp": end_time.isoformat(),
                "server_time": (end_time - start_time).total_seconds(),
            },
        )

        # Schedule background task for analytics
        if background_tasks:
            background_tasks.add_task(
                log_search_analytics,
                str(current_user.id),
                request.query,
                result.execution_time,
                result.confidence_score,
                len(result.agent_executions),
            )

        return response

    except asyncio.TimeoutError:
        logger.error(f"Search timeout for query: {request.query}")
        raise HTTPException(
            status_code=408,
            detail="Search request timed out. Please try with a simpler query or increase timeout.",
        )
    except Exception as e:
        logger.error(f"Enhanced multi-agent search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def get_service_status(current_user: User = Depends(get_current_user)):
    """
    Get comprehensive status of the multi-agent search service.

    Returns:
    - Service availability
    - Agent configuration status
    - Performance metrics
    - System health indicators
    """
    try:
        # Get service report
        performance_report = (
            multi_agent_search_service_v2.get_agent_performance_report()
        )

        # Check system health
        health_checks = {
            "crewai_available": performance_report["crewai_available"],
            "agents_configured": performance_report["agents_configured"],
            "memory_status": check_memory_status(),
            "cache_status": check_cache_status(),
        }

        # Calculate overall health score
        health_score = calculate_health_score(health_checks)

        return {
            "status": "healthy" if health_score >= 0.8 else "degraded",
            "health_score": health_score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_info": performance_report,
            "health_checks": health_checks,
            "capabilities": {
                "supported_workflows": [w.value for w in WorkflowType],
                "available_agents": [a.value for a in AgentType],
                "max_concurrent_searches": 10,
                "features": [
                    "workflow_optimization",
                    "query_learning",
                    "performance_tracking",
                    "enhanced_caching",
                    "parallel_execution",
                ],
            },
        }

    except Exception as e:
        logger.error(f"Failed to get service status: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/workflow-recommendations")
async def get_workflow_recommendations(
    request: WorkflowRecommendationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Get AI-powered workflow recommendations for a query.

    Returns:
    - Recommended workflow type
    - Suggested agents
    - Estimated execution time
    - Optimization tips
    """
    try:
        recommendations = multi_agent_search_service_v2.get_workflow_recommendations(
            request.query
        )

        # Enhance with user-specific recommendations
        if hasattr(current_user, "preferences"):
            user_recs = generate_user_recommendations(
                current_user.preferences, request.query
            )
            recommendations["user_specific"] = user_recs

        return {
            "query": request.query,
            "recommendations": recommendations,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get workflow recommendations: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/benchmark")
async def run_agent_benchmark(
    request: AgentBenchmarkRequest, current_user: User = Depends(get_current_user)
):
    """
    Run comprehensive benchmarking of agent performance.

    Tests:
    - Different workflow types
    - Query complexity variations
    - Agent collaboration effectiveness
    - Performance under load
    """
    try:
        logger.info(f"Starting benchmark for {len(request.queries)} queries")

        # Initialize benchmark results
        benchmark_results = {
            "test_id": f"benchmark_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "user_id": str(current_user.id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "num_queries": len(request.queries),
                "workflow_types": [w.value for w in request.workflow_types],
                "iterations": request.iterations,
                "parallel": request.parallel,
            },
            "results": {},
        }

        # Run benchmarks
        if request.parallel:
            # Run all tests in parallel
            tasks = [
                run_single_benchmark(query, workflow_type, request.iterations)
                for query in request.queries
                for workflow_type in request.workflow_types
            ]
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process parallel results
            from src.core.async_utils import reraise_if_cancelled

            for i, result in enumerate(parallel_results):
                reraise_if_cancelled(result)
                query_idx = i // len(request.workflow_types)
                workflow_idx = i % len(request.workflow_types)
                query = request.queries[query_idx]
                workflow = request.workflow_types[workflow_idx]

                if isinstance(result, Exception):
                    logger.error(
                        f"Benchmark error for {query} with {workflow.value}: {result}"
                    )
                    benchmark_results["results"][f"{query}_{workflow.value}"] = {
                        "error": str(result),
                        "status": "failed",
                    }
                else:
                    benchmark_results["results"][f"{query}_{workflow.value}"] = result

        else:
            # Run benchmarks sequentially
            for query in request.queries:
                for workflow_type in request.workflow_types:
                    result = await run_single_benchmark(
                        query, workflow_type, request.iterations
                    )
                    benchmark_results["results"][
                        f"{query}_{workflow_type.value}"
                    ] = result

        # Calculate summary statistics
        benchmark_results["summary"] = calculate_benchmark_summary(
            benchmark_results["results"]
        )

        # Log benchmark completion
        logger.info(
            f"Benchmark completed in {benchmark_results['summary'].get('total_time', 0):.2f}s"
        )

        return benchmark_results

    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/performance-report")
async def get_performance_report(
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed performance report for agents.

    Includes:
    - Execution statistics
    - Success rates
    - Performance trends
    - Error analysis
    """
    try:
        # Get base performance report
        report = multi_agent_search_service_v2.get_agent_performance_report()

        # Filter by agent type if specified
        if agent_type:
            if agent_type in report["agent_metrics"]:
                report["agent_metrics"] = {
                    agent_type: report["agent_metrics"][agent_type]
                }
            else:
                raise HTTPException(
                    status_code=404, detail=f"Agent type '{agent_type}' not found"
                )

        # Add historical trends if available
        report["trends"] = calculate_performance_trends(report["agent_metrics"], days)

        # Add optimization suggestions
        report["optimizations"] = generate_optimization_suggestions(
            report["agent_metrics"]
        )

        return {
            "report": report,
            "filters": {"agent_type": agent_type, "days_analyzed": days},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get performance report: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post("/reset-metrics")
async def reset_performance_metrics(
    confirm: bool = Query(..., description="Confirmation to reset metrics"),
    current_user: User = Depends(get_current_user),
):
    """
    Reset agent performance metrics.
    Requires admin privileges.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403, detail="Admin privileges required to reset metrics"
        )

    if not confirm:
        raise HTTPException(
            status_code=400, detail="Must confirm reset with 'confirm=true'"
        )

    try:
        # Reset all agent metrics
        for agent_type in AgentType:
            multi_agent_search_service_v2.agent_metrics[agent_type] = {
                "total_executions": 0,
                "successful_executions": 0,
                "average_execution_time": 0.0,
                "confidence_score": 0.0,
                "last_execution": None,
                "error_count": 0,
                "token_usage": 0,
            }

        # Clear query history
        multi_agent_search_service_v2.query_history.clear()

        logger.info(f"Performance metrics reset by admin user {current_user.id}")

        return {
            "message": "Performance metrics reset successfully",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reset_by": str(current_user.id),
        }

    except Exception as e:
        logger.error(f"Failed to reset metrics: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/query-history")
async def get_query_history(
    limit: int = Query(50, ge=1, le=500, description="Number of recent queries"),
    current_user: User = Depends(get_current_user),
):
    """
    Get recent query history for the user.
    Used for analytics and learning.
    """
    try:
        # Get user's query history
        history = multi_agent_search_service_v2.query_history[-limit:]

        # Format for response
        formatted_history = []
        for entry in history:
            formatted_entry = {
                "query": entry["query"],
                "timestamp": entry["timestamp"].isoformat(),
                "execution_time": entry["execution_time"],
                "success_rate": entry["success_rate"],
                "workflow_type": entry["analysis"].get("workflow_type", {}).value
                if isinstance(entry["analysis"].get("workflow_type"), WorkflowType)
                else "unknown",
            }
            formatted_history.append(formatted_entry)

        return {
            "history": formatted_history,
            "total_queries": len(formatted_history),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get query history: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


# Helper Functions
async def run_single_benchmark(
    query: str, workflow_type: WorkflowType, iterations: int
) -> Dict[str, Any]:
    """Run benchmark for a single query and workflow type"""
    results = {
        "query": query,
        "workflow_type": workflow_type.value,
        "iterations": [],
        "statistics": {},
    }

    total_time = 0
    successful_runs = 0
    total_confidence = 0

    for i in range(iterations):
        start_time = datetime.now(timezone.utc)

        try:
            result = await multi_agent_search_service_v2.orchestrate_search(
                query=query,
                user_id="benchmark_user",
                organization_id="benchmark_org",
                workflow_type=workflow_type,
                max_agents=4,
                timeout=60.0,
                enable_learning=False,  # Disable learning for benchmarks
            )

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            iteration_result = {
                "iteration": i + 1,
                "success": True,
                "execution_time": execution_time,
                "confidence_score": result.confidence_score,
                "agents_used": len(result.agent_executions),
                "collaboration_score": result.metadata.get("collaboration_score", 0),
            }

            results["iterations"].append(iteration_result)
            total_time += execution_time
            successful_runs += 1
            total_confidence += result.confidence_score

        except Exception as e:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            results["iterations"].append(
                {
                    "iteration": i + 1,
                    "success": False,
                    "execution_time": execution_time,
                    "error": str(e),
                }
            )

    # Calculate statistics
    if successful_runs > 0:
        results["statistics"] = {
            "success_rate": successful_runs / iterations,
            "avg_execution_time": total_time / successful_runs,
            "avg_confidence_score": total_confidence / successful_runs,
            "min_time": min(
                r["execution_time"] for r in results["iterations"] if r.get("success")
            ),
            "max_time": max(
                r["execution_time"] for r in results["iterations"] if r.get("success")
            ),
            "std_dev_time": calculate_std_dev(
                [r["execution_time"] for r in results["iterations"] if r.get("success")]
            ),
        }
    else:
        results["statistics"] = {
            "success_rate": 0,
            "avg_execution_time": 0,
            "avg_confidence_score": 0,
            "errors": [r.get("error", "Unknown error") for r in results["iterations"]],
        }

    return results


def calculate_benchmark_summary(results: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate summary statistics from benchmark results"""
    summary = {
        "total_tests": len(results),
        "successful_tests": 0,
        "failed_tests": 0,
        "total_time": 0,
        "avg_confidence": 0,
        "workflow_performance": {},
        "top_performers": {},
        "improvement_areas": [],
    }

    workflow_stats = {}
    total_confidence_sum = 0
    confidence_count = 0

    for test_name, test_result in results.items():
        if isinstance(test_result, dict) and "statistics" in test_result:
            stats = test_result["statistics"]
            workflow_type = test_result.get("workflow_type", "unknown")

            # Track workflow performance
            if workflow_type not in workflow_stats:
                workflow_stats[workflow_type] = {
                    "total_time": 0,
                    "success_count": 0,
                    "confidence_sum": 0,
                    "count": 0,
                }

            if stats.get("success_rate", 0) > 0:
                summary["successful_tests"] += 1
                workflow_stats[workflow_type]["success_count"] += 1
                workflow_stats[workflow_type]["total_time"] += stats.get(
                    "avg_execution_time", 0
                )

                if "avg_confidence_score" in stats:
                    total_confidence_sum += stats["avg_confidence_score"]
                    confidence_count += 1
                    workflow_stats[workflow_type]["confidence_sum"] += stats[
                        "avg_confidence_score"
                    ]
            else:
                summary["failed_tests"] += 1

            workflow_stats[workflow_type]["count"] += 1

    # Calculate workflow averages
    for workflow_type, stats in workflow_stats.items():
        if stats["count"] > 0:
            summary["workflow_performance"][workflow_type] = {
                "success_rate": stats["success_count"] / stats["count"],
                "avg_time": stats["total_time"] / max(stats["success_count"], 1),
                "avg_confidence": stats["confidence_sum"]
                / max(stats["success_count"], 1),
            }

    # Calculate overall averages
    if confidence_count > 0:
        summary["avg_confidence"] = total_confidence_sum / confidence_count

    # Identify top performers and improvement areas
    if summary["workflow_performance"]:
        # Find best performing workflow
        best_workflow = max(
            summary["workflow_performance"].items(),
            key=lambda x: x[1]["avg_confidence"],
        )
        summary["top_performers"]["best_confidence"] = {
            "workflow": best_workflow[0],
            "score": best_workflow[1]["avg_confidence"],
        }

        # Find fastest workflow
        fastest_workflow = min(
            summary["workflow_performance"].items(), key=lambda x: x[1]["avg_time"]
        )
        summary["top_performers"]["fastest"] = {
            "workflow": fastest_workflow[0],
            "time": fastest_workflow[1]["avg_time"],
        }

        # Identify workflows needing improvement
        for workflow, perf in summary["workflow_performance"].items():
            if perf["success_rate"] < 0.8:
                summary["improvement_areas"].append(
                    {
                        "workflow": workflow,
                        "issue": "low_success_rate",
                        "value": perf["success_rate"],
                    }
                )
            if perf["avg_time"] > 60:  # Slower than 1 minute
                summary["improvement_areas"].append(
                    {
                        "workflow": workflow,
                        "issue": "slow_execution",
                        "value": perf["avg_time"],
                    }
                )

    return summary


def check_memory_status() -> Dict[str, Any]:
    """Check memory usage status"""
    import sys

    import psutil

    process = psutil.Process()
    memory_info = process.memory_info()

    return {
        "rss_mb": memory_info.rss / 1024 / 1024,
        "vms_mb": memory_info.vms / 1024 / 1024,
        "percent": process.memory_percent(),
        "status": "healthy" if process.memory_percent() < 80 else "warning",
    }


def check_cache_status() -> Dict[str, Any]:
    """Check cache status"""
    search_tool = multi_agent_search_service_v2.agent_tools.get("search")
    kg_tool = multi_agent_search_service_v2.agent_tools.get("knowledge_graph")

    cache_info = {}

    if search_tool and hasattr(search_tool, "_cache"):
        cache_info["search_cache_size"] = len(search_tool._cache)
        cache_info["search_cache_status"] = "active"

    if kg_tool and hasattr(kg_tool, "_cache"):
        cache_info["kg_cache_size"] = len(kg_tool._cache)
        cache_info["kg_cache_status"] = "active"

    return cache_info or {"status": "no_active_caches"}


def calculate_health_score(health_checks: Dict[str, Any]) -> float:
    """Calculate overall health score from health checks"""
    score = 0.0
    weight_sum = 0.0

    weights = {
        "crewai_available": 0.3,
        "agents_configured": 0.2,
        "memory_status": 0.2,
        "cache_status": 0.3,
    }

    for check, value in health_checks.items():
        if check in weights:
            if isinstance(value, bool):
                check_score = 1.0 if value else 0.0
            elif isinstance(value, dict) and "status" in value:
                check_score = 1.0 if value["status"] == "healthy" else 0.5
            else:
                check_score = 0.5  # Neutral score

            score += check_score * weights[check]
            weight_sum += weights[check]

    return score / weight_sum if weight_sum > 0 else 0.0


def calculate_std_dev(values: List[float]) -> float:
    """Calculate standard deviation of values"""
    if len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance**0.5


def calculate_performance_trends(metrics: Dict[str, Any], days: int) -> Dict[str, Any]:
    """Calculate performance trends over time"""
    # This would integrate with time-series data storage
    # For now, return placeholder
    return {
        "trend_period_days": days,
        "note": "Historical trend analysis requires time-series database integration",
    }


def generate_optimization_suggestions(metrics: Dict[str, Any]) -> List[str]:
    """Generate optimization suggestions based on metrics"""
    suggestions = []

    for agent_type, agent_metrics in metrics.items():
        if agent_metrics["success_rate"] < 0.8:
            suggestions.append(
                f"Consider reviewing {agent_type} agent configuration - success rate is {agent_metrics['success_rate']:.1%}"
            )

        if agent_metrics["average_execution_time"] > 60:
            suggestions.append(
                f"{agent_type} agent is taking {agent_metrics['average_execution_time']:.1f}s on average - consider optimization"
            )

        if agent_metrics["error_rate"] > 0.2:
            suggestions.append(
                f"{agent_type} agent has high error rate ({agent_metrics['error_rate']:.1%}) - investigate failure patterns"
            )

    return suggestions or ["All agents are performing within acceptable parameters"]


def generate_user_recommendations(
    user_preferences: Dict[str, Any], query: str
) -> Dict[str, Any]:
    """Generate user-specific recommendations"""
    recommendations = {
        "workflow_adjustments": [],
        "agent_preferences": [],
        "optimization_tips": [],
    }

    # Based on user preferences
    if user_preferences.get("prefers_speed", False):
        recommendations["workflow_adjustments"].append(
            "Consider using FACTUAL_LOOKUP workflow for faster responses"
        )
        recommendations["agent_preferences"].append(
            "Limit to 3 agents for better performance"
        )

    if user_preferences.get("prefers_comprehensive", False):
        recommendations["workflow_adjustments"].append(
            "Use REASONING workflow for detailed analysis"
        )
        recommendations["agent_preferences"].append("Enable all available agents")

    # Based on query length
    if len(query.split()) > 15:
        recommendations["optimization_tips"].append(
            "Consider breaking down complex queries"
        )

    return recommendations


async def log_search_analytics(
    user_id: str,
    query: str,
    execution_time: float,
    confidence_score: float,
    num_agents: int,
):
    """Log search analytics in background"""
    # This would integrate with analytics service
    logger.info(
        f"Analytics logged: user={user_id}, query='{query}', time={execution_time:.2f}s, confidence={confidence_score:.2f}, agents={num_agents}"
    )
