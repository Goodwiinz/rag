# Redis Data Structures Design
## Real-time Caching and Session Management for Multimodal Enterprise RAG

This document defines the comprehensive Redis data structures used for caching, session management, real-time updates, and performance optimization in the Multimodal Enterprise RAG system.

---

## 1. Session Management

### 1.1 User Sessions
```redis
// Session data structure with TTL management
session:{session_id} -> Hash {
    user_id: UUID,
    organization_id: UUID,
    email: string,
    role: string,
    first_name: string,
    last_name: string,
    created_at: ISO8601_timestamp,
    last_activity: ISO8601_timestamp,
    expires_at: ISO8601_timestamp,
    ip_address: string,
    user_agent: string,
    device_fingerprint: string,
    preferences: JSON,
    ui_settings: JSON,
    current_query_count: integer,
    total_queries: integer,
    features_used: JSON,
    security_flags: JSON
}

// Session TTL management
TTL session:{session_id} = 3600 (1 hour)

// Active sessions by user (for session management)
user_sessions:{user_id} -> Set[session_id]

// Organization active sessions (for analytics and monitoring)
org_sessions:{organization_id} -> Set[session_id]
```

### 1.2 WebSocket Connection Management
```redis
// WebSocket connection tracking for real-time updates
ws_connections:{session_id} -> Hash {
    connection_id: string,
    node_id: string,
    connected_at: ISO8601_timestamp,
    last_ping: ISO8601_timestamp,
    last_pong: ISO8601_timestamp,
    subscriptions: JSON {
        processing_status: boolean,
        search_results: boolean,
        system_alerts: boolean,
        document_updates: boolean
    },
    connection_metadata: JSON {
        client_version: string,
        browser: string,
        platform: string,
        screen_resolution: string
    }
}

// User's active connections across devices
user_ws:{user_id} -> Set[connection_id]

// Organization WebSocket channels for broadcasting
ws_org:{organization_id} -> Set[connection_id]

// Topic-based subscriptions
ws_topic:{topic_name} -> Set[connection_id]  // e.g., processing_status, search_results
```

### 1.3 Session Analytics
```redis
// Real-time session metrics
session_metrics:{organization_id}:current -> Hash {
    active_sessions: integer,
    total_users_today: integer,
    avg_session_duration: integer,
    peak_concurrent_sessions: integer,
    session_start_rate: integer,  // sessions per minute
    session_end_rate: integer,
    current_time: ISO8601_timestamp
}

// Historical session analytics (time-series)
session_metrics:{organization_id}:history -> SortedSet {
    timestamp: score,
    JSON_data: member  // Contains session metrics snapshot
}

// User session patterns
user_session_patterns:{user_id} -> Hash {
    preferred_search_types: JSON,
    avg_session_duration: integer,
    typical_session_start_hour: integer,
    most_used_features: JSON,
    last_session_patterns: JSON
}
```

---

## 2. Document Processing Cache

### 2.1 Processing Status Cache
```redis
// Real-time document processing status
processing_status:{document_id} -> Hash {
    status: string,  // queued, processing, completed, failed, retrying
    progress_percentage: integer,
    current_step: string,  // ocr, transcription, embedding, entity_extraction
    started_at: ISO8601_timestamp,
    estimated_completion: ISO8601_timestamp,
    total_steps: integer,
    completed_steps: integer,
    error_message: string,
    error_details: JSON,
    processing_metadata: JSON {
        worker_id: string,
        queue_position: integer,
        priority: integer,
        retry_count: integer,
        max_retries: integer
    }
}

// TTL for processing status
TTL processing_status:{document_id} = 86400 (24 hours)

// Processing queue management
processing_queue:{organization_id} -> List[JSON {
    document_id: UUID,
    priority: integer,
    queued_at: ISO8601_timestamp,
    estimated_duration: integer,
    file_type: string,
    file_size: integer
}]

// Failed processing retry queue
processing_retry_queue -> SortedSet {
    retry_timestamp: score,
    JSON_data: member {
        document_id: UUID,
        retry_count: integer,
        error_type: string,
        backoff_multiplier: integer
    }
}
```

