"""
Comprehensive indexing strategy and database constraints for optimal performance
"""

import uuid
from typing import Any, Dict, List

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.schema import CreateIndex, CreateTable

# PRIMARY INDEXES FOR PERFORMANCE CRITICAL QUERIES

# User and Organization indexes
USER_ORGANIZATION_INDEXES = [
    # User table indexes
    Index("idx_users_email_unique", "email", unique=True),
    Index("idx_users_org_active", "organization_id", "is_active"),
    Index("idx_users_role_active", "role", "is_active"),
    Index("idx_users_last_login", "last_login"),
    Index("idx_users_created_at", "created_at"),
    # Organization table indexes
    Index("idx_organizations_name", "name"),
    Index("idx_organizations_active", "is_active"),
    Index("idx_organizations_created_at", "created_at"),
    Index("idx_organizations_subscription", "subscription_plan"),
]

# Document indexing strategy
DOCUMENT_INDEXES = [
    # Core document access patterns
    Index("idx_documents_org_user", "organization_id", "uploaded_by_user_id"),
    Index("idx_documents_org_status", "organization_id", "processing_status"),
    Index("idx_documents_user_uploaded", "uploaded_by_user_id", "created_at"),
    Index("idx_documents_status_created", "processing_status", "created_at"),
    # Search and retrieval
    Index("idx_documents_title_text", "title"),  # For title search
    Index("idx_documents_file_type", "document_type", "mime_type"),
    Index("idx_documents_size_range", "file_size_bytes"),  # For size filtering
    Index("idx_documents_embedding", "embedding_id"),  # Vector store lookup
    Index("idx_documents_search_vector", "search_vector"),  # Full-text search
    # Quality and metrics
    Index("idx_documents_quality_score", "overall_quality_score"),
    Index("idx_documents_quality_level", "quality_level"),
    Index("idx_documents_view_count", "view_count"),
    Index("idx_documents_access_control", "is_public", "sharing_level"),
    # Temporal and lifecycle
    Index("idx_documents_created_at", "created_at"),
    Index("idx_documents_expires_at", "expires_at"),
    Index(
        "idx_documents_processing_times",
        "processing_started_at",
        "processing_completed_at",
    ),
    # Multimodal content
    Index("idx_documents_modalities", "primary_modality"),
    Index("idx_documents_language", "language_detected"),
    Index("idx_documents_tags", "tags"),  # GIN index for array
    # File integrity and deduplication
    Index("idx_documents_file_hash_sha256", "file_hash_sha256"),  # For deduplication
    Index("idx_documents_file_hash_md5", "file_hash_md5"),  # Legacy support
    # Version control
    Index("idx_documents_version_parent", "parent_document_id", "version_number"),
    Index("idx_documents_latest_versions", "is_latest_version", "organization_id"),
]

# Query and RAG indexing strategy
QUERY_INDEXES = [
    # Core query access patterns
    Index("idx_queries_user_session", "user_id", "session_id"),
    Index("idx_queries_org_created", "organization_id", "created_at"),
    Index("idx_queries_type_created", "query_type", "created_at"),
    Index("idx_queries_quality_score", "overall_quality_score"),
    # Performance analytics
    Index("idx_queries_duration", "total_duration_ms"),
    Index("idx_queries_tokens_used", "total_tokens_used"),
    Index("idx_queries_rating", "user_rating"),
    Index("idx_queries_feedback", "was_helpful", "user_rating"),
    # Temporal and retention
    Index("idx_queries_expires_at", "expires_at"),
    Index("idx_queries_retention_cleanup", "marked_for_deletion", "expires_at"),
    Index("idx_queries_30day_window", "created_at"),  # For 30-day retention queries
    # Caching and optimization
    Index("idx_queries_cache_key", "cache_key"),
    Index("idx_queries_cache_hit", "cache_hit"),
    Index("idx_queries_similarity_cluster", "similarity_cluster_id"),
    # Content analysis
    Index("idx_queries_intent", "query_intent"),
    Index("idx_queries_complexity", "query_complexity"),
    Index("idx_queries_answer_type", "answer_type"),
    Index("idx_queries_answer_confidence", "answer_confidence"),
]

