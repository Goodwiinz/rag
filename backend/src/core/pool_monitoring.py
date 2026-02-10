"""
Connection Pool Monitoring for Scalable Systems

Provides monitoring, metrics, and health checks for database connection pools,
Redis connections, and other pooled resources.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool

logger = logging.getLogger(__name__)


# =============================================================================
# Pool Health Status
# =============================================================================


class PoolHealthStatus(Enum):
    """Health status for connection pools."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class PoolMetrics:
    """Metrics for a connection pool."""

    name: str
    pool_size: int
    checked_out: int
    overflow: int
    available: int
    checkins: int = 0
    checkouts: int = 0
    invalidated: int = 0
    soft_invalidated: int = 0
    detached: int = 0
    connects: int = 0
    disconnects: int = 0
    timeouts: int = 0
    errors: int = 0
    avg_checkout_time: float = 0.0
    max_checkout_time: float = 0.0
    utilization: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def status(self) -> PoolHealthStatus:
        """Determine pool health status based on metrics."""
        if self.utilization > 0.95:
            return PoolHealthStatus.CRITICAL
        elif self.utilization > 0.8 or self.errors > 0:
            return PoolHealthStatus.DEGRADED
        elif self.pool_size > 0:
            return PoolHealthStatus.HEALTHY
        return PoolHealthStatus.UNKNOWN


@dataclass
class PoolAlert:
    """Alert for pool issues."""

    pool_name: str
    severity: str  # "warning", "critical"
    message: str
    metric_name: str
    current_value: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# SQLAlchemy Pool Monitor
# =============================================================================


