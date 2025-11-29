"""
A/B Testing Microservice Architecture

This module defines the microservice architecture for the A/B testing system,
including service boundaries, communication patterns, data flow, and integration
points with the existing RAG system components.
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
import logging

from fastapi import BackgroundTasks
from pydantic import BaseModel
import redis.asyncio as redis
import aiohttp
from aiohttp import ClientTimeout, ClientSession

from ..core.config import settings
from ..models.ab_testing import Experiment, Variant, ExperimentAssignment
from ..cache.cache_keys import get_ab_testing_cache_key


logger = logging.getLogger(__name__)


# ============================================================================
# SERVICE ENUMS AND CONFIGURATIONS
# ============================================================================

class ServiceType(str, Enum):
    """Types of microservices in the A/B testing system"""
    EXPERIMENT_MANAGER = "experiment_manager"
    QUERY_ROUTER = "query_router"
    METRICS_COLLECTOR = "metrics_collector"
    STATISTICAL_ANALYZER = "statistical_analyzer"
    SEGMENT_MANAGER = "segment_manager"
    EVENT_PROCESSOR = "event_processor"
    CACHE_SERVICE = "cache_service"
    NOTIFICATION_SERVICE = "notification_service"


class CommunicationPattern(str, Enum):
    """Communication patterns between services"""
    SYNC_REQUEST_RESPONSE = "sync_request_response"
    ASYNC_EVENT_DRIVEN = "async_event_driven"
    STREAMING = "streaming"
    BATCH_PROCESSING = "batch_processing"
    PUBLISH_SUBSCRIBE = "publish_subscribe"


class Priority(str, Enum):
    """Message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# SERVICE DISCOVERY AND REGISTRATION
# ============================================================================

@dataclass
class ServiceEndpoint:
    """Service endpoint configuration"""
    service_type: ServiceType
    service_id: str
    host: str
    port: int
    version: str = "1.0.0"
    health_check_path: str = "/health"
    protocol: str = "http"
    is_healthy: bool = True
    last_health_check: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def base_url(self) -> str:
        """Get base URL for the service"""
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def health_check_url(self) -> str:
        """Get health check URL for the service"""
        return f"{self.base_url}{self.health_check_path}"


class ServiceRegistry:
    """Service discovery and registration"""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.service_cache: Dict[str, ServiceEndpoint] = {}
        self.cache_ttl = 300  # 5 minutes

    async def register_service(self, endpoint: ServiceEndpoint):
        """Register a service endpoint"""
        key = f"service_registry:{endpoint.service_type}:{endpoint.service_id}"

        service_data = {
            "service_type": endpoint.service_type,
            "service_id": endpoint.service_id,
            "host": endpoint.host,
            "port": endpoint.port,
            "version": endpoint.version,
            "health_check_path": endpoint.health_check_path,
            "protocol": endpoint.protocol,
            "metadata": endpoint.metadata,
            "registered_at": datetime.now(timezone.utc).isoformat()
        }

        await self.redis_client.hset(key, mapping=service_data)
        await self.redis_client.expire(key, self.cache_ttl)

        # Add to service type index
        index_key = f"service_index:{endpoint.service_type}"
        await self.redis_client.sadd(index_key, endpoint.service_id)
        await self.redis_client.expire(index_key, self.cache_ttl)

        # Update local cache
        cache_key = f"{endpoint.service_type}:{endpoint.service_id}"
        self.service_cache[cache_key] = endpoint

        logger.info(f"Registered service: {endpoint.service_type}:{endpoint.service_id}")

    async def discover_services(self, service_type: ServiceType) -> List[ServiceEndpoint]:
        """Discover all services of a given type"""
        index_key = f"service_index:{service_type}"
        service_ids = await self.redis_client.smembers(index_key)

        endpoints = []
        for service_id in service_ids:
            endpoint = await self.get_service_endpoint(service_type, service_id)
            if endpoint and endpoint.is_healthy:
                endpoints.append(endpoint)

        return endpoints

    async def get_service_endpoint(self, service_type: ServiceType, service_id: str) -> Optional[ServiceEndpoint]:
        """Get specific service endpoint"""
        cache_key = f"{service_type}:{service_id}"

        # Check local cache first
        if cache_key in self.service_cache:
            endpoint = self.service_cache[cache_key]
            if endpoint.last_health_check is not None and \
               (datetime.now(timezone.utc) - endpoint.last_health_check).total_seconds() < self.cache_ttl:
                return endpoint

        # Fetch from Redis
        key = f"service_registry:{service_type}:{service_id}"
        service_data = await self.redis_client.hgetall(key)

        if not service_data:
            return None

        endpoint = ServiceEndpoint(
            service_type=ServiceType(service_data["service_type"]),
            service_id=service_data["service_id"],
            host=service_data["host"],
            port=int(service_data["port"]),
            version=service_data.get("version", "1.0.0"),
            health_check_path=service_data.get("health_check_path", "/health"),
            protocol=service_data.get("protocol", "http"),
            metadata=json.loads(service_data.get("metadata", "{}"))
        )

        # Update cache
        self.service_cache[cache_key] = endpoint

        return endpoint

    async def deregister_service(self, service_type: ServiceType, service_id: str):
        """Deregister a service"""
        key = f"service_registry:{service_type}:{service_id}"
        await self.redis_client.delete(key)

        index_key = f"service_index:{service_type}"
        await self.redis_client.srem(index_key, service_id)

        cache_key = f"{service_type}:{service_id}"
        if cache_key in self.service_cache:
            del self.service_cache[cache_key]

        logger.info(f"Deregistered service: {service_type}:{service_id}")