# Entity and Knowledge Graph indexing strategy
ENTITY_INDEXES = [
    # Core entity access
    Index("idx_entities_org_type", "organization_id", "entity_type"),
    Index("idx_entities_name_variations", "name", "canonical_name"),
    Index("idx_entities_confidence", "extraction_confidence"),
    Index("idx_entities_quality", "quality_score"),
    # Search and discovery
    Index("idx_entities_display_name", "canonical_name"),  # Primary display name
    Index("idx_entities_aliases", "aliases"),  # GIN index for array
    Index(
        "idx_entities_external_ids", "external_ids"
    ),  # JSON index for external lookups
    Index("idx_entities_description", "description"),  # Full-text on description
    # Graph analytics
    Index("idx_entities_centrality", "degree_centrality"),
    Index("idx_entities_pagerank", "pagerank_score"),
    Index("idx_entities_community", "community_id"),
    Index("idx_entities_popularity", "popularity_score"),
    # Temporal and geographic
    Index("idx_entities_temporal", "valid_from", "valid_to"),
    Index("idx_entities_location", "latitude", "longitude"),
    Index("idx_entities_geographic", "country", "region", "city"),
    # Verification and status
    Index("idx_entities_verification", "is_verified", "verified_by_user_id"),
    Index("idx_entities_status", "status"),
    Index("idx_entities_neo4j", "neo4j_node_id"),
    # Entity relationships
    Index("idx_relationships_source_type", "source_entity_id", "relationship_type"),
    Index("idx_relationships_target_type", "target_entity_id", "relationship_type"),
    Index("idx_relationships_bidirectional", "is_bidirectional", "relationship_type"),
    Index("idx_relationships_confidence", "confidence"),
    Index("idx_relationships_weight", "weight"),
    Index("idx_relationships_temporal", "valid_from", "valid_to"),
    Index("idx_relationships_neo4j", "neo4j_relationship_id"),
    # Entity mentions in documents
    Index("idx_mentions_entity_document", "entity_id", "document_id"),
    Index("idx_mentions_document_analysis", "document_id", "confidence"),
    Index("idx_mentions_location", "mention_start", "mention_end"),
    Index("idx_mentions_page_section", "page_number", "section_title"),
]

# Processing and Job indexing strategy
PROCESSING_INDEXES = [
    # Job queue management
    Index("idx_jobs_status_priority", "status", "priority", "created_at"),
    Index("idx_jobs_queue_status", "queue_name", "status"),
    Index("idx_jobs_type_status", "job_type", "status"),
    Index("idx_jobs_retry_queue", "retry_count", "max_retries", "status"),
    # Job tracking and analytics
    Index("idx_jobs_duration", "duration_seconds"),
    Index("idx_jobs_progress", "progress_percentage"),
    Index("idx_jobs_performance", "cpu_time_seconds", "memory_peak_mb"),
    Index("idx_jobs_worker", "worker_id", "started_at"),
    # Document processing pipeline
    Index("idx_jobs_document_status", "document_id", "status"),
    Index("idx_jobs_user_tracking", "created_by_user_id", "job_type"),
    Index("idx_jobs_organization_jobs", "organization_id", "job_type", "status"),
    # Temporal analysis
    Index("idx_jobs_time_analysis", "queued_at", "started_at", "completed_at"),
    Index("idx_jobs_failure_analysis", "status", "error_type", "failed_at"),
]

