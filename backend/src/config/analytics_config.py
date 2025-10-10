"""
Analytics-specific configuration settings
Provides environment-based configuration for T3 analytics system
"""

import os
from typing import Dict, Any, Optional, List
from pydantic import field_validator, BaseModel
from pydantic_settings import BaseSettings
from enum import Enum


class AnalyticsEnvironment(str, Enum):
    """Analytics deployment environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DataRetentionConfig(BaseModel):
    """Data retention policy configuration"""

    # Retention periods in days
    search_queries_retention_days: int = 365
    user_sessions_retention_days: int = 180
    performance_logs_retention_days: int = 90
    analytics_events_retention_days: int = 365
    quality_metrics_retention_days: int = 730

    # Privacy settings
    anonymize_after_days: int = 90
    delete_pii_after_days: int = 2555  # 7 years

    # Data cleanup settings
    cleanup_batch_size: int = 1000
    cleanup_interval_hours: int = 24


class AnalyticsCacheConfig(BaseModel):
    """Analytics caching configuration"""

    # Cache TTL in seconds
    metrics_cache_ttl: int = 300  # 5 minutes
    reports_cache_ttl: int = 3600  # 1 hour
    dashboard_cache_ttl: int = 180  # 3 minutes

    # Cache size limits
    max_cache_size_mb: int = 100
    max_cache_entries: int = 10000

    # Cache invalidation
    invalidate_on_data_update: bool = True
    background_refresh_enabled: bool = True


class AnalyticsRateLimitConfig(BaseModel):
    """Analytics rate limiting configuration"""

    # Rate limits per role (requests per hour)
    user_rate_limit: int = 100
    analyst_rate_limit: int = 500
    content_manager_rate_limit: int = 1000
    admin_rate_limit: int = 2000

    # Special operation limits
    heavy_operation_limit: int = 10  # per hour
    export_limit: int = 20  # per hour
    api_call_limit: int = 50  # per 5 minutes

    # Rate limiting windows (in seconds)
    default_window: int = 3600  # 1 hour
    api_call_window: int = 300  # 5 minutes


class AnalyticsPerformanceConfig(BaseModel):
    """Analytics performance configuration"""

    # Query optimization
    max_query_time_seconds: int = 30
    query_timeout_seconds: int = 60
    max_concurrent_queries: int = 10

    # Background processing
    enable_async_processing: bool = True
    processing_queue_size: int = 1000
    worker_pool_size: int = 4

    # Memory management
    max_memory_usage_mb: int = 512
    enable_query_caching: bool = True
    result_batch_size: int = 1000


class AnalyticsReportingConfig(BaseModel):
    """Analytics reporting configuration"""

    # Report generation
    max_report_size_mb: int = 50
    default_report_format: str = "json"
    supported_export_formats: List[str] = ["json", "csv", "excel", "pdf"]

    # Scheduled reports
    enable_scheduled_reports: bool = True
    max_scheduled_reports: int = 50
    report_retention_days: int = 30

    # Email notifications
    enable_email_notifications: bool = True
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None


class AnalyticsPrivacyConfig(BaseModel):
    """Analytics privacy and compliance configuration"""

    # GDPR compliance
    enable_gdpr_compliance: bool = True
    cookie_consent_required: bool = True
    data_processing_consent_required: bool = True

    # Anonymization settings
    enable_data_anonymization: bool = True
    anonymize_ip_addresses: bool = True
    anonymize_user_agents: bool = True
    hash_user_ids: bool = True

    # Data subject rights
    enable_data_export: bool = True
    enable_data_deletion: bool = True
    enable_data_correction: bool = True

    # Regional compliance
    regional_data_retention: Dict[str, int] = {
        "EU": 2555,  # 7 years for GDPR
        "US": 1825,  # 5 years for CCPA
        "DEFAULT": 1095  # 3 years default
    }


class AnalyticsMonitoringConfig(BaseModel):
    """Analytics monitoring and alerting configuration"""

    # Health checks
    enable_health_checks: bool = True
    health_check_interval_seconds: int = 60

    # Metrics collection
    enable_metrics_collection: bool = True
    metrics_interval_seconds: int = 30

    # Alerting thresholds
    response_time_warning_threshold_ms: int = 1000
    response_time_critical_threshold_ms: int = 5000
    error_rate_warning_threshold: float = 0.05  # 5%
    error_rate_critical_threshold: float = 0.10  # 10%

    # External monitoring
    prometheus_enabled: bool = False
    prometheus_port: int = 9090
    grafana_enabled: bool = False


class AnalyticsConfig(BaseSettings):
    """Main analytics configuration"""

    # Environment settings
    analytics_environment: AnalyticsEnvironment = AnalyticsEnvironment.DEVELOPMENT
    analytics_enabled: bool = True
    debug_mode: bool = False

    # Database settings
    analytics_db_schema: str = "analytics"
    analytics_connection_pool_size: int = 10
    analytics_connection_timeout: int = 30

    # Feature flags
    enable_user_behavior_analytics: bool = True
    enable_quality_metrics: bool = True
    enable_performance_monitoring: bool = True
    enable_advanced_analytics: bool = False

    # Sub-configurations
    retention: DataRetentionConfig = DataRetentionConfig()
    cache: AnalyticsCacheConfig = AnalyticsCacheConfig()
    rate_limiting: AnalyticsRateLimitConfig = AnalyticsRateLimitConfig()
    performance: AnalyticsPerformanceConfig = AnalyticsPerformanceConfig()
    reporting: AnalyticsReportingConfig = AnalyticsReportingConfig()
    privacy: AnalyticsPrivacyConfig = AnalyticsPrivacyConfig()
    monitoring: AnalyticsMonitoringConfig = AnalyticsMonitoringConfig()

    # External service settings
    redis_analytics_url: Optional[str] = None
    elasticsearch_url: Optional[str] = None
    time_series_db_url: Optional[str] = None

    # Security settings
    enable_access_logging: bool = True
    audit_log_retention_days: int = 2555
    session_timeout_minutes: int = 30

    # Development settings
    mock_external_services: bool = False
    enable_test_endpoints: bool = False
    test_data_generation_enabled: bool = False

    @field_validator("analytics_environment")
    @classmethod
    def validate_environment(cls, v):
        if v not in AnalyticsEnvironment:
            raise ValueError(f"Invalid analytics environment: {v}")
        return v

    @field_validator("analytics_connection_pool_size")
    @classmethod
    def validate_pool_size(cls, v):
        if v < 1 or v > 100:
            raise ValueError("Analytics connection pool size must be between 1 and 100")
        return v

    @field_validator("performance")
    @classmethod
    def validate_performance_config(cls, v):
        if v.max_query_time_seconds <= 0:
            raise ValueError("Max query time must be positive")
        if v.max_concurrent_queries < 1:
            raise ValueError("Max concurrent queries must be at least 1")
        return v

    def get_environment_config(self) -> Dict[str, Any]:
        """Get environment-specific configuration"""
        env_configs = {
            AnalyticsEnvironment.DEVELOPMENT: {
                "debug_mode": True,
                "enable_test_endpoints": True,
                "test_data_generation_enabled": True,
                "cache": {"metrics_cache_ttl": 60, "reports_cache_ttl": 300},
                "monitoring": {"enable_metrics_collection": True, "health_check_interval_seconds": 30}
            },
            AnalyticsEnvironment.STAGING: {
                "debug_mode": False,
                "enable_test_endpoints": False,
                "test_data_generation_enabled": False,
                "cache": {"metrics_cache_ttl": 180, "reports_cache_ttl": 1800},
                "monitoring": {"enable_metrics_collection": True, "health_check_interval_seconds": 60}
            },
            AnalyticsEnvironment.PRODUCTION: {
                "debug_mode": False,
                "enable_test_endpoints": False,
                "test_data_generation_enabled": False,
                "cache": {"metrics_cache_ttl": 300, "reports_cache_ttl": 3600},
                "monitoring": {"enable_metrics_collection": True, "health_check_interval_seconds": 60}
            }
        }

        return env_configs.get(self.analytics_environment, env_configs[AnalyticsEnvironment.DEVELOPMENT])

    def apply_environment_overrides(self):
        """Apply environment-specific configuration overrides"""
        env_config = self.get_environment_config()

        for key, value in env_config.items():
            if hasattr(self, key):
                setattr(self, key, value)
            elif hasattr(self, key.replace('_', '')):
                setattr(self, key.replace('_', ''), value)

    def get_retention_policy(self, data_type: str, region: str = "DEFAULT") -> int:
        """Get retention period for a specific data type and region"""
        base_retention = getattr(self.retention, f"{data_type}_retention_days", 365)
        regional_multiplier = self.privacy.regional_data_retention.get(region, 365)
        return min(base_retention, regional_multiplier)

    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a specific analytics feature is enabled"""
        feature_attr = f"enable_{feature_name}"
        return getattr(self, feature_attr, False)

    def get_rate_limit(self, user_role: str, operation_type: str = "default") -> int:
        """Get rate limit for a specific user role and operation type"""
        if operation_type == "heavy":
            return self.rate_limiting.heavy_operation_limit
        elif operation_type == "export":
            return self.rate_limiting.export_limit
        elif operation_type == "api_call":
            return self.rate_limiting.api_call_limit
        else:
            return getattr(self.rate_limiting, f"{user_role}_rate_limit", 100)

    class Config:
        env_file = ".env"
        env_prefix = "ANALYTICS_"
        case_sensitive = True
        extra = "allow"  # Allow additional fields from environment


# Create global analytics configuration instance
analytics_config = AnalyticsConfig()

# Apply environment-specific overrides
analytics_config.apply_environment_overrides()


def get_analytics_config() -> AnalyticsConfig:
    """Get the global analytics configuration"""
    return analytics_config


def reload_analytics_config() -> AnalyticsConfig:
    """Reload analytics configuration from environment"""
    global analytics_config
    analytics_config = AnalyticsConfig()
    analytics_config.apply_environment_overrides()
    return analytics_config