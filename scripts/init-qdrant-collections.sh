#!/bin/bash

# Qdrant Collections Initialization Script
# This script initializes Qdrant collections for the Knowledge Graph embeddings
# Run this after starting Qdrant service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
QDRANT_URL="http://localhost:6333"
COLLECTIONS_CONFIG_FILE="../database/qdrant_knowledge_graph_collections.json"

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

# Check if Qdrant is running
check_qdrant_health() {
    log "Checking Qdrant connectivity..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -f "$QDRANT_URL/health" &> /dev/null; then
            success "Qdrant is accessible at $QDRANT_URL"
            return 0
        fi

        log "Attempt $attempt/$max_attempts - Qdrant not ready yet..."
        sleep 5
        ((attempt++))
    done

    error "Qdrant did not become healthy within $max_attempts attempts"
}

# Wait for Qdrant to be ready
wait_for_qdrant() {
    log "Waiting for Qdrant service to be ready..."

    # Check basic health
    while ! curl -f "$QDRANT_URL/health" &> /dev/null; do
        log "Waiting for Qdrant to start..."
        sleep 2
    done

    # Check collections endpoint
    while ! curl -f "$QDRANT_URL/collections" &> /dev/null; do
        log "Waiting for Qdrant API to be ready..."
        sleep 2
    done

    success "Qdrant is ready"
}

# Create collection with configuration
create_collection() {
    local collection_name="$1"
    local config_file="$2"

    log "Creating collection: $collection_name"

    if curl -s -X PUT "$QDRANT_URL/collections/$collection_name" \
         -H "Content-Type: application/json" \
         -d @"$config_file" | grep -q '"result":true\|status.*ok'; then
        success "Collection '$collection_name' created successfully"
    else
        # Try to get existing collection info
        local existing_info
        existing_info=$(curl -s "$QDRANT_URL/collections/$collection_name" 2>/dev/null || echo "")

        if echo "$existing_info" | grep -q '"result"'; then
            warning "Collection '$collection_name' already exists, skipping creation"
        else
            error "Failed to create collection '$collection_name'"
        fi
    fi
}

# Create collection from JSON configuration
create_collection_from_config() {
    local collection_name="$1"
    local collection_config="$2"

    log "Creating collection '$collection_name' with detailed configuration..."

    # Create a temporary config file for this collection
    local temp_config
    temp_config=$(mktemp)

    # Extract collection configuration from the JSON
    echo "$collection_config" > "$temp_config"

    # Create the collection
    if curl -s -X PUT "$QDRANT_URL/collections/$collection_name" \
         -H "Content-Type: application/json" \
         -d @"$temp_config" | grep -q '"result":true'; then
        success "Collection '$collection_name' created successfully"
    else
        local response
        response=$(curl -s -X PUT "$QDRANT_URL/collections/$collection_name" \
                         -H "Content-Type: application/json" \
                         -d @"$temp_config")

        if echo "$response" | grep -q "already exists"; then
            warning "Collection '$collection_name' already exists"
        else
            error "Failed to create collection '$collection_name': $response"
        fi
    fi

    # Clean up temp file
    rm -f "$temp_config"
}

# Create payload indexes for collection
create_payload_indexes() {
    local collection_name="$1"
    local indexes_config="$2"

    log "Creating payload indexes for collection '$collection_name'..."

    # Parse indexes and create them
    local index_count
    index_count=$(echo "$indexes_config" | jq '.payload_indexes | length' 2>/dev/null || echo "0")

    if [ "$index_count" -gt 0 ]; then
        for ((i = 0; i < index_count; i++)); do
            local field_name
            local field_schema

            field_name=$(echo "$indexes_config" | jq -r ".payload_indexes[$i].field_name")
            field_schema=$(echo "$indexes_config" | jq -r ".payload_indexes[$i].field_schema")

            if [ "$field_name" != "null" ] && [ "$field_schema" != "null" ]; then
                log "Creating index for field '$field_name' with schema '$field_schema'"

                local index_config
                index_config=$(cat <<EOF
{
    "field_name": "$field_name",
    "field_schema": {
        "type": "$field_schema"
    }
}
EOF
)

                if curl -s -X PUT "$QDRANT_URL/collections/$collection_name/index" \
                     -H "Content-Type: application/json" \
                     -d "$index_config" | grep -q '"result":true'; then
                    success "Index created for field '$field_name'"
                else
                    warning "Failed to create index for field '$field_name'"
                fi
            fi
        done
    fi
}

