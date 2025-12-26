#!/bin/bash

# Docker Compose Validation Script
# This script validates the Docker Compose configuration and checks for common issues

set -e

echo "🔍 Validating Docker Compose Configuration..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[VALIDATION]${NC} $1"
}

# Check if Docker is running
check_docker() {
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    print_status "Docker is running ✓"
}

# Check Docker Compose installation
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed."
        exit 1
    fi
    print_status "Docker Compose is installed ✓"
}

# Validate main docker-compose.yml
validate_main_compose() {
    print_header "Validating main docker-compose.yml..."

    if [ ! -f docker-compose.yml ]; then
        print_error "docker-compose.yml not found"
        return 1
    fi

    if docker-compose config --quiet; then
        print_status "docker-compose.yml is valid ✓"
    else
        print_error "docker-compose.yml has errors:"
        docker-compose config
        return 1
    fi
}

# Validate monitoring docker-compose if it exists
validate_monitoring_compose() {
    print_header "Validating monitoring docker-compose..."

    if [ -f monitoring/docker-compose.monitoring.yml ]; then
        cd monitoring
        if docker-compose -f docker-compose.monitoring.yml config --quiet; then
            print_status "monitoring/docker-compose.monitoring.yml is valid ✓"
        else
            print_error "monitoring/docker-compose.monitoring.yml has errors:"
            docker-compose -f docker-compose.monitoring.yml config
            cd ..
            return 1
        fi
        cd ..
    else
        print_warning "monitoring/docker-compose.monitoring.yml not found (optional)"
    fi
}

# Check for environment variables
check_environment() {
    print_header "Checking environment configuration..."

    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            print_warning ".env file not found, but .env.example exists"
            print_status "Consider copying .env.example to .env and configuring it"
        else
            print_warning "No .env or .env.example file found"
        fi
    else
        print_status ".env file exists ✓"
    fi
}

# Check for required files
check_required_files() {
    print_header "Checking required files..."

    local required_files=("docker-compose.yml" "QUICK_START_MONITORING.sh" "START_MONITORED_SYSTEM.sh")
    local missing_files=()

    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            missing_files+=("$file")
        fi
    done

    if [ ${#missing_files[@]} -eq 0 ]; then
        print_status "All required files exist ✓"
    else
        print_error "Missing required files:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        return 1
    fi
}

# Check for common configuration issues
check_common_issues() {
    print_header "Checking for common configuration issues..."

    # Check for obsolete version attribute
    if grep -q "^version:" docker-compose.yml; then
        print_error "Found obsolete 'version' attribute in docker-compose.yml"
        print_status "Modern Docker Compose doesn't require version specification"
        return 1
    else
        print_status "No obsolete 'version' attribute found ✓"
    fi

    # Check for container_name with replicas conflict
    if grep -A 5 -B 5 "replicas:" docker-compose.yml | grep -q "container_name:"; then
        print_error "Found 'container_name' with 'replicas' - this causes conflicts"
        print_status "Services with replicas cannot have container_name"
        return 1
    else
        print_status "No container_name/replicas conflicts found ✓"
    fi
}

# Check disk space
check_disk_space() {
    print_header "Checking available disk space..."

    local available_gb=$(df . | tail -1 | awk '{print int($4/1024/1024)}')

    if [ "$available_gb" -lt 5 ]; then
        print_warning "Low disk space: ${available_gb}GB available (recommended: 10GB+)"
    else
        print_status "Sufficient disk space: ${available_gb}GB available ✓"
    fi
}

# Check Docker resources
check_docker_resources() {
    print_header "Checking Docker resources..."

    # Check available memory
    local docker_info=$(docker system df --format "{{.Type}}: {{.Count}}" 2>/dev/null || echo "")

    if [ -n "$docker_info" ]; then
        print_status "Docker system info accessible ✓"
    else
        print_warning "Could not access Docker system info"
    fi
}

# Display summary
display_summary() {
    print_header "Validation Summary"
    echo ""
    echo -e "${GREEN}✅ Docker Compose configuration is valid and ready!${NC}"
    echo ""
    echo -e "${BLUE}🚀 Next Steps:${NC}"
    echo "  1. Start the complete system: ./START_MONITORED_SYSTEM.sh"
    echo "  2. Or start monitoring only: ./QUICK_START_MONITORING.sh"
    echo "  3. Or use Docker Compose directly: docker-compose up -d"
    echo ""
    echo -e "${BLUE}📚 Documentation:${NC}"
    echo "  • Full guide: docs/RUN_MONITORING.md"
    echo "  • Troubleshooting: docs/TROUBLESHOOTING.md"
    echo ""
}

# Main execution
main() {
    echo "🎯 Docker Compose Validation"
    echo "==========================="
    echo ""

    check_docker
    check_docker_compose
    validate_main_compose
    validate_monitoring_compose
    check_environment
    check_required_files
    check_common_issues
    check_disk_space
    check_docker_resources
    display_summary

    echo -e "${GREEN}✅ All validation checks passed!${NC}"
}

# Handle script interruption
trap 'print_warning "Validation interrupted."; exit 1' INT

# Run main function
main "$@"