"""
Quality Improvement Recommendations API endpoints
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.user import User
from src.schemas.quality_metrics import RecommendationItem
from src.services.quality.quality_recommendations_service import (
    QualityInsight,
    QualityRecommendation,
    RecommendationCategory,
    RecommendationPriority,
    RecommendationStatus,
    quality_recommendations_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/recommendations")
async def get_quality_recommendations(
    categories: Optional[List[str]] = Query(
        None, description="Filter by recommendation categories"
    ),
    priority: Optional[str] = Query(
        None,
        regex="^(critical|high|medium|low)$",
        description="Filter by priority level",
    ),
    status: Optional[str] = Query(
        None,
        regex="^(pending|in_progress|completed|rejected|deferred)$",
        description="Filter by status",
    ),
    days_back: int = Query(30, ge=1, le=365, description="Days of history to analyze"),
    limit: int = Query(
        50, ge=1, le=200, description="Maximum recommendations to return"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get quality improvement recommendations"""
    try:
        # Convert string parameters to enums
        focus_areas = None
        if categories:
            focus_areas = [
                RecommendationCategory(cat)
                for cat in categories
                if cat in [c.value for c in RecommendationCategory]
            ]

        priority_filter = None
        if priority:
            priority_filter = RecommendationPriority(priority)

        # Generate recommendations
        recommendations = (
            await quality_recommendations_service.generate_recommendations(
                organization_id=str(current_user.organization_id),
                focus_areas=focus_areas,
                priority_filter=priority_filter,
                days_back=days_back,
            )
        )

        # Filter by status if specified
        if status:
            recommendations = [r for r in recommendations if r.status.value == status]

        # Apply limit
        recommendations = recommendations[:limit]

        # Convert to response format
        response_recommendations = []
        for rec in recommendations:
            response_recommendations.append(
                {
                    "id": rec.id,
                    "category": rec.category.value,
                    "priority": rec.priority.value,
                    "title": rec.title,
                    "description": rec.description,
                    "impact_assessment": rec.impact_assessment,
                    "effort_required": rec.effort_required,
                    "actionable_steps": rec.actionable_steps,
                    "expected_outcome": rec.expected_outcome,
                    "metrics_to_track": rec.metrics_to_track,
                    "supporting_data": rec.supporting_data,
                    "estimated_improvement": rec.estimated_improvement,
                    "due_date": rec.due_date.isoformat() if rec.due_date else None,
                    "status": rec.status.value,
                    "assigned_to": rec.assigned_to,
                    "created_at": rec.created_at.isoformat()
                    if rec.created_at
                    else None,
                    "updated_at": rec.updated_at.isoformat()
                    if rec.updated_at
                    else None,
                }
            )

        return {
            "recommendations": response_recommendations,
            "total_count": len(response_recommendations),
            "filters": {
                "categories": categories,
                "priority": priority,
                "status": status,
                "days_back": days_back,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get quality recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights")
async def get_quality_insights(
    days_back: int = Query(30, ge=1, le=365, description="Days of history to analyze"),
    current_user: User = Depends(get_current_user),
):
    """Get quality metrics insights"""
    try:
        insights = await quality_recommendations_service.analyze_quality_insights(
            organization_id=str(current_user.organization_id), days_back=days_back
        )

        # Convert to response format
        response_insights = []
        for insight in insights:
            response_insights.append(
                {
                    "metric_name": insight.metric_name,
                    "current_value": insight.current_value,
                    "target_value": insight.target_value,
                    "gap": insight.gap,
                    "trend": insight.trend,
                    "impact_area": insight.impact_area,
                    "root_causes": insight.root_causes,
                    "related_metrics": insight.related_metrics,
                    "supporting_data": insight.supporting_data,
                }
            )

        return {
            "insights": response_insights,
            "total_count": len(response_insights),
            "period_days": days_back,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get quality insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendations/{recommendation_id}/progress")
async def update_recommendation_progress(
    recommendation_id: str,
    progress_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """Update recommendation implementation progress"""
    try:
        status = RecommendationStatus(progress_data.get("status", "pending"))
        notes = progress_data.get("notes")
        actual_improvement = progress_data.get("actual_improvement")

        success = await quality_recommendations_service.track_recommendation_progress(
            recommendation_id=recommendation_id,
            status=status,
            notes=notes,
            actual_improvement=actual_improvement,
        )

        if success:
            return {
                "recommendation_id": recommendation_id,
                "status": status.value,
                "updated_at": datetime.utcnow().isoformat(),
                "notes": notes,
                "actual_improvement": actual_improvement,
            }
        else:
            raise HTTPException(
                status_code=400, detail="Failed to update recommendation progress"
            )

    except Exception as e:
        logger.error(f"Failed to update recommendation progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/effectiveness")
async def get_recommendation_effectiveness(
    completed_days: int = Query(
        30, ge=1, le=365, description="Days to analyze for effectiveness"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get effectiveness analysis of implemented recommendations"""
    try:
        effectiveness = (
            await quality_recommendations_service.get_recommendation_effectiveness(
                organization_id=str(current_user.organization_id),
                completed_days=completed_days,
            )
        )

        return {
            "organization_id": effectiveness["organization_id"],
            "period_days": completed_days,
            "effectiveness": effectiveness["effectiveness"],
            "overall_improvement": effectiveness["overall_improvement"],
            "analyzed_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get recommendation effectiveness: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_recommendations_summary(
    days_back: int = Query(30, ge=1, le=365, description="Days of history to analyze"),
    current_user: User = Depends(get_current_user),
):
    """Get summary of quality recommendations by category and priority"""
    try:
        # Get all recommendations
        recommendations = (
            await quality_recommendations_service.generate_recommendations(
                organization_id=str(current_user.organization_id), days_back=days_back
            )
        )

        # Group by category and priority
        summary = {
            "by_category": {},
            "by_priority": {},
            "by_status": {},
            "total_count": len(recommendations),
            "estimated_total_improvement": sum(
                r.estimated_improvement for r in recommendations
            ),
        }

        # Group by category
        for rec in recommendations:
            category = rec.category.value
            if category not in summary["by_category"]:
                summary["by_category"][category] = {
                    "count": 0,
                    "total_estimated_improvement": 0,
                    "priorities": {},
                }

            summary["by_category"][category]["count"] += 1
            summary["by_category"][category][
                "total_estimated_improvement"
            ] += rec.estimated_improvement

            priority = rec.priority.value
            if priority not in summary["by_category"][category]["priorities"]:
                summary["by_category"][category]["priorities"][priority] = 0
            summary["by_category"][category]["priorities"][priority] += 1

        # Group by priority
        for rec in recommendations:
            priority = rec.priority.value
            if priority not in summary["by_priority"]:
                summary["by_priority"][priority] = {
                    "count": 0,
                    "avg_estimated_improvement": 0,
                }

            summary["by_priority"][priority]["count"] += 1

        # Calculate average improvement by priority
        for priority in summary["by_priority"]:
            priority_recs = [r for r in recommendations if r.priority.value == priority]
            if priority_recs:
                avg_improvement = sum(
                    r.estimated_improvement for r in priority_recs
                ) / len(priority_recs)
                summary["by_priority"][priority][
                    "avg_estimated_improvement"
                ] = avg_improvement

        # Group by status
        for rec in recommendations:
            status = rec.status.value
            if status not in summary["by_status"]:
                summary["by_status"][status] = 0
            summary["by_status"][status] += 1

        return {
            **summary,
            "period_days": days_back,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get recommendations summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_recommendation_categories(current_user: User = Depends(get_current_user)):
    """Get available recommendation categories with descriptions"""
    try:
        categories = [
            {
                "category": RecommendationCategory.CONTENT.value,
                "description": "Document content and metadata improvements",
                "examples": [
                    "Improve document quality and relevance",
                    "Update outdated content",
                    "Enhance document metadata",
                ],
                "typical_improvement": "15-30%",
            },
            {
                "category": RecommendationCategory.SEARCH_ALGORITHM.value,
                "description": "Search algorithm and ranking improvements",
                "examples": [
                    "Optimize ranking parameters",
                    "Implement semantic search",
                    "Add relevance feedback",
                ],
                "typical_improvement": "10-25%",
            },
            {
                "category": RecommendationCategory.INDEXING.value,
                "description": "Search index optimization and performance",
                "examples": [
                    "Optimize index mappings",
                    "Improve query performance",
                    "Add result caching",
                ],
                "typical_improvement": "20-40%",
            },
            {
                "category": RecommendationCategory.USER_EXPERIENCE.value,
                "description": "User interface and experience improvements",
                "examples": [
                    "Add search suggestions",
                    "Improve result presentation",
                    "Enhance filtering options",
                ],
                "typical_improvement": "10-20%",
            },
            {
                "category": RecommendationCategory.INFRASTRUCTURE.value,
                "description": "System infrastructure and scaling improvements",
                "examples": [
                    "Scale system resources",
                    "Optimize resource usage",
                    "Improve reliability",
                ],
                "typical_improvement": "25-50%",
            },
            {
                "category": RecommendationCategory.MONITORING.value,
                "description": "Monitoring and alerting improvements",
                "examples": [
                    "Add better metrics",
                    "Improve alert management",
                    "Enhance dashboards",
                ],
                "typical_improvement": "5-15%",
            },
        ]

        return {"categories": categories, "total_categories": len(categories)}

    except Exception as e:
        logger.error(f"Failed to get recommendation categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_quality_metrics_for_recommendations(
    days_back: int = Query(30, ge=1, le=365, description="Days of history to analyze"),
    current_user: User = Depends(get_current_user),
):
    """Get quality metrics data for generating recommendations"""
    try:
        # Get quality insights
        insights = await quality_recommendations_service.analyze_quality_insights(
            organization_id=str(current_user.organization_id), days_back=days_back
        )

        # Get performance metrics
        from src.services.quality.performance_dashboard_service import (
            MetricTimeRange,
            performance_dashboard_service,
        )

        performance = (
            await performance_dashboard_service.get_search_performance_metrics(
                organization_id=str(current_user.organization_id),
                time_range=MetricTimeRange.LAST_24H,
            )
        )

        # Get user behavior data
        from src.services.quality.user_behavior_service import (
            MetricTimeRange as BehaviorTimeRange,
        )
        from src.services.quality.user_behavior_service import user_behavior_service

        user_behavior = await user_behavior_service.get_behavior_trends(
            organization_id=str(current_user.organization_id),
            days_back=days_back,
            group_by="day",
        )

        return {
            "quality_insights": [
                {
                    "metric_name": insight.metric_name,
                    "current_value": insight.current_value,
                    "target_value": insight.target_value,
                    "gap": insight.gap,
                    "trend": insight.trend,
                }
                for insight in insights
            ],
            "search_performance": {
                "total_searches": performance.total_searches,
                "avg_response_time": performance.avg_response_time,
                "success_rate": performance.success_rate,
                "no_results_rate": performance.no_results_rate,
            },
            "user_behavior": {
                "active_users": len(
                    [
                        t
                        for t in user_behavior["engagement_trends"]
                        if t["active_users"] > 0
                    ]
                ),
                "search_volume": sum(
                    t["search_count"] for t in user_behavior["search_trends"]
                ),
                "avg_satisfaction": sum(
                    t["avg_satisfaction"]
                    for t in user_behavior["engagement_trends"]
                    if t["avg_satisfaction"]
                )
                / len(user_behavior["engagement_trends"])
                if user_behavior["engagement_trends"]
                else 0,
            },
            "period_days": days_back,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get quality metrics for recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_custom_recommendations(
    request_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Generate custom recommendations based on specific criteria"""
    try:
        focus_areas = request_data.get("focus_areas", [])
        priority_filter = request_data.get("priority_filter")
        days_back = request_data.get("days_back", 30)

        # Convert focus areas to enums
        if focus_areas:
            focus_areas = [
                RecommendationCategory(area)
                for area in focus_areas
                if area in [c.value for c in RecommendationCategory]
            ]

        if priority_filter:
            priority_filter = RecommendationPriority(priority_filter)

        # Generate recommendations
        recommendations = (
            await quality_recommendations_service.generate_recommendations(
                organization_id=str(current_user.organization_id),
                focus_areas=focus_areas,
                priority_filter=priority_filter,
                days_back=days_back,
            )
        )

        return {
            "recommendations": [
                {
                    "id": rec.id,
                    "category": rec.category.value,
                    "priority": rec.priority.value,
                    "title": rec.title,
                    "description": rec.description,
                    "estimated_improvement": rec.estimated_improvement,
                    "actionable_steps_count": len(rec.actionable_steps),
                    "due_date": rec.due_date.isoformat() if rec.due_date else None,
                }
                for rec in recommendations
            ],
            "total_count": len(recommendations),
            "request_criteria": request_data,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to generate custom recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def quality_recommendations_health():
    """Health check for quality recommendations service"""
    return {
        "status": "healthy",
        "service": "quality_recommendations",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "cache_ttl": quality_recommendations_service.cache_ttl,
        "cached_recommendations": len(
            quality_recommendations_service.recommendation_cache
        ),
        "cached_insights": len(quality_recommendations_service.insight_cache),
    }
