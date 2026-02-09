"""
PostgreSQL models for Knowledge Graph Service
"""

import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class EntitySQL(Base):
    """PostgreSQL model for entities"""

    __tablename__ = "entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    confidence_score = Column(Float, nullable=False, default=0.8)
    extraction_method = Column(String(50), nullable=False)
    position = Column(JSON, nullable=True)  # Store as JSON array
    context = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True, default=dict)
    source_document_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    source_relationships = relationship(
        "RelationshipSQL",
        foreign_keys="RelationshipSQL.source_entity_id",
        back_populates="source_entity",
        cascade="all, delete-orphan",
    )
    target_relationships = relationship(
        "RelationshipSQL",
        foreign_keys="RelationshipSQL.target_entity_id",
        back_populates="target_entity",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<EntitySQL(id={self.id}, name={self.name}, type={self.entity_type})>"


class RelationshipSQL(Base):
    """PostgreSQL model for relationships"""

    __tablename__ = "relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True
    )
    target_entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True
    )
    relationship_type = Column(String(50), nullable=False, index=True)
    strength = Column(Float, nullable=False, default=1.0)
    confidence_score = Column(Float, nullable=False, default=0.8)
    context = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True, default=list)
    metadata = Column(JSON, nullable=True, default=dict)
    source_document_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    source_entity = relationship(
        "EntitySQL",
        foreign_keys=[source_entity_id],
        back_populates="source_relationships",
    )
    target_entity = relationship(
        "EntitySQL",
        foreign_keys=[target_entity_id],
        back_populates="target_relationships",
    )

    def __repr__(self):
        return f"<RelationshipSQL(id={self.id}, type={self.relationship_type}, source={self.source_entity_id}, target={self.target_entity_id})>"


class DocumentEntityMapping(Base):
    """Mapping table for documents and entities"""

    __tablename__ = "document_entity_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True
    )
    tenant_id = Column(String(100), nullable=False, index=True)

    # Additional metadata about the mapping
    mention_count = Column(Integer, default=1)
    first_mention_position = Column(Integer, nullable=True)
    confidence_score = Column(Float, nullable=False, default=0.8)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    entity = relationship("EntitySQL")


class GraphAnalyticsCache(Base):
    """Cache table for graph analytics results"""

    __tablename__ = "graph_analytics_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, index=True)
    analytics_type = Column(
        String(50), nullable=False, index=True
    )  # centrality, clustering, etc.

    # Cached analytics data
    data = Column(JSON, nullable=False)
    computation_time = Column(Float, nullable=False)  # Time taken to compute in seconds

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self):
        return (
            f"<GraphAnalyticsCache(key={self.cache_key}, type={self.analytics_type})>"
        )


class EntitySearchIndex(Base):
    """Search index for entities"""

    __tablename__ = "entity_search_index"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(
        UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False, index=True
    )
    tenant_id = Column(String(100), nullable=False, index=True)

    # Search fields
    search_vector = Column(
        String, nullable=False
    )  # Could use PostgreSQL full-text search
    entity_name = Column(String(500), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)

    # Popularity and relevance metrics
    mention_count = Column(Integer, default=0, index=True)
    relationship_count = Column(Integer, default=0, index=True)
    last_accessed = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationship
    entity = relationship("EntitySQL")


class GraphEventLog(Base):
    """Audit log for graph operations"""

    __tablename__ = "graph_event_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(100), nullable=False, index=True)

    # Event details
    event_type = Column(
        String(50), nullable=False, index=True
    )  # entity_created, relationship_deleted, etc.
    operation = Column(String(20), nullable=False)  # CREATE, UPDATE, DELETE
    resource_type = Column(String(20), nullable=False)  # entity, relationship
    resource_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # User and context
    user_id = Column(String(100), nullable=True, index=True)
    user_role = Column(String(50), nullable=True)
    session_id = Column(String(100), nullable=True, index=True)

    # Event data
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True, default=dict)

    # Timing
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    processing_time = Column(
        Float, nullable=True
    )  # Time taken for operation in seconds


class SystemMetrics(Base):
    """System metrics for monitoring"""

    __tablename__ = "system_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(100), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)

    # Additional dimensions
    entity_type = Column(String(50), nullable=True, index=True)
    operation_type = Column(String(50), nullable=True, index=True)

    # Timing
    timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    hour_bucket = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD-HH


class TenantGraphSettings(Base):
    """Per-tenant graph settings"""

    __tablename__ = "tenant_graph_settings"

    tenant_id = Column(String(100), primary_key=True)

    # Entity extraction settings
    entity_confidence_threshold = Column(Float, default=0.7, nullable=False)
    relationship_confidence_threshold = Column(Float, default=0.6, nullable=False)
    max_entities_per_document = Column(Integer, default=1000, nullable=False)
    max_relationships_per_document = Column(Integer, default=2000, nullable=False)

    # Performance settings
    enable_caching = Column(Boolean, default=True, nullable=False)
    cache_ttl_seconds = Column(Integer, default=3600, nullable=False)
    enable_websocket_updates = Column(Boolean, default=True, nullable=False)

    # Analytics settings
    enable_analytics = Column(Boolean, default=True, nullable=False)
    analytics_computation_interval = Column(
        Integer, default=3600, nullable=False
    )  # seconds

    # Security settings
    enable_tenant_isolation = Column(Boolean, default=True, nullable=False)
    max_api_requests_per_minute = Column(Integer, default=1000, nullable=False)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    def __repr__(self):
        return f"<TenantGraphSettings(tenant_id={self.tenant_id})>"
