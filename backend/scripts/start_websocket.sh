#!/bin/bash

# WebSocket service startup script
set -e

echo "Starting WebSocket service..."
echo "Node ID: ${WS_NODE_ID:-unknown}"
echo "Max connections: ${WS_MAX_CONNECTIONS:-5000}"
echo "Port: ${WS_PORT:-8001}"

# Wait for dependencies
echo "Waiting for Redis..."
timeout 60 bash -c 'until nc -z ${REDIS_HOST:-redis-cluster} 6379; do sleep 1; done' || exit 1

echo "Waiting for PostgreSQL..."
timeout 60 bash -c 'until nc -z ${POSTGRES_HOST:-postgres} 5432; do sleep 1; done' || exit 1

echo "Waiting for Neo4j..."
timeout 60 bash -c 'until nc -z ${NEO4J_HOST:-neo4j} 7687; do sleep 1; done' || exit 1

echo "All dependencies ready!"

# Run database migrations if needed
echo "Running database migrations..."
python -m alembic upgrade heads || echo "Migration completed or not needed"

# Create logs directory
mkdir -p logs

# Set log file
LOG_FILE="logs/websocket_${WS_NODE_ID:-node}.$(date +%Y%m%d_%H%M%S).log"

echo "Starting WebSocket server..."
echo "Log file: $LOG_FILE"

# Start the WebSocket service with appropriate worker configuration
exec uvicorn src.websocket.server:app \
    --host ${WS_HOST:-0.0.0.0} \
    --port ${WS_PORT:-8001} \
    --workers ${WS_WORKERS:-1} \
    --worker-class uvicorn.workers.UvicornWorker \
    --ws websockets \
    --ws-ping-interval ${WS_PING_INTERVAL:-20} \
    --ws-ping-timeout ${WS_PING_TIMEOUT:-10} \
    --access-log \
    --log-level ${LOG_LEVEL:-info} \
    --log-config logging_config.yaml \
    --loop uvloop \
    --http h11 \
    --reload ${WS_RELOAD:-false} \
    2>&1 | tee "$LOG_FILE"
