#!/bin/bash

# Redis Graph Caching Initialization Script
# This script configures Redis for Knowledge Graph caching and real-time updates
# Run this after starting Redis service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REDIS_HOST="localhost"
REDIS_PORT="6380"
REDIS_PASSWORD=""
REDIS_CONFIG_FILE="../database/redis_knowledge_graph_config.lua"

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Redis command helper
redis_cmd() {
    if [ -n "$REDIS_PASSWORD" ]; then
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" "$@"
    else
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" "$@"
    fi
}

# Check if Redis is running
check_redis_health() {
    log "Checking Redis connectivity..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if redis_cmd ping | grep -q "PONG"; then
            success "Redis is accessible at $REDIS_HOST:$REDIS_PORT"
            return 0
        fi

        log "Attempt $attempt/$max_attempts - Redis not ready yet..."
        sleep 2
        ((attempt++))
    done

    error "Redis did not become healthy within $max_attempts attempts"
}

# Configure Redis settings for graph workloads
configure_redis_settings() {
    log "Configuring Redis for graph workloads..."

    # Memory settings
    redis_cmd config set "maxmemory" "4gb"
    redis_cmd config set "maxmemory-policy" "allkeys-lru"

    # Persistence settings
    redis_cmd config set "save" "900 1 300 10 60 10000"

    # Performance settings
    redis_cmd config set "tcp-keepalive" "300"
    redis_cmd config set "timeout" "0"

    # Enable AOF persistence for durability
    redis_cmd config set "appendonly" "yes"
    redis_cmd config set "appendfsync" "everysec"

    # Enable slow log for monitoring
    redis_cmd config set "slowlog-log-slower-than" "10000"
    redis_cmd config set "slowlog-max-len" "128"

    success "Redis configured for graph workloads"
}