# Verify collection exists and get info
verify_collection() {
    local collection_name="$1"

    log "Verifying collection '$collection_name'..."

    local collection_info
    collection_info=$(curl -s "$QDRANT_URL/collections/$collection_name")

    if echo "$collection_info" | grep -q '"result"'; then
        local vector_size
        vector_size=$(echo "$collection_info" | jq -r '.result.config.params.vectors.size')
        local distance
        distance=$(echo "$collection_info" | jq -r '.result.config.params.vectors.distance')
        local status
        status=$(echo "$collection_info" | jq -r '.result.status')

        success "Collection '$collection_name' verified:"
        echo "  - Vector Size: $vector_size"
        echo "  - Distance: $distance"
        echo "  - Status: $status"

        return 0
    else
        error "Collection '$collection_name' verification failed"
    fi
}

# List all collections
list_collections() {
    log "Listing all collections..."

    local collections
    collections=$(curl -s "$QDRANT_URL/collections")

    if echo "$collections" | grep -q '"result"'; then
        echo "$collections" | jq -r '.result.collections[].name' | while read -r collection; do
            echo "  - $collection"
        done
        success "Collections listed successfully"
    else
        warning "Failed to list collections"
    fi
}

# Get cluster information
get_cluster_info() {
    log "Getting Qdrant cluster information..."

    local cluster_info
    cluster_info=$(curl -s "$QDRANT_URL")

    if echo "$cluster_info" | grep -q '"title"'; then
        local title
        local version
        title=$(echo "$cluster_info" | jq -r '.title')
        version=$(echo "$cluster_info" | jq -r '.version')

        success "Qdrant cluster info:"
        echo "  - Title: $title"
        echo "  - Version: $version"
    else
        warning "Failed to get cluster information"
    fi
}

# Check system health and metrics
check_system_health() {
    log "Checking Qdrant system health..."

    # Get detailed health information
    local health_info
    health_info=$(curl -s "$QDRANT_URL/health")

    if echo "$health_info" | grep -q '"status"'; then
        local status
        status=$(echo "$health_info" | jq -r '.status')
        success "Qdrant health status: $status"
    fi

    # Get collections count
    local collections_info
    collections_info=$(curl -s "$QDRANT_URL/collections")

    if echo "$collections_info" | grep -q '"result"'; then
        local collections_count
        collections_count=$(echo "$collections_info" | jq '.result.collections | length')
        success "Total collections: $collections_count"
    fi
}

# Create test vectors for verification
create_test_vectors() {
    local collection_name="$1"
    local vector_size="$2"

    log "Creating test vectors in collection '$collection_name'..."

    # Generate test vector
    local test_vector="["
    for ((i = 0; i < vector_size; i++)); do
        if [ $i -gt 0 ]; then
            test_vector+=","
        fi
        test_vector+=$(echo "scale=6; $RANDOM/32767" | bc)
    done
    test_vector+="]"

    # Create test point
    local test_point
    test_point=$(cat <<EOF
{
    "points": [
        {
            "id": 1,
            "vector": $test_vector,
            "payload": {
                "entity_id": "test_entity_1",
                "entity_name": "Test Entity",
                "entity_type": "test",
                "organization_id": "test_org",
                "confidence": 0.95,
                "importance_score": 0.8,
                "created_at": $(date +%s)
            }
        }
    ]
}
EOF
)

    # Insert test point
    if curl -s -X PUT "$QDRANT_URL/collections/$collection_name/points" \
         -H "Content-Type: application/json" \
         -d "$test_point" | grep -q '"status":"ok"'; then
        success "Test vector created successfully"
    else
        warning "Failed to create test vector"
    fi
}

# Test search functionality
test_search() {
    local collection_name="$1"
    local vector_size="$2"

    log "Testing search functionality on collection '$collection_name'..."

    # Generate search vector
    local search_vector="["
    for ((i = 0; i < vector_size; i++)); do
        if [ $i -gt 0 ]; then
            search_vector+=","
        fi
        search_vector+=$(echo "scale=6; $RANDOM/32767" | bc)
    done
    search_vector+="]"

    # Create search request
    local search_request
    search_request=$(cat <<EOF
{
    "vector": $search_vector,
    "limit": 3,
    "with_payload": true,
    "with_vector": false
}
EOF
)

    # Perform search
    local search_result
    search_result=$(curl -s -X POST "$QDRANT_URL/collections/$collection_name/points/search" \
                         -H "Content-Type: application/json" \
                         -d "$search_request")

    if echo "$search_result" | grep -q '"result"'; then
        local result_count
        result_count=$(echo "$search_result" | jq '.result | length')
        success "Search test successful - found $result_count results"
    else
        warning "Search test failed"
    fi
}