# ============================================================================
# MESSAGE BROKER AND EVENT SYSTEM
# ============================================================================

@dataclass
class EventMessage:
    """Event message for inter-service communication"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    service_type: ServiceType = ServiceType.EXPERIMENT_MANAGER
    source_service_id: str = ""
    target_service_type: Optional[ServiceType] = None
    target_service_id: Optional[str] = None

    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    priority: Priority = Priority.NORMAL
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None

    timestamp: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "service_type": self.service_type.value,
            "source_service_id": self.source_service_id,
            "target_service_type": self.target_service_type.value if self.target_service_type else None,
            "target_service_id": self.target_service_id,
            "payload": self.payload,
            "metadata": self.metadata,
            "priority": self.priority.value,
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EventMessage':
        """Create from dictionary"""
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            service_type=ServiceType(data["service_type"]),
            source_service_id=data["source_service_id"],
            target_service_type=ServiceType(data["target_service_type"]) if data.get("target_service_type") else None,
            target_service_id=data.get("target_service_id"),
            payload=data["payload"],
            metadata=data["metadata"],
            priority=Priority(data["priority"]),
            correlation_id=data.get("correlation_id"),
            reply_to=data.get("reply_to"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3)
        )


class MessageBroker:
    """Message broker for inter-service communication"""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.subscribers: Dict[str, List[Callable]] = {}
        self.running = False

    async def publish(self, event: EventMessage) -> bool:
        """Publish an event"""
        try:
            # Determine channel
            if event.target_service_type and event.target_service_id:
                # Direct message to specific service
                channel = f"events:{event.target_service_type.value}:{event.target_service_id}"
            elif event.target_service_type:
                # Broadcast to all services of type
                channel = f"events:{event.target_service_type.value}:*"
            else:
                # Global broadcast
                channel = "events:*"

            # Add to priority queue
            priority_queue = f"priority_queue:{event.priority.value}"
            await self.redis_client.lpush(priority_queue, json.dumps(event.to_dict()))

            # Publish notification
            await self.redis_client.publish(channel, event.event_id)

            logger.debug(f"Published event {event.event_id} to {channel}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            return False

    async def subscribe(self, service_type: ServiceType, service_id: str, handler: Callable):
        """Subscribe to events for a specific service"""
        channel_pattern = f"events:{service_type.value}:*"

        if channel_pattern not in self.subscribers:
            self.subscribers[channel_pattern] = []
            # Start listener for this pattern
            asyncio.create_task(self._listen_for_events(channel_pattern))

        self.subscribers[channel_pattern].append({
            "service_id": service_id,
            "handler": handler
        })

        logger.info(f"Subscribed service {service_id} to {channel_pattern}")

    async def _listen_for_events(self, channel_pattern: str):
        """Listen for events on a channel pattern"""
        pubsub = self.redis_client.pubsub()
        await pubsub.psubscribe(channel_pattern)

        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                event_id = message["data"].decode()
                await self._process_event(event_id, channel_pattern)

    async def _process_event(self, event_id: str, channel_pattern: str):
        """Process an event message"""
        try:
            # Find the event in priority queues
            for priority in Priority:
                queue_key = f"priority_queue:{priority.value}"
                event_data = await self._find_event_in_queue(queue_key, event_id)
                if event_data:
                    event = EventMessage.from_dict(event_data)
                    await self._handle_event(event, channel_pattern)
                    break

        except Exception as e:
            logger.error(f"Failed to process event {event_id}: {e}")

    async def _find_event_in_queue(self, queue_key: str, event_id: str) -> Optional[Dict[str, Any]]:
        """Find specific event in queue"""
        events = await self.redis_client.lrange(queue_key, 0, -1)
        for event_json in events:
            event_data = json.loads(event_json)
            if event_data["event_id"] == event_id:
                return event_data
        return None

    async def _handle_event(self, event: EventMessage, channel_pattern: str):
        """Handle an event for subscribers"""
        if channel_pattern in self.subscribers:
            for subscriber in self.subscribers[channel_pattern]:
                try:
                    await subscriber["handler"](event)
                except Exception as e:
                    logger.error(f"Handler failed for event {event.event_id}: {e}")


# ============================================================================
# ABSTRACT SERVICE BASE CLASS
# ============================================================================

class MicroService(ABC):
    """Base class for all microservices"""

    def __init__(
        self,
        service_type: ServiceType,
        service_id: str,
        redis_client: redis.Redis,
        host: str = "localhost",
        port: int = 8000
    ):
        self.service_type = service_type
        self.service_id = service_id
        self.redis_client = redis_client

        self.endpoint = ServiceEndpoint(
            service_type=service_type,
            service_id=service_id,
            host=host,
            port=port
        )

        self.service_registry = ServiceRegistry(redis_client)
        self.message_broker = MessageBroker(redis_client)

        self.http_session: Optional[ClientSession] = None
        self.is_running = False

    async def start(self):
        """Start the microservice"""
        if self.is_running:
            return

        # Create HTTP session
        timeout = ClientTimeout(total=30)
        self.http_session = ClientSession(timeout=timeout)

        # Register with service registry
        await self.service_registry.register_service(self.endpoint)

        # Subscribe to relevant events
        await self.setup_event_subscriptions()

        # Start service-specific logic
        await self.start_service()

        self.is_running = True
        logger.info(f"Started microservice: {self.service_type}:{self.service_id}")

    async def stop(self):
        """Stop the microservice"""
        if not self.is_running:
            return

        # Stop service-specific logic
        await self.stop_service()

        # Deregister from service registry
        await self.service_registry.deregister_service(self.service_type, self.service_id)

        # Close HTTP session
        if self.http_session:
            await self.http_session.close()

        self.is_running = False
        logger.info(f"Stopped microservice: {self.service_type}:{self.service_id}")

    @abstractmethod
    async def start_service(self):
        """Start service-specific logic"""
        pass

    @abstractmethod
    async def stop_service(self):
        """Stop service-specific logic"""
        pass

    @abstractmethod
    async def setup_event_subscriptions(self):
        """Setup event subscriptions for this service"""
        pass

    async def send_event(self, event: EventMessage) -> bool:
        """Send an event to another service"""
        event.source_service_id = self.service_id
        event.service_type = self.service_type
        return await self.message_broker.publish(event)

    async def call_service(
        self,
        target_service_type: ServiceType,
        endpoint: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """Make synchronous call to another service"""
        try:
            # Discover target service
            services = await self.service_registry.discover_services(target_service_type)
            if not services:
                raise Exception(f"No available services of type {target_service_type}")

            # Use first available service (load balancing could be added)
            target_service = services[0]
            url = f"{target_service.base_url}{endpoint}"

            # Make HTTP request
            async with self.http_session.request(
                method=method,
                url=url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Service call failed: {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Failed to call service {target_service_type}:{endpoint}: {e}")
            return None

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for this service"""
        return {
            "service_type": self.service_type.value,
            "service_id": self.service_id,
            "status": "healthy" if self.is_running else "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).seconds if hasattr(self, 'start_time') else 0
        }