class SQLAlchemyPoolMonitor:
    """
    Monitor SQLAlchemy connection pool with event-based metrics collection.

    Usage:
        from sqlalchemy import create_engine
        from src.core.pool_monitoring import SQLAlchemyPoolMonitor

        engine = create_engine(...)
        monitor = SQLAlchemyPoolMonitor("primary_db", engine)
        monitor.start()

        # Get metrics
        metrics = monitor.get_metrics()

        # Check health
        if metrics.status == PoolHealthStatus.CRITICAL:
            logger.critical("Database pool exhausted!")
    """

    def __init__(
        self,
        name: str,
        engine: Engine,
        alert_callback: Optional[Callable[[PoolAlert], None]] = None,
    ):
        self.name = name
        self.engine = engine
        self.pool: Pool = engine.pool
        self.alert_callback = alert_callback

        # Counters
        self._checkins = 0
        self._checkouts = 0
        self._connects = 0
        self._disconnects = 0
        self._invalidated = 0
        self._soft_invalidated = 0
        self._detached = 0
        self._timeouts = 0
        self._errors = 0

        # Timing
        self._checkout_times: List[float] = []
        self._checkout_start_times: Dict[int, float] = {}

        # Alert thresholds
        self.thresholds = {
            "utilization_warning": 0.7,
            "utilization_critical": 0.9,
            "checkout_time_warning": 1.0,  # seconds
            "checkout_time_critical": 5.0,
            "overflow_warning": 0.5,  # 50% of max overflow
        }

        self._started = False

    def start(self):
        """Start monitoring by registering event listeners."""
        if self._started:
            return

        # Connection checkout
        event.listen(self.pool, "checkout", self._on_checkout)
        event.listen(self.pool, "checkin", self._on_checkin)

        # Connection lifecycle
        event.listen(self.pool, "connect", self._on_connect)
        event.listen(self.pool, "close", self._on_close)
        event.listen(self.pool, "detach", self._on_detach)
        event.listen(self.pool, "invalidate", self._on_invalidate)
        event.listen(self.pool, "soft_invalidate", self._on_soft_invalidate)

        # Reset
        event.listen(self.pool, "reset", self._on_reset)

        self._started = True
        logger.info(f"Pool monitoring started for '{self.name}'")

    def stop(self):
        """Stop monitoring by removing event listeners."""
        if not self._started:
            return

        event.remove(self.pool, "checkout", self._on_checkout)
        event.remove(self.pool, "checkin", self._on_checkin)
        event.remove(self.pool, "connect", self._on_connect)
        event.remove(self.pool, "close", self._on_close)
        event.remove(self.pool, "detach", self._on_detach)
        event.remove(self.pool, "invalidate", self._on_invalidate)
        event.remove(self.pool, "soft_invalidate", self._on_soft_invalidate)
        event.remove(self.pool, "reset", self._on_reset)

        self._started = False
        logger.info(f"Pool monitoring stopped for '{self.name}'")

    # Event handlers
    def _on_checkout(self, dbapi_connection, connection_record, connection_proxy):
        """Called when a connection is checked out from the pool."""
        self._checkouts += 1
        conn_id = id(connection_proxy)
        self._checkout_start_times[conn_id] = time.time()

        # Check utilization
        self._check_utilization_alert()

    def _on_checkin(self, dbapi_connection, connection_record):
        """Called when a connection is returned to the pool."""
        self._checkins += 1

        # Calculate checkout duration (approximate)
        # Note: We don't have direct access to the proxy here
        if self._checkout_start_times:
            # Use oldest checkout as estimate
            oldest_start = min(self._checkout_start_times.values())
            duration = time.time() - oldest_start
            self._checkout_times.append(duration)

            # Keep only last 100 measurements
            if len(self._checkout_times) > 100:
                self._checkout_times = self._checkout_times[-100:]

            # Clean up old entries
            self._cleanup_checkout_times()

            # Check for slow checkouts
            if duration > self.thresholds["checkout_time_critical"]:
                self._send_alert(
                    "critical",
                    f"Connection held for {duration:.2f}s",
                    "checkout_time",
                    duration,
                    self.thresholds["checkout_time_critical"],
                )

    def _on_connect(self, dbapi_connection, connection_record):
        """Called when a new connection is created."""
        self._connects += 1
        logger.debug(f"Pool '{self.name}': New connection created")

    def _on_close(self, dbapi_connection, connection_record):
        """Called when a connection is closed."""
        self._disconnects += 1
        logger.debug(f"Pool '{self.name}': Connection closed")

    def _on_detach(self, dbapi_connection, connection_record):
        """Called when a connection is detached from the pool."""
        self._detached += 1
        logger.warning(f"Pool '{self.name}': Connection detached")

    def _on_invalidate(self, dbapi_connection, connection_record, exception):
        """Called when a connection is invalidated."""
        self._invalidated += 1
        if exception:
            self._errors += 1
            logger.error(f"Pool '{self.name}': Connection invalidated: {exception}")

    def _on_soft_invalidate(self, dbapi_connection, connection_record):
        """Called when a connection is soft-invalidated."""
        self._soft_invalidated += 1

    def _on_reset(self, dbapi_connection, connection_record):
        """Called when a connection is reset."""
        pass  # Just track, no action needed

    def _cleanup_checkout_times(self):
        """Clean up old checkout start times."""
        current_time = time.time()
        # Remove entries older than 5 minutes (likely orphaned)
        self._checkout_start_times = {
            k: v
            for k, v in self._checkout_start_times.items()
            if current_time - v < 300
        }

    def _check_utilization_alert(self):
        """Check and send utilization alerts."""
        try:
            pool_size = self.pool.size()
            checked_out = self.pool.checkedout()
            max_overflow = getattr(self.pool, "_max_overflow", 0)
            total_capacity = pool_size + max_overflow

            if total_capacity > 0:
                utilization = checked_out / total_capacity

                if utilization >= self.thresholds["utilization_critical"]:
                    self._send_alert(
                        "critical",
                        f"Pool utilization at {utilization:.1%}",
                        "utilization",
                        utilization,
                        self.thresholds["utilization_critical"],
                    )
                elif utilization >= self.thresholds["utilization_warning"]:
                    self._send_alert(
                        "warning",
                        f"Pool utilization at {utilization:.1%}",
                        "utilization",
                        utilization,
                        self.thresholds["utilization_warning"],
                    )
        except Exception as e:
            logger.error(f"Error checking utilization: {e}")

    def _send_alert(
        self,
        severity: str,
        message: str,
        metric_name: str,
        current_value: float,
        threshold: float,
    ):
        """Send an alert through the callback."""
        alert = PoolAlert(
            pool_name=self.name,
            severity=severity,
            message=message,
            metric_name=metric_name,
            current_value=current_value,
            threshold=threshold,
        )

        logger.log(
            logging.CRITICAL if severity == "critical" else logging.WARNING,
            f"Pool alert [{self.name}]: {message}",
        )

        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                logger.error(f"Error sending alert: {e}")

    def get_metrics(self) -> PoolMetrics:
        """Get current pool metrics."""
        try:
            pool_size = self.pool.size()
            checked_out = self.pool.checkedout()
            overflow = self.pool.overflow()
            max_overflow = getattr(self.pool, "_max_overflow", 0)

            total_capacity = pool_size + max_overflow
            utilization = checked_out / total_capacity if total_capacity > 0 else 0.0

            avg_checkout = (
                sum(self._checkout_times) / len(self._checkout_times)
                if self._checkout_times
                else 0.0
            )
            max_checkout = max(self._checkout_times) if self._checkout_times else 0.0

            return PoolMetrics(
                name=self.name,
                pool_size=pool_size,
                checked_out=checked_out,
                overflow=overflow,
                available=pool_size - checked_out + (max_overflow - overflow),
                checkins=self._checkins,
                checkouts=self._checkouts,
                invalidated=self._invalidated,
                soft_invalidated=self._soft_invalidated,
                detached=self._detached,
                connects=self._connects,
                disconnects=self._disconnects,
                timeouts=self._timeouts,
                errors=self._errors,
                avg_checkout_time=avg_checkout,
                max_checkout_time=max_checkout,
                utilization=utilization,
            )
        except Exception as e:
            logger.error(f"Error getting pool metrics: {e}")
            return PoolMetrics(
                name=self.name,
                pool_size=0,
                checked_out=0,
                overflow=0,
                available=0,
            )

    def reset_counters(self):
        """Reset all counters (useful for periodic reporting)."""
        self._checkins = 0
        self._checkouts = 0
        self._connects = 0
        self._disconnects = 0
        self._invalidated = 0
        self._soft_invalidated = 0
        self._detached = 0
        self._timeouts = 0
        self._errors = 0
        self._checkout_times.clear()