### 2.2 Document Content Cache
```redis
// Cached document content for fast retrieval
document_content:{document_id} -> Hash {
    text_content: string,
    summary: string,
    extracted_entities: JSON,
    extracted_metadata: JSON,
    quality_score: float,
    processing_completed_at: ISO8601_timestamp,
    cache_version: integer,
    access_count: integer,
    last_accessed: ISO8601_timestamp
}

// TTL for document content cache
TTL document_content:{document_id} = 86400 (24 hours)

// Multi-modal content cache
multimodal_content:{document_id}:{modality} -> Hash {
    content_type: string,
    extracted_data: JSON,
    quality_score: float,
    confidence: float,
    extraction_method: string,
    created_at: ISO8601_timestamp,
    file_references: JSON
}

// Document quality metrics cache
document_quality:{document_id} -> Hash {
    overall_score: float,
    text_clarity_score: float,
    image_resolution_score: float,
    audio_clarity_score: float,
    video_quality_score: float,
    quality_issues: JSON,
    improvement_recommendations: JSON,
    last_evaluated: ISO8601_timestamp
}
```

### 2.3 Processing Analytics
```redis
// Real-time processing metrics
processing_metrics:{organization_id}:current -> Hash {
    total_processing_time_ms: integer,
    avg_processing_time_ms: integer,
    documents_processed_today: integer,
    processing_success_rate: float,
    queue_length: integer,
    worker_utilization: float,
    error_rate: float,
    most_common_errors: JSON,
    current_time: ISO8601_timestamp
}

// Processing performance by document type
processing_performance:{document_type} -> Hash {
    avg_processing_time_ms: integer,
    success_rate: float,
    avg_quality_score: float,
    error_rate: float,
    total_processed: integer,
    last_updated: ISO8601_timestamp
}

// Worker performance tracking
worker_performance:{worker_id} -> Hash {
    processed_documents: integer,
    avg_processing_time_ms: integer,
    error_count: integer,
    current_load: integer,
    max_concurrent: integer,
    last_activity: ISO8601_timestamp,
    worker_status: string
}
```

---

## 3. Search Results Cache

### 3.1 Query Result Cache
```redis
// Search query cache with intelligent invalidation
search_cache:{query_hash} -> Hash {
    query_text: string,
    organization_id: UUID,
    query_type: string,
    query_parameters: JSON,
    results: JSON {
        documents: Array[{
            document_id: UUID,
            title: string,
            relevance_score: float,
            snippet: string,
            metadata: JSON
        }],
        total_count: integer,
        search_time_ms: integer,
        facets: JSON,
        suggestions: JSON
    },
    total_count: integer,
    execution_time_ms: integer,
    cache_timestamp: ISO8601_timestamp,
    hit_count: integer,
    last_hit: ISO8601_timestamp,
    user_id: UUID,
    session_id: UUID
}

// TTL for search cache based on query complexity
TTL search_cache:{query_hash} = 1800 (30 minutes)

// Popular queries tracking with decay
popular_queries:{organization_id} -> SortedSet {
    query_text: score (frequency * recency_factor)
}

// User-specific recent searches with relevance tracking
user_recent_searches:{user_id} -> List[JSON {
    query_text: string,
    query_hash: string,
    timestamp: ISO8601_timestamp,
    result_count: integer,
    clicked_results: integer,
    user_satisfaction: integer,
    search_type: string
}]
// Keep last 50 searches per user
LTRIM user_recent_searches:{user_id} 0 49
```

