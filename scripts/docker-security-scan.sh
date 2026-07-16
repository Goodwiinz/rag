#!/bin/bash
# =============================================================================
# Docker Security Scanning Script
# =============================================================================
# This script performs comprehensive security scanning of Docker images
# before they are deployed to production environments

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_IMAGE="${BACKEND_IMAGE:-knowledge-graph-backend:latest}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-knowledge-graph-frontend:latest}"
REGISTRY="${REGISTRY:-ghcr.io}"
SCAN_REPORTS_DIR="${PROJECT_ROOT}/security-reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create reports directory
create_reports_dir() {
    log_info "Creating security reports directory..."
    mkdir -p "$SCAN_REPORTS_DIR"
    log_success "Reports directory created: $SCAN_REPORTS_DIR"
}

# Check if required tools are installed
check_dependencies() {
    log_info "Checking dependencies..."

    local missing_deps=()

    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    fi

    if ! command -v trivy &> /dev/null; then
        missing_deps+=("trivy")
    fi

    if ! command -v snyk &> /dev/null; then
        missing_deps+=("snyk")
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_info "Please install missing dependencies:"
        for dep in "${missing_deps[@]}"; do
            case $dep in
                "docker")
                    echo "  - Docker: https://docs.docker.com/get-docker/"
                    ;;
                "trivy")
                    echo "  - Trivy: https://github.com/aquasecurity/trivy"
                    ;;
                "snyk")
                    echo "  - Snyk: https://snyk.io/docs/cli/"
                    ;;
            esac
        done
        exit 1
    fi

    log_success "All dependencies are installed"
}

# Pull images for scanning
pull_images() {
    log_info "Pulling Docker images for scanning..."

    # Pull backend image
    if docker pull "$BACKEND_IMAGE" &>/dev/null; then
        log_success "Backend image pulled: $BACKEND_IMAGE"
    else
        log_warning "Backend image not found locally or failed to pull: $BACKEND_IMAGE"
    fi

    # Pull frontend image
    if docker pull "$FRONTEND_IMAGE" &>/dev/null; then
        log_success "Frontend image pulled: $FRONTEND_IMAGE"
    else
        log_warning "Frontend image not found locally or failed to pull: $FRONTEND_IMAGE"
    fi
}

# Run Trivy vulnerability scan
run_trivy_scan() {
    local image_name="$1"
    local image_tag="$2"
    local report_file="$SCAN_REPORTS_DIR/trivy_${image_tag}_${TIMESTAMP}.json"

    log_info "Running Trivy vulnerability scan on $image_name..."

    if docker images --format "table {{.Repository}}:{{.Tag}}" | grep -q "$image_name"; then
        trivy image --format json --output "$report_file" --quiet --no-progress "$image_name"

        # Convert to human-readable format
        local human_report_file="$SCAN_REPORTS_DIR/trivy_${image_tag}_${TIMESTAMP}.txt"
        trivy image --format table --output "$human_report_file" --quiet --no-progress "$image_name"

        # Check for critical vulnerabilities
        local critical_count=$(jq '.Results[]? | select(.Vulnerabilities) | .Vulnerabilities[] | select(.Severity == "CRITICAL") | .VulnerabilityID' "$report_file" | wc -l || echo "0")
        local high_count=$(jq '.Results[]? | select(.Vulnerabilities) | .Vulnerabilities[] | select(.Severity == "HIGH") | .VulnerabilityID' "$report_file" | wc -l || echo "0")

        if [ "$critical_count" -gt 0 ]; then
            log_error "Found $critical_count CRITICAL vulnerabilities in $image_name"
            echo "Critical vulnerabilities:"
            jq -r '.Results[]? | select(.Vulnerabilities) | .Vulnerabilities[] | select(.Severity == "CRITICAL") | "- \(.VulnerabilityID): \(.Title)"' "$report_file"
            return 1
        elif [ "$high_count" -gt 5 ]; then
            log_warning "Found $high_count HIGH vulnerabilities in $image_name (threshold: 5)"
        else
            log_success "Trivy scan completed for $image_name (Critical: $critical_count, High: $high_count)"
        fi

        log_success "Trivy report saved to: $report_file"
    else
        log_warning "Image $image_name not found for scanning"
        return 1
    fi
}

