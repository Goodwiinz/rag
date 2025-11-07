"""
Advanced Connection Pool Manager for Multimodal Enterprise RAG System

This module provides intelligent connection pooling, auto-scaling, and resource management
across all databases with production-ready features for high-load scenarios.
"""

import asyncio
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import queue
import weakref
from concurrent.futures import ThreadPoolExecutor

from .postgresql_optimizer import DatabaseConfig, OptimizationLevel
from .neo4j_optimizer import Neo4jConfig, Neo4jOptimizationLevel
from .redis_optimizer import RedisConfig, RedisOptimizationLevel
from ..qdrant_optimization import QdrantOptimizationConfig

logger = logging.getLogger(__name__)


class PoolScalingStrategy(str, Enum):
    """Connection pool scaling strategies"""
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    AUTO_SCALING = "auto_scaling"
    LOAD_BASED = "load_based"


class ConnectionState(str, Enum):
    """Connection state tracking"""
    IDLE = "idle"
    ACTIVE = "active"
    CHECKED_OUT = "checked_out"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class PoolConfiguration:
    """Base configuration for connection pools"""
    min_connections: int = 5
    max_connections: int = 50
    connection_timeout: float = 30.0
    idle_timeout: float = 300.0  # 5 minutes
    max_lifetime: float = 3600.0  # 1 hour
    health_check_interval: float = 60.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    scaling_strategy: PoolScalingStrategy = PoolScalingStrategy.DYNAMIC
    enable_connection_validation: bool = True
    enable_metrics: bool = True