# ============================================================================
# QUERY ROUTER SERVICE
# ============================================================================

class QueryRouterService(MicroService):
    """Service for real-time query routing and experiment assignment"""

    def __init__(self, redis_client: redis.Redis, service_id: str = None):
        service_id = service_id or f"query-router-{uuid.uuid4().hex[:8]}"
        super().__init__(ServiceType.QUERY_ROUTER, service_id, redis_client)
        self.assignment_cache = {}
        self.start_time = datetime.now(timezone.utc)

    async def start_service(self):
        """Start query router service"""
        # Load configuration
        await self.load_configuration()

        # Start assignment cache cleanup
        asyncio.create_task(self.cleanup_assignment_cache())

    async def stop_service(self):
        """Stop query router service"""
        pass

    async def setup_event_subscriptions(self):
        """Setup event subscriptions"""
        await self.message_broker.subscribe(
            ServiceType.EXPERIMENT_MANAGER,
            self.service_id,
            self.handle_experiment_events
        )

    async def handle_experiment_events(self, event: EventMessage):
        """Handle experiment-related events"""
        if event.event_type == "experiment_started":
            await self.invalidate_assignment_cache(event.payload.get("experiment_id"))
        elif event.event_type == "experiment_stopped":
            await self.invalidate_assignment_cache(event.payload.get("experiment_id"))
        elif event.event_type == "experiment_updated":
            await self.invalidate_assignment_cache(event.payload.get("experiment_id"))

    async def assign_variant(
        self,
        user_id: Optional[str],
        session_id: Optional[str],
        organization_id: str,
        query_context: Dict[str, Any]
    ) -> Optional[ExperimentAssignment]:
        """Assign user to experiment variant"""
        try:
            # Check cache first
            cache_key = f"assignment:{organization_id}:{user_id or session_id}"
            cached_assignment = await self.redis_client.get(cache_key)

            if cached_assignment:
                assignment_data = json.loads(cached_assignment)
                # Validate assignment is still valid
                if await self.is_assignment_valid(assignment_data):
                    return ExperimentAssignment(**assignment_data)

            # Get active experiments for organization
            active_experiments = await self.get_active_experiments(organization_id)

            if not active_experiments:
                return None

            # Find matching experiments
            matching_experiments = await self.filter_matching_experiments(
                active_experiments,
                user_id,
                session_id,
                query_context
            )

            if not matching_experiments:
                return None

            # Select experiment and assign variant
            selected_experiment = await self.select_experiment(matching_experiments)
            variant = await self.select_variant(selected_experiment, user_id, session_id)

            # Create assignment
            assignment = ExperimentAssignment(
                user_id=uuid.UUID(user_id) if user_id else None,
                session_id=session_id,
                experiment_id=selected_experiment.id,
                variant_id=variant.id,
                assignment_type="automatic"
            )

            # Cache assignment
            await self.cache_assignment(cache_key, assignment)

            # Send assignment event
            event = EventMessage(
                event_type="variant_assigned",
                target_service_type=ServiceType.METRICS_COLLECTOR,
                payload={
                    "assignment_id": str(assignment.id),
                    "experiment_id": str(selected_experiment.id),
                    "variant_id": str(variant.id),
                    "user_id": user_id,
                    "session_id": session_id
                }
            )
            await self.send_event(event)

            return assignment

        except Exception as e:
            logger.error(f"Failed to assign variant: {e}")
            return None

    async def get_active_experiments(self, organization_id: str) -> List[Experiment]:
        """Get active experiments for organization"""
        # This would query the experiment manager service
        experiments_data = await self.call_service(
            ServiceType.EXPERIMENT_MANAGER,
            f"/experiments/active?organization_id={organization_id}"
        )

        if experiments_data:
            return [Experiment(**exp_data) for exp_data in experiments_data]
        return []

    async def filter_matching_experiments(
        self,
        experiments: List[Experiment],
        user_id: Optional[str],
        session_id: Optional[str],
        query_context: Dict[str, Any]
    ) -> List[Experiment]:
        """Filter experiments that match user and query criteria"""
        matching_experiments = []

        for experiment in experiments:
            if await self.experiment_matches(experiment, user_id, session_id, query_context):
                matching_experiments.append(experiment)

        return matching_experiments

    async def experiment_matches(
        self,
        experiment: Experiment,
        user_id: Optional[str],
        session_id: Optional[str],
        query_context: Dict[str, Any]
    ) -> bool:
        """Check if experiment matches user and query criteria"""
        # Check user segment targeting
        if experiment.target_user_segments:
            user_segments = await self.get_user_segments(user_id, session_id)
            if not any(segment in user_segments for segment in experiment.target_user_segments):
                return False

        # Check query pattern targeting
        if experiment.target_query_patterns:
            query_text = query_context.get("query", "")
            if not any(pattern.lower() in query_text.lower() for pattern in experiment.target_query_patterns):
                return False

        return True

    async def select_variant(
        self,
        experiment: Experiment,
        user_id: Optional[str],
        session_id: Optional[str]
    ) -> Variant:
        """Select variant based on experiment configuration"""
        import random

        # Filter active variants
        active_variants = [variant for variant in experiment.variants if variant.is_deleted == False]

        if not active_variants:
            logger.error(f"No active variants found for experiment")
            return None

        # Calculate weights
        total_weight = sum(variant.weight for variant in active_variants)
        weights = [variant.weight / total_weight for variant in active_variants]

        # Weighted random selection
        selected_variant = random.choices(active_variants, weights=weights)[0]

        return selected_variant

    async def cache_assignment(self, cache_key: str, assignment: ExperimentAssignment):
        """Cache assignment for future use"""
        assignment_data = {
            "id": str(assignment.id),
            "user_id": str(assignment.user_id) if assignment.user_id else None,
            "session_id": assignment.session_id,
            "experiment_id": str(assignment.experiment_id),
            "variant_id": str(assignment.variant_id),
            "assignment_type": assignment.assignment_type,
            "assigned_at": assignment.assigned_at.isoformat()
        }

        # Cache for 1 hour
        await self.redis_client.setex(cache_key, 3600, json.dumps(assignment_data))

    async def is_assignment_valid(self, assignment_data: Dict[str, Any]) -> bool:
        """Check if cached assignment is still valid"""
        try:
            # Check if experiment is still active
            experiment_id = assignment_data["experiment_id"]
            experiment_status = await self.call_service(
                ServiceType.EXPERIMENT_MANAGER,
                f"/experiments/{experiment_id}/status"
            )

            return experiment_status and experiment_status.get("status") == "running"

        except Exception:
            return False

    async def invalidate_assignment_cache(self, experiment_id: str):
        """Invalidate cached assignments for an experiment"""
        # This would find and remove all cached assignments for the experiment
        # Implementation depends on cache structure
        pass

    async def cleanup_assignment_cache(self):
        """Periodic cleanup of expired assignments"""
        while self.is_running:
            try:
                # Find and remove expired cache entries
                # This is a simplified implementation
                await asyncio.sleep(300)  # Every 5 minutes
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")

    async def load_configuration(self):
        """Load service configuration"""
        # Load configuration from config service or database
        pass

    async def get_user_segments(self, user_id: Optional[str], session_id: Optional[str]) -> List[str]:
        """Get user segments for targeting"""
        # This would call the segment manager service
        return []


