-- Multimodal Enterprise RAG System - Redis Configuration and Setup
-- This script configures Redis with data structures, caching strategies, and real-time features

-- =================================================================
-- BASIC CONFIGURATION
-- =================================================================

-- Memory configuration
redis.call('CONFIG', 'SET', 'maxmemory', '256mb')
redis.call('CONFIG', 'SET', 'maxmemory-policy', 'allkeys-lru')

-- Security configuration
redis.call('CONFIG', 'SET', 'requirepass', 'REDACTED')

-- Performance configuration
redis.call('CONFIG', 'SET', 'tcp-keepalive', '300')
redis.call('CONFIG', 'SET', 'timeout', '0')

-- =================================================================
-- CACHE CONFIGURATION STRUCTURES
-- =================================================================

-- Cache configuration hashes
redis.call('HSET', 'cache_configs', 'search_ttl', '3600')
redis.call('HSET', 'cache_configs', 'search_max_size', '1000')
redis.call('HSET', 'cache_configs', 'document_ttl', '7200')
redis.call('HSET', 'cache_configs', 'document_max_size', '500')
redis.call('HSET', 'cache_configs', 'entity_ttl', '1800')
redis.call('HSET', 'cache_configs', 'entity_max_size', '2000')
redis.call('HSET', 'cache_configs', 'user_ttl', '1800')
redis.call('HSET', 'cache_configs', 'user_max_size', '1000')
redis.call('HSET', 'cache_configs', 'session_ttl', '86400')
redis.call('HSET', 'cache_configs', 'session_max_size', '500')

-- Rate limiting configurations
redis.call('HSET', 'rate_limits', 'search_per_minute', '60')
redis.call('HSET', 'rate_limits', 'upload_per_hour', '100')
redis.call('HSET', 'rate_limits', 'api_requests_per_minute', '1000')
redis.call('HSET', 'rate_limits', 'login_attempts_per_hour', '10')

-- Feature flags
redis.call('HSET', 'feature_flags', 'multimodal_search', 'true')
redis.call('HSET', 'feature_flags', 'advanced_analytics', 'true')
redis.call('HSET', 'feature_flags', 'real_time_updates', 'false')
redis.call('HSET', 'feature_flags', 'experimental_features', 'false')

-- =================================================================
-- PUB/SUB CHANNELS
-- =================================================================

-- Active channels for real-time updates
redis.call('SADD', 'active_channels', 'search_updates')
redis.call('SADD', 'active_channels', 'processing_jobs')
redis.call('SADD', 'active_channels', 'notifications')
redis.call('SADD', 'active_channels', 'user_activity')
redis.call('SADD', 'active_channels', 'system_events')
redis.call('SADD', 'active_channels', 'document_updates')
redis.call('SADD', 'active_channels', 'entity_updates')

-- Channel configurations
redis.call('HSET', 'channel_configs', 'search_updates', '{"retention": 3600, "max_subscribers": 1000}')
redis.call('HSET', 'channel_configs', 'processing_jobs', '{"retention": 7200, "max_subscribers": 500}')
redis.call('HSET', 'channel_configs', 'notifications', '{"retention": 86400, "max_subscribers": 2000}')
redis.call('HSET', 'channel_configs', 'user_activity', '{"retention": 1800, "max_subscribers": 100}')

-- =================================================================
-- USER SESSIONS
-- =================================================================

-- Session management structure
redis.call('HSET', 'session_configs', 'default_timeout', '3600')
redis.call('HSET', 'session_configs', 'max_sessions_per_user', '5')
redis.call('HSET', 'session_configs', 'cleanup_interval', '300')

-- Sample session data (for development)
local sampleSession = {
    user_id = '550e8400-e29b-41d4-a716-446655440002',
    organization_id = '550e8400-e29b-41d4-a716-446655440001',
    email = 'admin@demo.com',
    role = 'admin',
    permissions = '{"read": true, "write": true, "admin": true}',
    created_at = '2024-01-01T00:00:00Z',
    last_activity = '2024-01-01T12:00:00Z',
    ip_address = '127.0.0.1',
    user_agent = 'Mozilla/5.0 (compatible; RAG-System/1.0)'
}

redis.call('HMSET', 'session:demo_session_001', unpack(sampleSession))
redis.call('EXPIRE', 'session:demo_session_001', 3600)

-- =================================================================
-- SEARCH CACHE STRUCTURES
-- =================================================================

-- Search result cache templates
redis.call('HMSET', 'search_cache:template',
    'query_hash', '',
    'results', '',
    'total_count', '0',
    'search_time_ms', '0',
    'cache_time', '0',
    'ttl', '3600'
)

