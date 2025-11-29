#!/bin/bash

# Multimodal Enterprise RAG System - Database Initialization Script
# This script initializes all four databases with proper configuration and sample data

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Database connection configurations
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_USER="raguser"
POSTGRES_PASSWORD="rag_password_123"
POSTGRES_DB="ragdb"

NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="neo4j_password_123"

QDRANT_URL="http://localhost:6333"
QDRANT_API_KEY="qdrant_api_key_123"

REDIS_HOST="localhost"
REDIS_PORT="6379"
REDIS_PASSWORD="redis_password_123"

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Logging
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Function to check if a service is ready
wait_for_service() {
    local service_name=$1
    local host=$2
    local port=$3
    local timeout=${4:-30}

    info "Waiting for $service_name to be ready..."

    for i in $(seq 1 $timeout); do
        if nc -z "$host" "$port" 2>/dev/null; then
            log "$service_name is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
    done

    error "$service_name is not ready after $timeout seconds"
}

# Function to check PostgreSQL connection
check_postgres() {
    info "Checking PostgreSQL connection..."

    if PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" >/dev/null 2>&1; then
        log "PostgreSQL connection successful"
        return 0
    else
        error "PostgreSQL connection failed"
    fi
}

# Function to initialize PostgreSQL
init_postgresql() {
    info "Initializing PostgreSQL database..."

    # Create extensions
    PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOF
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
EOF

    # Execute schema SQL
    if PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "$SCRIPT_DIR/01_schema.sql"; then
        log "PostgreSQL schema created successfully"
    else
        error "PostgreSQL schema creation failed"
    fi
}

# Function to initialize Qdrant
init_qdrant() {
    info "Initializing Qdrant vector database..."

    # Create Qdrant setup script
    cat > "$SCRIPT_DIR/qdrant_setup.py" << 'EOF'
#!/usr/bin/env python3
import json
import sys
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

def main():
    config_file = sys.argv[1] if len(sys.argv) > 1 else "03_qdrant_setup.json"

    with open(config_file, 'r') as f:
        config = json.load(f)

    client = QdrantClient(
        url="http://localhost:6333",
        api_key="qdrant_api_key_123"
    )

    collections_created = 0

    for collection_name, collection_config in config["collections"].items():
        try:
            # Check if collection exists
            existing_collections = client.get_collections().collections
            exists = any(c.name == collection_name for c in existing_collections)

            if not exists:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=collection_config["vectors"]
                )
                print(f"✅ Created collection: {collection_name}")
                collections_created += 1
            else:
                print(f"✅ Collection already exists: {collection_name}")

        except Exception as e:
            print(f"❌ Failed to create collection {collection_name}: {e}")

    print(f"🎉 Qdrant setup completed! Created {collections_created} new collections.")

if __name__ == "__main__":
    main()
EOF

    # Execute Qdrant setup
    if python3 "$SCRIPT_DIR/qdrant_setup.py" "$SCRIPT_DIR/03_qdrant_setup.json"; then
        log "Qdrant vector database setup completed"
    else
        error "Qdrant setup failed"
    fi

    # Cleanup temporary script
    rm -f "$SCRIPT_DIR/qdrant_setup.py"
}

