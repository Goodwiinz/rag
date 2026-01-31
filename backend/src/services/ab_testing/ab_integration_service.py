"""
A/B Testing Integration Service
Coordinates all A/B testing components and provides integration with existing RAG system
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.core.config import settings
from src.core.database import get_db
from src.models.ab_testing import Experiment, ExperimentAssignment, Variant
from src.models.search_schemas import SearchQuery, SearchResponse
from src.models.user import User
from src.services.ab_testing.ab_caching_service import cache_manager
from src.services.ab_testing.ab_event_service import (
    EventType,
    create_metric_collected_event,
    create_user_assigned_event,
    event_service,
)
from src.services.ab_testing.ab_experiment_assignment_service import (
    AssignmentContext,
    AssignmentResult,
    experiment_assignment_service,
)
from src.services.ab_testing.ab_metrics_collection_service import (
    MetricEvent,
    metrics_collection_service,
)
from src.services.ab_testing.ab_resilience_service import (
    resilience_service,
    with_resilience,
)
from src.services.ab_testing.ab_statistical_analysis_service import (
    statistical_analysis_service,
)

logger = logging.getLogger(__name__)


class ABTestingIntegrationService:
    """
    Main integration service that coordinates all A/B testing components
    and provides seamless integration with the existing RAG system
    """

    def __init__(self):
        self.initialized = False
        self.assignment_cache_ttl = 3600  # 1 hour
        self.metrics_batch_size = 100

    async def initialize(self):
        """Initialize all A/B testing components"""
        if self.initialized:
            return

        try:
            # Initialize all services
            await experiment_assignment_service.initialize()
            await metrics_collection_service.initialize()
            await cache_manager.initialize()
            await event_service.initialize()

            # Start event subscribers
            await event_service.start_all_subscribers()

            # Register event handlers
            self._register_event_handlers()

            self.initialized = True
            logger.info("A/B Testing integration service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize A/B testing integration: {e}")
            raise

    def _register_event_handlers(self):
        """Register event handlers for cross-service communication"""

        async def on_experiment_started(event):
            """Handle experiment started event"""
            experiment_id = event.data.get("experiment_id")
            logger.info(
                f"Experiment {experiment_id} started, invalidating relevant caches"
            )

            # Invalidate any cached assignments for this experiment
            await cache_manager.invalidate_experiment_cache(experiment_id)

        async def on_user_assigned(event):
            """Handle user assigned event"""
            experiment_id = event.data.get("experiment_id")
            variant_id = event.data.get("variant_id")
            user_id = event.data.get("user_id")

            logger.debug(
                f"User {user_id} assigned to variant {variant_id} in experiment {experiment_id}"
            )

            # Cache the assignment for quick lookup
            assignment_data = event.data.get("assignment_data", {})
            await cache_manager.set_variant_assignment(
                user_id=user_id, experiment_id=experiment_id, assignment=assignment_data
            )

        async def on_metric_collected(event):
            """Handle metric collected event"""
            experiment_id = event.data.get("experiment_id")
            metric_type = event.data.get("metric_type")

            logger.debug(
                f"Metric {metric_type} collected for experiment {experiment_id}"
            )

            # Invalidate cached metrics for this experiment
            await cache_manager.invalidate_experiment_cache(experiment_id)

        # Register handlers
        event_service.register_handler(
            EventType.EXPERIMENT_STARTED,
            on_experiment_started,
            service_name="integration_service",
        )

        event_service.register_handler(
            EventType.USER_ASSIGNED,
            on_user_assigned,
            service_name="integration_service",
        )

        event_service.register_handler(
            EventType.METRIC_COLLECTED,
            on_metric_collected,
            service_name="integration_service",
        )

    @with_resilience("experiment_assignment")
    async def process_search_query_with_ab_testing(
        self, search_query: SearchQuery, user: User, search_context: Dict[str, Any]
    ) -> Tuple[SearchQuery, Optional[Dict[str, Any]]]:
        """
        Process search query with A/B testing integration

        This method should be called before executing the search to determine
        if the user should be part of any A/B testing experiments.
        """
        if not self.initialized:
            await self.initialize()

        try:
            # Create assignment context
            context = AssignmentContext(
                user_id=str(user.id),
                session_id=search_context.get("session_id"),
                organization_id=str(user.organization_id),
                query_text=search_query.query,
                query_features={
                    "search_type": search_query.search_type.value,
                    "limit": search_query.limit,
                    "filters": search_query.filters or {},
                },
                user_segments=self._get_user_segments(user),
                device_info=search_context.get("device_info", {}),
                timestamp=datetime.utcnow(),
            )

            # Get experiment assignment
            assignment_result = await experiment_assignment_service.assign_experiment(
                context=context, search_query=search_query, db=next(get_db())
            )

            # Modify search query based on assignment
            modified_search_query = search_query
            experiment_config = None

            if assignment_result.assigned and assignment_result.variant_config:
                (
                    modified_search_query,
                    experiment_config,
                ) = self._apply_variant_configuration(
                    search_query, assignment_result.variant_config
                )

                # Publish assignment event
                await event_service.publish_event(
                    EventType.USER_ASSIGNED,
                    {
                        "experiment_id": assignment_result.experiment_id,
                        "variant_id": assignment_result.variant_id,
                        "user_id": str(user.id),
                        "assignment_data": {
                            "search_query": search_query.query,
                            "variant_config": assignment_result.variant_config,
                            "assignment_reason": assignment_result.assignment_reason,
                        },
                    },
                    source_service="integration_service",
                )

            return modified_search_query, experiment_config

        except Exception as e:
            logger.error(f"Error in A/B testing search processing: {e}")
            # Return original query without A/B testing modifications
            return search_query, None

    async def process_search_response_with_ab_testing(
        self,
        search_response: SearchResponse,
        original_query: SearchQuery,
        user: User,
        experiment_config: Optional[Dict[str, Any]],
        start_time: float,
        search_context: Dict[str, Any],
    ) -> SearchResponse:
        """
        Process search response with A/B testing metrics collection

        This method should be called after executing the search to collect
        metrics for any A/B testing experiments the user was part of.
        """
        if not self.initialized:
            await self.initialize()

        try:
            processing_time = (time.time() - start_time) * 1000

            # Collect metrics if user was in an experiment
            if experiment_config:
                await self._collect_search_metrics(
                    search_response=search_response,
                    experiment_config=experiment_config,
                    user=user,
                    processing_time=processing_time,
                    search_context=search_context,
                )

            return search_response

        except Exception as e:
            logger.error(f"Error collecting A/B testing metrics: {e}")
            # Return original response without failing the search
            return search_response

    async def _apply_variant_configuration(
        self, search_query: SearchQuery, variant_config: Dict[str, Any]
    ) -> Tuple[SearchQuery, Dict[str, Any]]:
        """Apply variant configuration to search query"""
        modified_query = search_query
        experiment_config = {
            "variant_id": variant_config.get("variant_id"),
            "experiment_id": variant_config.get("experiment_id"),
            "modifications": [],
        }

        # Apply different configurations based on experiment type
        if "search_config" in variant_config:
            search_config = variant_config["search_config"]

            # Modify search algorithm
            if "algorithm" in search_config:
                modified_query.search_type = search_config["algorithm"]
                experiment_config["modifications"].append(
                    {
                        "type": "algorithm",
                        "old_value": search_query.search_type.value,
                        "new_value": search_config["algorithm"],
                    }
                )

            # Modify search parameters
            if "parameters" in search_config:
                params = search_config["parameters"]

                if "limit" in params:
                    modified_query.limit = params["limit"]
                    experiment_config["modifications"].append(
                        {
                            "type": "limit",
                            "old_value": search_query.limit,
                            "new_value": params["limit"],
                        }
                    )

                if "filters" in params:
                    if modified_query.filters is None:
                        modified_query.filters = {}
                    modified_query.filters.update(params["filters"])
                    experiment_config["modifications"].append(
                        {"type": "filters", "added_filters": params["filters"]}
                    )

        # Apply ranking modifications
        if "ranking_weights" in variant_config:
            ranking_weights = variant_config["ranking_weights"]
            experiment_config["ranking_weights"] = ranking_weights
            experiment_config["modifications"].append(
                {"type": "ranking_weights", "weights": ranking_weights}
            )

        # Apply retrieval modifications
        if "retrieval_config" in variant_config:
            retrieval_config = variant_config["retrieval_config"]
            experiment_config["retrieval_config"] = retrieval_config
            experiment_config["modifications"].append(
                {"type": "retrieval_config", "config": retrieval_config}
            )

        return modified_query, experiment_config

    async def _collect_search_metrics(
        self,
        search_response: SearchResponse,
        experiment_config: Dict[str, Any],
        user: User,
        processing_time: float,
        search_context: Dict[str, Any],
    ):
        """Collect metrics for A/B testing analysis"""
        try:
            experiment_id = experiment_config.get("experiment_id")
            variant_id = experiment_config.get("variant_id")

            if not experiment_id or not variant_id:
                return

            # Collect search metrics
            await metrics_collection_service.collect_search_metrics(
                search_response=search_response,
                assignment_result=type(
                    "AssignmentResult",
                    (),
                    {
                        "assigned": True,
                        "experiment_id": experiment_id,
                        "variant_id": variant_id,
                    },
                )(),
                context={
                    "user_id": str(user.id),
                    "session_id": search_context.get("session_id"),
                    "query_text": search_context.get("query_text", ""),
                    "experiment_config": experiment_config,
                },
                start_time=time.time() - (processing_time / 1000),
                db=next(get_db()),
            )

            # Publish metric collection event
            await event_service.publish_event(
                EventType.METRIC_COLLECTED,
                {
                    "experiment_id": experiment_id,
                    "variant_id": variant_id,
                    "metric_type": "search_response_time",
                    "metric_value": processing_time,
                    "user_id": str(user.id),
                    "additional_metrics": {
                        "result_count": len(search_response.results),
                        "search_time_ms": search_response.search_time_ms,
                        "has_results": len(search_response.results) > 0,
                    },
                },
                source_service="integration_service",
            )

        except Exception as e:
            logger.error(f"Error collecting search metrics: {e}")

    def _get_user_segments(self, user: User) -> List[str]:
        """Get user segments for targeting"""
        segments = []

        # Add role-based segments
        if user.role:
            segments.append(f"role:{user.role.value}")

        # Add organization-based segments
        if user.organization_id:
            segments.append(f"organization:{user.organization_id}")

        # Add activity-based segments (could be enhanced with actual activity data)
        segments.append("active_user")  # Placeholder

        return segments

    async def create_experiment_from_template(
        self, template_name: str, parameters: Dict[str, Any], creator_user: User
    ) -> str:
        """
        Create experiment from predefined template

        Provides quick experiment creation for common use cases.
        """
        templates = {
            "search_algorithm_comparison": {
                "experiment_type": "search_algorithm",
                "primary_metric": "relevance_score",
                "variants": [
                    {
                        "name": "Control (Current)",
                        "is_control": True,
                        "config": {"search_config": {"algorithm": "hybrid"}},
                    },
                    {
                        "name": "Vector Only",
                        "is_control": False,
                        "config": {"search_config": {"algorithm": "vector"}},
                    },
                    {
                        "name": "Graph Enhanced",
                        "is_control": False,
                        "config": {
                            "search_config": {
                                "algorithm": "hybrid",
                                "graph_weight": 0.3,
                            }
                        },
                    },
                ],
            },
            "ranking_weights_test": {
                "experiment_type": "ranking_model",
                "primary_metric": "click_through_rate",
                "variants": [
                    {
                        "name": "Current Ranking",
                        "is_control": True,
                        "config": {
                            "ranking_weights": {
                                "relevance": 0.7,
                                "recency": 0.2,
                                "popularity": 0.1,
                            }
                        },
                    },
                    {
                        "name": "Recency Boosted",
                        "is_control": False,
                        "config": {
                            "ranking_weights": {
                                "relevance": 0.5,
                                "recency": 0.4,
                                "popularity": 0.1,
                            }
                        },
                    },
                ],
            },
        }

        if template_name not in templates:
            raise ValueError(f"Unknown template: {template_name}")

        template = templates[template_name]

        # Create experiment using template
        experiment_data = {
            "name": parameters.get("name", f"{template_name} Experiment"),
            "description": parameters.get(
                "description", f"Experiment based on {template_name} template"
            ),
            "hypothesis": parameters.get(
                "hypothesis", f"Testing {template_name} improvements"
            ),
            "experiment_type": template["experiment_type"],
            "primary_metric": template["primary_metric"],
            "target_improvement": parameters.get("target_improvement", 10.0),
            "traffic_percentage": parameters.get("traffic_percentage", 20.0),
            "minimum_sample_size": parameters.get("minimum_sample_size", 1000),
            "confidence_level": parameters.get("confidence_level", 0.95),
        }

        # This would create the experiment and variants using the existing API
        # For now, return a placeholder
        experiment_id = f"template_{template_name}_{int(time.time())}"

        await event_service.publish_event(
            EventType.EXPERIMENT_CREATED,
            {
                "experiment_id": experiment_id,
                "template_name": template_name,
                "parameters": parameters,
                "created_by": str(creator_user.id),
            },
            source_service="integration_service",
        )

        return experiment_id

    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive health status of A/B testing system"""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {},
        }

        try:
            # Check resilience service
            resilience_health = await resilience_service.health_check()
            health_status["components"]["resilience"] = resilience_health

            # Check cache manager
            cache_stats = cache_manager.get_performance_stats()
            health_status["components"]["cache"] = {
                "status": "healthy",
                "stats": cache_stats,
            }

            # Check event service
            event_stats = event_service.get_event_stats()
            health_status["components"]["events"] = {
                "status": "healthy",
                "stats": event_stats,
            }

            # Check active experiments count
            db = next(get_db())
            active_experiments = (
                db.query(Experiment).filter(Experiment.status == "running").count()
            )
            health_status["components"]["experiments"] = {
                "status": "healthy",
                "active_count": active_experiments,
            }

            # Determine overall status
            component_statuses = [
                component["status"]
                for component in health_status["components"].values()
            ]

            if "unhealthy" in component_statuses:
                health_status["status"] = "unhealthy"
            elif "degraded" in component_statuses:
                health_status["status"] = "degraded"

        except Exception as e:
            logger.error(f"Error getting A/B testing system health: {e}")
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)

        return health_status

    async def shutdown(self):
        """Graceful shutdown of all A/B testing components"""
        try:
            logger.info("Shutting down A/B testing integration service")

            # Stop event subscribers
            await event_service.stop_all_subscribers()

            # Shutdown metrics collection
            await metrics_collection_service.shutdown()

            logger.info("A/B testing integration service shutdown complete")

        except Exception as e:
            logger.error(f"Error during A/B testing shutdown: {e}")