### 3.2 Search Performance Metrics
```redis
// Real-time search performance
search_performance:{organization_id}:current -> Hash {
    queries_per_second: float,
    avg_response_time_ms: integer,
    p95_response_time_ms: integer,
    cache_hit_rate: float,
    result_count_avg: float,
    click_through_rate: float,
    user_satisfaction_avg: float,
    error_rate: float,
    current_time: ISO8601_timestamp
}

// Search type performance breakdown
search_performance_by_type:{search_type} -> Hash {
    query_count: integer,
    avg_response_time_ms: integer,
    cache_hit_rate: float,
    user_satisfaction_avg: float,
    result_relevance_avg: float,
    last_updated: ISO8601_timestamp
}

// Query pattern analysis
query_patterns:{organization_id} -> Hash {
    most_common_terms: JSON,
    query_length_distribution: JSON,
    search_type_distribution: JSON,
    time_of_day_patterns: JSON,
    session_query_patterns: JSON,
    last_analyzed: ISO8601_timestamp
}
```

### 3.3 Semantic Search Cache
```redis
// Vector similarity search cache
vector_search_cache:{query_embedding_hash} -> Hash {
    query_vector: array,  // Compressed or referenced
    search_parameters: JSON,
    results: JSON {
        document_ids: Array[UUID],
        similarity_scores: Array[float],
        search_metadata: JSON
    },
    execution_time_ms: integer,
    index_used: string,
    total_candidates: integer,
    filtered_results: integer,
    cache_timestamp: ISO8601_timestamp
}

// TTL for vector search cache
TTL vector_search_cache:{query_embedding_hash} = 3600 (1 hour)

// Embedding cache for frequently queried text
text_embeddings:{text_hash} -> Hash {
    text: string,
    embedding: array[float],
    model: string,
    embedding_version: string,
    created_at: ISO8601_timestamp,
    access_count: integer,
    last_accessed: ISO8601_timestamp
}

// TTL for text embeddings
TTL text_embeddings:{text_hash} = 604800 (7 days)
```

---

## 4. Multi-Modal Content Cache

### 4.1 Image Processing Cache
```redis
// Image analysis and extraction results
image_analysis:{image_hash} -> Hash {
    file_path: string,
    image_metadata: JSON {
        width: integer,
        height: integer,
        format: string,
        size_bytes: integer,
        color_profile: string
    },
    extracted_text: string,
    objects_detected: JSON,
    scene_description: string,
    visual_embeddings: array[float],
    quality_score: float,
    processing_time_ms: integer,
    created_at: ISO8601_timestamp
}

// TTL for image analysis cache
TTL image_analysis:{image_hash} = 604800 (7 days)

// Thumbnail cache
image_thumbnails:{image_hash}:{size} -> String (base64 encoded image)
// Common sizes: small (100x100), medium (300x300), large (800x800)
TTL image_thumbnails:{image_hash}:* = 604800
```

### 4.2 Audio Processing Cache
```redis
// Audio transcription and analysis
audio_analysis:{audio_hash} -> Hash {
    file_path: string,
    audio_metadata: JSON {
        duration_seconds: float,
        sample_rate: integer,
        channels: integer,
        format: string,
        bitrate: integer
    },
    transcription: string,
    speaker_segments: JSON,
    audio_embeddings: array[float],
    speech_quality_score: float,
    processing_time_ms: integer,
    created_at: ISO8601_timestamp
}

// TTL for audio analysis cache
TTL audio_analysis:{audio_hash} = 604800 (7 days)
```

### 4.3 Video Processing Cache
```redis
// Video analysis and frame extraction
video_analysis:{video_hash} -> Hash {
    file_path: string,
    video_metadata: JSON {
        duration_seconds: float,
        fps: float,
        resolution: string,
        codec: string,
        size_bytes: integer
    },
    key_frames: JSON {
        timestamps: Array[float],
        frame_hashes: Array[string],
        frame_descriptions: Array[string]
    },
    audio_transcription: string,
    scene_descriptions: JSON,
    video_embeddings: array[float],
    processing_time_ms: integer,
    created_at: ISO8601_timestamp
}

// Individual frame cache
video_frames:{video_hash}:{frame_hash} -> String (base64 encoded frame)
TTL video_frames:{video_hash}:* = 604800

// TTL for video analysis cache
TTL video_analysis:{video_hash} = 604800 (7 days)
```

