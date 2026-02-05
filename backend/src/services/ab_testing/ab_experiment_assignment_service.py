"""
A/B Testing Experiment Assignment Service
Provides real-time experiment assignment with high performance and reliability
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import redis.asyncio as redis
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import get_db
from src.models.ab_testing import (
    Experiment,
    ExperimentAssignment,
    ExperimentStatus,
    ExperimentType,
    QueryRouting,
    TrafficSplitType,
    Variant,
)
from src.models.search_schemas import SearchQuery
from src.models.user import User
from src.services.cache.analytics_cache import analytics_cache

logger = logging.getLogger(__name__)


class AssignmentStrategy(Enum):
    """Assignment strategies for experiments"""

    CONSISTENT_HASH = "consistent_hash"  # Consistent user assignment
    RANDOM = "random"  # Pure random assignment
    WEIGHTED_RANDOM = "weighted_random"  # Weighted by traffic allocation
    BANDIT = "bandit"  # Multi-armed bandit optimization
    SESSION_BASED = "session_based"  # Session-based assignment


@dataclass
class AssignmentContext:
    """Context for experiment assignment"""

    user_id: str
    session_id: Optional[str]
    organization_id: str
    query_text: str
    query_features: Dict[str, Any]
    user_segments: List[str]
    device_info: Dict[str, Any]
    timestamp: datetime


@dataclass
class AssignmentResult:
    """Result of experiment assignment"""

    assigned: bool
    experiment_id: Optional[str]
    variant_id: Optional[str]
    variant_config: Optional[Dict[str, Any]]
    assignment_reason: str
    processing_time_ms: float
    cache_hit: bool = False


class ExperimentAssignmentService:
    """
    High-performance experiment assignment service with caching and resilience
    """

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._assignment_cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._circuit_breaker_timeout = 60  # seconds
        self._max_retries = 3
        self._bandit_state = {}  # For bandit algorithm state

    async def initialize(self):
        """Initialize Redis connection and background tasks"""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("Experiment assignment service initialized with Redis")
        except Exception as e:
            logger.warning(f"Redis not available for A/B testing: {e}")
            self.redis_client = None

    async def assign_experiment(
        self, context: AssignmentContext, search_query: SearchQuery, db: Session
    ) -> AssignmentResult:
        """
        Assign user to experiment variant with high performance
        """
        start_time = time.time()

        try:
            # Check cache first
            cache_key = self._get_cache_key(context)
            cached_result = await self._get_cached_assignment(cache_key)
            if cached_result:
                processing_time = (time.time() - start_time) * 1000
                return AssignmentResult(
                    assigned=True,
                    experiment_id=cached_result["experiment_id"],
                    variant_id=cached_result["variant_id"],
                    variant_config=cached_result["config"],
                    assignment_reason="cache_hit",
                    processing_time_ms=processing_time,
                    cache_hit=True,
                )

            # Find eligible experiments
            eligible_experiments = await self._find_eligible_experiments(
                context, search_query, db
            )

            if not eligible_experiments:
                return AssignmentResult(
                    assigned=False,
                    experiment_id=None,
                    variant_id=None,
                    variant_config=None,
                    assignment_reason="no_eligible_experiments",
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

            # Select experiment and variant
            experiment, variant = await self._select_experiment_and_variant(
                eligible_experiments, context, db
            )

            if not experiment or not variant:
                return AssignmentResult(
                    assigned=False,
                    experiment_id=None,
                    variant_id=None,
                    variant_config=None,
                    assignment_reason="selection_failed",
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

            # Create assignment
            await self._create_assignment(experiment.id, variant.id, context, db)

            # Cache the result
            assignment_data = {
                "experiment_id": str(experiment.id),
                "variant_id": str(variant.id),
                "config": variant.config,
                "assignment_time": datetime.now(timezone.utc).isoformat(),
            }
            await self._cache_assignment(cache_key, assignment_data)

            processing_time = (time.time() - start_time) * 1000

            return AssignmentResult(
                assigned=True,
                experiment_id=str(experiment.id),
                variant_id=str(variant.id),
                variant_config=variant.config,
                assignment_reason="new_assignment",
                processing_time_ms=processing_time,
                cache_hit=False,
            )

        except Exception as e:
            logger.error(f"Error in experiment assignment: {e}")
            return AssignmentResult(
                assigned=False,
                experiment_id=None,
                variant_id=None,
                variant_config=None,
                assignment_reason=f"error: {str(e)}",
                processing_time_ms=(time.time() - start_time) * 1000,
            )

    async def _find_eligible_experiments(
        self, context: AssignmentContext, search_query: SearchQuery, db: Session
    ) -> List[Experiment]:
        """Find experiments that user is eligible for"""
        try:
            # Base query for active experiments
            query = db.query(Experiment).filter(
                and_(
                    Experiment.organization_id == context.organization_id,
                    Experiment.status == ExperimentStatus.RUNNING,
                    Experiment.start_time <= datetime.now(timezone.utc),
                    Experiment.end_time >= datetime.now(timezone.utc),
                )
            )

            # Check experiment type compatibility
            compatible_types = self._get_compatible_experiment_types(search_query)
            query = query.filter(Experiment.experiment_type.in_(compatible_types))

            # Check traffic limits
            experiments = query.all()
            eligible_experiments = []

            for experiment in experiments:
                # Check if user already assigned
                existing_assignment = (
                    db.query(ExperimentAssignment)
                    .filter(
                        and_(
                            ExperimentAssignment.user_id == context.user_id,
                            ExperimentAssignment.experiment_id == experiment.id,
                        )
                    )
                    .first()
                )

                if existing_assignment:
                    continue  # Skip if already assigned

                # Check traffic percentage
                current_traffic = await self._get_current_traffic_percentage(
                    experiment, db
                )
                if current_traffic >= experiment.traffic_percentage:
                    continue  # Traffic limit reached

                # Check targeting criteria
                if not self._meets_targeting_criteria(
                    experiment, context, search_query
                ):
                    continue

                # Check user segments
                if not self._meets_segment_criteria(experiment, context):
                    continue

                eligible_experiments.append(experiment)

            return eligible_experiments

        except Exception as e:
            logger.error(f"Error finding eligible experiments: {e}")
            return []

    async def _select_experiment_and_variant(
        self, experiments: List[Experiment], context: AssignmentContext, db: Session
    ) -> Tuple[Optional[Experiment], Optional[Variant]]:
        """Select the best experiment and variant for this user"""
        if not experiments:
            return None, None

        try:
            # For now, select the first experiment (could implement prioritization)
            experiment = experiments[0]

            # Select variant based on traffic split strategy
            variant = await self._select_variant(experiment, context, db)

            return experiment, variant

        except Exception as e:
            logger.error(f"Error selecting experiment and variant: {e}")
            return None, None

    async def _select_variant(
        self, experiment: Experiment, context: AssignmentContext, db: Session
    ) -> Optional[Variant]:
        """Select variant based on experiment's traffic split strategy"""
        try:
            variants = [v for v in experiment.variants if not v.is_deleted]

            if not variants:
                return None

            if experiment.traffic_split_type == TrafficSplitType.UNIFORM:
                return self._select_uniform_variant(variants, context)
            elif experiment.traffic_split_type == TrafficSplitType.WEIGHTED:
                return self._select_weighted_variant(variants, context)
            elif experiment.traffic_split_type == TrafficSplitType.GRADUAL_ROLLOUT:
                return self._select_gradual_rollout_variant(
                    variants, experiment, context
                )
            elif experiment.traffic_split_type == TrafficSplitType.BANDIT:
                return self._select_bandit_variant(variants, experiment, context)
            else:
                # Default to uniform
                return self._select_uniform_variant(variants, context)

        except Exception as e:
            logger.error(f"Error selecting variant: {e}")
            return None

    def _select_uniform_variant(
        self, variants: List[Variant], context: AssignmentContext
    ) -> Optional[Variant]:
        """Uniform random variant selection"""
        # Use consistent hash for the same user
        hash_input = f"{context.user_id}_{context.session_id or 'no_session'}"
        hash_value = int(hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest(), 16)
        index = hash_value % len(variants)
        return variants[index]

    def _select_weighted_variant(
        self, variants: List[Variant], context: AssignmentContext
    ) -> Optional[Variant]:
        """Weighted random variant selection"""
        weights = [v.weight for v in variants]
        total_weight = sum(weights)

        if total_weight == 0:
            return variants[0]

        # Use consistent hash with weights
        hash_input = f"{context.user_id}_{context.session_id or 'no_session'}"
        hash_value = int(hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest(), 16)
        random_value = (hash_value % 1000) / 1000.0  # Normalize to [0, 1)

        cumulative_weight = 0
        for variant, weight in zip(variants, weights):
            cumulative_weight += weight / total_weight
            if random_value <= cumulative_weight:
                return variant

        return variants[-1]  # Fallback

    def _select_gradual_rollout_variant(
        self,
        variants: List[Variant],
        experiment: Experiment,
        context: AssignmentContext,
    ) -> Optional[Variant]:
        """Gradual rollout variant selection"""
        # Calculate rollout percentage based on experiment age
        elapsed_time = datetime.now(timezone.utc) - experiment.start_time
        total_duration = experiment.end_time - experiment.start_time
        rollout_percentage = min(
            elapsed_time.total_seconds() / total_duration.total_seconds(), 1.0
        )

        # Control variant gets more traffic early on
        control_variant = next((v for v in variants if v.is_control), variants[0])
        treatment_variants = [v for v in variants if not v.is_control]

        if np.random.random() > rollout_percentage:
            return control_variant
        else:
            if treatment_variants:
                return np.random.choice(treatment_variants)
            return control_variant

    def _select_bandit_variant(
        self,
        variants: List[Variant],
        experiment: Experiment,
        context: AssignmentContext,
    ) -> Optional[Variant]:
        """Multi-armed bandit variant selection using UCB1"""
        experiment_key = str(experiment.id)

        if experiment_key not in self._bandit_state:
            # Initialize bandit state
            self._bandit_state[experiment_key] = {
                "counts": {v.id: 0 for v in variants},
                "values": {v.id: 0.0 for v in variants},
                "total_pulls": 0,
            }

        state = self._bandit_state[experiment_key]
        total_pulls = state["total_pulls"]

        if total_pulls == 0:
            # Initialize with uniform random
            return np.random.choice(variants)

        # UCB1 algorithm
        ucb_values = []
        for variant in variants:
            if state["counts"][variant.id] == 0:
                ucb_values.append(float("inf"))
            else:
                average_reward = state["values"][variant.id]
                confidence = np.sqrt(
                    2 * np.log(total_pulls) / state["counts"][variant.id]
                )
                ucb_values.append(average_reward + confidence)

        # Select variant with highest UCB value
        best_index = np.argmax(ucb_values)
        selected_variant = variants[best_index]

        # Update state
        state["counts"][selected_variant.id] += 1
        state["total_pulls"] += 1

        return selected_variant

    def _get_compatible_experiment_types(
        self, search_query: SearchQuery
    ) -> List[ExperimentType]:
        """Get experiment types compatible with current search"""
        compatible_types = [
            ExperimentType.SEARCH_ALGORITHM,
            ExperimentType.RANKING_MODEL,
            ExperimentType.QUERY_PROCESSING,
            ExperimentType.MULTIMODAL_WEIGHTING,
        ]

        # Add specific compatibility logic
        if search_query.search_type.value == "hybrid":
            compatible_types.extend(
                [ExperimentType.FILTER_CONFIGURATION, ExperimentType.RESPONSE_FORMAT]
            )

        return compatible_types

    def _meets_targeting_criteria(
        self,
        experiment: Experiment,
        context: AssignmentContext,
        search_query: SearchQuery,
    ) -> bool:
        """Check if user meets experiment targeting criteria"""
        try:
            # Check user segments
            if experiment.target_user_segments:
                required_segments = set(experiment.target_user_segments)
                user_segments = set(context.user_segments)
                if not required_segments.intersection(user_segments):
                    return False

            # Check query patterns
            if experiment.target_query_patterns:
                query_text = search_query.query.lower()
                for pattern in experiment.target_query_patterns:
                    if pattern.lower() not in query_text:
                        return False

            # Check organization targeting
            if experiment.target_organization_ids:
                if context.organization_id not in experiment.target_organization_ids:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking targeting criteria: {e}")
            return False

    def _meets_segment_criteria(
        self, experiment: Experiment, context: AssignmentContext
    ) -> bool:
        """Check if user meets segment criteria"""
        # This would integrate with the user segmentation system
        # For now, assume all users are eligible
        return True

    async def _get_current_traffic_percentage(
        self, experiment: Experiment, db: Session
    ) -> float:
        """Get current traffic percentage for experiment"""
        try:
            # Count total assignments in the last hour
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            assignment_count = (
                db.query(ExperimentAssignment)
                .filter(
                    and_(
                        ExperimentAssignment.experiment_id == experiment.id,
                        ExperimentAssignment.assigned_at >= one_hour_ago,
                    )
                )
                .count()
            )

            # Estimate traffic percentage based on assignment count
            # This is a simplified calculation - in production, use actual query volume
            estimated_total_queries = 1000  # This should come from analytics
            traffic_percentage = (assignment_count / estimated_total_queries) * 100

            return min(traffic_percentage, experiment.traffic_percentage)

        except Exception as e:
            logger.error(f"Error calculating traffic percentage: {e}")
            return 0.0

    async def _create_assignment(
        self,
        experiment_id: str,
        variant_id: str,
        context: AssignmentContext,
        db: Session,
    ):
        """Create experiment assignment record"""
        try:
            assignment = ExperimentAssignment(
                user_id=context.user_id,
                session_id=context.session_id,
                experiment_id=experiment_id,
                variant_id=variant_id,
                user_segment=context.user_segments,
                query_context={
                    "query_text": context.query_text,
                    "query_features": context.query_features,
                },
                device_info=context.device_info,
            )

            db.add(assignment)

            # Update variant participant count
            variant = db.query(Variant).filter(Variant.id == variant_id).first()
            if variant:
                variant.participant_count += 1

            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"Error creating assignment: {e}")

    def _get_cache_key(self, context: AssignmentContext) -> str:
        """Generate cache key for assignment"""
        cache_data = {
            "user_id": context.user_id,
            "session_id": context.session_id,
            "organization_id": context.organization_id,
        }
        cache_string = json.dumps(cache_data, sort_keys=True)
        return f"ab_assignment:{hashlib.md5(cache_string.encode(), usedforsecurity=False).hexdigest()}"

    async def _get_cached_assignment(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached assignment"""
        try:
            if self.redis_client:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data)
            else:
                # Fallback to in-memory cache
                if cache_key in self._assignment_cache:
                    cached_entry = self._assignment_cache[cache_key]
                    if datetime.now(timezone.utc) - cached_entry[
                        "timestamp"
                    ] < timedelta(seconds=self._cache_ttl):
                        return cached_entry["data"]
                    else:
                        del self._assignment_cache[cache_key]
        except Exception as e:
            logger.error(f"Error getting cached assignment: {e}")
        return None

    async def _cache_assignment(self, cache_key: str, data: Dict[str, Any]):
        """Cache assignment result"""
        try:
            if self.redis_client:
                await self.redis_client.setex(
                    cache_key, self._cache_ttl, json.dumps(data)
                )
            else:
                # Fallback to in-memory cache
                self._assignment_cache[cache_key] = {
                    "data": data,
                    "timestamp": datetime.now(timezone.utc),
                }
        except Exception as e:
            logger.error(f"Error caching assignment: {e}")

    async def record_query_routing(
        self,
        query_id: str,
        assignment_result: AssignmentResult,
        context: AssignmentContext,
        db: Session,
    ):
        """Record query routing for analytics"""
        if not assignment_result.assigned:
            return

        try:
            routing = QueryRouting(
                query_id=query_id,
                user_id=context.user_id,
                session_id=context.session_id,
                experiment_id=assignment_result.experiment_id,
                variant_id=assignment_result.variant_id,
                routing_reason=assignment_result.assignment_reason,
                processing_overhead_ms=int(assignment_result.processing_time_ms),
            )

            db.add(routing)
            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"Error recording query routing: {e}")

    async def update_bandit_rewards(
        self, experiment_id: str, variant_id: str, reward: float
    ):
        """Update bandit algorithm with reward feedback"""
        try:
            experiment_key = str(experiment_id)
            if experiment_key in self._bandit_state:
                state = self._bandit_state[experiment_key]
                variant_key = variant_id

                # Update running average
                old_count = state["counts"][variant_key]
                old_value = state["values"][variant_key]

                state["values"][variant_key] = (old_value * old_count + reward) / (
                    old_count + 1
                )

        except Exception as e:
            logger.error(f"Error updating bandit rewards: {e}")

    async def cleanup_cache(self):
        """Clean up expired cache entries"""
        try:
            if not self.redis_client:
                # Clean up in-memory cache
                current_time = datetime.now(timezone.utc)
                expired_keys = [
                    key
                    for key, entry in self._assignment_cache.items()
                    if current_time - entry["timestamp"]
                    > timedelta(seconds=self._cache_ttl)
                ]
                for key in expired_keys:
                    del self._assignment_cache[key]

        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")


# Global service instance
experiment_assignment_service = ExperimentAssignmentService()


# Background task for cache cleanup
async def periodic_cache_cleanup():
    """Periodic cache cleanup task"""
    while True:
        try:
            await experiment_assignment_service.cleanup_cache()
            await asyncio.sleep(300)  # Run every 5 minutes
        except Exception as e:
            logger.error(f"Error in periodic cache cleanup: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute on error