# ============================================================================
# METRICS COLLECTOR SERVICE
# ============================================================================

class MetricsCollectorService(MicroService):
    """Service for collecting and processing experiment metrics"""

    def __init__(self, redis_client: redis.Redis, service_id: str = None):
        service_id = service_id or f"metrics-collector-{uuid.uuid4().hex[:8]}"
        super().__init__(ServiceType.METRICS_COLLECTOR, service_id, redis_client)
        self.metrics_buffer = []
        self.buffer_size = 100
        self.start_time = datetime.now(timezone.utc)

    async def start_service(self):
        """Start metrics collector service"""
        # Start periodic batch processing
        asyncio.create_task(self.process_metrics_batch())

    async def stop_service(self):
        """Stop metrics collector service"""
        # Process remaining metrics
        if self.metrics_buffer:
            await self.flush_metrics()

    async def setup_event_subscriptions(self):
        """Setup event subscriptions"""
        await self.message_broker.subscribe(
            ServiceType.QUERY_ROUTER,
            self.service_id,
            self.handle_assignment_events
        )

    async def handle_assignment_events(self, event: EventMessage):
        """Handle assignment events"""
        if event.event_type == "variant_assigned":
            # Track assignment for user journey analysis
            await self.track_assignment(event.payload)

    async def collect_metric(self, metric_data: Dict[str, Any]):
        """Collect a metric event"""
        try:
            # Add to buffer
            self.metrics_buffer.append({
                "data": metric_data,
                "timestamp": datetime.now(timezone.utc),
                "processed": False
            })

            # Process immediately if buffer is full
            if len(self.metrics_buffer) >= self.buffer_size:
                await self.flush_metrics()

        except Exception as e:
            logger.error(f"Failed to collect metric: {e}")

    async def flush_metrics(self):
        """Flush metrics buffer to storage"""
        if not self.metrics_buffer:
            return

        try:
            # Batch process metrics
            batch_metrics = [m["data"] for m in self.metrics_buffer if not m["processed"]]

            # Send to storage service
            success = await self.store_metrics_batch(batch_metrics)

            if success:
                # Mark as processed
                for metric in self.metrics_buffer:
                    metric["processed"] = True

                # Clear processed metrics
                self.metrics_buffer = [m for m in self.metrics_buffer if not m["processed"]]

                logger.info(f"Processed batch of {len(batch_metrics)} metrics")

        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")

    async def process_metrics_batch(self):
        """Periodic batch processing of metrics"""
        while self.is_running:
            try:
                await self.flush_metrics()
                await asyncio.sleep(60)  # Process every minute
            except Exception as e:
                logger.error(f"Batch processing error: {e}")

    async def store_metrics_batch(self, metrics: List[Dict[str, Any]]) -> bool:
        """Store metrics to database"""
        try:
            # This would call the storage service or database directly
            # For now, we'll simulate storage
            await self.redis_client.lpush(
                "metrics_storage_queue",
                *[json.dumps(metric) for metric in metrics]
            )

            # Keep only last 10000 metrics in queue
            await self.redis_client.ltrim("metrics_storage_queue", 0, 9999)

            return True

        except Exception as e:
            logger.error(f"Failed to store metrics batch: {e}")
            return False

    async def track_assignment(self, assignment_data: Dict[str, Any]):
        """Track experiment assignment for analytics"""
        tracking_data = {
            "event_type": "experiment_assignment",
            "experiment_id": assignment_data["experiment_id"],
            "variant_id": assignment_data["variant_id"],
            "user_id": assignment_data.get("user_id"),
            "session_id": assignment_data.get("session_id"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        await self.collect_metric(tracking_data)


# ============================================================================
# SERVICE ORCHESTRATION
# ============================================================================

class ServiceOrchestrator:
    """Orchestrates the microservice ecosystem"""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.services: Dict[str, MicroService] = {}
        self.service_registry = ServiceRegistry(redis_client)
        self.message_broker = MessageBroker(redis_client)

    async def start_service(self, service: MicroService):
        """Start a single service"""
        await service.start()
        self.services[service.service_id] = service

    async def stop_service(self, service_id: str):
        """Stop a single service"""
        if service_id in self.services:
            await self.services[service_id].stop()
            del self.services[service_id]

    async def start_all_services(self):
        """Start all core services"""
        services = [
            QueryRouterService(self.redis_client),
            MetricsCollectorService(self.redis_client),
            # Additional services would be added here
        ]

        for service in services:
            await self.start_service(service)

    async def stop_all_services(self):
        """Stop all services"""
        for service_id in list(self.services.keys()):
            await self.stop_service(service_id)

    async def get_service_health(self) -> Dict[str, Any]:
        """Get health status of all services"""
        health_status = {}

        for service_id, service in self.services.items():
            health_status[service_id] = await service.health_check()

        return health_status

    async def restart_service(self, service_id: str):
        """Restart a service"""
        if service_id in self.services:
            service = self.services[service_id]
            await service.stop()
            await service.start()


# ============================================================================
# INITIALIZATION AND CONFIGURATION
# ============================================================================

async def initialize_ab_testing_microservices(redis_client: redis.Redis) -> ServiceOrchestrator:
    """Initialize the A/B testing microservice ecosystem"""
    orchestrator = ServiceOrchestrator(redis_client)

    # Start core services
    await orchestrator.start_all_services()

    logger.info("A/B Testing microservices initialized")

    return orchestrator


def create_service_config(service_type: ServiceType) -> Dict[str, Any]:
    """Create configuration for a service type"""
    base_config = {
        "redis_url": settings.REDIS_URL,
        "log_level": settings.LOG_LEVEL,
        "max_retries": 3,
        "timeout": 30
    }

    service_configs = {
        ServiceType.QUERY_ROUTER: {
            **base_config,
            "cache_ttl": 3600,
            "max_cache_size": 10000,
            "assignment_timeout": 100  # milliseconds
        },

        ServiceType.METRICS_COLLECTOR: {
            **base_config,
            "buffer_size": 100,
            "batch_interval": 60,  # seconds
            "max_queue_size": 10000
        },

        ServiceType.EXPERIMENT_MANAGER: {
            **base_config,
            "default_experiment_duration": 30,  # days
            "max_concurrent_experiments": 100
        },

        ServiceType.STATISTICAL_ANALYZER: {
            **base_config,
            "confidence_level": 0.95,
            "min_sample_size": 1000
        }
    }

    return service_configs.get(service_type, base_config)