# Run Snyk vulnerability scan
run_snyk_scan() {
    local image_name="$1"
    local image_tag="$2"
    local report_file="$SCAN_REPORTS_DIR/snyk_${image_tag}_${TIMESTAMP}.json"

    log_info "Running Snyk vulnerability scan on $image_name..."

    if docker images --format "table {{.Repository}}:{{.Tag}}" | grep -q "$image_name"; then
        # Check if Snyk is authenticated
        if ! snyk auth &>/dev/null; then
            log_warning "Snyk not authenticated. Skipping Snyk scan."
            return 0
        fi

        # Run Snyk scan
        snyk container test "$image_name" --json --output-file="$report_file" || true

        # Convert to human-readable format
        local human_report_file="$SCAN_REPORTS_DIR/snyk_${image_tag}_${TIMESTAMP}.txt"
        snyk container test "$image_name" --sarif-file-output="$SCAN_REPORTS_DIR/snyk_${image_tag}_${TIMESTAMP}.sarif" || true

        log_success "Snyk report saved to: $report_file"
    else
        log_warning "Image $image_name not found for Snyk scanning"
        return 1
    fi
}

# Run Docker Bench Security check
run_docker_bench_security() {
    local report_file="$SCAN_REPORTS_DIR/docker-bench-security_${TIMESTAMP}.txt"

    log_info "Running Docker Bench Security check..."

    if command -v docker-bench-security &> /dev/null; then
        docker-bench-security -l "$report_file" || true
        log_success "Docker Bench Security report saved to: $report_file"
    else
        log_warning "Docker Bench Security not found. Skipping..."
    fi
}

# Analyze Dockerfile for security best practices
analyze_dockerfile() {
    local dockerfile="$1"
    local report_file="$SCAN_REPORTS_DIR/dockerfile-analysis_${TIMESTAMP}.txt"

    log_info "Analyzing Dockerfile: $dockerfile"

    if [ -f "$dockerfile" ]; then
        echo "Dockerfile Security Analysis: $dockerfile" > "$report_file"
        echo "Generated: $(date)" >> "$report_file"
        echo "" >> "$report_file"

        # Check for security best practices
        local issues=0

        # Check if user is root
        if grep -q "^USER " "$dockerfile" && ! grep -q "USER.*[^0-9]" "$dockerfile"; then
            echo "[INFO] Non-root user specified" >> "$report_file"
        else
            echo "[WARNING] No non-root user specified" >> "$report_file"
            ((issues++))
        fi

        # Check for base image
        if grep -q "^FROM.*:latest" "$dockerfile"; then
            echo "[WARNING] Using 'latest' tag for base image" >> "$report_file"
            ((issues++))
        else
            echo "[INFO] Using specific version tag for base image" >> "$report_file"
        fi

        # Check for health check
        if grep -q "^HEALTHCHECK" "$dockerfile"; then
            echo "[INFO] Health check defined" >> "$report_file"
        else
            echo "[WARNING] No health check defined" >> "$report_file"
            ((issues++))
        fi

        # Check for exposed ports
        if grep -q "^EXPOSE" "$dockerfile"; then
            echo "[INFO] Ports exposed" >> "$report_file"
        fi

        # Check for security updates
        if grep -q "apt-get update" "$dockerfile" && grep -q "apt-get upgrade" "$dockerfile"; then
            echo "[INFO] Security updates applied" >> "$report_file"
        else
            echo "[WARNING] Security updates may not be applied" >> "$report_file"
            ((issues++))
        fi

        echo "" >> "$report_file"
        echo "Total potential security issues: $issues" >> "$report_file"

        if [ $issues -eq 0 ]; then
            log_success "Dockerfile analysis passed with no issues"
        else
            log_warning "Dockerfile analysis found $issues potential issues"
        fi

        log_success "Dockerfile analysis saved to: $report_file"
    else
        log_warning "Dockerfile not found: $dockerfile"
    fi
}

