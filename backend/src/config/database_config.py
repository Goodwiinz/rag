"""
Database configuration for analytics system
Provides database-specific settings and connection management
"""

import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings


class DatabaseConnectionConfig(BaseModel):
    """Database connection configuration"""

    # Connection settings
    host: str = "localhost"
    port: int = 5432
    database: str = "multimodal_rag_dev"
    username: str = "postgres"
    password: str = "postgres"
    schema: str = "public"

    # Connection pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600

    # SSL settings
    ssl_mode: str = "prefer"
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None
    ssl_ca: Optional[str] = None

    # Connection timeout settings
    connect_timeout: int = 10
    command_timeout: int = 30

    @property
    def connection_url(self) -> str:
        """Generate database connection URL"""
        if self.password:
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            return (
                f"postgresql://{self.username}@{self.host}:{self.port}/{self.database}"
            )

    @field_validator("port")
    @classmethod
    def validate_port(cls, v):
        if v < 1 or v > 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @field_validator("pool_size")
    @classmethod
    def validate_pool_size(cls, v):
        if v < 1 or v > 100:
            raise ValueError("Pool size must be between 1 and 100")
        return v


class AnalyticsDatabaseConfig(BaseModel):
    """Analytics-specific database configuration"""

    # Analytics database settings
    analytics_schema: str = "analytics"
    enable_time_series_optimization: bool = True
    enable_partitioning: bool = True

    # Table optimization settings
    enable_auto_vacuum: bool = True
    vacuum_threshold: float = 0.2  # 20% dead tuples
    analyze_threshold: float = 0.1  # 10% data change

    # Index management
    enable_auto_index_creation: bool = True
    index_fill_factor: float = 0.9
    enable_concurrent_index_builds: bool = True

    # Query optimization
    enable_query_cache: bool = True
    query_cache_size_mb: int = 64
    enable_parallel_queries: bool = True
    max_parallel_workers: int = 4

    # Partitioning settings
    partition_by_time: bool = True
    partition_granularity: str = "monthly"  # daily, weekly, monthly
    partition_retention_months: int = 24

    # Replication settings (if applicable)
    enable_read_replicas: bool = False
    replica_hosts: list = []
    replica_pool_size: int = 5

    def get_table_settings(self, table_name: str) -> Dict[str, Any]:
        """Get table-specific settings"""
        table_settings = {
            "user_sessions": {
                "partition_key": "created_at",
                "partition_granularity": "weekly",
                "retention_months": 6,
                "vacuum_threshold": 0.15,
                "enable_compression": True,
            },
            "analytics_events": {
                "partition_key": "event_timestamp",
                "partition_granularity": "daily",
                "retention_months": 12,
                "vacuum_threshold": 0.2,
                "enable_compression": True,
            },
            "performance_logs": {
                "partition_key": "timestamp",
                "partition_granularity": "weekly",
                "retention_months": 3,
                "vacuum_threshold": 0.1,
                "enable_compression": True,
            },
            "search_queries": {
                "partition_key": "created_at",
                "partition_granularity": "monthly",
                "retention_months": 24,
                "vacuum_threshold": 0.25,
                "enable_compression": False,
            },
        }

        return table_settings.get(
            table_name,
            {
                "partition_key": "created_at",
                "partition_granularity": self.partition_granularity,
                "retention_months": self.partition_retention_months,
                "vacuum_threshold": self.vacuum_threshold,
                "enable_compression": True,
            },
        )