@dataclass
class PoolMetrics:
    """Connection pool performance metrics"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    failed_connections: int = 0
    connection_errors: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_wait_time_ms: float = 0.0
    max_wait_time_ms: float = 0.0
    avg_connection_lifetime_ms: float = 0.0
    pool_utilization: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def success_rate(self) -> float:
        return (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0

    @property
    def error_rate(self) -> float:
        return (self.failed_requests / self.total_requests * 100) if self.total_requests > 0 else 0


class ManagedConnection:
    """Managed database connection with health monitoring"""

    def __init__(self, connection: Any, pool_id: str, created_at: datetime):
        self.connection = connection
        self.pool_id = pool_id
        self.created_at = created_at
        self.last_used_at = created_at
        self.state = ConnectionState.IDLE
        self.checkout_count = 0
        self.error_count = 0
        self.last_health_check = created_at
        self.is_healthy = True

    def checkout(self):
        """Check out connection for use"""
        self.state = ConnectionState.CHECKED_OUT
        self.checkout_count += 1
        self.last_used_at = datetime.utcnow()

    def checkin(self):
        """Check connection back into pool"""
        self.state = ConnectionState.IDLE
        self.last_used_at = datetime.utcnow()

    def mark_error(self):
        """Mark connection as having an error"""
        self.error_count += 1
        self.state = ConnectionState.ERROR
        self.last_used_at = datetime.utcnow()

    def get_age_seconds(self) -> float:
        """Get connection age in seconds"""
        return (datetime.utcnow() - self.created_at).total_seconds()

    def get_idle_seconds(self) -> float:
        """Get idle time in seconds"""
        if self.state != ConnectionState.IDLE:
            return 0
        return (datetime.utcnow() - self.last_used_at).total_seconds()


class BaseConnectionPool:
    """Base connection pool with common functionality"""

    def __init__(self, pool_id: str, config: PoolConfiguration):
        self.pool_id = pool_id
        self.config = config
        self.connections: Dict[str, ManagedConnection] = {}
        self.available_connections = queue.Queue()
        self.lock = asyncio.Lock()
        self.metrics = PoolMetrics()
        self.is_shutdown = False
        self.health_check_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self.scaling_task: Optional[asyncio.Task] = None
        self._connection_callbacks: List[Callable] = []

    async def initialize(self):
        """Initialize the connection pool"""
        await self._create_initial_connections()
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        if self.config.scaling_strategy in [PoolScalingStrategy.DYNAMIC, PoolScalingStrategy.AUTO_SCALING]:
            self.scaling_task = asyncio.create_task(self._scaling_loop())
        logger.info(f"Connection pool {self.pool_id} initialized with {len(self.connections)} connections")

    async def _create_initial_connections(self):
        """Create initial set of connections"""
        for _ in range(self.config.min_connections):
            await self._add_connection()

    async def get_connection(self, timeout: Optional[float] = None) -> ManagedConnection:
        """Get a connection from the pool"""
        if self.is_shutdown:
            raise RuntimeError(f"Pool {self.pool_id} is shutdown")

        start_time = time.time()
        timeout = timeout or self.config.connection_timeout
        self.metrics.total_requests += 1

        try:
            # Try to get available connection
            connection = await self._get_available_connection(timeout)

            # Validate connection if enabled
            if self.config.enable_connection_validation and not await self._validate_connection(connection):
                await self._remove_connection(connection.connection_id)
                # Try again with a new connection
                connection = await self._get_available_connection(timeout)

            connection.checkout()
            self.metrics.active_connections += 1
            self.metrics.successful_requests += 1

            wait_time = (time.time() - start_time) * 1000
            self.metrics.avg_wait_time_ms = (
                (self.metrics.avg_wait_time_ms * (self.metrics.total_requests - 1) + wait_time) /
                self.metrics.total_requests
            )
            self.metrics.max_wait_time_ms = max(self.metrics.max_wait_time_ms, wait_time)

            return connection

        except Exception as e:
            self.metrics.failed_requests += 1
            self.metrics.connection_errors += 1
            logger.error(f"Failed to get connection from pool {self.pool_id}: {e}")
            raise

    async def _get_available_connection(self, timeout: float) -> ManagedConnection:
        """Get an available connection, creating new one if needed"""
        try:
            # Try to get from available queue
            connection_id = await asyncio.wait_for(
                self.available_connections.get(),
                timeout=0.1  # Short timeout for first attempt
            )
            return self.connections[connection_id]
        except asyncio.TimeoutError:
            # No available connection, try to create new one
            async with self.lock:
                if len(self.connections) < self.config.max_connections:
                    return await self._add_connection()
                else:
                    # Pool at max capacity, wait for available connection
                    connection_id = await asyncio.wait_for(
                        self.available_connections.get(),
                        timeout=timeout - 0.1
                    )
                    return self.connections[connection_id]

    async def return_connection(self, connection: ManagedConnection):
        """Return a connection to the pool"""
        if connection.state == ConnectionState.CHECKED_OUT:
            connection.checkin()
            self.metrics.active_connections -= 1
            self.available_connections.put(connection.connection_id)

    async def _add_connection(self) -> ManagedConnection:
        """Add a new connection to the pool"""
        connection = await self._create_connection()
        managed_conn = ManagedConnection(
            connection=connection,
            pool_id=self.pool_id,
            created_at=datetime.utcnow()
        )

        self.connections[managed_conn.connection_id] = managed_conn
        self.available_connections.put(managed_conn.connection_id)
        self.metrics.total_connections += 1
        self.metrics.idle_connections += 1

        # Notify callbacks
        for callback in self._connection_callbacks:
            try:
                await callback('connection_created', managed_conn)
            except Exception as e:
                logger.warning(f"Connection callback error: {e}")

        return managed_conn

    async def _remove_connection(self, connection_id: str):
        """Remove a connection from the pool"""
        async with self.lock:
            if connection_id in self.connections:
                connection = self.connections.pop(connection_id)
                self.metrics.total_connections -= 1
                if connection.state == ConnectionState.IDLE:
                    self.metrics.idle_connections -= 1
                elif connection.state == ConnectionState.CHECKED_OUT:
                    self.metrics.active_connections -= 1
                await self._close_connection(connection.connection)

    async def _validate_connection(self, connection: ManagedConnection) -> bool:
        """Validate connection health"""
        try:
            connection.last_health_check = datetime.utcnow()
            is_valid = await self._ping_connection(connection.connection)
            connection.is_healthy = is_valid
            return is_valid
        except Exception as e:
            logger.warning(f"Connection validation failed for {connection.connection_id}: {e}")
            connection.mark_error()
            return False

    async def _health_check_loop(self):
        """Periodic health check for all connections"""
        while not self.is_shutdown:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error in pool {self.pool_id}: {e}")

    async def _perform_health_checks(self):
        """Perform health checks on all connections"""
        unhealthy_connections = []

        for connection in list(self.connections.values()):
            if not connection.is_healthy or connection.error_count > 3:
                unhealthy_connections.append(connection)
            elif (datetime.utcnow() - connection.last_health_check).total_seconds() > self.config.health_check_interval:
                if not await self._validate_connection(connection):
                    unhealthy_connections.append(connection)

        # Remove unhealthy connections
        for connection in unhealthy_connections:
            await self._remove_connection(connection.connection_id)

        # Create new connections if needed (only if below minimum)
        if len(self.connections) < self.config.min_connections:
            connections_needed = self.config.min_connections - len(self.connections)
            for _ in range(connections_needed):
                await self._add_connection()

    async def _cleanup_loop(self):
        """Periodic cleanup of old connections"""
        while not self.is_shutdown:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_old_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error in pool {self.pool_id}: {e}")

    async def _cleanup_old_connections(self):
        """Remove old or idle connections"""
        current_time = datetime.utcnow()
        connections_to_remove = []

        for connection in list(self.connections.values()):
            # Remove connections that exceed max lifetime
            if connection.get_age_seconds() > self.config.max_lifetime:
                connections_to_remove.append(connection)
            # Remove idle connections that exceed idle timeout (but keep minimum)
            elif (connection.get_idle_seconds() > self.config.idle_timeout and
                  len(self.connections) > self.config.min_connections):
                connections_to_remove.append(connection)

        for connection in connections_to_remove:
            await self._remove_connection(connection.connection_id)

    async def _scaling_loop(self):
        """Auto-scaling loop based on load"""
        while not self.is_shutdown:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._adjust_pool_size()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scaling loop error in pool {self.pool_id}: {e}")

    async def _adjust_pool_size(self):
        """Adjust pool size based on current load"""
        if self.config.scaling_strategy == PoolScalingStrategy.DYNAMIC:
            await self._dynamic_scaling()
        elif self.config.scaling_strategy == PoolScalingStrategy.AUTO_SCALING:
            await self._auto_scaling()

    async def _dynamic_scaling(self):
        """Dynamic scaling based on pool utilization"""
        utilization = self.metrics.pool_utilization

        if utilization > 0.8 and len(self.connections) < self.config.max_connections:
            # High utilization, add connections
            connections_to_add = min(2, self.config.max_connections - len(self.connections))
            for _ in range(connections_to_add):
                await self._add_connection()
        elif utilization < 0.2 and len(self.connections) > self.config.min_connections:
            # Low utilization, remove connections
            connections_to_remove = min(2, len(self.connections) - self.config.min_connections)
            idle_connections = [conn for conn in self.connections.values() if conn.state == ConnectionState.IDLE]
            for connection in idle_connections[:connections_to_remove]:
                await self._remove_connection(connection.connection_id)

    async def _auto_scaling(self):
        """Auto-scaling based on request patterns and response times"""
        if self.metrics.avg_wait_time_ms > 100 and len(self.connections) < self.config.max_connections:
            # High wait times, add connections
            await self._add_connection()
        elif self.metrics.avg_wait_time_ms < 10 and len(self.connections) > self.config.min_connections:
            # Low wait times, can remove connections
            idle_connections = [conn for conn in self.connections.values() if conn.state == ConnectionState.IDLE]
            if idle_connections:
                await self._remove_connection(idle_connections[0].connection_id)

    def update_metrics(self):
        """Update pool metrics"""
        self.metrics.active_connections = sum(1 for conn in self.connections.values() if conn.state == ConnectionState.CHECKED_OUT)
        self.metrics.idle_connections = sum(1 for conn in self.connections.values() if conn.state == ConnectionState.IDLE)
        self.metrics.pool_utilization = self.metrics.active_connections / self.config.max_connections if self.config.max_connections > 0 else 0

    async def shutdown(self):
        """Shutdown the connection pool"""
        self.is_shutdown = True

        # Cancel background tasks
        if self.health_check_task:
            self.health_check_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()
        if self.scaling_task:
            self.scaling_task.cancel()

        # Close all connections
        for connection in list(self.connections.values()):
            await self._close_connection(connection.connection)

        self.connections.clear()
        logger.info(f"Connection pool {self.pool_id} shutdown complete")

    # Abstract methods to be implemented by specific pool types
    async def _create_connection(self) -> Any:
        """Create a new database connection"""
        raise NotImplementedError

    async def _close_connection(self, connection: Any):
        """Close a database connection"""
        raise NotImplementedError

    async def _ping_connection(self, connection: Any) -> bool:
        """Ping connection to check if it's alive"""
        raise NotImplementedError

    @property
    def connection_id(self, connection: Any) -> str:
        """Get unique connection ID"""
        return str(id(connection))


