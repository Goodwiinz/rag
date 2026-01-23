#!/bin/bash

# Quick Start Script for RAG System Monitoring
# This script will set up and start the complete monitoring stack

set -e

echo "🚀 Starting RAG System Monitoring Setup..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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
    echo -e "${BLUE}[SETUP]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi

    print_status "Prerequisites check passed ✓"
}

# Setup environment
setup_environment() {
    print_header "Setting up environment..."

    # Create monitoring directory if it doesn't exist
    mkdir -p monitoring/{prometheus,grafana,elasticsearch,kibana,jaeger}

    # Create environment file if it doesn't exist
    if [ ! -f .env.local ]; then
        cp .env.example .env.local
        print_warning "Created .env.local from template. Please review and update the configuration."
    fi

    print_status "Environment setup completed ✓"
}

# Create monitoring configurations
create_monitoring_configs() {
    print_header "Creating monitoring configurations..."

    # Create Prometheus configuration
    cat > monitoring/prometheus/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'rag-backend'
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s

  - job_name: 'rag-frontend'
    static_configs:
      - targets: ['host.docker.internal:3000']
    metrics_path: '/api/metrics'
    scrape_interval: 30s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
EOF

    # Create alert rules
    cat > monitoring/prometheus/alert_rules.yml << EOF
groups:
  - name: rag_system_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors per second"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High response time detected"
          description: "95th percentile response time is {{ $value }} seconds"

      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service is down"
          description: "{{ $labels.instance }} has been down for more than 1 minute"
EOF

    # Create Grafana configuration
    cat > monitoring/grafana/grafana.ini << EOF
[server]
root_url = http://localhost:3001
serve_from_sub_path = false

[security]
admin_user = admin
admin_password = admin

[users]
allow_sign_up = false

[database]
type = sqlite3
path = /var/lib/grafana/grafana.db
EOF

    print_status "Monitoring configurations created ✓"
}

# Create Docker Compose file
create_docker_compose() {
    print_header "Creating Docker Compose configuration..."

    cat > monitoring/docker-compose.monitoring.yml << EOF
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:v2.40.0
    container_name: rag-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    networks:
      - monitoring
    restart: unless-stopped

  grafana:
    image: grafana/grafana:9.3.0
    container_name: rag-grafana
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/grafana.ini:/etc/grafana/grafana.ini
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    networks:
      - monitoring
    restart: unless-stopped

  jaeger:
    image: jaegertracing/all-in-one:1.42
    container_name: rag-jaeger
    ports:
      - "16686:16686"
      - "14268:14268"
      - "14250:14250"
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    networks:
      - monitoring
    restart: unless-stopped

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: rag-elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    networks:
      - monitoring
    restart: unless-stopped

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    container_name: rag-kibana
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch
    networks:
      - monitoring
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:v1.5.0
    container_name: rag-node-exporter
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    networks:
      - monitoring
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.46.0
    container_name: rag-cadvisor
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    privileged: true
    devices:
      - /dev/kmsg
    networks:
      - monitoring
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:v0.25.0
    container_name: rag-alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager:/etc/alertmanager
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    networks:
      - monitoring
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
  elasticsearch_data:
  alertmanager_data:

networks:
  monitoring:
    driver: bridge
EOF

    # Create AlertManager configuration
    mkdir -p monitoring/alertmanager
    cat > monitoring/alertmanager/alertmanager.yml << EOF
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@rag.company.com'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
  - name: 'web.hook'
    webhook_configs:
      - url: 'http://127.0.0.1:5001/'
EOF

    print_status "Docker Compose configuration created ✓"
}

# Start monitoring stack
start_monitoring() {
    print_header "Starting monitoring stack..."

    cd monitoring

    # Start the monitoring services
    docker-compose -f docker-compose.monitoring.yml up -d

    cd ..

    print_status "Monitoring stack started ✓"
}

# Wait for services to be ready
wait_for_services() {
    print_header "Waiting for services to be ready..."

    local services=("prometheus:9090" "grafana:3000" "jaeger:16686" "elasticsearch:9200" "kibana:5601")

    for service in "${services[@]}"; do
        local name=$(echo $service | cut -d: -f1)
        local port=$(echo $service | cut -d: -f2)
        local host="localhost"

        print_status "Waiting for $name to be ready..."

        local timeout=60
        local count=0

        while ! curl -f http://$host:$port &>/dev/null; do
            if [ $count -ge $timeout ]; then
                print_error "$name failed to start within $timeout seconds"
                return 1
            fi

            sleep 2
            count=$((count + 2))
            echo -n "."
        done

        echo ""
        print_status "$name is ready ✓"
    done
}

# Configure Grafana
configure_grafana() {
    print_header "Configuring Grafana..."

    # Wait for Grafana to be fully ready
    sleep 10

    # Add Prometheus datasource
    curl -X POST \
        -H "Content-Type: application/json" \
        -d '{
            "name": "Prometheus",
            "type": "prometheus",
            "url": "http://prometheus:9090",
            "access": "proxy",
            "isDefault": true
        }' \
        http://admin:admin@localhost:3001/api/datasources || print_warning "Could not add Prometheus datasource automatically"

    print_status "Grafana configuration completed ✓"
}

# Display access information
display_access_info() {
    print_header "Monitoring Stack Access Information"
    echo ""
    echo -e "${GREEN}🔗 Monitoring Services:${NC}"
    echo "  • Grafana Dashboards:     http://localhost:3001 (admin/admin)"
    echo "  • Prometheus:            http://localhost:9090"
    echo "  • Jaeger Tracing:        http://localhost:16686"
    echo "  • Kibana Logs:           http://localhost:5601"
    echo "  • AlertManager:          http://localhost:9093"
    echo "  • Node Exporter:         http://localhost:9100/metrics"
    echo "  • cAdvisor:              http://localhost:8080"
    echo ""
    echo -e "${GREEN}📊 Quick Commands:${NC}"
    echo "  • View logs:             docker-compose -f monitoring/docker-compose.monitoring.yml logs -f [service]"
    echo "  • Stop monitoring:       docker-compose -f monitoring/docker-compose.monitoring.yml down"
    echo "  • Restart service:       docker-compose -f monitoring/docker-compose.monitoring.yml restart [service]"
    echo ""
    echo -e "${GREEN}📚 Next Steps:${NC}"
    echo "  1. Start your RAG backend: cd backend && uvicorn src.main:app --host 0.0.0.0 --port 8000"
    echo "  2. Start your RAG frontend: cd frontend && npm run dev"
    echo "  3. Access Grafana to view dashboards"
    echo "  4. Check documentation: docs/RUN_MONITORING.md"
    echo ""
}

# Main execution
main() {
    echo "🎯 RAG System Monitoring Setup"
    echo "================================="
    echo ""

    check_prerequisites
    setup_environment
    create_monitoring_configs
    create_docker_compose
    start_monitoring
    wait_for_services
    configure_grafana
    display_access_info

    echo -e "${GREEN}✅ Monitoring setup completed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}💡 Tip: Start your RAG application services to see metrics in the dashboards.${NC}"
}

# Handle script interruption
trap 'print_warning "Setup interrupted. Run the script again to continue."; exit 1' INT

# Run main function
main "$@"