# Global integration service instance
ab_integration_service = ABTestingIntegrationService()


# Decorator for automatic A/B testing integration


def with_ab_testing():
    """
    Decorator to automatically add A/B testing to search functions

    Usage:
    @with_ab_testing()
    async def search_function(search_query, user, **kwargs):
        # Original search logic
        return results
    """

    def decorator(search_func):
        async def wrapper(search_query: SearchQuery, user: User, **kwargs):
            if not ab_integration_service.initialized:
                await ab_integration_service.initialize()

            # Extract search context
            search_context = kwargs.get("context", {})
            start_time = time.time()

            try:
                # Process query with A/B testing
                (
                    modified_query,
                    experiment_config,
                ) = await ab_integration_service.process_search_query_with_ab_testing(
                    search_query=search_query, user=user, search_context=search_context
                )

                # Execute search with modified query
                search_response = await search_func(modified_query, user, **kwargs)

                # Process response with A/B testing
                processed_response = await ab_integration_service.process_search_response_with_ab_testing(
                    search_response=search_response,
                    original_query=search_query,
                    user=user,
                    experiment_config=experiment_config,
                    start_time=start_time,
                    search_context=search_context,
                )

                return processed_response

            except Exception as e:
                logger.error(f"Error in A/B testing integration: {e}")
                # Fallback to original search function
                return await search_func(search_query, user, **kwargs)

        return wrapper

    return decorator
