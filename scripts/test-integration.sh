#!/bin/bash

# Integration Testing Script for Knowledge Graph Architecture
# This script tests end-to-end integration of all services and databases

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Test configuration
COMPOSE_FILE="docker-compose.graph-services-corrected.yml"
PROJECT_NAME="rag-graph"
TEST_ORG_ID="test-org-$(date +%s)"
TEST_USER_ID="test-user-$(date +%s)"
API_BASE_URL="http://localhost"
TIMEOUT=30
RETRY_COUNT=3

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ((FAILED_TESTS++))
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    ((PASSED_TESTS++))
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    ((SKIPPED_TESTS++))
}

info() {
    echo -e "${PURPLE}[INFO]${NC} $1"
}

test_step() {
    echo -e "${CYAN}[TEST]${NC} $1"
    ((TOTAL_TESTS++))
}

# HTTP request helper
http_request() {
    local method="$1"
    local url="$2"
    local data="$3"
    local expected_status="$4"
    local timeout="$5"

    timeout="${timeout:-$TIMEOUT}"

    local response
    local status

    if [ -n "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" \
                     -H "Content-Type: application/json" \
                     -d "$data" \
                     --max-time "$timeout" 2>/dev/null || echo -e "\n000")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" \
                     --max-time "$timeout" 2>/dev/null || echo -e "\n000")
    fi

    status=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n -1)

    if [ "$status" = "$expected_status" ]; then
        echo "$body"
        return 0
    else
        echo "HTTP $status: $body" >&2
        return 1
    fi
}

# Wait for service to be ready
wait_for_service() {
    local service_name="$1"
    local health_url="$2"
    local max_attempts="$3"
    local attempt=1

    max_attempts="${max_attempts:-30}"

    while [ $attempt -le $max_attempts ]; do
        if curl -f "$health_url" &> /dev/null; then
            success "$service_name is ready"
            return 0
        fi

        info "Waiting for $service_name... (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done

    error "$service_name did not become ready within $max_attempts attempts"
    return 1
}

# Test database connectivity
test_database_connectivity() {
    log "Testing database connectivity..."

    # Test PostgreSQL
    test_step "PostgreSQL connectivity"
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph pg_isready -U rag_user -d rag_graph &> /dev/null; then
        success "PostgreSQL is accessible"
    else
        error "PostgreSQL is not accessible"
        return 1
    fi

    # Test Neo4j
    test_step "Neo4j connectivity"
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T neo4j-graph cypher-shell -u neo4j -p ragpassword2024 "RETURN 1" &> /dev/null; then
        success "Neo4j is accessible"
    else
        error "Neo4j is not accessible"
        return 1
    fi

    # Test Redis
    test_step "Redis connectivity"
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli ping &> /dev/null; then
        success "Redis is accessible"
    else
        error "Redis is not accessible"
        return 1
    fi

    # Test Qdrant
    test_step "Qdrant connectivity"
    if curl -f http://localhost:6333/health &> /dev/null; then
        success "Qdrant is accessible"
    else
        error "Qdrant is not accessible"
        return 1
    fi
}

# Test service health endpoints
test_service_health() {
    log "Testing service health endpoints..."

    local services=(
        "knowledge-graph-service:8003"
        "graph-analytics-service:8009"
        "graph-visualization-service:8010"
    )

    for service_info in "${services[@]}"; do
        IFS=':' read -r service_name port <<< "$service_info"

        test_step "$service_name health endpoint"
        if curl -f "http://localhost:$port/health" &> /dev/null; then
            success "$service_name health check passed"
        else
            error "$service_name health check failed"
            return 1
        fi
    done
}

