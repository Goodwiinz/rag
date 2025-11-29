#!/bin/bash

# Comprehensive Health Check Script for Knowledge Graph Architecture
# This script performs detailed health checks on all services and databases

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.graph-services-corrected.yml"
PROJECT_NAME="rag-graph"
HEALTH_CHECK_TIMEOUT=30
DETAILED_CHECK_TIMEOUT=10
REPORT_FILE="health_check_report_$(date +%Y%m%d_%H%M%S).json"

# Health check counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# Logging functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ((FAILED_CHECKS++))
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    ((PASSED_CHECKS++))
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    ((WARNING_CHECKS++))
}

info() {
    echo -e "${PURPLE}[INFO]${NC} $1"
}

check_step() {
    echo -e "${CYAN}[CHECK]${NC} $1"
    ((TOTAL_CHECKS++))
}

# Initialize JSON report
init_report() {
    cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "checks": {
    "services": {},
    "databases": {},
    "infrastructure": {},
    "performance": {}
  },
  "summary": {
    "total_checks": 0,
    "passed_checks": 0,
    "failed_checks": 0,
    "warning_checks": 0,
    "overall_status": "unknown"
  }
}
EOF
}

# Update JSON report
update_report() {
    local category="$1"
    local check_name="$2"
    local status="$3"
    local details="$4"
    local response_time="$5"

    local temp_file
    temp_file=$(mktemp)

    jq --arg category "$category" \
       --arg check_name "$check_name" \
       --arg status "$status" \
       --arg details "$details" \
       --arg response_time "$response_time" \
       '.checks[$category][$check_name] = {
         "status": $status,
         "details": $details,
         "response_time": $response_time,
         "timestamp": (now | strftime("%Y-%m-%dT%H:%M:%S%z"))
       }' "$REPORT_FILE" > "$temp_file"

    mv "$temp_file" "$REPORT_FILE"
}

# Finalize JSON report
finalize_report() {
    local temp_file
    temp_file=$(mktemp)

    jq --argjson total "$TOTAL_CHECKS" \
       --argjson passed "$PASSED_CHECKS" \
       --argjson failed "$FAILED_CHECKS" \
       --argjson warnings "$WARNING_CHECKS" \
       --arg overall_status "$(if [ $FAILED_CHECKS -eq 0 ]; then echo "healthy"; elif [ $FAILED_CHECKS -le 2 ]; then echo "degraded"; else echo "unhealthy"; fi)" \
       '.summary.total_checks = $total |
        .summary.passed_checks = $passed |
        .summary.failed_checks = $failed |
        .summary.warning_checks = $warnings |
        .summary.overall_status = $overall_status |
        .summary.success_rate = ($passed / $total * 100 | floor)' "$REPORT_FILE" > "$temp_file"

    mv "$temp_file" "$REPORT_FILE"
}

# Measure response time
measure_response_time() {
    local command="$1"
    local start_time
    start_time=$(date +%s%N)

    eval "$command" &> /dev/null
    local exit_code=$?

    local end_time
    end_time=$(date +%s%N)
    local response_time=$(((end_time - start_time) / 1000000))

    echo "$response_time"
    return $exit_code
}

# Check Docker services
check_docker_services() {
    log "Checking Docker services..."

    # Check if Docker is running
    check_step "Docker daemon"
    if docker info &> /dev/null; then
        local response_time
        response_time=$(measure_response_time "docker info")
        success "Docker daemon is running (${response_time}ms)"
        update_report "infrastructure" "docker_daemon" "passed" "Docker daemon is running" "$response_time"
    else
        error "Docker daemon is not running"
        update_report "infrastructure" "docker_daemon" "failed" "Docker daemon is not running" "0"
        return 1
    fi

    # Check Docker Compose
    check_step "Docker Compose"
    if command -v docker-compose &> /dev/null; then
        success "Docker Compose is available"
        update_report "infrastructure" "docker_compose" "passed" "Docker Compose is available" "0"
    else
        error "Docker Compose is not available"
        update_report "infrastructure" "docker_compose" "failed" "Docker Compose is not available" "0"
        return 1
    fi

    # Check if containers are running
    check_step "Container status"
    local running_containers
    running_containers=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps -q | wc -l)

    if [ "$running_containers" -gt 0 ]; then
        success "Containers are running ($running_containers containers)"
        update_report "infrastructure" "containers" "passed" "Containers are running" "0"
    else
        error "No containers are running"
        update_report "infrastructure" "containers" "failed" "No containers are running" "0"
        return 1
    fi

    # Check container health
    check_step "Container health"
    local unhealthy_containers
    unhealthy_containers=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps | grep -c "unhealthy\|exited" || echo "0")

    if [ "$unhealthy_containers" -eq 0 ]; then
        success "All containers are healthy"
        update_report "infrastructure" "container_health" "passed" "All containers are healthy" "0"
    else
        warning "$unhealthy_containers containers are unhealthy"
        update_report "infrastructure" "container_health" "warning" "$unhealthy_containers containers are unhealthy" "0"
    fi
}

