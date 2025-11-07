# Monitoring Database ERD (Entity Relationship Diagram)

## Overview
This ERD documents the comprehensive monitoring and observability database schema for the Multimodal Enterprise RAG System. The schema is designed to support SLI/SLO tracking, performance monitoring, user analytics, system health monitoring, and business metrics.

## Core Entity Groups

### 1. SLI/SLO Monitoring (Service Level Monitoring)

```mermaid
erDiagram
    organizations ||--o{ service_level_indicators : defines
    organizations ||--o{ sli_measurements : measures
    organizations ||--o{ slo_breach_events : experiences
    service_level_indicators ||--o{ sli_measurements : generates
    service_level_indicators ||--o{ slo_breach_events : triggers

    organizations {
        uuid id PK
        string name
        string plan
        jsonb settings
        timestamp created_at
        timestamp updated_at
        boolean is_deleted
    }

    service_level_indicators {
        uuid id PK
        string sli_name
        string sli_category
        text description
        uuid organization_id FK
        string metric_source
        jsonb metric_query
        integer aggregation_window_minutes
        string aggregation_function
        float slo_target_percentile
        float slo_target_value
        string slo_target_unit
        integer slo_period_days
        float alert_burn_rate_threshold
        jsonb alert_notification_channels
        timestamp created_at
        timestamp updated_at
        boolean is_deleted
    }

    sli_measurements {
        uuid id PK
        uuid sli_id FK
        uuid organization_id FK
        timestamp measurement_time
        timestamp window_start
        timestamp window_end
        float measurement_value
        string measurement_unit
        boolean meets_slo
        float slo_budget_consumed
        float slo_budget_remaining
        integer sample_size
        float data_quality_score
        string environment
        string region
        string node_id
        date measurement_date
        integer measurement_hour
        timestamp created_at
        string batch_id
    }

    slo_breach_events {
        uuid id PK
        uuid sli_id FK
        uuid organization_id FK
        timestamp breach_start
        timestamp breach_end
        integer breach_duration_minutes
        string breach_severity
        float sli_value_before_breach
        float sli_value_during_breach
        float slo_target_value
        integer affected_users_count
        integer affected_requests_count
        float business_impact_score
        decimal revenue_impact_estimate
        string root_cause_category
        text root_cause_details
        jsonb contributing_factors
        string resolution_status
        jsonb resolution_actions
        string post_mortem_url
        timestamp created_at
        timestamp updated_at
        timestamp detected_at
    }
```

### 2. Performance Monitoring

```mermaid
erDiagram
    organizations ||--o{ performance_metrics : generates
    organizations ||--o{ database_performance_metrics : tracks
    organizations ||--o{ resource_utilization_metrics : monitors
    organizations ||--o{ queue_monitoring_metrics : processes

    performance_metrics {
        uuid id PK
        string metric_name
        string metric_category
        string component_name
        uuid organization_id FK
        timestamp timestamp
        float value
        string unit
        float p50
        float p90
        float p95
        float p99
        float p999
        float min_value
        float max_value
        float std_deviation
        integer request_count
        integer error_count
        bigint total_request_size_bytes
        bigint total_response_size_bytes
        string environment
        string node_id
        string pod_name
        string deployment_version
        jsonb tags
        string trace_id
        string span_id
        date metric_date
        integer metric_hour
        timestamp created_at
        string batch_id
        boolean processed
    }

    database_performance_metrics {
        uuid id PK
        string database_type
        string database_instance
        uuid organization_id FK
        timestamp timestamp
        integer active_connections
        integer idle_connections
        integer max_connections
        float connection_utilization_percent
        float queries_per_second
        integer slow_queries_count
        float avg_query_time_ms
        float p95_query_time_ms
        float p99_query_time_ms
        float cpu_usage_percent
        bigint memory_usage_bytes
        float memory_usage_percent
        bigint disk_usage_bytes
        float disk_usage_percent
        float disk_io_read_mb_per_sec
        float disk_io_write_mb_per_sec
        jsonb database_metrics
        date metric_date
        integer metric_hour
        timestamp created_at
    }

    resource_utilization_metrics {
        uuid id PK
        string resource_type
        string resource_id
        string resource_name
        uuid organization_id FK
        timestamp timestamp
        float cpu_usage_cores
        float cpu_usage_percent
        float cpu_limit_cores
        float cpu_request_cores
        bigint memory_usage_bytes
        float memory_usage_percent
        bigint memory_limit_bytes
        bigint memory_request_bytes
        bigint memory_cache_bytes
        bigint disk_usage_bytes
        float disk_usage_percent
        float disk_io_reads_per_sec
        float disk_io_writes_per_sec
        bigint disk_read_bytes_per_sec
        bigint disk_write_bytes_per_sec
        bigint network_rx_bytes_per_sec
        bigint network_tx_bytes_per_sec
        float network_rx_packets_per_sec
        float network_tx_packets_per_sec
        integer network_connections_active
        float gpu_usage_percent
        bigint gpu_memory_usage_bytes
        float gpu_memory_usage_percent
        float gpu_utilization
        string environment
        string node_name
        string namespace
        jsonb labels
        date metric_date
        integer metric_hour
        timestamp created_at
    }

    queue_monitoring_metrics {
        uuid id PK
        string queue_name
        string queue_type
        string service_name
        uuid organization_id FK
        timestamp timestamp
        integer queue_depth
        bigint queue_size_bytes
        integer workers_active
        integer workers_idle
        integer workers_total
        float jobs_processed_per_minute
        float jobs_failed_per_minute
        float jobs_successful_per_minute
        float avg_processing_time_seconds
        float p95_processing_time_seconds
        float max_processing_time_seconds
        float error_rate_percent
        integer retry_count
        integer dead_letter_queue_size
        float memory_usage_mb
        float cpu_usage_percent
        jsonb queue_metrics
        string environment
        string node_id
        date metric_date
        integer metric_hour
        timestamp created_at
    }
```