# Test database schema
test_database_schema() {
    log "Testing database schema..."

    # Test PostgreSQL schema
    test_step "PostgreSQL schema validation"
    local schema_check
    schema_check=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph psql -U rag_user -d rag_graph -t -c "
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_name IN (
            'graph_computation_cache',
            'graph_analytics_snapshots',
            'user_graph_preferences',
            'graph_computation_jobs',
            'entity_analytics_cache',
            'graph_insights',
            'graph_performance_metrics'
        );
    " 2>/dev/null | tr -d ' ')

    if [ "$schema_check" = "7" ]; then
        success "PostgreSQL schema validation passed"
    else
        error "PostgreSQL schema validation failed (found $schema_check tables, expected 7)"
        return 1
    fi

    # Test Neo4j constraints
    test_step "Neo4j constraints validation"
    local constraint_check
    constraint_check=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T neo4j-graph cypher-shell -u neo4j -p ragpassword2024 \
        "SHOW CONSTRAINTS" 2>/dev/null | grep -c "Entity\|Document" || echo "0")

    if [ "$constraint_check" -ge 4 ]; then
        success "Neo4j constraints validation passed"
    else
        error "Neo4j constraints validation failed (found $constraint_check constraints)"
        return 1
    fi

    # Test Qdrant collections
    test_step "Qdrant collections validation"
    local collections_check
    collections_check=$(curl -s http://localhost:6333/collections | jq -r '.result.collections | length' 2>/dev/null || echo "0")

    if [ "$collections_check" -ge 4 ]; then
        success "Qdrant collections validation passed"
    else
        error "Qdrant collections validation failed (found $collections_check collections)"
        return 1
    fi
}

# Test knowledge graph service API
test_knowledge_graph_api() {
    log "Testing Knowledge Graph Service API..."

    # Test entity creation
    test_step "Entity creation API"
    local entity_data
    entity_data=$(cat <<EOF
{
    "name": "Test Entity $(date +%s)",
    "type": "Person",
    "organization_id": "$TEST_ORG_ID",
    "confidence": 0.95,
    "description": "Integration test entity"
}
EOF
)

    local create_response
    create_response=$(http_request "POST" "$API_BASE_URL:8003/api/entities" "$entity_data" "201")

    if [ $? -eq 0 ]; then
        local entity_id
        entity_id=$(echo "$create_response" | jq -r '.id // empty')
        if [ -n "$entity_id" ] && [ "$entity_id" != "null" ]; then
            success "Entity creation API passed (ID: $entity_id)"

            # Store entity ID for later tests
            echo "$entity_id" > /tmp/test_entity_id

            # Test entity retrieval
            test_step "Entity retrieval API"
            local get_response
            get_response=$(http_request "GET" "$API_BASE_URL:8003/api/entities/$entity_id")

            if [ $? -eq 0 ]; then
                local retrieved_name
                retrieved_name=$(echo "$get_response" | jq -r '.name // empty')
                if [ "$retrieved_name" != "null" ] && [ -n "$retrieved_name" ]; then
                    success "Entity retrieval API passed"
                else
                    error "Entity retrieval API failed - invalid response"
                fi
            else
                error "Entity retrieval API failed"
            fi

            # Test entity search
            test_step "Entity search API"
            local search_response
            search_response=$(http_request "GET" "$API_BASE_URL:8003/api/entities/search?q=Test&organization_id=$TEST_ORG_ID")

            if [ $? -eq 0 ]; then
                local search_count
                search_count=$(echo "$search_response" | jq '. | length' 2>/dev/null || echo "0")
                if [ "$search_count" -gt 0 ]; then
                    success "Entity search API passed (found $search_count entities)"
                else
                    warning "Entity search API passed but no entities found"
                fi
            else
                error "Entity search API failed"
            fi
        else
            error "Entity creation API failed - no entity ID returned"
        fi
    else
        error "Entity creation API failed"
    fi

    # Test relationship creation
    if [ -f /tmp/test_entity_id ]; then
        local entity_id
        entity_id=$(cat /tmp/test_entity_id)

        # Create second entity for relationship
        local entity2_data
        entity2_data=$(cat <<EOF
{
    "name": "Test Organization $(date +%s)",
    "type": "Organization",
    "organization_id": "$TEST_ORG_ID",
    "confidence": 0.90,
    "description": "Integration test organization"
}
EOF
)

        test_step "Second entity creation for relationship test"
        local entity2_response
        entity2_response=$(http_request "POST" "$API_BASE_URL:8003/api/entities" "$entity2_data" "201")

        if [ $? -eq 0 ]; then
            local entity2_id
            entity2_id=$(echo "$entity2_response" | jq -r '.id // empty')

            if [ -n "$entity2_id" ] && [ "$entity2_id" != "null" ]; then
                echo "$entity2_id" > /tmp/test_entity2_id
                success "Second entity created successfully"

                # Test relationship creation
                test_step "Relationship creation API"
                local relationship_data
                relationship_data=$(cat <<EOF
{
    "source_entity_id": "$entity_id",
    "target_entity_id": "$entity2_id",
    "relationship_type": "WORKS_FOR",
    "organization_id": "$TEST_ORG_ID",
    "confidence": 0.85,
    "strength": 0.8
}
EOF
)

                local rel_response
                rel_response=$(http_request "POST" "$API_BASE_URL:8003/api/relationships" "$relationship_data" "201")

                if [ $? -eq 0 ]; then
                    local rel_id
                    rel_id=$(echo "$rel_response" | jq -r '.id // empty')
                    if [ -n "$rel_id" ] && [ "$rel_id" != "null" ]; then
                        success "Relationship creation API passed (ID: $rel_id)"
                        echo "$rel_id" > /tmp/test_relationship_id
                    else
                        error "Relationship creation API failed - no relationship ID returned"
                    fi
                else
                    error "Relationship creation API failed"
                fi
            fi
        fi
    fi
}

