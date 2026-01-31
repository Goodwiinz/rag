"""
A/B Testing Event Service
Provides event-driven communication patterns for A/B testing operations
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from src.core.config import settings
from src.services.cache.analytics_cache import analytics_cache

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types for A/B testing system"""

    EXPERIMENT_CREATED = "experiment_created"
    EXPERIMENT_STARTED = "experiment_started"
    EXPERIMENT_STOPPED = "experiment_stopped"
    EXPERIMENT_UPDATED = "experiment_updated"
    EXPERIMENT_DELETED = "experiment_deleted"

    VARIANT_CREATED = "variant_created"
    VARIANT_UPDATED = "variant_updated"
    VARIANT_DELETED = "variant_deleted"

    USER_ASSIGNED = "user_assigned"
    USER_UNASSIGNED = "user_unassigned"

    METRIC_COLLECTED = "metric_collected"
    METRICS_BATCH_PROCESSED = "metrics_batch_processed"

    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"

    CACHE_INVALIDATED = "cache_invalidated"
    ERROR_OCCURRED = "error_occurred"

    TRAFFIC_ALLOCATION_CHANGED = "traffic_allocation_changed"
    SAMPLE_SIZE_REACHED = "sample_size_reached"
    STATISTICAL_SIGNIFICANCE_ACHIEVED = "statistical_significance_achieved"


class EventPriority(Enum):
    """Event priorities for processing"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class EventStatus(Enum):
    """Event processing status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Event:
    """Base event structure"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType = field(default=EventType.ERROR_OCCURRED)
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source_service: str = "unknown"
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None  # ID of event that caused this event
    priority: EventPriority = EventPriority.NORMAL
    retry_count: int = 0
    max_retries: int = 3
    delay_until: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source_service": self.source_service,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "priority": self.priority.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "delay_until": self.delay_until.isoformat() if self.delay_until else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create event from dictionary"""
        event = cls()
        event.id = data["id"]
        event.type = EventType(data["type"])
        event.data = data["data"]
        event.timestamp = datetime.fromisoformat(data["timestamp"])
        event.source_service = data["source_service"]
        event.correlation_id = data.get("correlation_id")
        event.causation_id = data.get("causation_id")
        event.priority = EventPriority(data["priority"])
        event.retry_count = data["retry_count"]
        event.max_retries = data["max_retries"]
        event.delay_until = (
            datetime.fromisoformat(data["delay_until"])
            if data.get("delay_until")
            else None
        )
        event.metadata = data.get("metadata", {})
        return event


@dataclass
class EventHandler:
    """Event handler configuration"""

    event_type: EventType
    handler_func: Callable
    service_name: str
    priority: int = 0
    async_handler: bool = True
    retry_on_failure: bool = True
    timeout_seconds: int = 30