# WebSocket and Real-time indexing strategy
WEBSOCKET_INDEXES = [
    # Connection management
    Index("idx_ws_connections_user_status", "user_id", "connection_status"),
    Index("idx_ws_connections_org_active", "organization_id", "connection_status"),
    Index("idx_ws_connections_heartbeat", "last_heartbeat"),
    Index("idx_ws_connections_client_type", "client_type", "connected_at"),
    # Status updates and notifications
    Index("idx_status_updates_connection_type", "connection_id", "update_type"),
    Index("idx_status_updates_priority_created", "priority", "created_at"),
    Index("idx_status_updates_delivery_status", "delivery_status", "created_at"),
    Index("idx_status_updates_expires", "expires_at", "delivery_status"),
    # Event tracking
    Index("idx_connection_events_time_type", "event_timestamp", "event_type"),
    Index("idx_connection_events_error", "event_type", "event_timestamp"),
]

# Evaluation Metrics indexing strategy
EVALUATION_INDEXES = [
    # Evaluation runs
    Index("idx_eval_runs_org_status", "organization_id", "status"),
    Index("idx_eval_runs_period", "evaluation_period_start", "evaluation_period_end"),
    Index("idx_eval_runs_score", "overall_score"),
    Index("idx_eval_runs_type_created", "run_type", "created_at"),
    # Individual measurements
    Index("idx_measurements_run_type", "evaluation_run_id", "metric_type"),
    Index("idx_measurements_entity_score", "entity_type", "entity_id", "metric_score"),
    Index("idx_measurements_threshold", "meets_threshold", "metric_score"),
    Index("idx_measurements_timestamp", "evaluation_timestamp"),
    # Aggregated metrics
    Index(
        "idx_aggregations_level_window",
        "aggregation_level",
        "window_start",
        "window_end",
    ),
    Index("idx_aggregations_org_metric", "organization_id", "metric_name"),
    Index("idx_aggregations_user_metric", "user_id", "metric_name"),
    Index("idx_aggregations_score_quality", "avg_score", "quality_threshold_met"),
]

# Storage Quota indexing strategy
QUOTA_INDEXES = [
    # User quota tracking
    Index("idx_quota_org_status", "organization_id", "quota_status"),
    Index("idx_quota_storage_usage", "storage_used_bytes"),
    Index("idx_quota_warning_levels", "quota_status", "warning_sent_at"),
    Index("idx_quota_grace_period", "grace_period_ends_at", "is_suspended"),
    # Quota adjustments and alerts
    Index("idx_quota_adjustments_user", "user_quota_id", "created_at"),
    Index("idx_quota_alerts_type_sent", "alert_type", "sent_at"),
    Index(
        "idx_quota_snapshots_daily", "user_quota_id", "snapshot_date", "snapshot_type"
    ),
]

# UNIQUE CONSTRAINTS FOR DATA INTEGRITY
UNIQUE_CONSTRAINTS = [
    # Users and authentication
    UniqueConstraint("email", name="uq_users_email"),
    UniqueConstraint("username", name="uq_users_username"),
    # Organizations
    UniqueConstraint("name", name="uq_organizations_name"),
    UniqueConstraint("domain", name="uq_organizations_domain"),
    # Documents
    UniqueConstraint(
        "organization_id", "file_hash_sha256", name="uq_documents_file_hash"
    ),
    UniqueConstraint(
        "organization_id", "stored_filename", name="uq_documents_filename"
    ),
    # Entities
    UniqueConstraint("organization_id", "entity_uri", name="uq_entities_uri"),
    UniqueConstraint(
        "organization_id",
        "canonical_name",
        "entity_type",
        name="uq_entities_canonical_name_type",
    ),
    # Entity relationships
    UniqueConstraint(
        "source_entity_id",
        "target_entity_id",
        "relationship_type",
        "valid_from",
        name="uq_relationships_unique",
    ),
    # Queries
    UniqueConstraint("cache_key", name="uq_queries_cache_key"),
    # WebSocket connections
    UniqueConstraint("connection_id", name="uq_ws_connections_id"),
    # Evaluation runs
    UniqueConstraint(
        "organization_id", "run_name", "created_at", name="uq_eval_runs_org_name_date"
    ),
]