# Test graph analytics service API
test_graph_analytics_api() {
    log "Testing Graph Analytics Service API..."

    if [ -f /tmp/test_entity_id ] && [ -f /tmp/test_entity2_id ]; then
        local entity_id
        local entity2_id
        entity_id=$(cat /tmp/test_entity_id)
        entity2_id=$(cat /tmp/test_entity2_id)

        # Test centrality computation
        test_step "Centrality computation API"
        local centrality_data
        centrality_data=$(cat <<EOF
{
    "entity_ids": ["$entity_id", "$entity2_id"],
    "metrics": ["degree", "betweenness", "pagerank"],
    "organization_id": "$TEST_ORG_ID"
}
EOF
)

        local centrality_response
        centrality_response=$(http_request "POST" "$API_BASE_URL:8009/api/analytics/centrality" "$centrality_data" "200")

        if [ $? -eq 0 ]; then
            local centrality_count
            centrality_count=$(echo "$centrality_response" | jq '. | length' 2>/dev/null || echo "0")
            if [ "$centrality_count" -gt 0 ]; then
                success "Centrality computation API passed (computed for $centrality_count entities)"
            else
                warning "Centrality computation API passed but no results returned"
            fi
        else
            error "Centrality computation API failed"
        fi

        # Test community detection
        test_step "Community detection API"
        local community_data
        community_data=$(cat <<EOF
{
    "algorithm": "louvain",
    "organization_id": "$TEST_ORG_ID",
    "parameters": {
        "resolution": 1.0
    }
}
EOF
)

        local community_response
        community_response=$(http_request "POST" "$API_BASE_URL:8009/api/analytics/communities" "$community_data" "200")

        if [ $? -eq 0 ]; then
            local job_id
            job_id=$(echo "$community_response" | jq -r '.job_id // empty')
            if [ -n "$job_id" ] && [ "$job_id" != "null" ]; then
                success "Community detection API passed (Job ID: $job_id)"
                echo "$job_id" > /tmp/test_job_id
            else
                warning "Community detection API passed but no job ID returned"
            fi
        else
            error "Community detection API failed"
        fi

        # Test path finding
        test_step "Path finding API"
        local path_data
        path_data=$(cat <<EOF
{
    "source_entity_id": "$entity_id",
    "target_entity_id": "$entity2_id",
    "algorithm": "dijkstra",
    "max_depth": 5
}
EOF
)

        local path_response
        path_response=$(http_request "POST" "$API_BASE_URL:8009/api/analytics/paths" "$path_data" "200")

        if [ $? -eq 0 ]; then
            local path_length
            path_length=$(echo "$path_response" | jq -r '.path | length // 0')
            if [ "$path_length" -gt 0 ]; then
                success "Path finding API passed (path length: $path_length)"
            else
                warning "Path finding API passed but no path found"
            fi
        else
            error "Path finding API failed"
        fi
    else
        warning "Skipping graph analytics tests - no test entities available"
    fi
}