class EventPublisher:
    """Event publisher for sending events"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.redis_client = None
        self.event_queue = asyncio.Queue()
        self.publishing = False

    async def initialize(self):
        """Initialize publisher"""
        try:
            import redis.asyncio as redis

            self.redis_client = redis.from_url(settings.REDIS_URL)
            await self.redis_client.ping()
            logger.info(f"Event publisher initialized for {self.service_name}")
        except Exception as e:
            logger.warning(f"Redis not available for event publishing: {e}")

    async def publish_event(self, event: Event):
        """Publish an event"""
        event.source_service = self.service_name

        # Add to internal queue for batching
        await self.event_queue.put(event)

        # Start background publisher if not running
        if not self.publishing:
            asyncio.create_task(self._background_publisher())

    async def publish_events_batch(self, events: List[Event]):
        """Publish multiple events"""
        for event in events:
            event.source_service = self.service_name
            await self.event_queue.put(event)

        if not self.publishing:
            asyncio.create_task(self._background_publisher())

    async def _background_publisher(self):
        """Background task for publishing events"""
        self.publishing = True
        batch_size = 100
        batch_timeout = 1.0  # seconds

        try:
            while True:
                events = []
                deadline = asyncio.time() + batch_timeout

                # Collect events for batching
                while len(events) < batch_size and asyncio.time() < deadline:
                    try:
                        timeout = max(0.1, deadline - asyncio.time())
                        event = await asyncio.wait_for(
                            self.event_queue.get(), timeout=timeout
                        )
                        events.append(event)
                    except asyncio.TimeoutError:
                        break

                if not events:
                    continue

                # Publish batch
                await self._publish_to_message_bus(events)

        except Exception as e:
            logger.error(f"Error in background event publisher: {e}")
        finally:
            self.publishing = False

    async def _publish_to_message_bus(self, events: List[Event]):
        """Publish events to message bus (Redis)"""
        if not self.redis_client:
            logger.warning("Redis not available, events not published")
            return

        try:
            # Group events by type for efficient processing
            events_by_type = {}
            for event in events:
                event_type = event.type.value
                if event_type not in events_by_type:
                    events_by_type[event_type] = []
                events_by_type[event_type].append(event)

            # Publish to Redis streams
            for event_type, type_events in events_by_type.items():
                stream_key = f"events:{event_type}"

                for event in type_events:
                    await self.redis_client.xadd(
                        stream_key,
                        event.to_dict(),
                        maxlen=10000,  # Keep last 10k events per stream
                    )

                # Set expiry on stream
                await self.redis_client.expire(stream_key, 86400)  # 24 hours

            logger.debug(
                f"Published {len(events)} events across {len(events_by_type)} streams"
            )

        except Exception as e:
            logger.error(f"Error publishing events to Redis: {e}")


class EventSubscriber:
    """Event subscriber for processing events"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.redis_client = None
        self.handlers: Dict[EventType, List[EventHandler]] = {}
        self.consumer_groups: Dict[str, str] = {}  # stream -> consumer group
        self.processing = False
        self.last_processed_ids: Dict[str, str] = {}  # stream -> last_id

    async def initialize(self):
        """Initialize subscriber"""
        try:
            import redis.asyncio as redis

            self.redis_client = redis.from_url(settings.REDIS_URL)
            await self.redis_client.ping()

            # Create consumer groups
            await self._ensure_consumer_groups()

            logger.info(f"Event subscriber initialized for {self.service_name}")
        except Exception as e:
            logger.warning(f"Redis not available for event subscription: {e}")

    def register_handler(self, handler: EventHandler):
        """Register an event handler"""
        if handler.event_type not in self.handlers:
            self.handlers[handler.event_type] = []
        self.handlers[handler.event_type].append(handler)

        # Sort by priority (higher priority first)
        self.handlers[handler.event_type].sort(key=lambda h: h.priority, reverse=True)

        logger.info(
            f"Registered handler for {handler.event_type.value} in {self.service_name}"
        )

    async def start_processing(self):
        """Start processing events"""
        if self.processing:
            return

        self.processing = True
        asyncio.create_task(self._event_processor())
        logger.info(f"Started event processing for {self.service_name}")

    async def stop_processing(self):
        """Stop processing events"""
        self.processing = False
        logger.info(f"Stopped event processing for {self.service_name}")

    async def _ensure_consumer_groups(self):
        """Ensure consumer groups exist for all event types"""
        for event_type in EventType:
            stream_key = f"events:{event_type.value}"
            group_name = f"{self.service_name}_group"

            try:
                # Try to create consumer group
                await self.redis_client.xgroup_create(
                    stream_key, group_name, id="0", mkstream=True
                )
                self.consumer_groups[event_type.value] = group_name
            except Exception as e:
                # Group might already exist
                if "BUSYGROUP" not in str(e):
                    logger.warning(
                        f"Error creating consumer group for {event_type.value}: {e}"
                    )
                self.consumer_groups[event_type.value] = group_name

    async def _event_processor(self):
        """Main event processing loop"""
        while self.processing:
            try:
                # Process events for each subscribed type
                for event_type, handlers in self.handlers.items():
                    if not handlers:
                        continue

                    await self._process_event_type(event_type, handlers)

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in event processing loop: {e}")
                await asyncio.sleep(1.0)

    async def _process_event_type(
        self, event_type: EventType, handlers: List[EventHandler]
    ):
        """Process events of a specific type"""
        if not self.redis_client:
            return

        stream_key = f"events:{event_type.value}"
        group_name = self.consumer_groups.get(event_type.value)

        if not group_name:
            return

        try:
            # Read events from stream
            consumer_name = f"{self.service_name}_{uuid.uuid4().hex[:8]}"
            messages = await self.redis_client.xreadgroup(
                group_name,
                consumer_name,
                {stream_key: ">"},  # Read new messages
                count=10,  # Process up to 10 messages at once
                block=1000,  # Block for 1 second
            )

            if not messages:
                return

            # Process each message
            for stream, events in messages:
                for event_id, event_data in events:
                    try:
                        event = Event.from_dict(event_data)
                        await self._handle_event(event, handlers)

                        # Acknowledge message
                        await self.redis_client.xack(stream_key, group_name, event_id)

                    except Exception as e:
                        logger.error(f"Error processing event {event_id}: {e}")
                        # Move to dead-letter queue after retries
                        await self._handle_failed_event(
                            stream_key, group_name, event_id, e
                        )

        except Exception as e:
            logger.error(f"Error processing events for {event_type.value}: {e}")

    async def _handle_event(self, event: Event, handlers: List[EventHandler]):
        """Handle a single event"""
        for handler in handlers:
            try:
                if handler.async_handler:
                    await handler.handler_func(event)
                else:
                    # Run synchronous handler in thread pool
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, handler.handler_func, event)

                # If successful and this is the first handler, mark as processed
                if handlers[0] == handler:
                    logger.debug(
                        f"Successfully processed event {event.id} with {handler.service_name}"
                    )

            except Exception as e:
                logger.error(
                    f"Handler {handler.service_name} failed for event {event.id}: {e}"
                )

                if not handler.retry_on_failure:
                    continue

                # Retry logic
                if event.retry_count < event.max_retries:
                    event.retry_count += 1
                    event.delay_until = datetime.utcnow() + timedelta(
                        seconds=2**event.retry_count  # Exponential backoff
                    )

                    # Re-queue event
                    await self._requeue_event(event)
                else:
                    logger.error(
                        f"Event {event.id} exceeded max retries, moving to dead-letter"
                    )
                    await self._move_to_dead_letter(event, e)

    async def _handle_failed_event(
        self, stream_key: str, group_name: str, event_id: str, error: Exception
    ):
        """Handle failed event processing"""
        try:
            # Move to dead-letter stream
            dead_letter_key = f"{stream_key}:dead_letter"
            await self.redis_client.xadd(
                dead_letter_key,
                {
                    "original_id": event_id,
                    "error": str(error),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            # Acknowledge to remove from pending queue
            await self.redis_client.xack(stream_key, group_name, event_id)

        except Exception as e:
            logger.error(f"Error handling failed event: {e}")

    async def _requeue_event(self, event: Event):
        """Re-queue event for retry"""
        if not self.redis_client:
            return

        try:
            stream_key = f"events:{event.type.value}"
            retry_key = f"{stream_key}:retry"

            await self.redis_client.xadd(retry_key, event.to_dict())

            # Set TTL for retry queue
            await self.redis_client.expire(retry_key, 3600)  # 1 hour

        except Exception as e:
            logger.error(f"Error re-queuing event {event.id}: {e}")

    async def _move_to_dead_letter(self, event: Event, error: Exception):
        """Move event to dead-letter queue"""
        if not self.redis_client:
            return

        try:
            dead_letter_key = f"events:dead_letter"
            await self.redis_client.xadd(
                dead_letter_key,
                {
                    **event.to_dict(),
                    "error": str(error),
                    "failed_at": datetime.utcnow().isoformat(),
                },
            )

        except Exception as e:
            logger.error(f"Error moving event {event.id} to dead-letter: {e}")


class EventService:
    """Main event service for A/B testing system"""

    def __init__(self):
        self.publishers: Dict[str, EventPublisher] = {}
        self.subscribers: Dict[str, EventSubscriber] = {}
        self.event_store: List[Event] = []  # In-memory event store for debugging
        self.initialized = False

    async def initialize(self):
        """Initialize event service"""
        if self.initialized:
            return

        # Create default publisher and subscriber
        default_publisher = EventPublisher("ab_testing_service")
        default_subscriber = EventSubscriber("ab_testing_service")

        await default_publisher.initialize()
        await default_subscriber.initialize()

        self.publishers["default"] = default_publisher
        self.subscribers["default"] = default_subscriber

        self.initialized = True
        logger.info("Event service initialized")

    def get_publisher(self, service_name: str = "default") -> EventPublisher:
        """Get event publisher for a service"""
        if service_name not in self.publishers:
            self.publishers[service_name] = EventPublisher(service_name)
            # Initialize asynchronously
            asyncio.create_task(self.publishers[service_name].initialize())
        return self.publishers[service_name]

    def get_subscriber(self, service_name: str = "default") -> EventSubscriber:
        """Get event subscriber for a service"""
        if service_name not in self.subscribers:
            self.subscribers[service_name] = EventSubscriber(service_name)
            # Initialize asynchronously
            asyncio.create_task(self.subscribers[service_name].initialize())
        return self.subscribers[service_name]

    async def publish_event(
        self, event_type: EventType, data: Dict[str, Any], **kwargs
    ):
        """Publish an event"""
        if not self.initialized:
            await self.initialize()

        event = Event(type=event_type, data=data, **kwargs)

        # Store in memory for debugging
        self.event_store.append(event)
        if len(self.event_store) > 1000:  # Keep last 1000 events
            self.event_store = self.event_store[-1000:]

        # Publish
        publisher = self.get_publisher()
        await publisher.publish_event(event)

        return event.id

    async def create_event_chain(
        self,
        events: List[tuple[EventType, Dict[str, Any]]],
        correlation_id: Optional[str] = None,
    ) -> str:
        """Create a chain of related events"""
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        causation_id = None

        for event_type, data in events:
            event_id = await self.publish_event(
                event_type=event_type,
                data=data,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
            causation_id = event_id

        return correlation_id

    def register_handler(
        self,
        event_type: EventType,
        handler_func: Callable,
        service_name: str = "default",
        **kwargs,
    ):
        """Register an event handler"""
        handler = EventHandler(
            event_type=event_type,
            handler_func=handler_func,
            service_name=service_name,
            **kwargs,
        )

        subscriber = self.get_subscriber(service_name)
        subscriber.register_handler(handler)

    async def start_all_subscribers(self):
        """Start all event subscribers"""
        for subscriber in self.subscribers.values():
            await subscriber.start_processing()

    async def stop_all_subscribers(self):
        """Stop all event subscribers"""
        for subscriber in self.subscribers.values():
            await subscriber.stop_processing()

    def get_event_stats(self) -> Dict[str, Any]:
        """Get event service statistics"""
        return {
            "initialized": self.initialized,
            "publishers": list(self.publishers.keys()),
            "subscribers": list(self.subscribers.keys()),
            "events_in_memory": len(self.event_store),
            "total_handlers": sum(
                len(subscriber.handlers) for subscriber in self.subscribers.values()
            ),
        }


# Event factory functions for common A/B testing events


def create_experiment_created_event(
    experiment_id: str, experiment_data: Dict[str, Any], created_by: str
) -> Event:
    """Create experiment created event"""
    return Event(
        type=EventType.EXPERIMENT_CREATED,
        data={
            "experiment_id": experiment_id,
            "experiment_data": experiment_data,
            "created_by": created_by,
        },
        priority=EventPriority.NORMAL,
    )


def create_experiment_started_event(
    experiment_id: str, started_by: str, start_time: datetime
) -> Event:
    """Create experiment started event"""
    return Event(
        type=EventType.EXPERIMENT_STARTED,
        data={
            "experiment_id": experiment_id,
            "started_by": started_by,
            "start_time": start_time.isoformat(),
        },
        priority=EventPriority.HIGH,
    )


def create_user_assigned_event(
    experiment_id: str, variant_id: str, user_id: str, assignment_data: Dict[str, Any]
) -> Event:
    """Create user assigned event"""
    return Event(
        type=EventType.USER_ASSIGNED,
        data={
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "user_id": user_id,
            "assignment_data": assignment_data,
        },
        priority=EventPriority.NORMAL,
    )


def create_metric_collected_event(
    experiment_id: str,
    variant_id: str,
    metric_type: str,
    metric_value: float,
    user_id: Optional[str] = None,
) -> Event:
    """Create metric collected event"""
    return Event(
        type=EventType.METRIC_COLLECTED,
        data={
            "experiment_id": experiment_id,
            "variant_id": variant_id,
            "metric_type": metric_type,
            "metric_value": metric_value,
            "user_id": user_id,
        },
        priority=EventPriority.NORMAL,
    )


def create_analysis_completed_event(
    experiment_id: str, analysis_result: Dict[str, Any], confidence_level: float
) -> Event:
    """Create analysis completed event"""
    return Event(
        type=EventType.ANALYSIS_COMPLETED,
        data={
            "experiment_id": experiment_id,
            "analysis_result": analysis_result,
            "confidence_level": confidence_level,
        },
        priority=EventPriority.HIGH,
    )


# Global event service instance
event_service = EventService()


# Decorator for event publishing


def publish_event_on_success(
    event_type: EventType,
    data_extractor: Callable = None,
    service_name: str = "default",
):
    """
    Decorator to publish event when function succeeds
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)

                # Extract event data
                if data_extractor:
                    event_data = data_extractor(result, *args, **kwargs)
                else:
                    event_data = {"result": result}

                # Publish event
                await event_service.publish_event(
                    event_type=event_type, data=event_data, source_service=service_name
                )

                return result

            except Exception as e:
                # Publish error event
                await event_service.publish_event(
                    event_type=EventType.ERROR_OCCURRED,
                    data={
                        "error": str(e),
                        "function": func.__name__,
                        "args": str(args)[:100],  # Truncate for size
                        "kwargs": str(kwargs)[:100],
                    },
                    source_service=service_name,
                )
                raise

        return wrapper

    return decorator