# =============================================================================
# Redis Pool Monitor
# =============================================================================


@dataclass
class RedisPoolMetrics:
    """Metrics for Redis connection pool."""

    name: str
    created_connections: int
    available_connections: int
    in_use_connections: int
    max_connections: int
    utilization: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def status(self) -> PoolHealthStatus:
        if self.utilization > 0.95:
            return PoolHealthStatus.CRITICAL
        elif self.utilization > 0.8:
            return PoolHealthStatus.DEGRADED
        return PoolHealthStatus.HEALTHY


class RedisPoolMonitor:
    """
    Monitor Redis connection pool.

    Usage:
        from redis.asyncio import Redis
        from src.core.pool_monitoring import RedisPoolMonitor

        redis = Redis.from_url("redis://localhost")
        monitor = RedisPoolMonitor("cache", redis)

        metrics = await monitor.get_metrics()
    """

    def __init__(self, name: str, redis_client):
        self.name = name
        self.redis = redis_client

    async def get_metrics(self) -> RedisPoolMetrics:
        """Get current Redis pool metrics."""
        try:
            pool = self.redis.connection_pool

            created = (
                pool._created_connections
                if hasattr(pool, "_created_connections")
                else 0
            )
            available = (
                len(pool._available_connections)
                if hasattr(pool, "_available_connections")
                else 0
            )
            in_use = (
                pool._in_use_connections if hasattr(pool, "_in_use_connections") else 0
            )
            max_conn = pool.max_connections if hasattr(pool, "max_connections") else 10

            utilization = in_use / max_conn if max_conn > 0 else 0.0

            return RedisPoolMetrics(
                name=self.name,
                created_connections=created,
                available_connections=available,
                in_use_connections=in_use,
                max_connections=max_conn,
                utilization=utilization,
            )
        except Exception as e:
            logger.error(f"Error getting Redis pool metrics: {e}")
            return RedisPoolMetrics(
                name=self.name,
                created_connections=0,
                available_connections=0,
                in_use_connections=0,
                max_connections=0,
                utilization=0.0,
            )