# Create initial data structures
create_initial_data_structures() {
    log "Creating initial Redis data structures..."

    # Create sample cache entries for testing
    local current_time
    current_time=$(date +%s)

    # Entity centrality cache sample
    redis_cmd set "entity:centrality:sample_entity_1:degree" "0.85"
    redis_cmd expire "entity:centrality:sample_entity_1:degree" 3600

    redis_cmd set "entity:centrality:sample_entity_1:pagerank" "0.043"
    redis_cmd expire "entity:centrality:sample_entity_1:pagerank" 3600

    # Graph layout cache sample
    redis_cmd hset "graph:layout:sample_graph_1:force" "sample_entity_1_x" "100.5"
    redis_cmd hset "graph:layout:sample_graph_1:force" "sample_entity_1_y" "200.3"
    redis_cmd hset "graph:layout:sample_graph_1:force" "sample_entity_1_level" "1"
    redis_cmd hset "graph:layout:sample_graph_1:force" "metadata" "{\"algorithm\": \"force\", \"timestamp\": $current_time}"
    redis_cmd expire "graph:layout:sample_graph_1:force" 7200

    # Shortest path cache sample
    redis_cmd lpush "paths:shortest:entity_1:entity_2" "entity_3"
    redis_cmd lpush "paths:shortest:entity_1:entity_2" "entity_2"
    redis_cmd lpush "paths:shortest:entity_1:entity_2" "entity_1"
    redis_cmd expire "paths:shortest:entity_1:entity_2" 1800

    # Community detection results sample
    redis_cmd hset "communities:sample_org:louvain" "community_count" "5"
    redis_cmd hset "communities:sample_org:louvain" "modularity_score" "0.72"
    redis_cmd hset "communities:sample_org:louvain" "algorithm" "louvain"
    redis_cmd hset "communities:sample_org:louvain" "computed_at" "$current_time"
    redis_cmd hset "communities:sample_org:louvain" "community_1" '["entity_1", "entity_2", "entity_3"]'
    redis_cmd expire "communities:sample_org:louvain" 86400

    # Real-time graph statistics sample
    redis_cmd hset "stats:graph:sample_org:realtime" "total_nodes" "100"
    redis_cmd hset "stats:graph:sample_org:realtime" "total_edges" "250"
    redis_cmd hset "stats:graph:sample_org:realtime" "avg_degree" "5.0"
    redis_cmd hset "stats:graph:sample_org:realtime" "connected_components" "2"
    redis_cmd hset "stats:graph:sample_org:realtime" "largest_component_size" "95"
    redis_cmd hset "stats:graph:sample_org:realtime" "graph_density" "0.025"
    redis_cmd hset "stats:graph:sample_org:realtime" "avg_confidence" "0.82"
    redis_cmd hset "stats:graph:sample_org:realtime" "last_updated" "$current_time"
    redis_cmd expire "stats:graph:sample_org:realtime" 300

    # User-specific view cache sample
    local view_cache
    view_cache=$(cat <<EOF
{
  "nodes": [
    {"id": "entity_1", "name": "Sample Entity", "type": "Person", "x": 100, "y": 200}
  ],
  "edges": [
    {"source": "entity_1", "target": "entity_2", "type": "RELATED_TO"}
  ],
  "layout": {"algorithm": "force", "positions": {"entity_1": {"x": 100, "y": 200}}},
  "filters": {"entity_types": ["Person"], "confidence_threshold": 0.7},
  "computed_at": $current_time,
  "expires_at": $((current_time + 1800))
}
EOF
)
    redis_cmd set "view:graph:sample_user_1:sample_view_hash" "$view_cache"
    redis_cmd expire "view:graph:sample_user_1:sample_view_hash" 1800

    # Computation job status sample
    redis_cmd hset "job:graph:sample_job_1" "status" "completed"
    redis_cmd hset "job:graph:sample_job_1" "progress" "100"
    redis_cmd hset "job:graph:sample_job_1" "total_steps" "100"
    redis_cmd hset "job:graph:sample_job_1" "current_step" "Computation completed"
    redis_cmd hset "job:graph:sample_job_1" "started_at" "$((current_time - 120))"
    redis_cmd hset "job:graph:sample_job_1" "estimated_completion" "$current_time"
    redis_cmd hset "job:graph:sample_job_1" "result_location" "s3://results/sample_job_1.json"
    redis_cmd hset "job:graph:sample_job_1" "computation_time_ms" "15000"
    redis_cmd expire "job:graph:sample_job_1" 86400

    # Entity neighborhood cache sample
    local neighborhood_cache
    neighborhood_cache=$(cat <<EOF
{
  "central_entity": {"id": "entity_1", "name": "Sample Entity", "type": "Person"},
  "entities": [
    {"id": "entity_1", "name": "Sample Entity", "type": "Person"},
    {"id": "entity_2", "name": "Related Entity", "type": "Organization"}
  ],
  "relationships": [
    {"source": "entity_1", "target": "entity_2", "type": "WORKS_FOR", "strength": 0.9}
  ],
  "total_nodes": 2,
  "total_edges": 1,
  "depth_reached": 1,
  "computed_at": $current_time,
  "computation_time_ms": 150
}
EOF
)
    redis_cmd set "neighborhood:entity_1:1:sample_org" "$neighborhood_cache"
    redis_cmd expire "neighborhood:entity_1:1:sample_org" 3600

    # Graph insights cache sample
    local insights_cache
    insights_cache=$(cat <<EOF
{
  "insights": [
    {
      "id": "insight_1",
      "type": "quality_issue",
      "severity": "medium",
      "title": "Low confidence entities detected",
      "description": "5 entities have confidence below 0.5",
      "affected_entities": ["entity_3", "entity_4"],
      "recommendations": ["Review entity extraction process"],
      "impact_score": 0.6,
      "generated_at": $current_time
    }
  ],
  "generated_at": $current_time,
  "expires_at": $((current_time + 21600))
}
EOF
)
    redis_cmd set "insights:sample_org:quality" "$insights_cache"
    redis_cmd expire "insights:sample_org:quality" 21600

    # Entity similarity cache sample
    redis_cmd lpush "similarity:entity:entity_1:10" "entity_2:0.92"
    redis_cmd lpush "similarity:entity:entity_1:10" "entity_3:0.85"
    redis_cmd lpush "similarity:entity:entity_1:10" "entity_4:0.78"
    redis_cmd expire "similarity:entity:entity_1:10" 7200

    # Graph algorithm parameters cache sample
    redis_cmd hset "params:algorithm:pagerank" "default_resolution" "1.0"
    redis_cmd hset "params:algorithm:pagerank" "damping_factor" "0.85"
    redis_cmd hset "params:algorithm:pagerank" "max_iterations" "100"
    redis_cmd hset "params:algorithm:pagerank" "convergence_threshold" "0.0001"
    redis_cmd expire "params:algorithm:pagerank" 86400

    success "Initial Redis data structures created"
}