class PostgreSQLConnectionPool(BaseConnectionPool):
    """PostgreSQL connection pool implementation"""

    def __init__(self, config: DatabaseConfig, pool_config: PoolConfiguration):
        super().__init__("postgresql", pool_config)
        self.db_config = config
        self.async_pool: Optional[asyncpg.Pool] = None

    async def _create_connection(self) -> Any:
        """Create PostgreSQL connection"""
        return await asyncpg.connect(
            host=self.db_config.host,
            port=self.db_config.port,
            user=self.db_config.user,
            password=self.db_config.password,
            database=self.db_config.database,
            command_timeout=self.config.connection_timeout
        )

    async def _close_connection(self, connection: Any):
        """Close PostgreSQL connection"""
        await connection.close()

    async def _ping_connection(self, connection: Any) -> bool:
        """Ping PostgreSQL connection"""
        try:
            await connection.fetchval("SELECT 1")
            return True
        except:
            return False


class Neo4jConnectionPool(BaseConnectionPool):
    """Neo4j connection pool implementation"""

    def __init__(self, config: Neo4jConfig, pool_config: PoolConfiguration):
        super().__init__("neo4j", pool_config)
        self.neo4j_config = config
        self.driver: Optional[Any] = None

    async def _create_connection(self) -> Any:
        """Create Neo4j session"""
        if not self.driver:
            from neo4j import AsyncGraphDatabase
            self.driver = AsyncGraphDatabase.driver(
                self.neo4j_config.uri,
                auth=(self.neo4j_config.user, self.neo4j_config.password)
            )
        return self.driver.session(database=self.neo4j_config.database)

    async def _close_connection(self, connection: Any):
        """Close Neo4j session"""
        await connection.close()

    async def _ping_connection(self, connection: Any) -> bool:
        """Ping Neo4j session"""
        try:
            result = await connection.run("RETURN 1")
            await result.single()
            return True
        except:
            return False