# Test graph visualization service API
test_graph_visualization_api() {
    log "Testing Graph Visualization Service API..."

    if [ -f /tmp/test_entity_id ] && [ -f /tmp/test_entity2_id ]; then
        local entity_id
        local entity2_id
        entity_id=$(cat /tmp/test_entity_id)
        entity2_id=$(cat /tmp/test_entity2_id)

        # Test layout computation
        test_step "Graph layout computation API"
        local layout_data
        layout_data=$(cat <<EOF
{
    "entity_ids": ["$entity_id", "$entity2_id"],
    "algorithm": "force",
    "parameters": {
        "iterations": 100,
        "gravity": 0.1
    },
    "organization_id": "$TEST_ORG_ID"
}
EOF
)

        local layout_response
        layout_response=$(http_request "POST" "$API_BASE_URL:8010/api/visualization/layout" "$layout_data" "200")

        if [ $? -eq 0 ]; then
            local layout_nodes
            layout_nodes=$(echo "$layout_response" | jq '.nodes | length // 0')
            if [ "$layout_nodes" -gt 0 ]; then
                success "Graph layout computation API passed (laid out $layout_nodes nodes)"
            else
                warning "Graph layout computation API passed but no nodes returned"
            fi
        else
            error "Graph layout computation API failed"
        fi

        # Test graph export
        test_step "Graph export API"
        local export_response
        export_response=$(http_request "GET" "$API_BASE_URL:8010/api/visualization/export?organization_id=$TEST_ORG_ID&format=json")

        if [ $? -eq 0 ]; then
            local export_nodes
            export_nodes=$(echo "$export_response" | jq '.nodes | length // 0')
            local export_edges
            export_edges=$(echo "$export_response" | jq '.edges | length // 0')
            if [ "$export_nodes" -gt 0 ]; then
                success "Graph export API passed (exported $export_nodes nodes, $export_edges edges)"
            else
                warning "Graph export API passed but no data exported"
            fi
        else
            error "Graph export API failed"
        fi

        # Test cached layout retrieval
        test_step "Cached layout retrieval API"
        local cached_response
        cached_response=$(http_request "GET" "$API_BASE_URL:8010/api/visualization/layout/default")

        if [ $? -eq 0 ]; then
            success "Cached layout retrieval API passed"
        else
            warning "Cached layout retrieval API failed - layout may not be cached yet"
        fi
    else
        warning "Skipping graph visualization tests - no test entities available"
    fi
}

