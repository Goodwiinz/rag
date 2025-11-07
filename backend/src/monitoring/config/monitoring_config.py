"""
Monitoring Configuration Management

Configuration settings for monitoring and observability services.
"""

import os
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


class MetricsConfig(BaseModel):
    """Configuration for metrics collection"""

    # Prometheus configuration
    prometheus_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    prometheus_port: int = Field(default=8000, description="Prometheus metrics port")
    prometheus_path: str = Field(default="/metrics", description="Prometheus metrics endpoint")

    # Custom metrics
    custom_metrics_enabled: bool = Field(default=True, description="Enable custom business metrics")
    metrics_retention_days: int = Field(default=30, description="Metrics retention period in days")

    # Collection intervals
    collection_interval_seconds: int = Field(default=30, description="Metrics collection interval")
    system_metrics_interval: int = Field(default=60, description="System metrics collection interval")
    application_metrics_interval: int = Field(default=30, description="Application metrics collection interval")

    # Business metrics
    track_rag_performance: bool = Field(default=True, description="Track RAG-specific performance metrics")
    track_user_behavior: bool = Field(default=True, description="Track user behavior metrics")
    track_content_processing: bool = Field(default=True, description="Track content processing metrics")


class TracingConfig(BaseModel):
    """Configuration for distributed tracing"""

    # OpenTelemetry configuration
    enabled: bool = Field(default=True, description="Enable distributed tracing")
    service_name: str = Field(default="rag-system", description="Service name for tracing")
    service_version: str = Field(default="1.0.0", description="Service version")

    # Sampling
    sampling_ratio: float = Field(default=0.1, ge=0.0, le=1.0, description="Sampling ratio for traces")
    trace_parent_span: bool = Field(default=True, description="Trace parent spans")

    # Exporters
    jaeger_enabled: bool = Field(default=True, description="Enable Jaeger exporter")
    jaeger_endpoint: str = Field(default="http://localhost:14268/api/traces", description="Jaeger collector endpoint")

    otlp_enabled: bool = Field(default=False, description="Enable OTLP exporter")
    otlp_endpoint: str = Field(default="http://localhost:4317", description="OTLP endpoint")
    otlp_headers: Dict[str, str] = Field(default_factory=dict, description="OTLP headers")

    # Instrumentation
    auto_instrumentation: bool = Field(default=True, description="Enable automatic instrumentation")
    instrument_fastapi: bool = Field(default=True, description="Instrument FastAPI")
    instrument_sqlalchemy: bool = Field(default=True, description="Instrument SQLAlchemy")
    instrument_redis: bool = Field(default=True, description="Instrument Redis")
    instrument_httpx: bool = Field(default=True, description="Instrument HTTP clients")


class LoggingConfig(BaseModel):
    """Configuration for structured logging"""

    # General settings
    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format (json or text)")
    structured_logging: bool = Field(default=True, description="Enable structured logging")

    # Log destinations
    console_logging: bool = Field(default=True, description="Enable console logging")
    file_logging: bool = Field(default=True, description="Enable file logging")
    log_file_path: str = Field(default="/app/logs/rag-system.log", description="Log file path")
    log_file_max_size: str = Field(default="100MB", description="Maximum log file size")
    log_file_backup_count: int = Field(default=5, description="Number of log file backups")

    # Elasticsearch integration
    elasticsearch_enabled: bool = Field(default=False, description="Enable Elasticsearch logging")
    elasticsearch_host: str = Field(default="localhost:9200", description="Elasticsearch host")
    elasticsearch_index: str = Field(default="rag-logs", description="Elasticsearch index name")

    # Log enrichment
    add_correlation_id: bool = Field(default=True, description="Add correlation IDs to logs")
    add_user_context: bool = Field(default=True, description="Add user context to logs")
    add_request_context: bool = Field(default=True, description="Add request context to logs")

    # Sensitive data
    mask_sensitive_data: bool = Field(default=True, description="Mask sensitive data in logs")
    sensitive_fields: List[str] = Field(default_factory=lambda: ["password", "token", "api_key", "secret"], description="Fields to mask")