# Check service endpoints
check_service_endpoints() {
    log "Checking service endpoints..."

    local services=(
        "knowledge-graph-service:8003"
        "graph-analytics-service:8009"
        "graph-visualization-service:8010"
    )

    for service_info in "${services[@]}"; do
        IFS=':' read -r service_name port <<< "$service_info"

        check_step "$service_name health endpoint"
        local response_time
        response_time=$(measure_response_time "curl -f http://localhost:$port/health")

        if [ $? -eq 0 ]; then
            success "$service_name is healthy (${response_time}ms)"
            update_report "services" "$service_name" "passed" "Service is responding to health checks" "$response_time"
        else
            error "$service_name health check failed"
            update_report "services" "$service_name" "failed" "Service is not responding to health checks" "$response_time"
        fi
    done

    # Check API documentation endpoints
    check_step "API documentation endpoints"
    local docs_available=0
    local total_docs=0

    for service_info in "${services[@]}"; do
        IFS=':' read -r service_name port <<< "$service_info"
        ((total_docs++))

        if curl -f "http://localhost:$port/docs" &> /dev/null; then
            ((docs_available++))
        fi
    done

    if [ "$docs_available" -eq "$total_docs" ]; then
        success "All API documentation endpoints are available"
        update_report "services" "api_docs" "passed" "All API documentation endpoints are available" "0"
    else
        warning "$docs_available/$total_docs API documentation endpoints are available"
        update_report "services" "api_docs" "warning" "$docs_available/$total_docs API documentation endpoints are available" "0"
    fi
}

# Check PostgreSQL database
check_postgresql() {
    log "Checking PostgreSQL database..."

    # Check connectivity
    check_step "PostgreSQL connectivity"
    local response_time
    response_time=$(measure_response_time "docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME exec -T postgres-graph pg_isready -U rag_user -d rag_graph")

    if [ $? -eq 0 ]; then
        success "PostgreSQL is accessible (${response_time}ms)"
        update_report "databases" "postgresql_connectivity" "passed" "PostgreSQL is accessible" "$response_time"
    else
        error "PostgreSQL is not accessible"
        update_report "databases" "postgresql_connectivity" "failed" "PostgreSQL is not accessible" "$response_time"
        return 1
    fi

    # Check database size
    check_step "PostgreSQL database size"
    local db_size
    db_size=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph psql -U rag_user -d rag_graph -t -c "
        SELECT pg_size_pretty(pg_database_size('rag_graph'));
    " 2>/dev/null | tr -d ' ')

    if [ -n "$db_size" ]; then
        success "PostgreSQL database size: $db_size"
        update_report "databases" "postgresql_size" "passed" "Database size: $db_size" "0"
    else
        warning "Could not determine PostgreSQL database size"
        update_report "databases" "postgresql_size" "warning" "Could not determine database size" "0"
    fi

    # Check connection count
    check_step "PostgreSQL connection count"
    local connection_count
    connection_count=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph psql -U rag_user -d rag_graph -t -c "
        SELECT count(*) FROM pg_stat_activity WHERE datname = 'rag_graph';
    " 2>/dev/null | tr -d ' ')

    if [ -n "$connection_count" ] && [ "$connection_count" -gt 0 ]; then
        if [ "$connection_count" -lt 80 ]; then
            success "PostgreSQL connections: $connection_count"
            update_report "databases" "postgresql_connections" "passed" "Active connections: $connection_count" "0"
        else
            warning "PostgreSQL connections: $connection_count (high)"
            update_report "databases" "postgresql_connections" "warning" "High connection count: $connection_count" "0"
        fi
    else
        warning "Could not determine PostgreSQL connection count"
        update_report "databases" "postgresql_connections" "warning" "Could not determine connection count" "0"
    fi

    # Check table counts
    check_step "PostgreSQL table validation"
    local table_count
    table_count=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph psql -U rag_user -d rag_graph -t -c "
        SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
    " 2>/dev/null | tr -d ' ')

    if [ -n "$table_count" ] && [ "$table_count" -ge 7 ]; then
        success "PostgreSQL tables: $table_count"
        update_report "databases" "postgresql_tables" "passed" "Tables found: $table_count" "0"
    else
        warning "PostgreSQL tables: $table_count (expected at least 7)"
        update_report "databases" "postgresql_tables" "warning" "Table count: $table_count (expected at least 7)" "0"
    fi

    # Check slow queries
    check_step "PostgreSQL slow queries"
    local slow_queries
    slow_queries=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph psql -U rag_user -d rag_graph -t -c "
        SELECT COUNT(*) FROM pg_stat_statements WHERE mean_time > 1000;
    " 2>/dev/null | tr -d ' ')

    if [ -n "$slow_queries" ]; then
        if [ "$slow_queries" -eq 0 ]; then
            success "No slow PostgreSQL queries detected"
            update_report "databases" "postgresql_slow_queries" "passed" "No slow queries detected" "0"
        else
            warning "PostgreSQL slow queries: $slow_queries"
            update_report "databases" "postgresql_slow_queries" "warning" "Slow queries detected: $slow_queries" "0"
        fi
    else
        warning "Could not check PostgreSQL slow queries (pg_stat_statements may not be enabled)"
        update_report "databases" "postgresql_slow_queries" "warning" "Could not check slow queries" "0"
    fi
}