-- Popular searches tracking
redis.call('ZADD', 'popular_searches', 10, 'artificial intelligence')
redis.call('ZADD', 'popular_searches', 8, 'machine learning')
redis.call('ZADD', 'popular_searches', 6, 'cloud computing')
redis.call('ZADD', 'popular_searches', 5, 'data analytics')
redis.call('ZADD', 'popular_searches', 4, 'neural networks')

-- Search suggestions cache
redis.call('SADD', 'search_suggestions:ai', 'artificial intelligence', 'machine learning', 'deep learning', 'neural networks')
redis.call('SADD', 'search_suggestions:cloud', 'cloud computing', 'aws', 'azure', 'google cloud', 'serverless')
redis.call('SADD', 'search_suggestions:data', 'data analytics', 'big data', 'data science', 'database')

-- =================================================================
-- RATE LIMITING STRUCTURES
-- =================================================================

-- Rate limiting sliding window implementation
local function setupRateLimiting()
    -- Search rate limiting per user
    redis.call('HMSET', 'rate_limit:search:user:550e8400-e29b-41d4-a716-446655440002',
        'count', '0',
        'window_start', tostring(ARGV[1]),
        'limit', '60'
    )

    -- API rate limiting per organization
    redis.call('HMSET', 'rate_limit:api:org:550e8400-e29b-41d4-a716-446655440001',
        'count', '0',
        'window_start', tostring(ARGV[1]),
        'limit', '1000'
    )

    -- Upload rate limiting per user
    redis.call('HMSET', 'rate_limit:upload:user:550e8400-e29b-41d4-a716-446655440002',
        'count', '0',
        'window_start', tostring(ARGV[1]),
        'limit', '100'
    )
end

-- Initialize rate limiting
setupRateLimiting()

-- =================================================================
-- DOCUMENT PROCESSING QUEUE
-- =================================================================

-- Job queue configuration
redis.call('HMSET', 'queue_configs', 'processing_jobs', '{"max_size": 1000, "priority_levels": 5}')
redis.call('HMSET', 'queue_configs', 'search_indexing', '{"max_size": 500, "priority_levels": 3}')
redis.call('HMSET', 'queue_configs', 'notifications', '{"max_size": 2000, "priority_levels": 1}')

-- Sample processing jobs
local job1 = {
    id = 'job_001',
    type = 'document_ingestion',
    status = 'pending',
    priority = '5',
    organization_id = '550e8400-e29b-41d4-a716-446655440001',
    user_id = '550e8400-e29b-41d4-a716-446655440002',
    document_id = '550e8400-e29b-41d4-a716-446655440004',
    created_at = tostring(ARGV[1]),
    retry_count = '0',
    max_retries = '3'
}

redis.call('HMSET', 'job:job_001', unpack(job1))
redis.call('LPUSH', 'queue:processing_jobs', 'job_001')

local job2 = {
    id = 'job_002',
    type = 'entity_extraction',
    status = 'pending',
    priority = '4',
    organization_id = '550e8400-e29b-41d4-a716-446655440001',
    user_id = '550e8400-e29b-41d4-a716-446655440003',
    document_id = '550e8400-e29b-41d4-a716-446655440005',
    created_at = tostring(ARGV[1]),
    retry_count = '0',
    max_retries = '3'
}

redis.call('HMSET', 'job:job_002', unpack(job2))
redis.call('LPUSH', 'queue:processing_jobs', 'job_002')

-- =================================================================
-- ANALYTICS AND METRICS
-- =================================================================

-- Real-time metrics counters
redis.call('HMSET', 'metrics:system',
    'total_searches', '0',
    'total_documents', '0',
    'total_users', '2',
    'active_sessions', '1',
    'processing_jobs', '2',
    'cache_hit_rate', '0.85'
)

-- Organization-specific metrics
redis.call('HMSET', 'metrics:org:550e8400-e29b-41d4-a716-446655440001',
    'search_count', '0',
    'document_count', '2',
    'user_count', '2',
    'storage_used_gb', '0.1',
    'avg_response_time_ms', '150',
    'last_activity', tostring(ARGV[1])
)

-- User activity tracking
redis.call('HMSET', 'metrics:user:550e8400-e29b-41d4-a716-446655440002',
    'search_count', '0',
    'document_uploads', '1',
    'session_count', '1',
    'last_login', tostring(ARGV[1]),
    'total_time_minutes', '0'
)

-- Time series data for performance monitoring
local timestamp = math.floor(ARGV[1])
redis.call('ZADD', 'timeseries:search_response_time', timestamp, '150')
redis.call('ZADD', 'timeseries:document_processing_time', timestamp, '2000')
redis.call('ZADD', 'timeseries:api_response_time', timestamp, '120')
redis.call('ZADD', 'timeseries:cache_hit_rate', timestamp, '0.85')

-- =================================================================
-- NOTIFICATION SYSTEM
-- =================================================================

