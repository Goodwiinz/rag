#!/bin/bash
# Generate TypeScript types from OpenAPI schema
# This script fetches the OpenAPI schema from the running backend and generates TypeScript types

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
OUTPUT_DIR="$ROOT_DIR/frontend/src/types/generated"
OUTPUT_FILE="$OUTPUT_DIR/api.ts"

echo "Generating API types from $BACKEND_URL/openapi.json..."

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# Check if backend is running
if ! curl -s --connect-timeout 5 "$BACKEND_URL/openapi.json" > /dev/null 2>&1; then
    echo "Error: Backend is not running at $BACKEND_URL"
    echo "Please start the backend with: docker-compose -f docker-compose.development.yml up backend"
    exit 1
fi

# Check if openapi-typescript is installed
if ! command -v npx &> /dev/null; then
    echo "Error: npx is not installed. Please install Node.js"
    exit 1
fi

# Generate types using openapi-typescript
echo "Fetching OpenAPI schema and generating types..."
npx openapi-typescript "$BACKEND_URL/openapi.json" -o "$OUTPUT_FILE"

echo "Types generated successfully at $OUTPUT_FILE"
echo ""
echo "Import generated types with:"
echo "  import type { paths, components, operations } from '@/types/generated/api';"
