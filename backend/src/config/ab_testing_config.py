"""
A/B Testing System Configuration

Configuration settings for the A/B testing system optimized for
high-volume Multimodal Enterprise RAG deployments.
"""

import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, List

from .database_config import DatabaseSettings

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Environment types for A/B testing"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class CacheSettings:
    """Redis cache configuration"""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = None
    max_connections: int = 100
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    health_check_interval: int = 30


@dataclass
class PerformanceSettings:
    """Performance optimization settings"""

    # Batch processing
    batch_size: int = 1000
    batch_flush_interval: int = 30  # seconds
    max_batch_memory_mb: int = 100

    # Connection pooling
    db_pool_size: int = 20
    db_max_overflow: int = 30
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600

    # Metrics collection
    metrics_buffer_size: int = 10000
    metrics_flush_interval: int = 10  # seconds
    async_metrics_workers: int = 4

    # Caching
    default_cache_ttl: int = 300  # seconds
    dashboard_cache_ttl: int = 60  # seconds
    assignment_cache_ttl: int = 1800  # seconds

    # Query optimization
    query_timeout: int = 30  # seconds
    slow_query_threshold: int = 1000  # milliseconds


@dataclass
class StatisticalSettings:
    """Statistical analysis configuration"""

    # Default significance levels
    default_confidence_level: float = 0.95
    default_power_level: float = 0.80
    default_minimum_effect_size: float = 0.10  # 10% minimum detectable effect

    # Sample size calculations
    minimum_sample_size: int = 1000
    maximum_sample_size: int = 100000
    sample_size_calculation_method: str = "normal_approximation"

    # Multiple testing correction
    multiple_testing_correction: str = (
        "bonferroni"  # bonferroni, holm, benjamini_hochberg
    )
    family_wise_error_rate: float = 0.05

    # Automated stopping rules
    enable_early_stopping: bool = True
    early_stopping_alpha: float = 0.01
    early_stopping_effect_size: float = 0.20  # 20% effect size for early stopping

    # Analysis methods
    default_statistical_test: str = "two_sample_t_test"
    enable_bayesian_analysis: bool = True
    bayesian_prior_type: str = "jeffreys"  # jeffreys, uniform, informative


@dataclass
class ExperimentSettings:
    """Experiment management configuration"""

    # Traffic allocation
    default_traffic_percentage: float = 100.0
    maximum_traffic_percentage: float = 100.0
    traffic_change_cooldown: int = 3600  # seconds

    # Experiment duration
    minimum_duration_hours: int = 24
    maximum_duration_days: int = 90
    default_duration_days: int = 14

    # Variant management
    maximum_variants_per_experiment: int = 10
    require_control_variant: bool = True
    control_variant_weight: float = 1.0

    # Targeting and segmentation
    enable_user_segmentation: bool = True
    maximum_segments_per_experiment: int = 50
    segment_update_interval: int = 3600  # seconds

    # Success criteria
    default_primary_metric: str = "relevance_score"
    minimum_conversion_rate: float = 0.01  # 1% minimum conversion
    maximum_p_value_for_significance: float = 0.05


@dataclass
class SecuritySettings:
    """Security and privacy configuration"""

    # Data retention
    metrics_retention_days: int = 365
    assignment_retention_days: int = 730
    dashboard_data_retention_days: int = 90

    # Anonymization
    enable_user_anonymization: bool = True
    anonymization_method: str = "hash"  # hash, tokenization
    retain_pseudonym_mapping: bool = False

    # Access control
    require_experiment_approval: bool = True
    experiment_approval_roles: List[str] = None
    enable_experiment_auditing: bool = True

    # Rate limiting
    api_rate_limit_per_minute: int = 1000
    dashboard_rate_limit_per_minute: int = 100

    def __post_init__(self):
        if self.experiment_approval_roles is None:
            self.experiment_approval_roles = ["admin", "analyst"]


@dataclass
class MonitoringSettings:
    """Monitoring and alerting configuration"""

    # Performance monitoring
    enable_performance_monitoring: bool = True
    slow_query_threshold_ms: int = 1000
    memory_usage_threshold_mb: int = 1024
    cpu_usage_threshold_percent: float = 80.0

    # Metrics collection
    collect_system_metrics: bool = True
    collect_application_metrics: bool = True
    collect_business_metrics: bool = True
    metrics_collection_interval: int = 60  # seconds

    # Alerting
    enable_alerting: bool = True
    alert_webhook_url: str = None
    alert_email_recipients: List[str] = None
    alert_cooldown_minutes: int = 15

    # Health checks
    enable_health_checks: bool = True
    health_check_interval: int = 30  # seconds
    health_check_timeout: int = 5  # seconds

    def __post_init__(self):
        if self.alert_email_recipients is None:
            self.alert_email_recipients = []