# =============================================================================
# Pool Manager (Central Registry)
# =============================================================================


class PoolManager:
    """
    Central registry for all connection pool monitors.

    Usage:
        from src.core.pool_monitoring import pool_manager

        # Register pools
        pool_manager.register_sqlalchemy("primary", engine)
        pool_manager.register_redis("cache", redis_client)

        # Get all metrics
        all_metrics = pool_manager.get_all_metrics()

        # Health check
        health = pool_manager.health_check()
    """

    def __init__(self):
        self._sqlalchemy_monitors: Dict[str, SQLAlchemyPoolMonitor] = {}
        self._redis_monitors: Dict[str, RedisPoolMonitor] = {}

    def register_sqlalchemy(
        self,
        name: str,
        engine: Engine,
        alert_callback: Optional[Callable[[PoolAlert], None]] = None,
    ) -> SQLAlchemyPoolMonitor:
        """Register and start monitoring a SQLAlchemy engine."""
        monitor = SQLAlchemyPoolMonitor(name, engine, alert_callback)
        monitor.start()
        self._sqlalchemy_monitors[name] = monitor
        logger.info(f"Registered SQLAlchemy pool monitor: {name}")
        return monitor

    def register_redis(self, name: str, redis_client) -> RedisPoolMonitor:
        """Register a Redis client for monitoring."""
        monitor = RedisPoolMonitor(name, redis_client)
        self._redis_monitors[name] = monitor
        logger.info(f"Registered Redis pool monitor: {name}")
        return monitor

    def get_sqlalchemy_metrics(self, name: str) -> Optional[PoolMetrics]:
        """Get metrics for a specific SQLAlchemy pool."""
        monitor = self._sqlalchemy_monitors.get(name)
        return monitor.get_metrics() if monitor else None

    async def get_redis_metrics(self, name: str) -> Optional[RedisPoolMetrics]:
        """Get metrics for a specific Redis pool."""
        monitor = self._redis_monitors.get(name)
        return await monitor.get_metrics() if monitor else None

    def get_all_sqlalchemy_metrics(self) -> Dict[str, PoolMetrics]:
        """Get metrics for all SQLAlchemy pools."""
        return {name: m.get_metrics() for name, m in self._sqlalchemy_monitors.items()}

    async def get_all_redis_metrics(self) -> Dict[str, RedisPoolMetrics]:
        """Get metrics for all Redis pools."""
        results = {}
        for name, monitor in self._redis_monitors.items():
            results[name] = await monitor.get_metrics()
        return results

    async def get_all_metrics(self) -> Dict[str, Any]:
        """Get all pool metrics."""
        return {
            "sqlalchemy": self.get_all_sqlalchemy_metrics(),
            "redis": await self.get_all_redis_metrics(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all pools."""
        sqlalchemy_health = {}
        for name, monitor in self._sqlalchemy_monitors.items():
            metrics = monitor.get_metrics()
            sqlalchemy_health[name] = {
                "status": metrics.status.value,
                "utilization": metrics.utilization,
                "checked_out": metrics.checked_out,
                "errors": metrics.errors,
            }

        overall_status = PoolHealthStatus.HEALTHY
        for health in sqlalchemy_health.values():
            if health["status"] == PoolHealthStatus.CRITICAL.value:
                overall_status = PoolHealthStatus.CRITICAL
                break
            elif health["status"] == PoolHealthStatus.DEGRADED.value:
                overall_status = PoolHealthStatus.DEGRADED

        return {
            "overall_status": overall_status.value,
            "sqlalchemy_pools": sqlalchemy_health,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def shutdown(self):
        """Stop all monitors."""
        for monitor in self._sqlalchemy_monitors.values():
            monitor.stop()
        self._sqlalchemy_monitors.clear()
        self._redis_monitors.clear()
        logger.info("All pool monitors stopped")


# Global pool manager instance
pool_manager = PoolManager()