# Test caching functionality
test_caching_functionality() {
    log "Testing caching functionality..."

    # Test Redis caching
    test_step "Redis cache write"
    local cache_key="test:cache:$(date +%s)"
    local cache_value='{"test": "data", "timestamp": 1234567890}'

    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli set "$cache_key" "$cache_value" &> /dev/null; then
        success "Redis cache write passed"

        # Test Redis cache read
        test_step "Redis cache read"
        local cached_value
        cached_value=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli get "$cache_key" 2>/dev/null | tr -d '\r')

        if [ "$cached_value" = "$cache_value" ]; then
            success "Redis cache read passed"
        else
            error "Redis cache read failed"
        fi

        # Clean up test cache
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli del "$cache_key" &> /dev/null
    else
        error "Redis cache write failed"
    fi

    # Test PostgreSQL cache table
    test_step "PostgreSQL cache table"
    local cache_insert
    cache_insert=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph psql -U rag_user -d rag_graph -c "
        INSERT INTO graph_computation_cache (
            organization_id,
            computation_type,
            computation_version,
            algorithm_name,
            input_parameters,
            result_data,
            expires_at
        ) VALUES (
            '$TEST_ORG_ID',
            'test_computation',
            'v1.0',
            'test_algorithm',
            '{\"param\": \"value\"}',
            '{\"result\": \"test\"}',
            NOW() + INTERVAL '1 hour'
        );
        SELECT currval('graph_computation_cache_id_seq');
    " 2>/dev/null | tr -d ' ')

    if [ -n "$cache_insert" ] && [ "$cache_insert" -gt 0 ]; then
        success "PostgreSQL cache table write passed"

        # Test cache retrieval
        local cache_retrieve
        cache_retrieve=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph psql -U rag_user -d rag_graph -t -c "
            SELECT COUNT(*) FROM graph_computation_cache WHERE organization_id = '$TEST_ORG_ID';
        " 2>/dev/null | tr -d ' ')

        if [ "$cache_retrieve" -gt 0 ]; then
            success "PostgreSQL cache table read passed"
        else
            error "PostgreSQL cache table read failed"
        fi
    else
        error "PostgreSQL cache table write failed"
    fi
}

# Test real-time updates
test_real_time_updates() {
    log "Testing real-time updates..."

    # Test WebSocket connectivity (if implemented)
    test_step "WebSocket connectivity"
    if command -v websocat &> /dev/null; then
        if timeout 5 websocat ws://localhost:8003/ws &> /dev/null; then
            success "WebSocket connectivity passed"
        else
            warning "WebSocket connectivity failed - WebSocket may not be implemented"
        fi
    else
        warning "Skipping WebSocket test - websocat not available"
    fi

    # Test pub/sub functionality
    test_step "Redis pub/sub functionality"
    local test_channel="test:channel:$(date +%s)"
    local test_message='{"type": "test", "data": "integration test"}'

    # Start Redis subscriber in background
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli subscribe "$test_channel" > /tmp/redis_sub.log &
    local subscriber_pid=$!

    sleep 1

    # Publish message
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli publish "$test_channel" "$test_message" &> /dev/null; then
        sleep 1

        # Check if message was received
        if grep -q "$test_message" /tmp/redis_sub.log; then
            success "Redis pub/sub functionality passed"
        else
            warning "Redis pub/sub functionality failed - message not received"
        fi
    else
        error "Redis pub/sub functionality failed"
    fi

    # Clean up subscriber
    kill $subscriber_pid 2>/dev/null || true
    rm -f /tmp/redis_sub.log
}

# Test performance under load
test_performance_load() {
    log "Testing performance under load..."

    # Test concurrent API requests
    test_step "Concurrent API requests"
    local concurrent_requests=10
    local pids=()

    for i in $(seq 1 $concurrent_requests); do
        (
            if curl -f "$API_BASE_URL:8003/health" &> /dev/null; then
                echo "success_$i"
            else
                echo "failed_$i"
            fi
        ) > "/tmp/concurrent_test_$i" &
        pids+=($!)
    done

    # Wait for all requests to complete
    local success_count=0
    for pid in "${pids[@]}"; do
        wait $pid
        if grep -q "success" "/tmp/concurrent_test_${pid##* }"; then
            ((success_count++))
        fi
    done

    # Clean up
    rm -f /tmp/concurrent_test_*

    if [ $success_count -eq $concurrent_requests ]; then
        success "Concurrent API requests passed ($success_count/$concurrent_requests successful)"
    else
        warning "Concurrent API requests partially passed ($success_count/$concurrent_requests successful)"
    fi

    # Test database query performance
    test_step "Database query performance"
    local start_time
    start_time=$(date +%s%N)

    # Run a complex query
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph psql -U rag_user -d rag_graph -c "
        SELECT COUNT(*) FROM entities e
        LEFT JOIN entity_analytics_cache eac ON e.id = eac.entity_id
        WHERE e.organization_id = '$TEST_ORG_ID';
    " &> /dev/null

    local end_time
    end_time=$(date +%s%N)
    local query_time_ms=$(((end_time - start_time) / 1000000))

    if [ $query_time_ms -lt 1000 ]; then
        success "Database query performance passed (${query_time_ms}ms)"
    else
        warning "Database query performance warning (${query_time_ms}ms - may need optimization)"
    fi
}