# CHECK CONSTRAINTS FOR DATA VALIDATION
CHECK_CONSTRAINTS = [
    # File size constraints
    CheckConstraint("file_size_bytes > 0", name="ck_file_size_positive"),
    CheckConstraint(
        "file_size_bytes <= 5368709120", name="ck_file_size_max_5gb"
    ),  # 5GB max
    # Score and percentage constraints
    CheckConstraint(
        "confidence >= 0.0 AND confidence <= 1.0", name="ck_confidence_range"
    ),
    CheckConstraint(
        "quality_score >= 0.0 AND quality_score <= 1.0", name="ck_quality_score_range"
    ),
    CheckConstraint(
        "progress_percentage >= 0.0 AND progress_percentage <= 100.0",
        name="ck_progress_percentage_range",
    ),
    # Rating constraints
    CheckConstraint(
        "user_rating >= 1 AND user_rating <= 5", name="ck_user_rating_range"
    ),
    CheckConstraint("rating >= 1 AND rating <= 5", name="ck_rating_range"),
    # Temporal constraints
    CheckConstraint("valid_from <= valid_to", name="ck_valid_date_range"),
    CheckConstraint(
        "evaluation_period_start <= evaluation_period_end",
        name="ck_evaluation_period_range",
    ),
    CheckConstraint("window_start <= window_end", name="ck_window_date_range"),
    # Count constraints
    CheckConstraint("retry_count >= 0", name="ck_retry_count_positive"),
    CheckConstraint("max_retries >= 0", name="ck_max_retries_positive"),
    CheckConstraint("retry_count <= max_retries", name="ck_retry_count_limit"),
    # Processing priority constraints
    CheckConstraint(
        "processing_priority >= 1 AND processing_priority <= 10",
        name="ck_processing_priority_range",
    ),
    # Quota constraints
    CheckConstraint("storage_quota_bytes > 0", name="ck_storage_quota_positive"),
    CheckConstraint("storage_used_bytes >= 0", name="ck_storage_used_non_negative"),
    CheckConstraint(
        "storage_used_bytes <= storage_quota_bytes", name="ck_storage_usage_limit"
    ),
    # Performance constraints
    CheckConstraint("total_duration_ms >= 0", name="ck_duration_positive"),
    CheckConstraint("total_tokens_used >= 0", name="ck_tokens_positive"),
]

# FOREIGN KEY CONSTRAINTS FOR REFERENTIAL INTEGRITY
FOREIGN_KEY_CONSTRAINTS = [
    # Basic referential integrity constraints
    ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
    ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
    # Document-specific constraints
    ForeignKeyConstraint(
        ["parent_document_id"], ["enhanced_documents.id"], ondelete="SET NULL"
    ),
    ForeignKeyConstraint(
        ["document_id"], ["enhanced_documents.id"], ondelete="CASCADE"
    ),
    # Entity relationship constraints
    ForeignKeyConstraint(
        ["source_entity_id"], ["knowledge_entities.id"], ondelete="CASCADE"
    ),
    ForeignKeyConstraint(
        ["target_entity_id"], ["knowledge_entities.id"], ondelete="CASCADE"
    ),
    ForeignKeyConstraint(
        ["merged_into_id"], ["knowledge_entities.id"], ondelete="SET NULL"
    ),
    # Processing constraints
    ForeignKeyConstraint(
        ["document_id"], ["enhanced_documents.id"], ondelete="CASCADE"
    ),
    ForeignKeyConstraint(
        ["evaluation_run_id"], ["evaluation_runs.id"], ondelete="CASCADE"
    ),
    # WebSocket constraints
    ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    ForeignKeyConstraint(
        ["connection_id"], ["websocket_connections.id"], ondelete="CASCADE"
    ),
]