# Check Neo4j database
check_neo4j() {
    log "Checking Neo4j database..."

    # Check connectivity
    check_step "Neo4j connectivity"
    local response_time
    response_time=$(measure_response_time "docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME exec -T neo4j-graph cypher-shell -u neo4j -p ragpassword2024 'RETURN 1'")

    if [ $? -eq 0 ]; then
        success "Neo4j is accessible (${response_time}ms)"
        update_report "databases" "neo4j_connectivity" "passed" "Neo4j is accessible" "$response_time"
    else
        error "Neo4j is not accessible"
        update_report "databases" "neo4j_connectivity" "failed" "Neo4j is not accessible" "$response_time"
        return 1
    fi

    # Check node count
    check_step "Neo4j node count"
    local node_count
    node_count=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T neo4j-graph cypher-shell -u neo4j -p ragpassword2024 --format plain "
        MATCH (n) RETURN count(n) as count;
    " 2>/dev/null | grep -E '^[0-9]+$' || echo "0")

    if [ -n "$node_count" ]; then
        success "Neo4j nodes: $node_count"
        update_report "databases" "neo4j_nodes" "passed" "Total nodes: $node_count" "0"
    else
        warning "Could not determine Neo4j node count"
        update_report "databases" "neo4j_nodes" "warning" "Could not determine node count" "0"
    fi

    # Check relationship count
    check_step "Neo4j relationship count"
    local rel_count
    rel_count=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T neo4j-graph cypher-shell -u neo4j -p ragpassword2024 --format plain "
        MATCH ()-[r]->() RETURN count(r) as count;
    " 2>/dev/null | grep -E '^[0-9]+$' || echo "0")

    if [ -n "$rel_count" ]; then
        success "Neo4j relationships: $rel_count"
        update_report "databases" "neo4j_relationships" "passed" "Total relationships: $rel_count" "0"
    else
        warning "Could not determine Neo4j relationship count"
        update_report "databases" "neo4j_relationships" "warning" "Could not determine relationship count" "0"
    fi

    # Check constraints
    check_step "Neo4j constraints"
    local constraint_count
    constraint_count=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T neo4j-graph cypher-shell -u neo4j -p ragpassword2024 --format plain "
        SHOW CONSTRAINTS;
    " 2>/dev/null | wc -l)

    if [ -n "$constraint_count" ] && [ "$constraint_count" -gt 0 ]; then
        success "Neo4j constraints: $constraint_count"
        update_report "databases" "neo4j_constraints" "passed" "Constraints found: $constraint_count" "0"
    else
        warning "Neo4j constraints: $constraint_count (may need setup)"
        update_report "databases" "neo4j_constraints" "warning" "Constraint count: $constraint_count" "0"
    fi

    # Check index usage
    check_step "Neo4j index usage"
    local index_count
    index_count=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T neo4j-graph cypher-shell -u neo4j -p ragpassword2024 --format plain "
        SHOW INDEXES;
    " 2>/dev/null | wc -l)

    if [ -n "$index_count" ] && [ "$index_count" -gt 0 ]; then
        success "Neo4j indexes: $index_count"
        update_report "databases" "neo4j_indexes" "passed" "Indexes found: $index_count" "0"
    else
        warning "Neo4j indexes: $index_count (may need setup)"
        update_report "databases" "neo4j_indexes" "warning" "Index count: $index_count" "0"
    fi
}