class RedisConnectionPool(BaseConnectionPool):
    """Redis connection pool implementation"""

    def __init__(self, config: RedisConfig, pool_config: PoolConfiguration):
        super().__init__("redis", pool_config)
        self.redis_config = config
        self.pool: Optional[redis.ConnectionPool] = None

    async def _create_connection(self) -> Any:
        """Create Redis connection"""
        if not self.pool:
            import redis.asyncio as redis
            self.pool = redis.ConnectionPool(
                host=self.redis_config.host,
                port=self.redis_config.port,
                password=self.redis_config.password,
                db=self.redis_config.database,
                max_connections=self.config.max_connections
            )
        import redis.asyncio as redis
        return redis.Redis(connection_pool=self.pool)

    async def _close_connection(self, connection: Any):
        """Close Redis connection"""
        await connection.close()

    async def _ping_connection(self, connection: Any) -> bool:
        """Ping Redis connection"""
        try:
            await connection.ping()
            return True
        except:
            return False


class QdrantConnectionPool(BaseConnectionPool):
    """Qdrant connection pool implementation"""

    def __init__(self, client: Any, pool_config: PoolConfiguration):
        super().__init__("qdrant", pool_config)
        self.client = client
        self.connection_semaphore = asyncio.Semaphore(pool_config.max_connections)

    async def _create_connection(self) -> Any:
        """Get Qdrant client (Qdrant client is thread-safe)"""
        return self.client

    async def _close_connection(self, connection: Any):
        """Qdrant client doesn't need explicit closing"""
        pass

    async def _ping_connection(self, connection: Any) -> bool:
        """Ping Qdrant client"""
        try:
            connection.get_collections()
            return True
        except:
            return False