### 3. User Analytics and Session Management

```mermaid
erDiagram
    organizations ||--o{ users : has
    organizations ||--o{ user_sessions : hosts
    organizations ||--o{ user_activity_events : generates
    organizations ||--o{ feature_usage_metrics : tracks
    users ||--o{ user_sessions : creates
    users ||--o{ user_activity_events : performs
    users ||--o{ feature_usage_metrics : uses
    user_sessions ||--o{ user_activity_events : contains

    users {
        uuid id PK
        string email
        string name
        uuid organization_id FK
        string role
        jsonb preferences
        timestamp created_at
        timestamp updated_at
        boolean is_deleted
    }

    user_sessions {
        uuid id PK
        uuid user_id FK
        uuid organization_id FK
        string session_id
        string session_token_hash
        timestamp session_start
        timestamp session_end
        integer session_duration_seconds
        timestamp last_activity
        string session_status
        string termination_reason
        text user_agent
        inet ip_address
        string country
        string city
        string device_type
        string browser
        string os
        string authentication_method
        boolean mfa_verified
        integer pages_viewed
        integer searches_performed
        integer documents_viewed
        integer api_requests_made
        float data_uploaded_mb
        float data_downloaded_mb
        jsonb security_flags
        float risk_score
        timestamp created_at
        timestamp updated_at
    }

    user_activity_events {
        uuid id PK
        uuid user_id FK
        uuid organization_id FK
        string session_id
        string event_type
        string event_category
        string event_action
        text event_description
        timestamp event_timestamp
        integer event_duration_ms
        text page_url
        string api_endpoint
        text referrer_url
        jsonb event_properties
        jsonb request_payload
        jsonb response_payload
        integer response_time_ms
        integer database_query_time_ms
        integer external_service_time_ms
        float business_value
        string conversion_step
        text user_agent
        inet ip_address
        string device_fingerprint
        date event_date
        integer event_hour
        timestamp created_at
        boolean processed
        string batch_id
    }

    feature_usage_metrics {
        uuid id PK
        uuid organization_id FK
        uuid user_id FK
        string feature_name
        string feature_category
        string feature_version
        timestamp usage_timestamp
        integer usage_duration_seconds
        jsonb usage_context
        jsonb feature_parameters
        integer user_satisfaction_score
        text user_feedback
        integer feature_response_time_ms
        boolean feature_error_occurred
        text feature_error_message
        jsonb business_outcome
        decimal revenue_impact
        string experiment_id
        string variant_name
        boolean is_control_group
        date usage_date
        timestamp created_at
    }
```

### 4. System Health and Status Monitoring

