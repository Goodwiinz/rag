"""
Health Check Database Models

Models for storing health check results and component health status.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, Index, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from src.models.base import BaseModel


class HealthStatus(str, Enum):
    """Health status values"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"


class CheckType(str, Enum):
    """Health check types"""
    DATABASE = "database"
    REDIS = "redis"
    NEO4J = "neo4j"
    QDRANT = "qdrant"
    EXTERNAL_API = "external_api"
    DISK_SPACE = "disk_space"
    MEMORY = "memory"
    CPU = "cpu"
    NETWORK = "network"
    CUSTOM = "custom"


class HealthCheck(BaseModel):
    """Health check definitions"""
    __tablename__ = "monitoring_health_checks"

    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text)
    check_type = Column(String(50), nullable=False, index=True)
    component_name = Column(String(255), nullable=False, index=True)

    # Check configuration
    endpoint_url = Column(String(500))
    timeout_seconds = Column(Integer, default=10)
    check_interval_seconds = Column(Integer, default=30)
    retry_count = Column(Integer, default=3)
    retry_delay_seconds = Column(Integer, default=5)

    # Expected results
    expected_status_code = Column(Integer, default=200)
    expected_response_time_ms = Column(Integer, default=1000)
    expected_content = Column(Text)
    validation_script = Column(Text)  # Custom validation logic

    # Thresholds
    response_time_warning_ms = Column(Integer, default=500)
    response_time_critical_ms = Column(Integer, default=2000)
    success_rate_warning_percent = Column(Float, default=95.0)
    success_rate_critical_percent = Column(Float, default=90.0)

    # Check settings
    is_active = Column(Boolean, default=True)
    is_critical = Column(Boolean, default=False)  # Critical checks affect overall system health
    dependencies = Column(JSONB, default=list)  # List of check names this check depends on

    # Check metadata
    tags = Column(JSONB, default=list)
    metadata = Column(JSONB, default=dict)
    created_by = Column(String(255))

    # Relationships
    results = relationship("HealthCheckResult", back_populates="check", cascade="all, delete-orphan")
    component_health = relationship("ComponentHealth", back_populates="health_check")
    history = relationship("HealthCheckHistory", back_populates="check", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_health_checks_type_active', 'check_type', 'is_active'),
        Index('idx_health_checks_component', 'component_name'),
        Index('idx_health_checks_critical', 'is_critical'),
    )


class HealthCheckResult(BaseModel):
    """Individual health check results"""
    __tablename__ = "monitoring_health_check_results"

    check_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_health_checks.id"), nullable=False, index=True)
    check_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Results
    status = Column(String(50), nullable=False, index=True)
    response_time_ms = Column(Float)
    status_code = Column(Integer)
    success = Column(Boolean, nullable=False)

    # Check details
    error_message = Column(Text)
    error_details = Column(JSONB, default=dict)
    response_body = Column(Text)
    response_headers = Column(JSONB, default=dict)

    # Performance metrics
    dns_lookup_time_ms = Column(Float)
    connection_time_ms = Column(Float)
    ssl_handshake_time_ms = Column(Float)
    first_byte_time_ms = Column(Float)

    # Resource usage at check time
    cpu_usage_percent = Column(Float)
    memory_usage_percent = Column(Float)
    disk_usage_percent = Column(Float)

    # Check metadata
    check_version = Column(String(50))
    check_metadata = Column(JSONB, default=dict)

    # Relationships
    check = relationship("HealthCheck", back_populates="results")

    # Indexes
    __table_args__ = (
        Index('idx_health_results_check_time', 'check_id', 'check_timestamp'),
        Index('idx_health_results_status_time', 'status', 'check_timestamp'),
        Index('idx_health_results_success_time', 'success', 'check_timestamp'),
    )


class HealthCheckHistory(BaseModel):
    """Aggregated health check history"""
    __tablename__ = "monitoring_health_check_history"

    check_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_health_checks.id"), nullable=False, index=True)
    time_bucket = Column(DateTime(timezone=True), nullable=False, index=True)
    bucket_size_minutes = Column(Integer, nullable=False)

    # Aggregated metrics
    total_checks = Column(Integer, default=0)
    successful_checks = Column(Integer, default=0)
    failed_checks = Column(Integer, default=0)

    # Success rates
    success_rate_percent = Column(Float, default=0.0)
    availability_percent = Column(Float, default=0.0)

    # Performance metrics
    avg_response_time_ms = Column(Float)
    min_response_time_ms = Column(Float)
    max_response_time_ms = Column(Float)
    p95_response_time_ms = Column(Float)
    p99_response_time_ms = Column(Float)

    # Status distribution
    healthy_count = Column(Integer, default=0)
    degraded_count = Column(Integer, default=0)
    unhealthy_count = Column(Integer, default=0)
    unknown_count = Column(Integer, default=0)

    # Error analysis
    top_errors = Column(JSONB, default=list)
    error_patterns = Column(JSONB, default=dict)

    # Relationships
    check = relationship("HealthCheck", back_populates="history")

    # Indexes
    __table_args__ = (
        Index('idx_health_history_check_time', 'check_id', 'time_bucket'),
        Index('idx_health_history_success_rate', 'success_rate_percent'),
        Index('idx_health_history_availability', 'availability_percent'),
    )


class ComponentHealth(BaseModel):
    """Overall component health status"""
    __tablename__ = "monitoring_component_health"

    component_name = Column(String(255), nullable=False, index=True)
    component_type = Column(String(100), nullable=False, index=True)
    health_check_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_health_checks.id"), nullable=False)

    # Current status
    status = Column(String(50), nullable=False, index=True)
    status_message = Column(Text)
    last_check_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    status_duration_minutes = Column(Float)

    # Health metrics
    uptime_percentage = Column(Float, default=100.0)
    mttr_minutes = Column(Float, default=0.0)  # Mean Time To Repair
    incident_count_24h = Column(Integer, default=0)
    incident_count_7d = Column(Integer, default=0)

    # Dependencies
    dependencies = Column(JSONB, default=list)  # List of component names this depends on
    dependents = Column(JSONB, default=list)  # List of components that depend on this

    # Service level indicators
    sli_current = Column(Float)  # Current Service Level Indicator value
    slo_target = Column(Float)   # Service Level Objective target
    slo_compliance_percent = Column(Float)  # SLO compliance percentage

    # Component metadata
    version = Column(String(100))
    environment = Column(String(100))
    owner = Column(String(255))
    tags = Column(JSONB, default=list)
    metadata = Column(JSONB, default=dict)

    # Relationships
    health_check = relationship("HealthCheck", back_populates="component_health")

    # Unique constraint on component name
    __table_args__ = (
        Index('idx_component_health_name_type', 'component_name', 'component_type'),
        Index('idx_component_health_status_time', 'status', 'last_check_timestamp'),
        Index('idx_component_health_slo', 'slo_compliance_percent'),
    )