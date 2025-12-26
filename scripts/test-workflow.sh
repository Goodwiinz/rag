#!/bin/bash

# Test GitHub Actions workflow locally using act
# Usage: ./test-workflow.sh [job-name]
# Example: ./test-workflow.sh lint

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

JOB=${1:-lint}

echo -e "${BLUE}Testing GitHub Actions workflow locally${NC}"
echo -e "${BLUE}Job: $JOB${NC}"
echo ""

# Run act with dry-run to validate workflow
echo -e "${GREEN}Running dry-run validation...${NC}"
act -j "$JOB" \
  --container-architecture linux/amd64 \
  -P ubuntu-latest=catthehacker/ubuntu:act-latest \
  --dryrun

echo ""
echo -e "${GREEN}✅ Workflow validation successful!${NC}"
echo ""
echo "To run the workflow for real (will use Docker):"
echo "  act -j $JOB --container-architecture linux/amd64 -P ubuntu-latest=catthehacker/ubuntu:act-latest"
echo ""
echo "Available jobs:"
echo "  - lint"
echo "  - test"
echo "  - docker-build"
echo "  - security-scan"