```mermaid
erDiagram
    organizations ||--o{ service_health_status : monitors
    organizations ||--o{ system_alerts : experiences

    service_health_status {
        uuid id PK
        string service_name
        string service_type
        string service_instance
        uuid organization_id FK
        string health_status
        string status_reason
        float health_score
        timestamp check_timestamp
        integer check_duration_ms
        string check_type
        string check_url
        integer check_status_code
        jsonb dependencies
        jsonb dependency_status
        integer response_time_ms
        float cpu_usage_percent
        float memory_usage_percent
        float error_rate_percent
        integer active_connections
        integer queue_depth
        float cache_hit_rate
        string environment
        string region
        string availability_zone
        string node_id
        boolean alert_triggered
        string alert_severity
        timestamp last_alert_sent
        timestamp created_at
        timestamp first_failure_timestamp
        integer failure_duration_minutes
    }

    system_alerts {
        uuid id PK
        string alert_name
        string alert_type
        string alert_severity
        uuid organization_id FK
        timestamp triggered_at
        timestamp acknowledged_at
        timestamp resolved_at
        integer duration_minutes
        string alert_status
        text alert_description
        jsonb alert_details
        jsonb affected_services
        jsonb affected_components
        string metric_name
        float metric_value
        float threshold_value
        string threshold_operator
        text business_impact
        integer affected_users_count
        decimal estimated_revenue_impact
        string assigned_to
        jsonb response_actions
        text resolution_summary
        boolean notification_sent
        jsonb notification_channels
        jsonb stakeholders_notified
        boolean post_mortem_required
        boolean post_mortem_completed
        string post_mortem_url
        text lessons_learned
        jsonb prevention_measures
        jsonb monitoring_improvements
        timestamp created_at
        timestamp updated_at
    }
```

### 5. Business and Quality Metrics

```mermaid
erDiagram
    organizations ||--o{ document_processing_metrics : processes
    organizations ||--o{ search_quality_metrics : measures
    organizations ||--o{ rag_quality_metrics : evaluates
    users ||--o{ document_processing_metrics : uploads
    users ||--o{ search_quality_metrics : performs
    users ||--o{ rag_quality_metrics : queries

    document_processing_metrics {
        uuid id PK
        uuid organization_id FK
        uuid user_id FK
        uuid document_id
        string document_name
        string document_type
        bigint document_size_bytes
        string file_extension
        timestamp upload_timestamp
        timestamp processing_started
        timestamp processing_completed
        integer total_processing_time_seconds
        integer upload_time_seconds
        integer validation_time_seconds
        integer ocr_time_seconds
        integer transcription_time_seconds
        integer embedding_time_seconds
        integer indexing_time_seconds
        integer quality_check_time_seconds
        string processing_status
        string failure_reason
        string failure_stage
        integer retry_count
        float ocr_quality_score
        float transcription_quality_score
        float overall_quality_score
        integer pages_processed
        integer text_extracted_chars
        integer entities_extracted
        integer metadata_extracted_fields
        float cpu_time_seconds
        float memory_peak_mb
        float gpu_time_seconds
        integer api_calls_made
        decimal processing_cost_usd
        decimal storage_cost_usd_per_month
        string processing_node
        string environment
        timestamp created_at
        string batch_id
    }

    search_quality_metrics {
        uuid id PK
        uuid organization_id FK
        uuid user_id FK
        string session_id
        uuid search_id
        text query_text
        string query_type
        timestamp search_timestamp
        integer total_response_time_ms
        integer vector_search_time_ms
        integer graph_search_time_ms
        integer keyword_search_time_ms
        integer reranking_time_ms
        integer total_results_count
        integer returned_results_count
        integer results_filtered_count
        float relevance_score
        float diversity_score
        float freshness_score
        float overall_quality_score
        integer clicked_results
        jsonb clicked_result_positions
        integer time_to_first_click_ms
        integer session_search_position
        integer user_rating
        text user_feedback
        boolean feedback_helpful
        jsonb filters_applied
        string sort_order
        string search_scope
        jsonb search_context
        boolean cache_hit
        integer cache_response_time_ms
        integer database_queries_count
        integer external_api_calls_count
        string conversion_event
        decimal business_value
        timestamp created_at
        boolean processed
        date search_date
        integer search_hour
    }

    rag_quality_metrics {
        uuid id PK
        uuid organization_id FK
        uuid user_id FK
        uuid query_id
        text query_text
        timestamp query_timestamp
        string query_type
        integer retrieval_time_ms
        integer context_preparation_time_ms
        integer generation_time_ms
        integer total_pipeline_time_ms
        integer retrieved_documents_count
        float context_relevance_score
        float context_completeness_score
        float context_freshness_score
        float answer_relevance_score
        float answer_accuracy_score
        float answer_completeness_score
        float faithfulness_score
        float rag_triad_score
        jsonb modality_types
        float cross_modal_coherence_score
        float multimodal_integration_score
        integer user_satisfaction_score
        text user_feedback
        boolean helpful_vote
        boolean hallucination_detected
        string hallucination_severity
        integer factual_errors_count
        integer sources_cited
        float source_attribution_accuracy
        string retrieval_model
        string generation_model
        string embedding_model
        decimal api_cost_usd
        integer token_count
        timestamp created_at
        string evaluation_batch_id
        date query_date
        integer query_hour
    }
```

