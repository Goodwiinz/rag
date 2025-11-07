"""
Observability configuration for the Multimodal RAG System.
"""

import os
from typing import Optional, Dict, Any
from pydantic import BaseSettings, Field


class ObservabilityConfig(BaseSettings):
    """Configuration for observability components."""

    # OpenTelemetry Configuration
    otel_service_name: str = Field(default="multimodal-rag-system", env="OTEL_SERVICE_NAME")
    otel_service_version: str = Field(default="1.0.0", env="OTEL_SERVICE_VERSION")
    otel_environment: str = Field(default="development", env="OTEL_ENVIRONMENT")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://jaeger:4317",
        env="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_exporter_jaeger_endpoint: str = Field(
        default="http://jaeger:14250",
        env="OTEL_EXPORTER_JAEGER_ENDPOINT"
    )
    otel_sampling_probability: float = Field(
        default=0.1,
        env="OTEL_SAMPLING_PROBABILITY"
    )
    otel_batch_timeout: int = Field(default=5000, env="OTEL_BATCH_TIMEOUT")
    otel_max_export_batch_size: int = Field(default=512, env="OTEL_MAX_EXPORT_BATCH_SIZE")

    # Prometheus Configuration
    prometheus_port: int = Field(default=9090, env="PROMETHEUS_PORT")
    prometheus_metrics_path: str = Field(default="/metrics", env="PROMETHEUS_METRICS_PATH")
    prometheus_registry_enabled: bool = Field(default=True, env="PROMETHEUS_REGISTRY_ENABLED")

    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")  # json or console
    log_correlation_enabled: bool = Field(default=True, env="LOG_CORRELATION_ENABLED")
    log_file_path: Optional[str] = Field(default=None, env="LOG_FILE_PATH")

    # Performance Monitoring
    performance_profiling_enabled: bool = Field(default=False, env="PERFORMANCE_PROFILING_ENABLED")
    memory_profiling_enabled: bool = Field(default=False, env="MEMORY_PROFILING_ENABLED")
    cpu_profiling_enabled: bool = Field(default=False, env="CPU_PROFILING_ENABLED")

    # SLI/SLO Configuration
    slo_response_time_p95_target: float = Field(default=3000.0, env="SLO_RESPONSE_TIME_P95_TARGET")  # ms
    slo_response_time_p99_target: float = Field(default=5000.0, env="SLO_RESPONSE_TIME_P99_TARGET")  # ms
    slo_error_rate_target: float = Field(default=0.005, env="SLO_ERROR_RATE_TARGET")  # 0.5%
    slo_availability_target: float = Field(default=0.995, env="SLO_AVAILABILITY_TARGET")  # 99.5%

    # Business Metrics
    business_metrics_enabled: bool = Field(default=True, env="BUSINESS_METRICS_ENABLED")
    user_tracking_enabled: bool = Field(default=False, env="USER_TRACKING_ENABLED")
    query_analytics_enabled: bool = Field(default=True, env="QUERY_ANALYTICS_ENABLED")

    # Alerting Configuration
    alerting_enabled: bool = Field(default=True, env="ALERTING_ENABLED")
    alert_webhook_url: Optional[str] = Field(default=None, env="ALERT_WEBHOOK_URL")
    alert_email_enabled: bool = Field(default=False, env="ALERT_EMAIL_ENABLED")

    class Config:
        env_file = ".env"
        case_sensitive = False

    def get_otel_resource_attributes(self) -> Dict[str, Any]:
        """Get OpenTelemetry resource attributes."""
        return {
            "service.name": self.otel_service_name,
            "service.version": self.otel_service_version,
            "deployment.environment": self.otel_environment,
            "host.name": os.uname().nodename,
        }

    def get_jaeger_config(self) -> Dict[str, Any]:
        """Get Jaeger exporter configuration."""
        return {
            "endpoint": self.otel_exporter_jaeger_endpoint,
            "timeout": 5000,
            "retry": True,
        }

    def get_prometheus_config(self) -> Dict[str, Any]:
        """Get Prometheus configuration."""
        return {
            "port": self.prometheus_port,
            "path": self.prometheus_metrics_path,
            "registry_enabled": self.prometheus_registry_enabled,
        }


# Global configuration instance
config = ObservabilityConfig()