---

## 5. Knowledge Graph Cache

### 5.1 Entity Cache
```redis
// Frequently accessed entities
entity_cache:{entity_id} -> Hash {
    entity_name: string,
    entity_type: string,
    canonical_name: string,
    aliases: JSON,
    properties: JSON,
    description: string,
    confidence_score: float,
    document_count: integer,
    relationship_count: integer,
    last_updated: ISO8601_timestamp,
    cache_version: integer
}

// TTL for entity cache
TTL entity_cache:{entity_id} = 3600 (1 hour)

// Entity relationship cache
entity_relationships:{entity_id} -> Hash {
    relationships: JSON {
        target_entities: Array[{
            entity_id: UUID,
            entity_name: string,
            relationship_type: string,
            confidence: float,
            source_documents: Array[UUID]
        }]
    },
    total_relationships: integer,
    relationship_types: JSON,
    last_updated: ISO8601_timestamp
}

// TTL for entity relationships cache
TTL entity_relationships:{entity_id} = 1800 (30 minutes)
```

### 5.2 Graph Traversal Cache
```redis
// Graph path finding cache
graph_paths:{source_entity_id}:{target_entity_id} -> Hash {
    path_type: string,  // shortest, all_paths, weighted
    paths: JSON {
        Array[{
            path: Array[UUID],
            total_weight: float,
            hop_count: integer,
            confidence: float
        }]
    },
    calculation_time_ms: integer,
    graph_version: string,
    cached_at: ISO8601_timestamp
}

// TTL for graph paths cache
TTL graph_paths:* = 1800 (30 minutes)

// Entity similarity cache
entity_similarity:{entity_id_1}:{entity_id_2} -> Hash {
    similarity_score: float,
    similarity_method: string,
    shared_properties: JSON,
    shared_relationships: JSON,
    calculated_at: ISO8601_timestamp
}

// TTL for entity similarity cache
TTL entity_similarity:* = 3600 (1 hour)
```

---

## 6. Real-Time Analytics

### 6.1 Performance Metrics Buffer
```redis
// High-frequency metrics streaming
metrics:performance -> Stream {
    timestamp: ISO8601_timestamp,
    metric_name: string,
    value: float,
    organization_id: UUID,
    component: string,
    metadata: JSON
}

// Real-time aggregation with sliding window
metrics:current:{metric_name}:{organization_id} -> Hash {
    current_value: float,
    count_1m: integer,
    sum_1m: float,
    min_1m: float,
    max_1m: float,
    avg_1m: float,
    count_5m: integer,
    sum_5m: float,
    avg_5m: float,
    last_updated: ISO8601_timestamp
}

// TTL for current metrics (maintain sliding window)
TTL metrics:current:* = 300 (5 minutes)

// Performance alerts threshold checking
metrics:alerts:{organization_id} -> List[JSON {
    alert_type: string,
    metric_name: string,
    current_value: float,
    threshold_value: float,
    severity: string,
    triggered_at: ISO8601_timestamp,
    acknowledged: boolean
}]
```