class ABTestingConfig:
    """
    Main configuration class for the A/B testing system
    """

    def __init__(self, environment: Environment = Environment.PRODUCTION):
        self.environment = environment

        # Load base configuration
        self.cache = CacheSettings()
        self.performance = PerformanceSettings()
        self.statistical = StatisticalSettings()
        self.experiment = ExperimentSettings()
        self.security = SecuritySettings()
        self.monitoring = MonitoringSettings()
        self.database = DatabaseSettings()

        # Apply environment-specific overrides
        self._apply_environment_overrides()

        # Apply runtime environment variable overrides
        self._apply_env_overrides()

    def _apply_environment_overrides(self):
        """Apply environment-specific configuration overrides"""

        if self.environment == Environment.DEVELOPMENT:
            # Development environment - relaxed settings
            self.performance.batch_size = 100
            self.performance.default_cache_ttl = 60
            self.experiment.minimum_duration_hours = 1
            self.statistical.minimum_sample_size = 100
            self.statistical.default_confidence_level = 0.90

        elif self.environment == Environment.STAGING:
            # Staging environment - production-like settings with smaller scale
            self.performance.batch_size = 500
            self.performance.db_pool_size = 10
            self.experiment.minimum_duration_hours = 4
            self.statistical.minimum_sample_size = 500

        elif self.environment == Environment.PRODUCTION:
            # Production environment - optimized for performance and reliability
            self.performance.batch_size = 1000
            self.performance.db_pool_size = 20
            self.performance.max_batch_memory_mb = 200
            self.monitoring.enable_alerting = True
            self.security.require_experiment_approval = True

    def _apply_env_overrides(self):
        """Apply runtime environment variable overrides"""

        def _parse_numeric(env_var: str, current_value, caster):
            raw_value = os.getenv(env_var)
            if raw_value is None:
                return current_value
            try:
                return caster(raw_value)
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid value for %s=%s; retaining default %s",
                    env_var,
                    raw_value,
                    current_value,
                )
                return current_value

        # Cache settings
        self.cache.host = os.getenv("REDIS_HOST", self.cache.host)
        self.cache.port = _parse_numeric("REDIS_PORT", self.cache.port, int)
        self.cache.password = os.getenv("REDIS_PASSWORD", self.cache.password)

        # Database settings
        self.database.host = os.getenv("DB_HOST", self.database.host)
        self.database.port = _parse_numeric("DB_PORT", self.database.port, int)
        self.database.username = os.getenv("DB_USERNAME", self.database.username)
        self.database.password = os.getenv("DB_PASSWORD", self.database.password)

        # Performance settings
        self.performance.batch_size = _parse_numeric(
            "AB_BATCH_SIZE", self.performance.batch_size, int
        )
        self.performance.default_cache_ttl = _parse_numeric(
            "AB_CACHE_TTL", self.performance.default_cache_ttl, int
        )

        # Statistical settings
        self.statistical.default_confidence_level = _parse_numeric(
            "AB_CONFIDENCE_LEVEL", self.statistical.default_confidence_level, float
        )

        # Security settings
        self.security.metrics_retention_days = _parse_numeric(
            "AB_METRICS_RETENTION_DAYS", self.security.metrics_retention_days, int
        )

        # Monitoring settings
        self.monitoring.slow_query_threshold_ms = _parse_numeric(
            "AB_SLOW_QUERY_THRESHOLD", self.monitoring.slow_query_threshold_ms, int
        )

    def get_redis_url(self) -> str:
        """Get Redis connection URL"""
        auth_part = f":{self.cache.password}@" if self.cache.password else ""
        return f"redis://{auth_part}{self.cache.host}:{self.cache.port}/{self.cache.db}"

    def get_database_url(self) -> str:
        """Get database connection URL"""
        return self.database.get_url()

    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == Environment.DEVELOPMENT

    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration as dictionary"""
        return {
            "host": self.cache.host,
            "port": self.cache.port,
            "db": self.cache.db,
            "password": self.cache.password,
            "max_connections": self.cache.max_connections,
            "socket_timeout": self.cache.socket_timeout,
            "socket_connect_timeout": self.cache.socket_connect_timeout,
            "retry_on_timeout": self.cache.retry_on_timeout,
            "health_check_interval": self.cache.health_check_interval,
        }

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration as dictionary"""
        return {
            "url": self.get_database_url(),
            "pool_size": self.performance.db_pool_size,
            "max_overflow": self.performance.db_max_overflow,
            "pool_timeout": self.performance.db_pool_timeout,
            "pool_recycle": self.performance.db_pool_recycle,
            "echo": self.is_development(),  # SQL logging in development
        }

    def get_statistical_config(self) -> Dict[str, Any]:
        """Get statistical analysis configuration"""
        return {
            "confidence_level": self.statistical.default_confidence_level,
            "power_level": self.statistical.default_power_level,
            "minimum_effect_size": self.statistical.default_minimum_effect_size,
            "minimum_sample_size": self.statistical.minimum_sample_size,
            "maximum_sample_size": self.statistical.maximum_sample_size,
            "multiple_testing_correction": self.statistical.multiple_testing_correction,
            "family_wise_error_rate": self.statistical.family_wise_error_rate,
            "enable_early_stopping": self.statistical.enable_early_stopping,
            "early_stopping_alpha": self.statistical.early_stopping_alpha,
            "default_test": self.statistical.default_statistical_test,
            "enable_bayesian": self.statistical.enable_bayesian_analysis,
        }

    def get_performance_config(self) -> Dict[str, Any]:
        """Get performance optimization configuration"""
        return {
            "batch_size": self.performance.batch_size,
            "batch_flush_interval": self.performance.batch_flush_interval,
            "max_batch_memory_mb": self.performance.max_batch_memory_mb,
            "metrics_buffer_size": self.performance.metrics_buffer_size,
            "metrics_flush_interval": self.performance.metrics_flush_interval,
            "async_metrics_workers": self.performance.async_metrics_workers,
            "default_cache_ttl": self.performance.default_cache_ttl,
            "dashboard_cache_ttl": self.performance.dashboard_cache_ttl,
            "assignment_cache_ttl": self.performance.assignment_cache_ttl,
            "query_timeout": self.performance.query_timeout,
            "slow_query_threshold": self.performance.slow_query_threshold,
        }

    def validate_configuration(self) -> List[str]:
        """
        Validate configuration settings
        Returns list of validation errors
        """
        errors = []

        # Validate statistical settings
        if not (0 < self.statistical.default_confidence_level < 1):
            errors.append("Confidence level must be between 0 and 1")

        if not (0 < self.statistical.default_power_level < 1):
            errors.append("Power level must be between 0 and 1")

        if self.statistical.minimum_sample_size < 30:
            errors.append(
                "Minimum sample size should be at least 30 for statistical validity"
            )

        # Validate experiment settings
        if not (0 < self.experiment.default_traffic_percentage <= 100):
            errors.append("Default traffic percentage must be between 0 and 100")

        if self.experiment.minimum_duration_hours < 1:
            errors.append("Minimum duration should be at least 1 hour")

        # Validate performance settings
        if self.performance.batch_size < 1:
            errors.append("Batch size must be at least 1")

        if self.performance.default_cache_ttl < 0:
            errors.append("Cache TTL cannot be negative")

        # Validate security settings
        if self.security.metrics_retention_days < 1:
            errors.append("Metrics retention period must be at least 1 day")

        return errors

    def __str__(self) -> str:
        """String representation of configuration"""
        return (
            f"ABTestingConfig(environment={self.environment.value}, "
            f"cache_ttl={self.performance.default_cache_ttl}s, "
            f"batch_size={self.performance.batch_size}, "
            f"confidence_level={self.statistical.default_confidence_level})"
        )