# Initialize all collections from configuration file
initialize_collections_from_config() {
    log "Initializing collections from configuration file..."

    if [ ! -f "$COLLECTIONS_CONFIG_FILE" ]; then
        error "Collections configuration file not found: $COLLECTIONS_CONFIG_FILE"
    fi

    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        error "jq is required to parse JSON configuration. Please install jq."
    fi

    # Parse collections from config
    local collections
    collections=$(jq -r '.collections | keys[]' "$COLLECTIONS_CONFIG_FILE")

    for collection_name in $collections; do
        log "Processing collection: $collection_name"

        # Get collection configuration
        local collection_config
        collection_config=$(jq ".collections.\"$collection_name\"" "$COLLECTIONS_CONFIG_FILE")

        # Extract vector size for testing
        local vector_size
        vector_size=$(echo "$collection_config" | jq -r '.vectors.size')

        # Create collection
        create_collection_from_config "$collection_name" "$collection_config"

        # Create payload indexes if available
        local indexes_config
        indexes_config=$(jq ".indexing_strategies.\"$collection_name\"" "$COLLECTIONS_CONFIG_FILE" 2>/dev/null || echo "{}")

        if [ "$indexes_config" != "{}" ] && [ "$indexes_config" != "null" ]; then
            create_payload_indexes "$collection_name" "$indexes_config"
        fi

        # Verify collection
        verify_collection "$collection_name"

        # Create test vectors (optional - for testing only)
        if [ "$SKIP_TEST_VECTORS" != "true" ]; then
            create_test_vectors "$collection_name" "$vector_size"
        fi

        # Test search (optional - for testing only)
        if [ "$SKIP_TEST_SEARCH" != "true" ]; then
            test_search "$collection_name" "$vector_size"
        fi
    done
}

# Clean up test data
cleanup_test_data() {
    log "Cleaning up test data..."

    local collections
    collections=$(curl -s "$QDRANT_URL/collections" | jq -r '.result.collections[].name' 2>/dev/null || echo "")

    for collection_name in $collections; do
        log "Cleaning test points from collection '$collection_name'..."

        # Delete test points (points with test_entity_id)
        local delete_request
        delete_request=$(cat <<EOF
{
    "points": [
        {
            "filter": {
                "must": [
                    {
                        "key": "entity_id",
                        "match": {
                            "value": "test_entity_1"
                        }
                    }
                ]
            }
        }
    ]
}
EOF
)

        curl -s -X POST "$QDRANT_URL/collections/$collection_name/points/delete" \
             -H "Content-Type: application/json" \
             -d "$delete_request" > /dev/null
    done

    success "Test data cleaned up"
}

# Display usage information
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -c, --config FILE       Use custom configuration file (default: $COLLECTIONS_CONFIG_FILE)"
    echo "  -u, --url URL           Qdrant URL (default: $QDRANT_URL)"
    echo "  --skip-test-vectors     Skip creating test vectors"
    echo "  --skip-test-search      Skip testing search functionality"
    echo "  --cleanup-only          Only clean up test data"
    echo "  --verify-only           Only verify existing collections"
    echo ""
    echo "Commands:"
    echo "  init                    Initialize all collections (default)"
    echo "  list                    List all collections"
    echo "  verify                  Verify collection configurations"
    echo "  cleanup                 Clean up test data"
    echo "  health                  Check system health"
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
            -c|--config)
                COLLECTIONS_CONFIG_FILE="$2"
                shift 2
                ;;
            -u|--url)
                QDRANT_URL="$2"
                shift 2
                ;;
            --skip-test-vectors)
                export SKIP_TEST_VECTORS="true"
                shift
                ;;
            --skip-test-search)
                export SKIP_TEST_SEARCH="true"
                shift
                ;;
            --cleanup-only)
                command="cleanup"
                shift
                ;;
            --verify-only)
                command="verify"
                shift
                ;;
            init|list|verify|cleanup|health)
                command="$1"
                shift
                ;;
            *)
                error "Unknown option: $1. Use --help for usage information."
                ;;
        esac
    done

    log "Starting Qdrant Collections Initialization..."
    log "Qdrant URL: $QDRANT_URL"
    log "Configuration file: $COLLECTIONS_CONFIG_FILE"

    case "$command" in
        "init")
            check_qdrant_health
            wait_for_qdrant
            get_cluster_info
            initialize_collections_from_config
            list_collections
            check_system_health
            success "Qdrant collections initialization completed successfully!"
            ;;
        "list")
            check_qdrant_health
            list_collections
            ;;
        "verify")
            check_qdrant_health

            local collections
            collections=$(curl -s "$QDRANT_URL/collections" | jq -r '.result.collections[].name' 2>/dev/null || echo "")

            for collection_name in $collections; do
                verify_collection "$collection_name"
            done
            ;;
        "cleanup")
            check_qdrant_health
            cleanup_test_data
            ;;
        "health")
            check_qdrant_health
            get_cluster_info
            check_system_health
            ;;
        *)
            error "Unknown command: $command"
            ;;
    esac
}

# Trap to clean up on exit
trap cleanup_test_data EXIT

# Run main function with all arguments
main "$@"