class CacheDatabaseConfig(BaseModel):
    """Cache database configuration (Redis/Memcached)"""

    # Redis settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_ssl: bool = False

    # Redis connection pool
    redis_pool_size: int = 10
    redis_max_connections: int = 50

    # Redis cluster settings (if applicable)
    redis_cluster_enabled: bool = False
    redis_cluster_nodes: list = []

    # Cache settings
    default_ttl: int = 3600  # 1 hour
    max_memory_mb: int = 256
    eviction_policy: str = "allkeys-lru"

    @property
    def redis_url(self) -> str:
        """Generate Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


class TimeSeriesDatabaseConfig(BaseModel):
    """Time series database configuration (InfluxDB/Prometheus)"""

    # Time series database settings
    tsdb_enabled: bool = False
    tsdb_type: str = "influxdb"  # influxdb, prometheus, timescaledb
    tsdb_host: str = "localhost"
    tsdb_port: int = 8086
    tsdb_database: str = "analytics"
    tsdb_username: Optional[str] = None
    tsdb_password: Optional[str] = None

    # Retention settings
    tsdb_retention_days: int = 90
    tsdb_shard_duration: str = "1d"
    tsdb_replication_factor: int = 1

    # Performance settings
    tsdb_max_series_per_database: int = 1000000
    tsdb_max_values_per_tag: int = 100000
    tsdb_query_timeout: int = 60

    @property
    def tsdb_url(self) -> str:
        """Generate time series database URL"""
        if self.tsdb_type == "influxdb":
            if self.tsdb_password:
                return f"http://{self.tsdb_username}:{self.tsdb_password}@{self.tsdb_host}:{self.tsdb_port}"
            else:
                return f"http://{self.tsdb_host}:{self.tsdb_port}"
        elif self.tsdb_type == "prometheus":
            return f"http://{self.tsdb_host}:{self.tsdb_port}"
        else:
            return f"{self.tsdb_type}://{self.tsdb_host}:{self.tsdb_port}"


class DatabaseConfig(BaseSettings):
    """Main database configuration"""

    # Primary database
    primary: DatabaseConnectionConfig = DatabaseConnectionConfig()
    analytics: AnalyticsDatabaseConfig = AnalyticsDatabaseConfig()
    cache: CacheDatabaseConfig = CacheDatabaseConfig()
    time_series: TimeSeriesDatabaseConfig = TimeSeriesDatabaseConfig()

    # Migration settings
    enable_auto_migrations: bool = False
    migration_timeout: int = 300  # 5 minutes
    backup_before_migration: bool = True

    # Health check settings
    enable_health_checks: bool = True
    health_check_interval: int = 30  # seconds
    health_check_timeout: int = 5

    # Connection retry settings
    max_retry_attempts: int = 3
    retry_delay: int = 1  # seconds
    exponential_backoff: bool = True

    # Security settings
    enable_connection_logging: bool = True
    log_slow_queries: bool = True
    slow_query_threshold: int = 1000  # milliseconds

    def get_analytics_connection_url(self) -> str:
        """Get analytics database connection URL with schema"""
        base_url = self.primary.connection_url
        if self.analytics.analytics_schema != "public":
            return (
                f"{base_url}?options=--search_path%3D{self.analytics.analytics_schema}"
            )
        return base_url

    def get_connection_pool_config(self) -> Dict[str, Any]:
        """Get connection pool configuration"""
        return {
            "pool_size": self.primary.pool_size,
            "max_overflow": self.primary.max_overflow,
            "pool_timeout": self.primary.pool_timeout,
            "pool_recycle": self.primary.pool_recycle,
            "pool_pre_ping": True,
            "echo": False,
        }

    def get_ssl_config(self) -> Dict[str, Any]:
        """Get SSL configuration"""
        ssl_config = {"sslmode": self.analytics.ssl_mode}

        if self.analytics.ssl_cert:
            ssl_config["sslcert"] = self.analytics.ssl_cert
        if self.analytics.ssl_key:
            ssl_config["sslkey"] = self.analytics.ssl_key
        if self.analytics.ssl_ca:
            ssl_config["sslrootcert"] = self.analytics.ssl_ca

        return ssl_config

    def get_redis_config(self) -> Dict[str, Any]:
        """Get Redis configuration"""
        return {
            "host": self.cache.redis_host,
            "port": self.cache.redis_port,
            "db": self.cache.redis_db,
            "password": self.cache.redis_password,
            "ssl": self.cache.redis_ssl,
            "max_connections": self.cache.redis_max_connections,
            "decode_responses": True,
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
            "retry_on_timeout": True,
        }

    def should_enable_read_replicas(self) -> bool:
        """Check if read replicas should be enabled"""
        return (
            self.analytics.enable_read_replicas
            and len(self.analytics.replica_hosts) > 0
        )

    def get_replica_configs(self) -> list:
        """Get configurations for read replicas"""
        if not self.should_enable_read_replicas():
            return []

        replica_configs = []
        for host in self.analytics.replica_hosts:
            replica_config = self.primary.model_copy()
            replica_config.host = host
            replica_config.pool_size = self.analytics.replica_pool_size
            replica_configs.append(replica_config)

        return replica_configs

    class Config:
        env_file = ".env"
        env_prefix = "DB_"
        case_sensitive = True
        extra = "allow"


# Create global database configuration instance
database_config = DatabaseConfig()


def get_database_config() -> DatabaseConfig:
    """Get the global database configuration"""
    return database_config


def get_analytics_db_config() -> AnalyticsDatabaseConfig:
    """Get analytics database configuration"""
    return database_config.analytics


def get_cache_config() -> CacheDatabaseConfig:
    """Get cache database configuration"""
    return database_config.cache


def reload_database_config() -> DatabaseConfig:
    """Reload database configuration from environment"""
    global database_config
    database_config = DatabaseConfig()
    return database_config