### 6.2 User Activity Analytics
```redis
// User activity event streaming
activity:user:{user_id} -> Stream {
    event_type: string,
    timestamp: ISO8601_timestamp,
    data: JSON {
        component: string,
        action: string,
        metadata: JSON
    }
}

// Organization activity aggregation
activity:org:{organization_id}:count -> Hash {
    active_users_1m: integer,
    active_users_5m: integer,
    active_users_1h: integer,
    total_queries_1m: integer,
    total_queries_5m: integer,
    total_documents_accessed_1m: integer,
    avg_session_duration_1h: float,
    current_time: ISO8601_timestamp
}

// TTL for activity counters
TTL activity:org:*:count = 300 (5 minutes)

// User behavior patterns
user_patterns:{user_id} -> Hash {
    preferred_search_types: JSON,
    common_query_patterns: JSON,
    peak_activity_hours: JSON,
    average_session_length: float,
    document_type_preferences: JSON,
    feature_usage_frequency: JSON,
    last_analyzed: ISO8601_timestamp
}
```

### 6.3 System Health Monitoring
```redis
// System health status cache
system_health:{component} -> Hash {
    status: string,  // healthy, degraded, critical, offline
    health_score: float,
    response_time_ms: integer,
    success_rate: float,
    error_rate: float,
    last_check: ISO8601_timestamp,
    consecutive_failures: integer,
    dependencies_status: JSON,
    resource_usage: JSON {
        cpu_percent: float,
        memory_mb: integer,
        disk_usage_percent: float
    }
}

// TTL for system health cache
TTL system_health:* = 60 (1 minute)

// Alert management
alerts:active:{organization_id} -> Hash {
    total_alerts: integer,
    critical_alerts: integer,
    warning_alerts: integer,
    info_alerts: integer,
    last_alert: ISO8601_timestamp,
    alert_summary: JSON
}

// Individual alert details
alert:{alert_id} -> Hash {
    alert_type: string,
    severity: string,
    component: string,
    message: string,
    details: JSON,
    triggered_at: ISO8601_timestamp,
    acknowledged: boolean,
    acknowledged_by: UUID,
    acknowledged_at: ISO8601_timestamp,
    resolved: boolean,
    resolved_at: ISO8601_timestamp
}

// TTL for resolved alerts
TTL alert:* = 86400 (24 hours)
```

---

## 7. Rate Limiting and Throttling

### 7.1 API Rate Limiting
```redis
// User-based rate limiting with sliding window
rate_limit:user:{user_id}:{endpoint} -> SortedSet {
    timestamp: score,
    request_id: member
}

// Clean up old entries (maintain sliding window)
ZREMRANGEBYSCORE rate_limit:user:{user_id}:{endpoint} 0 (current_timestamp - window_size)

// Organization-based rate limiting
rate_limit:org:{organization_id}:{endpoint} -> SortedSet {
    timestamp: score,
    request_id: member
}

// IP-based rate limiting
rate_limit:ip:{ip_address}:{endpoint} -> SortedSet {
    timestamp: score,
    request_id: member
}

// Rate limit status cache
rate_limit_status:{user_id}:{endpoint} -> Hash {
    current_count: integer,
    remaining_requests: integer,
    reset_time: ISO8601_timestamp,
    limit_exceeded: boolean,
    retry_after: integer
}

// TTL for rate limit status
TTL rate_limit_status:* = 300 (5 minutes)
```

### 7.2 Resource Usage Limiting
```redis
// File upload rate limiting
upload_limit:user:{user_id} -> Integer (files uploaded in current window)
upload_limit:org:{organization_id} -> Integer (files uploaded in current window)

// TTL for upload limits
TTL upload_limit:user:* = 3600 (1 hour)
TTL upload_limit:org:* = 3600

// Storage quota tracking
storage_quota:user:{user_id} -> Hash {
    used_gb: float,
    document_count: integer,
    last_updated: ISO8601_timestamp,
    quota_limit_gb: float,
    available_gb: float,
    warning_sent: boolean
}

// Organization storage tracking
storage_quota:org:{organization_id} -> Hash {
    used_gb: float,
    document_count: integer,
    user_count: integer,
    last_updated: ISO8601_timestamp,
    quota_limit_gb: float,
    available_gb: float,
    usage_distribution: JSON {
        by_user: JSON,
        by_type: JSON,
        by_modality: JSON
    }
}

// Processing quota limiting
processing_quota:user:{user_id} -> Hash {
    processing_minutes_used: float,
    documents_processed: integer,
    current_hour_requests: integer,
    daily_requests: integer,
    last_reset: ISO8601_timestamp,
    quota_limits: JSON
}
```