# Function to initialize Redis
init_redis() {
    info "Initializing Redis cache and data structures..."

    # Create Redis setup script without eval()
    cat > "$SCRIPT_DIR/redis_setup.py" << 'EOF'
#!/usr/bin/env python3
import redis
import time

def main():
    r = redis.Redis(
        host='localhost',
        port=6379,
        password='redis_password_123',
        decode_responses=True
    )

    # Test connection
    r.ping()
    print("✅ Redis connection successful")

    current_time = int(time.time())

    # Basic Redis setup (without eval for security)
    # Memory configuration
    r.config_set('maxmemory', '256mb')
    r.config_set('maxmemory-policy', 'allkeys-lru')

    # Cache configurations
    cache_configs = {
        'search_ttl': '3600',
        'search_max_size': '1000',
        'document_ttl': '7200',
        'document_max_size': '500',
        'entity_ttl': '1800',
        'entity_max_size': '2000',
        'user_ttl': '1800',
        'user_max_size': '1000',
        'session_ttl': '86400',
        'session_max_size': '500'
    }
    r.hset('cache_configs', mapping=cache_configs)

    # Rate limiting configurations
    rate_limits = {
        'search_per_minute': '60',
        'upload_per_hour': '100',
        'api_requests_per_minute': '1000',
        'login_attempts_per_hour': '10'
    }
    r.hset('rate_limits', mapping=rate_limits)

    # Feature flags
    feature_flags = {
        'multimodal_search': 'true',
        'advanced_analytics': 'true',
        'real_time_updates': 'false',
        'experimental_features': 'false'
    }
    r.hset('feature_flags', mapping=feature_flags)

    # Active channels
    channels = ['search_updates', 'processing_jobs', 'notifications', 'user_activity', 'system_events', 'document_updates', 'entity_updates']
    r.sadd('active_channels', *channels)

    # Sample session
    sample_session = {
        'user_id': '550e8400-e29b-41d4-a716-446655440002',
        'organization_id': '550e8400-e29b-41d4-a716-446655440001',
        'email': 'admin@demo.com',
        'role': 'admin',
        'permissions': '{"read": true, "write": true, "admin": true}',
        'created_at': str(current_time),
        'last_activity': str(current_time),
        'ip_address': '127.0.0.1',
        'user_agent': 'Mozilla/5.0 (compatible; RAG-System/1.0)'
    }
    r.hmset('session:demo_session_001', sample_session)
    r.expire('session:demo_session_001', 3600)

    # Popular searches
    searches = [('artificial intelligence', 10), ('machine learning', 8), ('cloud computing', 6), ('data analytics', 5), ('neural networks', 4)]
    r.zadd('popular_searches', searches)

    # Search suggestions
    r.sadd('search_suggestions:ai', 'artificial intelligence', 'machine learning', 'deep learning', 'neural networks')
    r.sadd('search_suggestions:cloud', 'cloud computing', 'aws', 'azure', 'google cloud', 'serverless')
    r.sadd('search_suggestions:data', 'data analytics', 'big data', 'data science', 'database')

    # System metrics
    metrics = {
        'total_searches': '0',
        'total_documents': '0',
        'total_users': '2',
        'active_sessions': '1',
        'processing_jobs': '2',
        'cache_hit_rate': '0.85'
    }
    r.hmset('metrics:system', metrics)

    print("✅ Redis configuration completed successfully")
    print(f"📊 Keys created: {r.dbsize()}")

if __name__ == "__main__":
    main()
EOF

    # Execute Redis setup
    if python3 "$SCRIPT_DIR/redis_setup.py"; then
        log "Redis configuration completed"
    else
        error "Redis configuration failed"
    fi

    # Cleanup temporary script
    rm -f "$SCRIPT_DIR/redis_setup.py"
}

# Function to run health checks
run_health_checks() {
    info "Running comprehensive health checks..."

    echo ""
    log "=== Database Health Check Results ==="

    # PostgreSQL health check
    if PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" >/dev/null 2>&1; then
        table_count=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
        echo "  ✅ PostgreSQL: Healthy ($table_count tables)"
    else
        echo "  ❌ PostgreSQL: Error"
    fi

    # Qdrant health check
    if curl -s -f "$QDRANT_URL/health" >/dev/null 2>&1; then
        echo "  ✅ Qdrant: Healthy"
    else
        echo "  ❌ Qdrant: Error"
    fi

    # Redis health check
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q "PONG"; then
        key_count=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" dbsize 2>/dev/null)
        echo "  ✅ Redis: Healthy ($key_count keys)"
    else
        echo "  ❌ Redis: Error"
    fi

    echo ""
}

# Main execution
main() {
    log "Starting Multimodal Enterprise RAG System database initialization..."

    # Wait for services to be ready
    wait_for_service "PostgreSQL" "$POSTGRES_HOST" "$POSTGRES_PORT" 60
    wait_for_service "Qdrant" "$POSTGRES_HOST" "6333" 60
    wait_for_service "Redis" "$REDIS_HOST" "$REDIS_PORT" 60

    # Check all connections
    check_postgres

    # Initialize databases
    init_postgresql
    init_qdrant
    init_redis

    # Run health checks
    run_health_checks

    log "🎉 Database initialization completed successfully!"
    log ""
    log "Next steps:"
    log "1. Update your application configuration with the database connection details"
    log "2. Run your application migrations if needed"
    log "3. Test the database connections from your application"
    log "4. Start using the Multimodal Enterprise RAG System!"
}

# Execute main function
main "$@"