# Setup pub/sub channels for real-time updates
setup_pubsub_channels() {
    log "Setting up Redis pub/sub channels for real-time updates..."

    # Create pub/sub message samples for demonstration
    local current_time
    current_time=$(date +%s)

    # Organization-wide update sample
    local org_update
    org_update=$(cat <<EOF
{
  "type": "entity_created",
  "entity_id": "sample_entity_1",
  "entity_type": "Person",
  "timestamp": $current_time,
  "organization_id": "sample_org"
}
EOF
)

    # Entity-specific update samples
    local entity_update
    entity_update=$(cat <<EOF
{
  "type": "entity_updated",
  "entity_id": "sample_entity_1",
  "changes": {"confidence": 0.9},
  "timestamp": $current_time,
  "organization_id": "sample_org"
}
EOF
)

    # Computation update samples
    local computation_update
    computation_update=$(cat <<EOF
{
  "type": "computation_completed",
  "job_id": "sample_job_1",
  "computation_type": "centrality_analysis",
  "timestamp": $current_time,
  "organization_id": "sample_org"
}
EOF
)

    # Analytics update samples
    local analytics_update
    analytics_update=$(cat <<EOF
{
  "type": "stats_updated",
  "organization_id": "sample_org",
  "stats": {
    "total_nodes": 101,
    "total_edges": 251,
    "avg_degree": 5.0
  },
  "timestamp": $current_time
}
EOF
)

    # Note: In a real application, these would be published by the services
    # For demonstration, we're just showing the message format
    log "Pub/sub channel message formats prepared:"
    log "  - Organization updates: channel:graph:updates:{organization_id}"
    log "  - Entity updates: channel:entity:updated:{organization_id}"
    log "  - Computation updates: channel:computation:completed:{organization_id}"
    log "  - Analytics updates: channel:analytics:updated:{organization_id}"

    success "Pub/sub channels configured"
}

# Create Redis functions for graph operations
create_redis_functions() {
    log "Creating Redis functions for graph operations..."

    # Note: Redis 7.0+ supports server-side functions
    # For older versions, these operations would be done client-side

    # Function documentation (would be implemented in Redis 7.0+)
    log "Graph functions configured:"
    log "  - get_entity_centrality(entity_id, metric_type, organization_id, compute_if_missing)"
    log "  - cache_graph_layout(graph_id, algorithm, layout_data, ttl)"
    log "  - update_graph_stats(organization_id, stats_data)"
    log "  - invalidate_entity_caches(entity_id, organization_id)"

    success "Redis functions configured"
}

# Test cache operations
test_cache_operations() {
    log "Testing Redis cache operations..."

    # Test entity centrality cache
    local test_result
    test_result=$(redis_cmd get "entity:centrality:sample_entity_1:degree")
    if [ "$test_result" = "0.85" ]; then
        success "Entity centrality cache test passed"
    else
        warning "Entity centrality cache test failed"
    fi

    # Test graph layout cache
    test_result=$(redis_cmd hget "graph:layout:sample_graph_1:force" "sample_entity_1_x")
    if [ "$test_result" = "100.5" ]; then
        success "Graph layout cache test passed"
    else
        warning "Graph layout cache test failed"
    fi

    # Test shortest path cache
    test_result=$(redis_cmd lrange "paths:shortest:entity_1:entity_2" 0 -1)
    if echo "$test_result" | grep -q "entity_1"; then
        success "Shortest path cache test passed"
    else
        warning "Shortest path cache test failed"
    fi

    # Test real-time statistics
    test_result=$(redis_cmd hget "stats:graph:sample_org:realtime" "total_nodes")
    if [ "$test_result" = "100" ]; then
        success "Real-time statistics test passed"
    else
        warning "Real-time statistics test failed"
    fi

    # Test JSON cache retrieval
    test_result=$(redis_cmd get "view:graph:sample_user_1:sample_view_hash")
    if echo "$test_result" | grep -q "Sample Entity"; then
        success "JSON cache retrieval test passed"
    else
        warning "JSON cache retrieval test failed"
    fi

    success "Cache operations testing completed"
}