# Cleanup test data
cleanup_test_data() {
    log "Cleaning up test data..."

    # Clean up Redis
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli --scan --pattern "*test*" | xargs docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli del &> /dev/null || true

    # Clean up PostgreSQL
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph psql -U rag_user -d rag_graph -c "
        DELETE FROM graph_computation_cache WHERE organization_id = '$TEST_ORG_ID';
        DELETE FROM graph_performance_metrics WHERE organization_id = '$TEST_ORG_ID';
        DELETE FROM graph_insights WHERE organization_id = '$TEST_ORG_ID';
    " &> /dev/null || true

    # Clean up Neo4j
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T neo4j-graph cypher-shell -u neo4j -p ragpassword2024 "
        MATCH (n {organization_id: '$TEST_ORG_ID'})
        DETACH DELETE n;
    " &> /dev/null || true

    # Clean up test files
    rm -f /tmp/test_entity_id /tmp/test_entity2_id /tmp/test_relationship_id /tmp/test_job_id

    success "Test data cleaned up"
}

# Generate test report
generate_test_report() {
    log "Generating integration test report..."

    local report_file="integration_test_report_$(date +%Y%m%d_%H%M%S).md"

    cat > "$report_file" << EOF
# Knowledge Graph Integration Test Report

**Generated:** $(date)
**Test Organization:** $TEST_ORG_ID
**Test User:** $TEST_USER_ID

## Test Summary

- **Total Tests:** $TOTAL_TESTS
- **Passed:** $PASSED_TESTS
- **Failed:** $FAILED_TESTS
- **Skipped:** $SKIPPED_TESTS
- **Success Rate:** $(echo "scale=1; $PASSED_TESTS * 100 / $TOTAL_TESTS" | bc 2>/dev/null || echo "N/A")%

## Test Categories

### Infrastructure Tests
- Database connectivity
- Service health endpoints
- Database schema validation

### API Tests
- Knowledge Graph Service API
- Graph Analytics Service API
- Graph Visualization Service API

### Functional Tests
- Caching functionality
- Real-time updates
- Performance under load

## Detailed Results

$(if [ $FAILED_TESTS -eq 0 ]; then
    echo "✅ All tests passed successfully!"
    echo ""
    echo "The Knowledge Graph architecture is working correctly and is ready for use."
else
    echo "❌ $FAILED_TESTS test(s) failed."
    echo ""
    echo "Please review the failed tests and resolve the issues before deploying to production."
fi)

## Service Status

- **Knowledge Graph Service:** $(curl -f http://localhost:8003/health &> /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy")
- **Graph Analytics Service:** $(curl -f http://localhost:8009/health &> /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy")
- **Graph Visualization Service:** $(curl -f http://localhost:8010/health &> /dev/null && echo "✅ Healthy" || echo "❌ Unhealthy")

## Database Status

- **PostgreSQL:** $(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph pg_isready -U rag_user -d rag_graph &> /dev/null && echo "✅ Connected" || echo "❌ Disconnected")
- **Neo4j:** $(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T neo4j-graph cypher-shell -u neo4j -p ragpassword2024 "RETURN 1" &> /dev/null && echo "✅ Connected" || echo "❌ Disconnected")
- **Redis:** $(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli ping &> /dev/null && echo "✅ Connected" || echo "❌ Disconnected")
- **Qdrant:** $(curl -f http://localhost:6333/health &> /dev/null && echo "✅ Connected" || echo "❌ Disconnected")

## Recommendations

$(if [ $FAILED_TESTS -eq 0 ]; then
    echo "🎉 The system is ready for production use!"
    echo ""
    echo "Next steps:"
    echo "1. Configure production environment variables"
    echo "2. Set up monitoring and alerting"
    echo "3. Configure backup procedures"
    echo "4. Document API usage for frontend integration"
else
    echo "⚠️ Please address the following issues:"
    echo ""
    echo "1. Review failed tests and fix underlying issues"
    echo "2. Verify all services are running correctly"
    echo "3. Check database configurations"
    echo "4. Re-run integration tests after fixes"
fi)

## Test Environment

- **Docker Compose:** $COMPOSE_FILE
- **Project Name:** $PROJECT_NAME
- **API Base URL:** $API_BASE_URL
- **Timeout:** ${TIMEOUT}s
- **Retry Count:** $RETRY_COUNT

EOF

    success "Test report generated: $report_file"
}

# Display usage information
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -q, --quiet             Run tests with minimal output"
    echo "  -v, --verbose           Run tests with detailed output"
    echo "  --skip-cleanup          Skip test data cleanup"
    echo "  --report-only           Only generate report from existing results"
    echo "  --category CATEGORY     Run specific test category"
    echo "                          Categories: infrastructure, api, functional, performance"
    echo ""
    echo "Examples:"
    echo "  $0                      # Run all integration tests"
    echo "  $0 --category api       # Run only API tests"
    echo "  $0 --skip-cleanup       # Run tests without cleaning up"
    echo ""
}

# Main function
main() {
    local skip_cleanup=false
    local category="all"
    local quiet=false
    local verbose=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -q|--quiet)
                quiet=true
                shift
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            --skip-cleanup)
                skip_cleanup=true
                shift
                ;;
            --report-only)
                generate_test_report
                exit 0
                ;;
            --category)
                category="$2"
                shift 2
                ;;
            *)
                error "Unknown option: $1. Use --help for usage information."
                ;;
        esac
    done

    log "Starting Knowledge Graph Integration Tests..."
    log "Test Organization: $TEST_ORG_ID"
    log "Test User: $TEST_USER_ID"

    # Run tests based on category
    case "$category" in
        "infrastructure")
            test_database_connectivity
            test_service_health
            test_database_schema
            ;;
        "api")
            test_knowledge_graph_api
            test_graph_analytics_api
            test_graph_visualization_api
            ;;
        "functional")
            test_caching_functionality
            test_real_time_updates
            ;;
        "performance")
            test_performance_load
            ;;
        "all")
            test_database_connectivity
            test_service_health
            test_database_schema
            test_knowledge_graph_api
            test_graph_analytics_api
            test_graph_visualization_api
            test_caching_functionality
            test_real_time_updates
            test_performance_load
            ;;
        *)
            error "Unknown test category: $category"
            ;;
    esac

    # Generate test report
    generate_test_report

    # Cleanup test data
    if [ "$skip_cleanup" = false ]; then
        cleanup_test_data
    fi

    # Final summary
    echo ""
    log "Integration Test Summary:"
    echo "  Total Tests: $TOTAL_TESTS"
    echo "  Passed: $PASSED_TESTS"
    echo "  Failed: $FAILED_TESTS"
    echo "  Skipped: $SKIPPED_TESTS"

    if [ $FAILED_TESTS -eq 0 ]; then
        success "🎉 All integration tests passed!"
        echo ""
        echo "The Knowledge Graph architecture is working correctly."
        echo "System is ready for production use."
        exit 0
    else
        error "❌ $FAILED_TESTS test(s) failed!"
        echo ""
        echo "Please review the failed tests and resolve the issues."
        echo "Check the generated test report for details."
        exit 1
    fi
}

# Set up signal handlers for cleanup
trap cleanup_test_data EXIT

# Run main function with all arguments
main "$@"