# Check Redis
check_redis() {
    log "Checking Redis cache..."

    # Check connectivity
    check_step "Redis connectivity"
    local response_time
    response_time=$(measure_response_time "docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME exec -T redis-graph redis-cli ping")

    if [ $? -eq 0 ]; then
        success "Redis is accessible (${response_time}ms)"
        update_report "databases" "redis_connectivity" "passed" "Redis is accessible" "$response_time"
    else
        error "Redis is not accessible"
        update_report "databases" "redis_connectivity" "failed" "Redis is not accessible" "$response_time"
        return 1
    fi

    # Check memory usage
    check_step "Redis memory usage"
    local memory_info
    memory_info=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli info memory 2>/dev/null | grep "used_memory_human:" | cut -d: -f2 | tr -d '\r')

    if [ -n "$memory_info" ]; then
        success "Redis memory usage: $memory_info"
        update_report "databases" "redis_memory" "passed" "Memory usage: $memory_info" "0"
    else
        warning "Could not determine Redis memory usage"
        update_report "databases" "redis_memory" "warning" "Could not determine memory usage" "0"
    fi

    # Check key count
    check_step "Redis key count"
    local key_count
    key_count=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli dbsize 2>/dev/null | tr -d '\r')

    if [ -n "$key_count" ]; then
        success "Redis keys: $key_count"
        update_report "databases" "redis_keys" "passed" "Total keys: $key_count" "0"
    else
        warning "Could not determine Redis key count"
        update_report "databases" "redis_keys" "warning" "Could not determine key count" "0"
    fi

    # Check hit rate
    check_step "Redis cache hit rate"
    local hits
    local misses
    hits=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli info stats 2>/dev/null | grep "keyspace_hits:" | cut -d: -f2 | tr -d '\r')
    misses=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli info stats 2>/dev/null | grep "keyspace_misses:" | cut -d: -f2 | tr -d '\r')

    if [ -n "$hits" ] && [ -n "$misses" ]; then
        if [ "$misses" -gt 0 ]; then
            local hit_rate
            hit_rate=$(echo "scale=1; $hits * 100 / ($hits + $misses)" | bc 2>/dev/null || echo "0")
            if [ "$(echo "$hit_rate > 80" | bc 2>/dev/null || echo "0")" -eq 1 ]; then
                success "Redis cache hit rate: ${hit_rate}%"
                update_report "databases" "redis_hit_rate" "passed" "Cache hit rate: ${hit_rate}%" "0"
            else
                warning "Redis cache hit rate: ${hit_rate}% (low)"
                update_report "databases" "redis_hit_rate" "warning" "Low cache hit rate: ${hit_rate}%" "0"
            fi
        else
            success "Redis cache hit rate: 100% (no misses)"
            update_report "databases" "redis_hit_rate" "passed" "Cache hit rate: 100%" "0"
        fi
    else
        warning "Could not determine Redis cache hit rate"
        update_report "databases" "redis_hit_rate" "warning" "Could not determine hit rate" "0"
    fi

    # Check slow log
    check_step "Redis slow log"
    local slow_log_length
    slow_log_length=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T redis-graph redis-cli slowlog len 2>/dev/null | tr -d '\r')

    if [ -n "$slow_log_length" ]; then
        if [ "$slow_log_length" -eq 0 ]; then
            success "No slow Redis commands detected"
            update_report "databases" "redis_slow_log" "passed" "No slow commands detected" "0"
        else
            warning "Redis slow log: $slow_log_length entries"
            update_report "databases" "redis_slow_log" "warning" "Slow commands: $slow_log_length" "0"
        fi
    else
        warning "Could not check Redis slow log"
        update_report "databases" "redis_slow_log" "warning" "Could not check slow log" "0"
    fi
}