# Generate summary report
generate_summary_report() {
    local summary_file="$SCAN_REPORTS_DIR/security-scan-summary_${TIMESTAMP}.txt"

    log_info "Generating security scan summary report..."

    cat > "$summary_file" << EOF
Security Scan Summary Report
============================
Generated: $(date)
Images Scanned:
- Backend: $BACKEND_IMAGE
- Frontend: $FRONTEND_IMAGE

Reports Generated:
EOF

    # List all generated reports
    find "$SCAN_REPORTS_DIR" -name "*_${TIMESTAMP}.*" -type f | while read -r report; do
        echo "- $(basename "$report")" >> "$summary_file"
    done

    cat >> "$summary_file" << EOF

Security Recommendations:
1. Review all CRITICAL and HIGH vulnerability findings
2. Update base images to latest secure versions
3. Remove unnecessary packages from images
4. Implement image signing and verification
5. Set up automated security scanning in CI/CD pipeline
6. Regularly update dependencies
7. Implement runtime security monitoring

Next Steps:
1. Address any CRITICAL vulnerabilities immediately
2. Plan remediation for HIGH vulnerabilities
3. Update Dockerfiles based on analysis recommendations
4. Configure automated scanning in deployment pipeline
EOF

    log_success "Summary report saved to: $summary_file"
}

# Main execution
main() {
    log_info "Starting Docker security scanning..."

    create_reports_dir
    check_dependencies
    pull_images

    # Scan backend image
    if docker images --format "table {{.Repository}}:{{.Tag}}" | grep -q "$BACKEND_IMAGE"; then
        run_trivy_scan "$BACKEND_IMAGE" "backend"
        run_snyk_scan "$BACKEND_IMAGE" "backend"
    else
        log_warning "Backend image not found for scanning"
    fi

    # Scan frontend image
    if docker images --format "table {{.Repository}}:{{.Tag}}" | grep -q "$FRONTEND_IMAGE"; then
        run_trivy_scan "$FRONTEND_IMAGE" "frontend"
        run_snyk_scan "$FRONTEND_IMAGE" "frontend"
    else
        log_warning "Frontend image not found for scanning"
    fi

    # Analyze Dockerfiles
    analyze_dockerfile "$PROJECT_ROOT/backend/Dockerfile.production"
    analyze_dockerfile "$PROJECT_ROOT/frontend/Dockerfile.production"

    # Run Docker Bench Security
    run_docker_bench_security

    # Generate summary
    generate_summary_report

    log_success "Docker security scanning completed!"
    log_info "All reports saved to: $SCAN_REPORTS_DIR"

    # Show quick summary
    echo
    echo "Quick Summary:"
    echo "=============="
    echo "Reports generated in: $SCAN_REPORTS_DIR"
    echo "Timestamp: $TIMESTAMP"
    echo
    echo "Key files to review:"
    find "$SCAN_REPORTS_DIR" -name "*_${TIMESTAMP}.*" -type f | sort
}

# Help function
show_help() {
    cat << EOF
Docker Security Scanning Script

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -b, --backend IMAGE     Backend image to scan (default: $BACKEND_IMAGE)
    -f, --frontend IMAGE    Frontend image to scan (default: $FRONTEND_IMAGE)
    -r, --registry REGISTRY Container registry (default: $REGISTRY)

Environment Variables:
    BACKEND_IMAGE           Backend image name
    FRONTEND_IMAGE          Frontend image name
    REGISTRY                Container registry

Examples:
    $0
    $0 -b my-backend:latest -f my-frontend:latest
    $0 --backend ghcr.io/myorg/backend:v1.0.0

Requirements:
    - Docker
    - Trivy
    - Snyk (optional, for additional scanning)

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -b|--backend)
            BACKEND_IMAGE="$2"
            shift 2
            ;;
        -f|--frontend)
            FRONTEND_IMAGE="$2"
            shift 2
            ;;
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Run main function
main "$@"