# PARTITIONING STRATEGIES FOR LARGE TABLES
PARTITIONING_STRATEGIES = {
    # Time-based partitioning for high-volume tables
    "rag_queries": {
        "type": "range",
        "column": "created_at",
        "strategy": "monthly",
        "retention_months": 3,  # Keep 3 months of active data
    },
    "search_queries": {
        "type": "range",
        "column": "created_at",
        "strategy": "monthly",
        "retention_months": 12,
    },
    "document_access_logs": {
        "type": "range",
        "column": "access_timestamp",
        "strategy": "weekly",
        "retention_weeks": 52,
    },
    "metric_measurements": {
        "type": "range",
        "column": "evaluation_timestamp",
        "strategy": "monthly",
        "retention_months": 24,
    },
    "websocket_connection_events": {
        "type": "range",
        "column": "event_timestamp",
        "strategy": "daily",
        "retention_days": 30,
    },
    # Hash-based partitioning for even distribution
    "search_results": {
        "type": "hash",
        "column": "search_query_id",
        "partitions": 8,  # 8 hash partitions
    },
    "entity_document_mentions": {
        "type": "hash",
        "column": "entity_id",
        "partitions": 16,
    },
}

# OPTIMIZATION RECOMMENDATIONS
OPTIMIZATION_RECOMMENDATIONS = {
    "index_maintenance": {
        "rebuild_frequency": {
            "high_write_tables": "weekly",  # Documents, queries, entities
            "medium_write_tables": "monthly",  # Organizations, users
            "low_write_tables": "quarterly",  # Configuration, templates
        },
        "analyze_frequency": {
            "high_change_tables": "daily",  # Tables with frequent updates
            "medium_change_tables": "weekly",  # Moderately active tables
            "low_change_tables": "monthly",  # Relatively static tables
        },
    },
    "query_optimization": {
        "prepared_statements": [
            "user_authentications",
            "document_searches",
            "entity_lookups",
            "query_executions",
        ],
        "materialized_views": [
            "user_quota_summary",
            "organization_metrics",
            "popular_entities",
            "recent_queries",
        ],
    },
    "storage_optimization": {
        "compression": {
            "text_fields": "pglz",
            "json_fields": "gzip",
            "large_text": "toast",
        },
        "tablespaces": {
            "hot_data": "fast_ssd",
            "warm_data": "standard_ssd",
            "cold_data": "hdd_archive",
            "indexes": "fast_ssd",
        },
    },
}

# DATABASE CONFIGURATION SETTINGS
DATABASE_CONFIG = {
    "postgresql_settings": {
        "shared_buffers": "256MB",
        "effective_cache_size": "1GB",
        "maintenance_work_mem": "64MB",
        "checkpoint_completion_target": "0.9",
        "wal_buffers": "16MB",
        "default_statistics_target": "100",
        "random_page_cost": "1.1",
        "effective_io_concurrency": "200",
    },
    "connection_pooling": {
        "max_connections": 100,
        "idle_connections": 20,
        "max_lifetime": 3600,  # 1 hour
        "connection_timeout": 30,
    },
    "performance_monitoring": {
        "log_slow_queries": True,
        "slow_query_threshold": 1000,  # ms
        "log_checkpoints": True,
        "log_connections": True,
        "log_disconnections": True,
        "log_lock_waits": True,
    },
}


def get_all_indexes() -> List[Index]:
    """Get all database indexes for the application"""
    all_indexes = []

    # Add all index groups
    index_groups = [
        USER_ORGANIZATION_INDEXES,
        DOCUMENT_INDEXES,
        QUERY_INDEXES,
        ENTITY_INDEXES,
        PROCESSING_INDEXES,
        WEBSOCKET_INDEXES,
        EVALUATION_INDEXES,
        QUOTA_INDEXES,
    ]

    for group in index_groups:
        all_indexes.extend(group)

    return all_indexes