# Global configuration instance
def get_config(environment: Environment = None) -> ABTestingConfig:
    """
    Get A/B testing configuration instance
    """
    if environment is None:
        env_name = os.getenv("AB_TESTING_ENV", "production").lower()
        environment = (
            Environment(env_name)
            if env_name in [e.value for e in Environment]
            else Environment.PRODUCTION
        )

    return ABTestingConfig(environment)


# Configuration presets for common use cases
def get_high_volume_config() -> ABTestingConfig:
    """
    Get configuration optimized for high-volume scenarios
    (>10,000 queries per hour)
    """
    config = ABTestingConfig(Environment.PRODUCTION)

    # Optimize for high throughput
    config.performance.batch_size = 2000
    config.performance.db_pool_size = 50
    config.performance.db_max_overflow = 100
    config.performance.metrics_buffer_size = 50000
    config.performance.async_metrics_workers = 8

    # Aggressive caching
    config.performance.default_cache_ttl = 600
    config.performance.dashboard_cache_ttl = 120

    # Relaxed statistical requirements for faster convergence
    config.statistical.minimum_sample_size = 500
    config.statistical.enable_early_stopping = True
    config.statistical.early_stopping_alpha = 0.05

    return config


def get_low_latency_config() -> ABTestingConfig:
    """
    Get configuration optimized for minimal latency
    (sub-5ms query routing)
    """
    config = ABTestingConfig(Environment.PRODUCTION)

    # Maximum caching
    config.performance.default_cache_ttl = 1800
    config.performance.assignment_cache_ttl = 3600

    # Smaller batches for faster processing
    config.performance.batch_size = 100
    config.performance.batch_flush_interval = 5

    # Simplified statistical analysis
    config.statistical.default_statistical_test = "z_test"
    config.statistical.enable_bayesian_analysis = False

    # Pre-warm all caches
    config.cache.max_connections = 200

    return config


def get_research_config() -> ABTestingConfig:
    """
    Get configuration optimized for research and experimentation
    (focus on statistical rigor over speed)
    """
    config = ABTestingConfig(Environment.STAGING)

    # Strict statistical requirements
    config.statistical.default_confidence_level = 0.99
    config.statistical.default_power_level = 0.90
    config.statistical.minimum_sample_size = 5000
    config.statistical.enable_bayesian_analysis = True
    config.statistical.multiple_testing_correction = "holm"

    # Longer experiments for better data
    config.experiment.minimum_duration_hours = 168  # 1 week
    config.experiment.default_duration_days = 30

    # Minimal caching for fresh data
    config.performance.default_cache_ttl = 60
    config.performance.dashboard_cache_ttl = 30

    return config