class AlertingConfig(BaseModel):
    """Configuration for alerting"""

    # General settings
    enabled: bool = Field(default=True, description="Enable alerting")
    alert_cooldown_minutes: int = Field(default=5, description="Alert cooldown period in minutes")
    max_alerts_per_hour: int = Field(default=100, description="Maximum alerts per hour")

    # Alert channels
    email_enabled: bool = Field(default=False, description="Enable email alerts")
    email_smtp_host: str = Field(default="localhost", description="SMTP host")
    email_smtp_port: int = Field(default=587, description="SMTP port")
    email_username: str = Field(default="", description="SMTP username")
    email_password: str = Field(default="", description="SMTP password")
    email_recipients: List[str] = Field(default_factory=list, description="Email recipients")

    slack_enabled: bool = Field(default=False, description="Enable Slack alerts")
    slack_webhook_url: str = Field(default="", description="Slack webhook URL")
    slack_channel: str = Field(default="#alerts", description="Slack channel")

    webhook_enabled: bool = Field(default=False, description="Enable webhook alerts")
    webhook_url: str = Field(default="", description="Webhook URL")
    webhook_headers: Dict[str, str] = Field(default_factory=dict, description="Webhook headers")

    # Alert rules
    cpu_threshold_percent: float = Field(default=80.0, description="CPU usage alert threshold")
    memory_threshold_percent: float = Field(default=80.0, description="Memory usage alert threshold")
    disk_threshold_percent: float = Field(default=85.0, description="Disk usage alert threshold")
    error_rate_threshold: float = Field(default=5.0, description="Error rate alert threshold")
    response_time_threshold_ms: int = Field(default=2000, description="Response time alert threshold")


class HealthCheckConfig(BaseModel):
    """Configuration for health checks"""

    # General settings
    enabled: bool = Field(default=True, description="Enable health checks")
    check_interval_seconds: int = Field(default=30, description="Health check interval")
    timeout_seconds: int = Field(default=10, description="Health check timeout")

    # Component checks
    check_database: bool = Field(default=True, description="Check database health")
    check_redis: bool = Field(default=True, description="Check Redis health")
    check_neo4j: bool = Field(default=True, description="Check Neo4j health")
    check_qdrant: bool = Field(default=True, description="Check Qdrant health")
    check_external_apis: bool = Field(default=True, description="Check external API health")

    # External endpoints to check
    external_endpoints: List[str] = Field(default_factory=list, description="External endpoints to check")

    # Health metrics
    collect_detailed_metrics: bool = Field(default=True, description="Collect detailed health metrics")
    save_health_history: bool = Field(default=True, description="Save health check history")
    history_retention_days: int = Field(default=7, description="Health history retention period")


class MonitoringConfig(BaseSettings):
    """Main monitoring configuration"""

    # Service configuration
    service_name: str = Field(default="rag-system", description="Service name")
    environment: str = Field(default="development", description="Environment (development, staging, production)")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Component configurations
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    alerting: AlertingConfig = Field(default_factory=AlertingConfig)
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)

    # Security
    authentication_required: bool = Field(default=False, description="Require authentication for monitoring endpoints")
    allowed_roles: List[str] = Field(default_factory=lambda: ["admin", "monitoring"], description="Allowed roles for monitoring access")

    class Config:
        env_prefix = "MONITORING_"
        env_file = ".env"
        env_nested_delimiter = "__"

    @validator("environment")
    def validate_environment(cls, v):
        """Validate environment value"""
        allowed = ["development", "staging", "production", "test"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v


# Global configuration instance
_monitoring_config: Optional[MonitoringConfig] = None


def get_monitoring_config() -> MonitoringConfig:
    """Get the global monitoring configuration"""
    global _monitoring_config
    if _monitoring_config is None:
        _monitoring_config = MonitoringConfig()
    return _monitoring_config


def reload_monitoring_config() -> MonitoringConfig:
    """Reload the monitoring configuration from environment"""
    global _monitoring_config
    _monitoring_config = MonitoringConfig()
    return _monitoring_config