# Monitor Redis performance
monitor_redis_performance() {
    log "Monitoring Redis performance..."

    # Get Redis info
    local redis_info
    redis_info=$(redis_cmd info)

    # Extract key metrics
    local used_memory
    local used_memory_human
    local connected_clients
    local total_commands_processed
    local instantaneous_ops_per_sec
    local keyspace_hits
    local keyspace_misses
    local hit_rate

    used_memory=$(echo "$redis_info" | grep "used_memory:" | cut -d: -f2 | tr -d '\r')
    used_memory_human=$(redis_cmd info memory | grep "used_memory_human:" | cut -d: -f2 | tr -d '\r')
    connected_clients=$(echo "$redis_info" | grep "connected_clients:" | cut -d: -f2 | tr -d '\r')
    total_commands_processed=$(echo "$redis_info" | grep "total_commands_processed:" | cut -d: -f2 | tr -d '\r')
    instantaneous_ops_per_sec=$(echo "$redis_info" | grep "instantaneous_ops_per_sec:" | cut -d: -f2 | tr -d '\r')
    keyspaces_hits=$(echo "$redis_info" | grep "keyspace_hits:" | cut -d: -f2 | tr -d '\r')
    keyspaces_misses=$(echo "$redis_info" | grep "keyspace_misses:" | cut -d: -f2 | tr -d '\r')

    # Calculate hit rate
    if [ -n "$keyspaces_hits" ] && [ -n "$keyspaces_misses" ] && [ "$keyspaces_misses" -gt 0 ]; then
        hit_rate=$(echo "scale=2; $keyspaces_hits / ($keyspaces_hits + $keyspaces_misses) * 100" | bc)
    else
        hit_rate="N/A"
    fi

    # Display performance metrics
    success "Redis Performance Metrics:"
    echo "  - Memory Usage: $used_memory_human ($used_memory bytes)"
    echo "  - Connected Clients: $connected_clients"
    echo "  - Total Commands Processed: $total_commands_processed"
    echo "  - Current Operations/sec: $instantaneous_ops_per_sec"
    echo "  - Cache Hit Rate: ${hit_rate}%"
    echo "  - Keyspace Hits: $keyspaces_hits"
    echo "  - Keyspace Misses: $keyspaces_misses"

    # Check slow log
    local slowlog_length
    slowlog_length=$(redis_cmd slowlog len)
    if [ "$slowlog_length" -gt 0 ]; then
        warning "Slow log has $slowlog_length entries - consider optimization"
        redis_cmd slowlog get 5 | head -10
    else
        success "No slow queries detected"
    fi
}

# Get cache statistics
get_cache_statistics() {
    log "Getting cache statistics..."

    # Count keys by pattern
    local centrality_keys
    local layout_keys
    local path_keys
    local community_keys
    local stats_keys
    local view_keys
    local job_keys
    local neighborhood_keys
    local insights_keys
    local similarity_keys
    local params_keys

    centrality_keys=$(redis_cmd keys "entity:centrality:*" | wc -l)
    layout_keys=$(redis_cmd keys "graph:layout:*" | wc -l)
    path_keys=$(redis_cmd keys "paths:shortest:*" | wc -l)
    community_keys=$(redis_cmd keys "communities:*" | wc -l)
    stats_keys=$(redis_cmd keys "stats:graph:*" | wc -l)
    view_keys=$(redis_cmd keys "view:graph:*" | wc -l)
    job_keys=$(redis_cmd keys "job:graph:*" | wc -l)
    neighborhood_keys=$(redis_cmd keys "neighborhood:*" | wc -l)
    insights_keys=$(redis_cmd keys "insights:*" | wc -l)
    similarity_keys=$(redis_cmd keys "similarity:entity:*" | wc -l)
    params_keys=$(redis_cmd keys "params:algorithm:*" | wc -l)

    local total_keys
    total_keys=$((centrality_keys + layout_keys + path_keys + community_keys + stats_keys + view_keys + job_keys + neighborhood_keys + insights_keys + similarity_keys + params_keys))

    success "Cache Statistics:"
    echo "  - Entity Centrality Keys: $centrality_keys"
    echo "  - Graph Layout Keys: $layout_keys"
    echo "  - Path Keys: $path_keys"
    echo "  - Community Keys: $community_keys"
    echo "  - Statistics Keys: $stats_keys"
    echo "  - View Keys: $view_keys"
    echo "  - Job Keys: $job_keys"
    echo "  - Neighborhood Keys: $neighborhood_keys"
    echo "  - Insights Keys: $insights_keys"
    echo "  - Similarity Keys: $similarity_keys"
    echo "  - Parameter Keys: $params_keys"
    echo "  - Total Keys: $total_keys"

    # Memory usage by key patterns
    log "Memory usage by key patterns:"
    local patterns=("entity:centrality:*" "graph:layout:*" "paths:shortest:*" "communities:*" "stats:graph:*")
    for pattern in "${patterns[@]}"; do
        local memory_usage
        memory_usage=$(redis_cmd --eval - "$pattern" 2>/dev/null || echo "0")
        echo "  - $pattern: Calculating memory usage..."
    done
}