class AdvancedConnectionPoolManager:
    """Advanced connection pool manager for all databases"""

    def __init__(self):
        self.pools: Dict[str, BaseConnectionPool] = {}
        self.metrics_history: List[Dict[str, Any]] = []
        self.is_initialized = False

    async def initialize(self, configs: Dict[str, Any]):
        """Initialize all connection pools"""
        # PostgreSQL pool
        if 'postgresql' in configs:
            pg_config = configs['postgresql']
            pool_config = PoolConfiguration(
                min_connections=10,
                max_connections=100,
                scaling_strategy=PoolScalingStrategy.AUTO_SCALING
            )
            pg_pool = PostgreSQLConnectionPool(pg_config, pool_config)
            await pg_pool.initialize()
            self.pools['postgresql'] = pg_pool

        # Neo4j pool
        if 'neo4j' in configs:
            neo4j_config = configs['neo4j']
            pool_config = PoolConfiguration(
                min_connections=5,
                max_connections=50,
                scaling_strategy=PoolScalingStrategy.DYNAMIC
            )
            neo4j_pool = Neo4jConnectionPool(neo4j_config, pool_config)
            await neo4j_pool.initialize()
            self.pools['neo4j'] = neo4j_pool

        # Redis pool
        if 'redis' in configs:
            redis_config = configs['redis']
            pool_config = PoolConfiguration(
                min_connections=20,
                max_connections=200,
                scaling_strategy=PoolScalingStrategy.AUTO_SCALING
            )
            redis_pool = RedisConnectionPool(redis_config, pool_config)
            await redis_pool.initialize()
            self.pools['redis'] = redis_pool

        # Qdrant pool (shared client)
        if 'qdrant' in configs:
            qdrant_client = configs['qdrant']
            pool_config = PoolConfiguration(
                min_connections=5,
                max_connections=20,
                scaling_strategy=PoolScalingStrategy.FIXED
            )
            qdrant_pool = QdrantConnectionPool(qdrant_client, pool_config)
            await qdrant_pool.initialize()
            self.pools['qdrant'] = qdrant_pool

        self.is_initialized = True
        logger.info(f"Advanced connection pool manager initialized with {len(self.pools)} pools")

    async def get_connection(self, database_type: str) -> ManagedConnection:
        """Get connection from specified pool"""
        if database_type not in self.pools:
            raise ValueError(f"No pool configured for database type: {database_type}")
        return await self.pools[database_type].get_connection()

    async def return_connection(self, database_type: str, connection: ManagedConnection):
        """Return connection to specified pool"""
        if database_type in self.pools:
            await self.pools[database_type].return_connection(connection)

    async def get_all_metrics(self) -> Dict[str, Any]:
        """Get metrics from all pools"""
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'pools': {}
        }

        total_connections = 0
        total_active = 0
        total_requests = 0
        total_failed = 0

        for pool_id, pool in self.pools.items():
            pool.update_metrics()
            pool_metrics = asdict(pool.metrics)
            metrics['pools'][pool_id] = pool_metrics

            total_connections += pool_metrics['total_connections']
            total_active += pool_metrics['active_connections']
            total_requests += pool_metrics['total_requests']
            total_failed += pool_metrics['failed_requests']

        # Calculate overall metrics
        metrics['overall'] = {
            'total_connections': total_connections,
            'total_active_connections': total_active,
            'total_requests': total_requests,
            'total_failed_requests': total_failed,
            'overall_success_rate': ((total_requests - total_failed) / total_requests * 100) if total_requests > 0 else 0,
            'active_pools': len(self.pools)
        }

        # Store in history
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > 1000:  # Keep last 1000 measurements
            self.metrics_history.pop(0)

        return metrics

    async def optimize_all_pools(self) -> Dict[str, Any]:
        """Run optimization on all pools"""
        optimization_results = {}

        for pool_id, pool in self.pools.items():
            try:
                # Trigger immediate cleanup and scaling
                await pool._cleanup_old_connections()
                await pool._adjust_pool_size()
                optimization_results[pool_id] = {'success': True}
            except Exception as e:
                optimization_results[pool_id] = {'success': False, 'error': str(e)}

        return optimization_results

    async def shutdown_all(self):
        """Shutdown all connection pools"""
        for pool_id, pool in self.pools.items():
            try:
                await pool.shutdown()
                logger.info(f"Shutdown pool {pool_id}")
            except Exception as e:
                logger.error(f"Error shutting down pool {pool_id}: {e}")

        self.pools.clear()
        self.is_initialized = False
        logger.info("All connection pools shutdown")


# Utility functions
async def create_production_pool_manager() -> AdvancedConnectionPoolManager:
    """Create production-ready pool manager with optimized configurations"""
    manager = AdvancedConnectionPoolManager()

    # Production configurations
    configs = {
        'postgresql': DatabaseConfig(
            host="localhost",
            port=5432,
            user="raguser",
            password="rag_password_123",
            database="ragdb",
            optimization_level=OptimizationLevel.PRODUCTION
        ),
        'neo4j': Neo4jConfig(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="neo4j_password_123",
            optimization_level=Neo4jOptimizationLevel.PRODUCTION
        ),
        'redis': RedisConfig(
            host="localhost",
            port=6379,
            password="redis_password_123",
            optimization_level=RedisOptimizationLevel.PRODUCTION
        ),
        # Qdrant client would be passed separately
    }

    await manager.initialize(configs)
    return manager