def get_all_constraints() -> Dict[str, List]:
    """Get all database constraints organized by type"""
    return {
        "unique_constraints": UNIQUE_CONSTRAINTS,
        "check_constraints": CHECK_CONSTRAINTS,
        "foreign_key_constraints": FOREIGN_KEY_CONSTRAINTS,
    }


def create_optimization_sql() -> List[str]:
    """Generate SQL statements for database optimization"""
    sql_statements = []

    # Create index statements
    for index in get_all_indexes():
        sql_statements.append(str(CreateIndex(index)))

    # Create tablespace statements (if needed)
    tablespaces = [
        "CREATE TABLESPACE IF NOT EXISTS fast_ssd LOCATION '/fast_ssd_data'",
        "CREATE TABLESPACE IF NOT EXISTS standard_ssd LOCATION '/standard_ssd_data'",
        "CREATE TABLESPACE IF NOT EXISTS hdd_archive LOCATION '/hdd_archive_data'",
    ]
    sql_statements.extend(tablespaces)

    # Set configuration parameters
    config_sql = [
        f"ALTER SYSTEM SET {key} = '{value}'"
        for key, value in DATABASE_CONFIG["postgresql_settings"].items()
    ]
    sql_statements.extend(config_sql)

    return sql_statements


def get_monitoring_queries() -> Dict[str, str]:
    """Get monitoring queries for database performance"""
    return {
        "index_usage": """
            SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
            FROM pg_stat_user_indexes
            ORDER BY idx_tup_read DESC;
        """,
        "slow_queries": """
            SELECT query, calls, total_time, mean_time, rows
            FROM pg_stat_statements
            WHERE mean_time > 1000
            ORDER BY mean_time DESC;
        """,
        "table_sizes": """
            SELECT schemaname, tablename,
                   pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_tables
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
        """,
        "connection_stats": """
            SELECT state, count(*)
            FROM pg_stat_activity
            GROUP BY state;
        """,
        "cache_hit_ratio": """
            SELECT sum(heap_blks_read) as heap_read,
                   sum(heap_blks_hit) as heap_hit,
                   sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
            FROM pg_statio_user_tables;
        """,
    }


# Performance tuning recommendations
def get_performance_tuning_recommendations() -> Dict[str, Any]:
    """Get performance tuning recommendations based on data model"""
    return {
        "query_patterns": {
            "user_document_access": {
                "frequency": "high",
                "recommended_indexes": [
                    "idx_documents_org_user",
                    "idx_documents_user_uploaded",
                ],
                "optimization": "Consider caching frequently accessed user documents",
            },
            "entity_search": {
                "frequency": "high",
                "recommended_indexes": [
                    "idx_entities_name_variations",
                    "idx_entities_confidence",
                ],
                "optimization": "Use trigram indexes for fuzzy name matching",
            },
            "rag_query_execution": {
                "frequency": "high",
                "recommended_indexes": [
                    "idx_queries_user_session",
                    "idx_queries_cache_key",
                ],
                "optimization": "Implement query result caching for common patterns",
            },
            "full_text_search": {
                "frequency": "medium",
                "recommended_indexes": [
                    "idx_documents_search_vector",
                    "idx_entities_description",
                ],
                "optimization": "Use PostgreSQL FTS with proper language configuration",
            },
        },
        "data_archival": {
            "queries_older_than_30_days": {
                "action": "move to cold storage",
                "method": "partition + archive table",
            },
            "logs_older_than_90_days": {
                "action": "compress and archive",
                "method": "partition + compression",
            },
            "metrics_older_than_1_year": {
                "action": "aggregate and archive",
                "method": "rollup + archive",
            },
        },
        "scaling_recommendations": {
            "read_replicas": "Consider read replicas for analytics queries",
            "connection_pooling": "Use PgBouncer for connection management",
            "caching_layer": "Redis for session and query caching",
            "search_engine": "Elasticsearch for advanced search features",
        },
    }