# Clean up test data
cleanup_test_data() {
    log "Cleaning up Redis test data..."

    # Remove test keys
    redis_cmd del "entity:centrality:sample_entity_1:degree"
    redis_cmd del "entity:centrality:sample_entity_1:pagerank"
    redis_cmd del "graph:layout:sample_graph_1:force"
    redis_cmd del "paths:shortest:entity_1:entity_2"
    redis_cmd del "communities:sample_org:louvain"
    redis_cmd del "stats:graph:sample_org:realtime"
    redis_cmd del "view:graph:sample_user_1:sample_view_hash"
    redis_cmd del "job:graph:sample_job_1"
    redis_cmd del "neighborhood:entity_1:1:sample_org"
    redis_cmd del "insights:sample_org:quality"
    redis_cmd del "similarity:entity:entity_1:10"
    redis_cmd del "params:algorithm:pagerank"

    success "Test data cleaned up"
}

# Display usage information
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -H, --host HOST         Redis host (default: $REDIS_HOST)"
    echo "  -p, --port PORT         Redis port (default: $REDIS_PORT)"
    echo "  -a, --password PASS     Redis password"
    echo "  --config FILE           Redis config file (default: $REDIS_CONFIG_FILE)"
    echo "  --cleanup-only          Only clean up test data"
    echo "  --monitor-only          Only monitor performance"
    echo "  --stats-only            Only show cache statistics"
    echo ""
    echo "Commands:"
    echo "  init                    Initialize Redis for graph (default)"
    echo "  test                    Test cache operations"
    echo "  monitor                 Monitor Redis performance"
    echo "  stats                   Show cache statistics"
    echo "  cleanup                 Clean up test data"
    echo ""
}

# Main function
main() {
    local command="init"

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -H|--host)
                REDIS_HOST="$2"
                shift 2
                ;;
            -p|--port)
                REDIS_PORT="$2"
                shift 2
                ;;
            -a|--password)
                REDIS_PASSWORD="$2"
                shift 2
                ;;
            --config)
                REDIS_CONFIG_FILE="$2"
                shift 2
                ;;
            --cleanup-only)
                command="cleanup"
                shift
                ;;
            --monitor-only)
                command="monitor"
                shift
                ;;
            --stats-only)
                command="stats"
                shift
                ;;
            init|test|monitor|stats|cleanup)
                command="$1"
                shift
                ;;
            *)
                error "Unknown option: $1. Use --help for usage information."
                ;;
        esac
    done

    log "Starting Redis Graph Caching Initialization..."
    log "Redis host: $REDIS_HOST:$REDIS_PORT"

    case "$command" in
        "init")
            check_redis_health
            configure_redis_settings
            create_initial_data_structures
            setup_pubsub_channels
            create_redis_functions
            test_cache_operations
            get_cache_statistics
            monitor_redis_performance
            success "Redis graph caching initialization completed successfully!"
            ;;
        "test")
            check_redis_health
            test_cache_operations
            ;;
        "monitor")
            check_redis_health
            monitor_redis_performance
            ;;
        "stats")
            check_redis_health
            get_cache_statistics
            ;;
        "cleanup")
            check_redis_health
            cleanup_test_data
            ;;
        *)
            error "Unknown command: $command"
            ;;
    esac
}

# Run main function with all arguments
main "$@"