# Check Qdrant
check_qdrant() {
    log "Checking Qdrant vector store..."

    # Check connectivity
    check_step "Qdrant connectivity"
    local response_time
    response_time=$(measure_response_time "curl -f http://localhost:6333/health")

    if [ $? -eq 0 ]; then
        success "Qdrant is accessible (${response_time}ms)"
        update_report "databases" "qdrant_connectivity" "passed" "Qdrant is accessible" "$response_time"
    else
        error "Qdrant is not accessible"
        update_report "databases" "qdrant_connectivity" "failed" "Qdrant is not accessible" "$response_time"
        return 1
    fi

    # Check collections
    check_step "Qdrant collections"
    local collection_info
    collection_info=$(curl -s http://localhost:6333/collections 2>/dev/null)

    if echo "$collection_info" | jq -e '.result.collections' &> /dev/null; then
        local collection_count
        collection_count=$(echo "$collection_info" | jq -r '.result.collections | length')

        if [ "$collection_count" -gt 0 ]; then
            success "Qdrant collections: $collection_count"
            update_report "databases" "qdrant_collections" "passed" "Collections found: $collection_count" "0"
        else
            warning "Qdrant collections: $collection_count (may need setup)"
            update_report "databases" "qdrant_collections" "warning" "No collections found" "0"
        fi
    else
        warning "Could not retrieve Qdrant collections"
        update_report "databases" "qdrant_collections" "warning" "Could not retrieve collections" "0"
    fi

    # Check cluster info
    check_step "Qdrant cluster info"
    local cluster_info
    cluster_info=$(curl -s http://localhost:6333 2>/dev/null)

    if echo "$cluster_info" | jq -e '.title' &> /dev/null; then
        local version
        version=$(echo "$cluster_info" | jq -r '.version')
        success "Qdrant version: $version"
        update_report "databases" "qdrant_version" "passed" "Version: $version" "0"
    else
        warning "Could not retrieve Qdrant cluster info"
        update_report "databases" "qdrant_version" "warning" "Could not retrieve cluster info" "0"
    fi

    # Check collection sizes (if any collections exist)
    if [ -n "$collection_info" ] && echo "$collection_info" | jq -e '.result.collections[0]' &> /dev/null; then
        check_step "Qdrant collection sizes"
        local total_points=0
        local collection_names
        collection_names=$(echo "$collection_info" | jq -r '.result.collections[].name')

        for collection_name in $collection_names; do
            local points_count
            points_count=$(curl -s "http://localhost:6333/collections/$collection_name" | jq -r '.result.points_count // 0')
            total_points=$((total_points + points_count))
        done

        if [ "$total_points" -gt 0 ]; then
            success "Qdrant total points: $total_points"
            update_report "databases" "qdrant_points" "passed" "Total points: $total_points" "0"
        else
            warning "Qdrant total points: $total_points (collections may be empty)"
            update_report "databases" "qdrant_points" "warning" "No points found" "0"
        fi
    fi
}

# Check performance metrics
check_performance_metrics() {
    log "Checking performance metrics..."

    # Check service response times
    check_step "Service response times"
    local services=("8003" "8009" "8010")
    local total_response_time=0
    local healthy_services=0

    for port in "${services[@]}"; do
        local response_time
        response_time=$(measure_response_time "curl -f http://localhost:$port/health")

        if [ $? -eq 0 ]; then
            total_response_time=$((total_response_time + response_time))
            ((healthy_services++))
        fi
    done

    if [ "$healthy_services" -gt 0 ]; then
        local avg_response_time=$((total_response_time / healthy_services))
        if [ "$avg_response_time" -lt 100 ]; then
            success "Average service response time: ${avg_response_time}ms"
            update_report "performance" "service_response_times" "passed" "Average response time: ${avg_response_time}ms" "$avg_response_time"
        else
            warning "Average service response time: ${avg_response_time}ms (slow)"
            update_report "performance" "service_response_times" "warning" "Slow response time: ${avg_response_time}ms" "$avg_response_time"
        fi
    else
        error "No healthy services to measure response times"
        update_report "performance" "service_response_times" "failed" "No healthy services" "0"
    fi

    # Check database query performance
    check_step "Database query performance"
    local db_start_time
    db_start_time=$(date +%s%N)

    # Run a simple PostgreSQL query
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T postgres-graph psql -U rag_user -d rag_graph -c "SELECT 1;" &> /dev/null; then
        local db_end_time
        db_end_time=$(date +%s%N)
        local db_query_time=$(((db_end_time - db_start_time) / 1000000))

        if [ "$db_query_time" -lt 100 ]; then
            success "PostgreSQL query time: ${db_query_time}ms"
            update_report "performance" "postgresql_query_time" "passed" "Query time: ${db_query_time}ms" "$db_query_time"
        else
            warning "PostgreSQL query time: ${db_query_time}ms (slow)"
            update_report "performance" "postgresql_query_time" "warning" "Slow query time: ${db_query_time}ms" "$db_query_time"
        fi
    else
        error "PostgreSQL query failed"
        update_report "performance" "postgresql_query_time" "failed" "Query failed" "0"
    fi

    # Check system resource usage
    check_step "System resource usage"
    local cpu_usage
    local memory_usage

    # Get CPU usage (simplified)
    if command -v top &> /dev/null; then
        cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//' 2>/dev/null || echo "unknown")
        memory_usage=$(free -h | awk '/^Mem:/ {print $3 "/" $2}' 2>/dev/null || echo "unknown")

        success "System usage - CPU: ${cpu_usage}%, Memory: $memory_usage"
        update_report "performance" "system_usage" "passed" "CPU: ${cpu_usage}%, Memory: $memory_usage" "0"
    else
        warning "Could not determine system resource usage"
        update_report "performance" "system_usage" "warning" "Could not determine resource usage" "0"
    fi

    # Check Docker resource usage
    check_step "Docker resource usage"
    local docker_stats
    if docker stats --no-stream &> /dev/null; then
        local high_memory_containers
        high_memory_containers=$(docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}" | grep -E "rag-[a-z-]+-[a-z]+" | awk '($2 ~ /GB/ && ($2 > 1.0 || ($2 > 0.5 && $3 ~ /[0-9]+GB/))) || ($2 ~ /MB/ && $2 > 1000)' | wc -l)

        if [ "$high_memory_containers" -eq 0 ]; then
            success "Docker container memory usage is normal"
            update_report "performance" "docker_memory" "passed" "Container memory usage is normal" "0"
        else
            warning "$high_memory_containers containers have high memory usage"
            update_report "performance" "docker_memory" "warning" "High memory usage in $high_memory_containers containers" "0"
        fi
    else
        warning "Could not check Docker resource usage"
        update_report "performance" "docker_memory" "warning" "Could not check Docker usage" "0"
    fi
}

# Check network connectivity
check_network_connectivity() {
    log "Checking network connectivity..."

    # Check port availability
    check_step "Port availability"
    local ports=("7474" "7687" "5433" "6333" "6380" "8003" "8009" "8010")
    local available_ports=0

    for port in "${ports[@]}"; do
        if timeout 3 bash -c "echo > /dev/tcp/localhost/$port" 2>/dev/null; then
            ((available_ports++))
        fi
    done

    if [ "$available_ports" -eq "${#ports[@]}" ]; then
        success "All required ports are available ($available_ports/${#ports[@]})"
        update_report "infrastructure" "port_availability" "passed" "All ports available" "0"
    else
        warning "$available_ports/${#ports[@]} ports are available"
        update_report "infrastructure" "port_availability" "warning" "$available_ports/${#ports[@]} ports available" "0"
    fi

    # Check DNS resolution
    check_step "DNS resolution"
    if nslookup localhost &> /dev/null; then
        success "DNS resolution is working"
        update_report "infrastructure" "dns_resolution" "passed" "DNS resolution is working" "0"
    else
        warning "DNS resolution may have issues"
        update_report "infrastructure" "dns_resolution" "warning" "DNS resolution issues" "0"
    fi

    # Check inter-service communication
    check_step "Inter-service communication"
    local service_communication_ok=true

    # Test if services can reach databases
    if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" exec -T knowledge-graph-service curl -f http://postgres-graph:5432 &> /dev/null; then
        success "Services can communicate with databases"
        update_report "infrastructure" "service_communication" "passed" "Inter-service communication is working" "0"
    else
        warning "Services may have communication issues"
        update_report "infrastructure" "service_communication" "warning" "Potential communication issues" "0"
    fi
}

# Display usage information
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -q, --quiet             Run with minimal output"
    echo "  -v, --verbose           Run with detailed output"
    echo "  --output-format FORMAT  Output format: text, json, both (default: both)"
    echo "  --timeout SECONDS       Health check timeout (default: $HEALTH_CHECK_TIMEOUT)"
    echo "  --skip-performance      Skip performance checks"
    echo "  --category CATEGORY     Run specific check category"
    echo "                          Categories: infrastructure, databases, services, performance"
    echo ""
    echo "Examples:"
    echo "  $0                      # Run all health checks"
    echo "  $0 --category databases # Run only database checks"
    echo "  $0 --skip-performance   # Skip performance checks"
    echo "  $0 --output-format json # Output only JSON report"
    echo ""
}

# Main function
main() {
    local output_format="both"
    local category="all"
    local skip_performance=false
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
            --output-format)
                output_format="$2"
                shift 2
                ;;
            --timeout)
                HEALTH_CHECK_TIMEOUT="$2"
                shift 2
                ;;
            --skip-performance)
                skip_performance=true
                shift
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

    if [ "$quiet" = false ]; then
        log "Starting Knowledge Graph Health Check..."
        log "Timeout: ${HEALTH_CHECK_TIMEOUT}s"
        log "Report file: $REPORT_FILE"
    fi

    # Initialize report
    init_report

    # Run checks based on category
    case "$category" in
        "infrastructure")
            check_docker_services
            check_network_connectivity
            ;;
        "databases")
            check_postgresql
            check_neo4j
            check_redis
            check_qdrant
            ;;
        "services")
            check_service_endpoints
            ;;
        "performance")
            check_performance_metrics
            ;;
        "all")
            check_docker_services
            check_network_connectivity
            check_service_endpoints
            check_postgresql
            check_neo4j
            check_redis
            check_qdrant
            if [ "$skip_performance" = false ]; then
                check_performance_metrics
            fi
            ;;
        *)
            error "Unknown check category: $category"
            ;;
    esac

    # Finalize report
    finalize_report

    # Display summary
    if [ "$quiet" = false ] || [ "$output_format" = "text" ] || [ "$output_format" = "both" ]; then
        echo ""
        log "Health Check Summary:"
        echo "  Total Checks: $TOTAL_CHECKS"
        echo "  Passed: $PASSED_CHECKS"
        echo "  Failed: $FAILED_CHECKS"
        echo "  Warnings: $WARNING_CHECKS"

        if [ $FAILED_CHECKS -eq 0 ]; then
            success "🎉 All critical health checks passed!"
            echo ""
            echo "The Knowledge Graph system is healthy and operational."
        else
            error "❌ $FAILED_CHECKS critical check(s) failed!"
            echo ""
            echo "Please address the failed checks before the system can be considered healthy."
        fi

        if [ $WARNING_CHECKS -gt 0 ]; then
            warning "⚠️ $WARNING_CHECKS warning(s) detected."
            echo ""
            echo "These should be reviewed but do not prevent system operation."
        fi
    fi

    # Output JSON report
    if [ "$output_format" = "json" ] || [ "$output_format" = "both" ]; then
        if [ "$quiet" = false ]; then
            echo ""
            log "JSON report saved to: $REPORT_FILE"
        fi

        if [ "$verbose" = true ]; then
            echo ""
            cat "$REPORT_FILE" | jq .
        fi
    fi

    # Exit with appropriate code
    if [ $FAILED_CHECKS -gt 0 ]; then
        exit 2  # Critical issues
    elif [ $WARNING_CHECKS -gt 0 ]; then
        exit 1  # Warnings
    else
        exit 0  # All healthy
    fi
}

# Run main function with all arguments
main "$@"