---

## 8. Notification and Event System

### 8.1 User Notifications
```redis
// User notification queue
notifications:{user_id} -> List[JSON {
    id: string,
    type: string,  // processing_complete, search_ready, system_alert, etc.
    title: string,
    message: string,
    data: JSON,
    priority: string,  // low, medium, high, urgent
    created_at: ISO8601_timestamp,
    read: boolean,
    read_at: ISO8601_timestamp,
    expires_at: ISO8601_timestamp
}]

// Unread notification count
notifications:unread:{user_id} -> Integer

// Notification delivery tracking
notification_delivery:{notification_id} -> Hash {
    delivery_channels: JSON {
        websocket: boolean,
        email: boolean,
        push: boolean
    },
    delivery_status: JSON,
    last_attempt: ISO8601_timestamp,
    retry_count: integer,
    max_retries: integer
}
```

### 8.2 Real-time Event Broadcasting
```redis
// Organization-wide events
events:org:{organization_id} -> Stream {
    event_id: string,
    event_type: string,
    component: string,
    data: JSON,
    timestamp: ISO8601_timestamp,
    user_id: UUID,  // if user-specific
    broadcast_to: JSON  // channels and user segments
}

// Document processing events
events:processing:{document_id} -> Stream {
    event_type: string,  // started, progress, completed, failed
    step: string,
    progress: integer,
    data: JSON,
    timestamp: ISO8601_timestamp
}

// Search events
events:search:{query_id} -> Stream {
    event_type: string,  // started, results_ready, timeout
    query_metadata: JSON,
    results_summary: JSON,
    timestamp: ISO8601_timestamp
}

// System events
events:system -> Stream {
    event_type: string,  // maintenance, alert, deployment
    severity: string,
    message: string,
    affected_components: JSON,
    timestamp: ISO8601_timestamp
}
```

---

## 9. Cache Management and Optimization

### 9.1 Cache Invalidation Strategy
```redis
// Cache invalidation tracking
cache_invalidation:{entity_type}:{entity_id} -> List[JSON {
    cache_key: string,
    invalidation_reason: string,
    timestamp: ISO8601_timestamp,
    invalidated_by: string
}]

// Smart cache warming
cache_warm:queue -> List[JSON {
    cache_key: string,
    priority: integer,
    warm_strategy: string,
    dependencies: JSON,
    scheduled_at: ISO8601_timestamp
}]

// Cache performance metrics
cache_performance:{cache_type} -> Hash {
    hit_rate: float,
    miss_rate: float,
    avg_response_time_us: integer,
    total_requests: integer,
    cache_size_mb: float,
    eviction_count: integer,
    last_updated: ISO8601_timestamp
}
```

### 9.2 Intelligent Cache Policies
```redis
// Cache configuration by data type
cache_config:{data_type} -> Hash {
    ttl_seconds: integer,
    max_size_mb: float,
    eviction_policy: string,  // lru, lfu, ttl
    compression_enabled: boolean,
    warm_on_startup: boolean,
    refresh_strategy: string
}

// Dynamic cache sizing
cache_sizing:{organization_id} -> Hash {
    total_memory_quota_mb: float,
    allocated_memory_mb: float,
    cache_distribution: JSON {
        search_cache: float,
        document_cache: float,
        session_cache: float,
        analytics_cache: float
    },
    last_optimization: ISO8601_timestamp
}
```

---

## 10. Monitoring and Debugging

