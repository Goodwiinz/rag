#!/bin/bash
# ============================================================================
# Push All Docker Images to Registry
# ============================================================================
# Usage: ./scripts/push_all_images.sh [registry]
# Example: ./scripts/push_all_images.sh docker.io/myusername
#          ./scripts/push_all_images.sh ghcr.io/myorg
# ============================================================================

set -e

# Configuration
REGISTRY="${1:-docker.io/goodwiinz}"  # Your Docker Hub registry
VERSION="${2:-latest}"
COMPOSE_FILE="config/docker-compose/docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Custom images to push (not pulling from Docker Hub)
CUSTOM_SERVICES=(
    "backend"
    "celery-worker"
    "celery-beat"
)

echo -e "${YELLOW}============================================${NC}"
echo -e "${YELLOW}  Docker Image Push Script${NC}"
echo -e "${YELLOW}============================================${NC}"
echo ""

# Check if registry is set
if [ "$REGISTRY" = "your-registry-here" ]; then
    echo -e "${RED}Error: Please specify your registry!${NC}"
    echo ""
    echo "Usage: $0 <registry> [version]"
    echo ""
    echo "Examples:"
    echo "  $0 docker.io/yourusername"
    echo "  $0 ghcr.io/yourorg"
    echo "  $0 your-acr.azurecr.io"
    echo ""
    exit 1
fi

echo -e "Registry: ${GREEN}${REGISTRY}${NC}"
echo -e "Version:  ${GREEN}${VERSION}${NC}"
echo ""

# Login check
echo -e "${YELLOW}Checking Docker login...${NC}"
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Build only the services we need (not frontend)
echo -e "${YELLOW}Building backend images only...${NC}"
docker compose -f "$COMPOSE_FILE" build backend celery-worker celery-beat

echo ""
echo -e "${YELLOW}Tagging and pushing images...${NC}"
echo ""

# Tag and push each custom service
for SERVICE in "${CUSTOM_SERVICES[@]}"; do
    LOCAL_IMAGE="docker-compose-${SERVICE}"
    REMOTE_IMAGE="${REGISTRY}/rag-${SERVICE}:${VERSION}"
    
    echo -e "${YELLOW}→ ${SERVICE}${NC}"
    
    # Check if local image exists
    if docker image inspect "$LOCAL_IMAGE" > /dev/null 2>&1 || \
       docker image inspect "${LOCAL_IMAGE}:latest" > /dev/null 2>&1; then
        
        # Tag the image
        echo "  Tagging: ${LOCAL_IMAGE} → ${REMOTE_IMAGE}"
        docker tag "${LOCAL_IMAGE}:latest" "$REMOTE_IMAGE" 2>/dev/null || \
        docker tag "$LOCAL_IMAGE" "$REMOTE_IMAGE"
        
        # Push the image
        echo "  Pushing: ${REMOTE_IMAGE}"
        if docker push "$REMOTE_IMAGE"; then
            echo -e "  ${GREEN}✓ Success${NC}"
        else
            echo -e "  ${RED}✗ Failed to push${NC}"
        fi
    else
        echo -e "  ${YELLOW}⚠ Image not found locally, skipping${NC}"
    fi
    echo ""
done

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Push Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "To pull these images on another machine:"
echo ""
for SERVICE in "${CUSTOM_SERVICES[@]}"; do
    echo "  docker pull ${REGISTRY}/rag-${SERVICE}:${VERSION}"
done
echo ""
