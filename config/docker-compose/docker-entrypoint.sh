#!/bin/bash
set -e

# Function to wait for a service to be available
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local timeout=${4:-60}

    echo "Waiting for $service_name to be ready at $host:$port..."

    for i in $(seq 1 $timeout); do
        if nc -z $host $port; then
            echo "$service_name is ready!"
            return 0
        fi
        echo "Attempt $i/$timeout: $service_name not ready yet, waiting..."
        sleep 2
    done

    echo "ERROR: $service_name not ready after $timeout seconds"
    exit 1
}

# Function to run database migrations
run_migrations() {
    echo "Running database migrations..."
    if [ -f "alembic.ini" ]; then
        # Check if alembic directory exists
        if [ -d "alembic" ]; then
            python -c "
from src.core.database import engine
from src.models.base import Base
print('Creating database tables...')
Base.metadata.create_all(bind=engine)
print('Database tables created successfully')
"
        else
            echo "Alembic directory not found, skipping migrations"
        fi
    else
        echo "No alembic.ini found, skipping migrations"
    fi
}

# Function to initialize Qdrant collections
init_qdrant_collections() {
    echo "Initializing Qdrant collections..."
    python -c "
import asyncio
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, CreateCollection
import os

async def init_collections():
    try:
        client = QdrantClient(url=os.getenv('QDRANT_URL', 'http://qdrant:6333'))

        # Create documents collection
        try:
            client.create_collection(
                collection_name='documents',
                vectors_config=VectorParams(
                    size=768,
                    distance=Distance.COSINE
                )
            )
            print('Created documents collection')
        except Exception as e:
            if 'already exists' in str(e):
                print('Documents collection already exists')
            else:
                raise e

        # Create entities collection
        try:
            client.create_collection(
                collection_name='entities',
                vectors_config=VectorParams(
                    size=768,
                    distance=Distance.COSINE
                )
            )
            print('Created entities collection')
        except Exception as e:
            if 'already exists' in str(e):
                print('Entities collection already exists')
            else:
                raise e

        print('Qdrant collections initialized successfully')
    except Exception as e:
        print(f'Error initializing Qdrant collections: {e}')

asyncio.run(init_collections())
"
}

# Function to initialize Neo4j constraints
init_neo4j_constraints() {
    echo "Initializing Neo4j constraints..."
    python -c "
from neo4j import GraphDatabase
import os

def init_constraints():
    try:
        driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI', 'bolt://neo4j:7687'),
            auth=(os.getenv('NEO4J_USER', 'neo4j'), os.getenv('NEO4J_PASSWORD', 'neo4jpassword'))
        )

        with driver.session() as session:
            # Create constraints
            constraints = [
                'CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE',
                'CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE',
                'CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE',
                'CREATE CONSTRAINT organization_id_unique IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE',
                'CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name)',
                'CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type)',
                'CREATE INDEX document_title_index IF NOT EXISTS FOR (d:Document) ON (d.title)',
                'CREATE INDEX document_type_index IF NOT EXISTS FOR (d:Document) ON (d.type)',
                'CREATE INDEX user_email_index IF NOT EXISTS FOR (u:User) ON (u.email)'
            ]

            for constraint in constraints:
                try:
                    session.run(constraint)
                    print(f'Applied: {constraint}')
                except Exception as e:
                    if 'already exists' in str(e) or 'equivalent' in str(e):
                        print(f'Already exists: {constraint}')
                    else:
                        print(f'Error applying constraint: {e}')

        driver.close()
        print('Neo4j constraints initialized successfully')
    except Exception as e:
        print(f'Error initializing Neo4j constraints: {e}')

init_constraints()
"
}

# Main initialization logic
echo "Starting RAG System service: ${SERVICE_NAME:-unknown}"

# Set default environment variables if not provided
export PORT=${PORT:-8000}
export DEBUG=${DEBUG:-false}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

# Wait for dependencies based on service
case ${SERVICE_NAME:-unknown} in
    "api-gateway")
        echo "API Gateway starting..."
        # API Gateway needs all services to be ready
        wait_for_service postgres 5432 PostgreSQL
        wait_for_service redis 6379 Redis
        ;;
    "document-management")
        echo "Document Management Service starting..."
        wait_for_service postgres 5432 PostgreSQL
        wait_for_service redis 6379 Redis
        run_migrations
        ;;
    "search-service")
        echo "Search Service starting..."
        wait_for_service postgres 5432 PostgreSQL
        wait_for_service redis 6379 Redis
        wait_for_service neo4j 7687 Neo4j
        wait_for_service qdrant 6333 Qdrant
        init_qdrant_collections
        init_neo4j_constraints
        ;;
    "knowledge-graph-service")
        echo "Knowledge Graph Service starting..."
        wait_for_service postgres 5432 PostgreSQL
        wait_for_service neo4j 7687 Neo4j
        init_neo4j_constraints
        ;;
    "evaluation-service")
        echo "Evaluation Service starting..."
        wait_for_service postgres 5432 PostgreSQL
        wait_for_service redis 6379 Redis
        ;;
    "processing-service")
        echo "Processing Pipeline Service starting..."
        wait_for_service postgres 5432 PostgreSQL
        wait_for_service redis 6379 Redis
        wait_for_service neo4j 7687 Neo4j
        wait_for_service qdrant 6333 Qdrant
        init_qdrant_collections
        init_neo4j_constraints
        ;;
    "analytics-service")
        echo "Analytics Service starting..."
        wait_for_service postgres 5432 PostgreSQL
        wait_for_service redis 6379 Redis
        ;;
    "user-management")
        echo "User Management Service starting..."
        wait_for_service postgres 5432 PostgreSQL
        wait_for_service redis 6379 Redis
        run_migrations
        ;;
    "realtime-communications")
        echo "Real-time Communications Service starting..."
        wait_for_service redis 6379 Redis
        ;;
    *)
        echo "Unknown service: ${SERVICE_NAME:-unknown}"
        echo "Available services:"
        echo "  - api-gateway"
        echo "  - document-management"
        echo "  - search-service"
        echo "  - knowledge-graph-service"
        echo "  - evaluation-service"
        echo "  - processing-service"
        echo "  - analytics-service"
        echo "  - user-management"
        echo "  - realtime-communications"
        exit 1
        ;;
esac

# Log service startup
echo "Service ${SERVICE_NAME:-unknown} starting on port ${PORT}"
echo "Environment: ${ENVIRONMENT:-development}"
echo "Debug mode: ${DEBUG}"
echo "Log level: ${LOG_LEVEL}"

# Start the service
if [ "${SERVICE_NAME}" = "api-gateway" ]; then
    exec python -m src.services.api_gateway
elif [ "${SERVICE_NAME}" = "document-management" ]; then
    exec python -m src.services.document_management
elif [ "${SERVICE_NAME}" = "search-service" ]; then
    exec python -m src.services.search_service
elif [ "${SERVICE_NAME}" = "knowledge-graph-service" ]; then
    exec python -m src.services.knowledge_graph_service
elif [ "${SERVICE_NAME}" = "evaluation-service" ]; then
    exec python -m src.services.evaluation_service
elif [ "${SERVICE_NAME}" = "processing-service" ]; then
    exec python -m src.services.processing_service
elif [ "${SERVICE_NAME}" = "analytics-service" ]; then
    exec python -m src.services.analytics_service
elif [ "${SERVICE_NAME}" = "user-management" ]; then
    exec python -m src.services.user_management
elif [ "${SERVICE_NAME}" = "realtime-communications" ]; then
    exec python -m src.services.realtime_service
else
    echo "Unknown service: ${SERVICE_NAME}"
    exit 1
fi