### 10.1 Redis Performance Monitoring
```redis
// Redis performance metrics
redis_metrics:performance -> Hash {
    used_memory_mb: float,
    used_memory_peak_mb: float,
    keyspace_hits: integer,
    keyspace_misses: integer,
    connected_clients: integer,
    total_commands_processed: integer,
    instantaneous_ops_per_sec: integer,
    memory_fragmentation_ratio: float,
    last_updated: ISO8601_timestamp
}

// Slow query log
redis_slow_queries -> List[JSON {
    query: string,
    execution_time_us: integer,
    timestamp: ISO8601_timestamp,
    client_info: JSON,
    keyspace: string
}]

// Cache hit rate analytics
cache_analytics:{organization_id} -> Hash {
    overall_hit_rate: float,
    search_cache_hit_rate: float,
    document_cache_hit_rate: float,
    session_cache_hit_rate: float,
    top_missed_keys: JSON,
    cache_efficiency_score: float,
    last_analyzed: ISO8601_timestamp
}
```

### 10.2 Debugging and Diagnostics
```redis
// Request tracing
request_trace:{request_id} -> Hash {
    user_id: UUID,
    organization_id: UUID,
    start_time: ISO8601_timestamp,
    end_time: ISO8601_timestamp,
    components_visited: JSON,
    cache_hits: JSON,
    cache_misses: JSON,
    total_time_ms: integer,
    status: string
}

// Error tracking
error_tracking:{error_id} -> Hash {
    error_type: string,
    error_message: string,
    stack_trace: string,
    user_id: UUID,
    organization_id: UUID,
    request_id: string,
    component: string,
    timestamp: ISO8601_timestamp,
    context: JSON
}

// Performance profiling
profiling:{component}:{session_id} -> Hash {
    operation_counts: JSON,
    timing_breakdown: JSON,
    memory_usage: JSON,
    cache_performance: JSON,
    bottlenecks: JSON,
    profiling_duration_ms: integer
}
```

---

## Usage Examples

### Basic Session Management
```python
# Create new session
await redis.hset(f"session:{session_id}", mapping={
    "user_id": user_id,
    "organization_id": org_id,
    "email": email,
    "role": role,
    "created_at": datetime.utcnow().isoformat(),
    "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
})

await redis.expire(f"session:{session_id}", 3600)

# Add to user's active sessions
await redis.sadd(f"user_sessions:{user_id}", session_id)

# Update last activity
await redis.hset(f"session:{session_id}", "last_activity", datetime.utcnow().isoformat())
```

### Document Processing Status
```python
# Update processing status
await redis.hset(f"processing_status:{document_id}", mapping={
    "status": "processing",
    "progress_percentage": 45,
    "current_step": "entity_extraction",
    "started_at": datetime.utcnow().isoformat()
})

# Notify WebSocket subscribers
await redis.xadd(f"events:processing:{document_id}", {
    "event_type": "progress",
    "step": "entity_extraction",
    "progress": "45",
    "timestamp": datetime.utcnow().isoformat()
})
```

### Search Result Caching
```python
# Cache search results
query_hash = hashlib.md5(query_text.encode()).hexdigest()
await redis.hset(f"search_cache:{query_hash}", mapping={
    "query_text": query_text,
    "organization_id": org_id,
    "results": json.dumps(results),
    "execution_time_ms": execution_time,
    "cache_timestamp": datetime.utcnow().isoformat()
})

await redis.expire(f"search_cache:{query_hash}", 1800)

# Track popular queries
await redis.zincrby(f"popular_queries:{org_id}", 1, query_text)
```

This comprehensive Redis data structure design provides:
- Real-time session management and WebSocket coordination
- Multi-level caching for optimal performance
- Document processing pipeline tracking
- Search result optimization and analytics
- Rate limiting and resource quota enforcement
- Real-time notifications and event broadcasting
- Comprehensive monitoring and debugging capabilities

The design scales to support 50 concurrent users with 99% uptime requirements while maintaining sub-second response times through intelligent caching strategies.