-- Notification queues by user
redis.call('HMSET', 'notification:user:550e8400-e29b-41d4-a716-446655440002:1',
    'id', 'notif_001',
    'type', 'info',
    'title', 'Welcome to RAG System',
    'message', 'Your account has been successfully created.',
    'created_at', tostring(ARGV[1]),
    'read', 'false',
    'priority', 'normal'
)

redis.call('LPUSH', 'notifications:user:550e8400-e29b-41d4-a716-446655440002', 'notif_001')

-- System-wide notifications
redis.call('HMSET', 'notification:system:1',
    'id', 'sys_notif_001',
    'type', 'system',
    'title', 'System Maintenance',
    'message', 'Scheduled maintenance will occur at 2:00 AM UTC.',
    'created_at', tostring(ARGV[1]),
    'expires_at', tostring(ARGV[1] + 86400),
    'severity', 'info'
)

-- =================================================================
-- LOCKS AND SEMAPHORES
-- =================================================================

-- Distributed locks for critical operations
redis.call('HMSET', 'lock_config:document_upload',
    'timeout', '300',
    'max_concurrent', '5',
    'retry_delay', '1'
)

redis.call('HMSET', 'lock_config:entity_extraction',
    'timeout', '600',
    'max_concurrent', '3',
    'retry_delay', '2'
)

-- Sample lock
if redis.call('SET', 'lock:document_upload:doc_001', 'locked', 'EX', 300, 'NX') then
    redis.call('HMSET', 'lock:document_upload:doc_001:meta',
        'owner', 'worker_001',
        'acquired_at', tostring(ARGV[1]),
        'expires_at', tostring(ARGV[1] + 300)
    )
end

-- =================================================================
-- HEALTH CHECK AND MONITORING
-- =================================================================

-- Health check indicators
redis.call('HMSET', 'health:system',
    'status', 'healthy',
    'last_check', tostring(ARGV[1]),
    'memory_usage', '45mb',
    'connected_clients', '1',
    'total_commands', '1000',
    'keyspace_hits', '850',
    'keyspace_misses', '150'
)

-- Service health indicators
redis.call('HMSET', 'health:postgresql',
    'status', 'healthy',
    'last_check', tostring(ARGV[1]),
    'response_time_ms', '15',
    'connection_pool', '5/10'
)

redis.call('HMSET', 'health:neo4j',
    'status', 'healthy',
    'last_check', tostring(ARGV[1]),
    'response_time_ms', '25',
    'active_connections', '3'
)

redis.call('HMSET', 'health:qdrant',
    'status', 'healthy',
    'last_check', tostring(ARGV[1]),
    'response_time_ms', '10',
    'collections_count', '3'
)

-- =================================================================
-- UTILITY FUNCTIONS
-- =================================================================

-- Function to get cache key with namespace
local function getCacheKey(namespace, key)
    return namespace .. ':' .. key
end

-- Function to set cache with TTL
local function setCacheWithTTL(key, value, ttl)
    redis.call('HMSET', key, 'data', value, 'cached_at', tostring(ARGV[1]))
    redis.call('EXPIRE', key, ttl)
end

-- Function to get rate limit status
local function checkRateLimit(identifier, limit, window)
    local current_time = tonumber(ARGV[1])
    local window_start = current_time - window

    local rate_key = 'rate_limit:' .. identifier
    redis.call('ZREMRANGEBYSCORE', rate_key, '-inf', window_start)
    local current_count = redis.call('ZCARD', rate_key)

    if current_count < limit then
        redis.call('ZADD', rate_key, current_time, tostring(current_time))
        redis.call('EXPIRE', rate_key, window)
        return true, limit - current_count - 1
    else
        return false, 0
    end
end

-- Store function definitions
redis.call('SCRIPT', 'LOAD', 'return getCacheKey(KEYS[1], ARGV[1])')
redis.call('SCRIPT', 'LOAD', 'return setCacheWithTTL(KEYS[1], ARGV[1], tonumber(ARGV[2]))')

-- =================================================================
-- COMPLETION AND SUMMARY
-- =================================================================

-- Setup summary
local setup_summary = {
    total_keys_created = redis.call('DBSIZE'),
    cache_configs = redis.call('HLEN', 'cache_configs'),
    rate_limits = redis.call('HLEN', 'rate_limits'),
    feature_flags = redis.call('HLEN', 'feature_flags'),
    active_channels = redis.call('SCARD', 'active_channels'),
    sample_sessions = 1,
    sample_jobs = 2,
    sample_notifications = 2
}

-- Store setup summary
redis.call('HMSET', 'setup_summary', unpack(setup_summary))
redis.call('HMSET', 'setup_summary', 'completed_at', tostring(ARGV[1]))
redis.call('HMSET', 'setup_summary', 'status', 'completed')

-- Return success message
return {
    status = 'success',
    message = 'Redis configuration completed successfully',
    summary = setup_summary,
    timestamp = ARGV[1]
}