### 6. Monitoring Configuration and Metadata

```mermaid
erDiagram
    organizations ||--o{ monitoring_dashboards : owns
    organizations ||--o{ alerting_rules : configures
    organizations ||--o{ data_retention_policies : applies
    users ||--o{ monitoring_dashboards : creates
    users ||--o{ alerting_rules : defines

    monitoring_dashboards {
        uuid id PK
        uuid organization_id FK
        string dashboard_name
        text dashboard_description
        string dashboard_type
        jsonb layout_config
        string time_range_default
        integer refresh_interval_seconds
        boolean is_public
        jsonb allowed_roles
        jsonb allowed_users
        uuid created_by FK
        timestamp created_at
        timestamp updated_at
        timestamp last_accessed
        integer access_count
        boolean is_deleted
    }

    alerting_rules {
        uuid id PK
        uuid organization_id FK
        string rule_name
        text rule_description
        string rule_category
        string metric_name
        string metric_source
        string condition_operator
        float threshold_value
        integer threshold_duration_minutes
        jsonb advanced_conditions
        boolean rule_enabled
        string rule_severity
        jsonb notification_channels
        jsonb notification_template
        integer notification_cooldown_minutes
        jsonb suppression_rules
        jsonb maintenance_windows
        uuid created_by FK
        timestamp created_at
        timestamp updated_at
        timestamp last_triggered
        integer trigger_count
        boolean is_deleted
    }

    data_retention_policies {
        uuid id PK
        uuid organization_id FK
        string policy_name
        string table_name
        integer detailed_retention_days
        integer hourly_retention_days
        integer daily_retention_days
        integer monthly_retention_years
        integer archive_after_days
        string archive_storage
        boolean archive_compression
        boolean auto_purge_enabled
        integer purge_after_days
        boolean purge_confirmation_required
        boolean policy_enabled
        timestamp last_run
        timestamp next_run
        string run_status
        text run_error_message
        bigint total_records_processed
        bigint total_records_archived
        bigint total_records_purged
        float storage_saved_gb
        timestamp created_at
        timestamp updated_at
    }
```

## Key Relationships and Data Flow

### Primary Data Flow Patterns

1. **SLI/SLO Flow**:
   - Organizations define SLIs → SLI measurements are collected → Breach events are triggered

2. **Performance Data Flow**:
   - Components generate metrics → Time-series aggregation → Alert rule evaluation → System alerts

3. **User Analytics Flow**:
   - Users create sessions → Activity events are logged → Feature usage is tracked → Business metrics are calculated

4. **Quality Metrics Flow**:
   - Documents are processed → Search queries are performed → RAG responses are generated → Quality scores are calculated

5. **System Health Flow**:
   - Services are monitored → Health status is updated → Alerts are triggered → Incidents are managed

### Critical Foreign Key Relationships

- `organization_id` appears in almost all tables for multi-tenancy
- `user_id` links user activities, sessions, and quality metrics
- Time-based partitioning through date/hour fields for performance optimization
- JSONB fields provide flexibility for evolving monitoring requirements

### Data Volume Considerations

- **High-Frequency Tables**: `performance_metrics`, `resource_utilization_metrics`, `sli_measurements`
- **Medium-Frequency Tables**: `user_activity_events`, `search_quality_metrics`, `queue_monitoring_metrics`
- **Low-Frequency Tables**: `slo_breach_events`, `system_alerts`, `document_processing_metrics`

## Performance Optimization Notes

1. **Time-series partitioning** on date/hour fields for large tables
2. **JSONB GIN indexes** for flexible tag and metadata queries
3. **Composite indexes** for common query patterns (org + time, metric + time)
4. **Separate alert tables** to avoid impacting monitoring query performance
5. **Archive and purge policies** to manage data growth over time