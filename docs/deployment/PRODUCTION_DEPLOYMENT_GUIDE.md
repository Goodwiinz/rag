# Production Deployment Guide
## Knowledge Graph Analytics Dashboard

### Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Infrastructure Setup](#infrastructure-setup)
4. [Application Deployment](#application-deployment)
5. [Monitoring and Observability](#monitoring-and-observability)
6. [Backup and Disaster Recovery](#backup-and-disaster-recovery)
7. [Troubleshooting](#troubleshooting)
8. [Maintenance Procedures](#maintenance-procedures)

---

## Overview

This guide provides step-by-step instructions for deploying the Knowledge Graph Analytics Dashboard to a production environment using AWS EKS, Terraform, and Helm.

### Architecture Components

- **Frontend**: Next.js application served via Nginx
- **Backend**: FastAPI Python application with WebSocket support
- **Database**: PostgreSQL for relational data
- **Cache**: Redis for caching and session management
- **Graph Database**: Neo4j for knowledge graph storage
- **Vector Database**: Qdrant for semantic search
- **Monitoring**: Prometheus, Grafana, Loki, and Promtail
- **Infrastructure**: AWS EKS, RDS, ElastiCache, S3

---

## Prerequisites

### Required Tools

| Tool | Version | Installation |
|------|---------|---------------|
| AWS CLI | >= 2.0 | `pip install awscli` |
| Terraform | >= 1.5.0 | [Download](https://www.terraform.io/downloads.html) |
| kubectl | >= 1.28 | [Download](https://kubernetes.io/docs/tasks/tools/) |
| helm | >= 3.10 | [Download](https://helm.sh/docs/intro/install/) |
| Docker | >= 24.0 | [Download](https://docs.docker.com/get-docker/) |
| Python | >= 3.11 | [Download](https://www.python.org/downloads/) |
| Node.js | >= 18.0 | [Download](https://nodejs.org/) |

### AWS Permissions

Ensure your AWS account has the following permissions:
- EKS cluster management
- RDS instance management
- ElastiCache management
- S3 bucket operations
- IAM role and policy management
- CloudWatch and CloudWatch Logs
- Route 53 (for DNS management)

### Environment Setup

```bash
# Clone the repository
git clone https://github.com/your-org/knowledge-graph-analytics.git
cd knowledge-graph-analytics

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
cd frontend && npm install && cd ..

# Configure AWS CLI
aws configure

# Set environment variables
export AWS_REGION=us-west-2
export TF_VAR_aws_region=us-west-2
export TF_VAR_environment=production
export NAMESPACE=knowledge-graph-analytics
```

---

## Infrastructure Setup

### 1. Create Terraform State Backend

```bash
# Create S3 bucket for Terraform state
aws s3api create-bucket \
    --bucket knowledge-graph-analytics-terraform-state \
    --region us-west-2

# Create DynamoDB table for state locking
aws dynamodb create-table \
    --table-name knowledge-graph-analytics-terraform-locks \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
    --region us-west-2
```

### 2. Deploy Infrastructure with Terraform

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Review the execution plan
terraform plan

# Apply the configuration
terraform apply

# Save the outputs for later use
terraform output -json > ../terraform-outputs.json
```

### 3. Configure kubectl

```bash
# Update kubeconfig with EKS cluster details
aws eks update-kubeconfig --name knowledge-graph-analytics-cluster --region us-west-2

# Verify cluster access
kubectl get nodes
```

---

## Application Deployment

### 1. Setup Secrets

```bash
# Generate secrets
cd ../../scripts
./setup-secrets.sh generate

# Edit the generated seed file
nano seed-secrets.env

# Apply secrets to Kubernetes
./setup-secrets.sh setup

# Optionally setup AWS Secrets Manager
./setup-secrets.sh aws-secrets
```

### 2. Deploy Monitoring Stack

```bash
cd ../infrastructure/helm/monitoring-stack

# Add Helm repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Deploy monitoring stack
helm install monitoring-stack . \
    --namespace monitoring \
    --create-namespace \
    --values values.yaml
```

### 3. Deploy Application

```bash
cd ../knowledge-graph-analytics

# Deploy the application
helm upgrade --install knowledge-graph-analytics . \
    --namespace knowledge-graph-analytics \
    --create-namespace \
    --values values-prod.yaml \
    --wait

# Verify deployment
kubectl get pods -n knowledge-graph-analytics
kubectl get services -n knowledge-graph-analytics
```

### 4. Configure Ingress and SSL

```bash
# Install cert-manager for SSL certificates
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Wait for cert-manager to be ready
kubectl wait --for=condition=available deployment/cert-manager -n cert-manager --timeout=300s

# Create ClusterIssuer for Let's Encrypt
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: devops@yourcompany.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

### 5. Verify Deployment

```bash
# Check pod status
kubectl get pods -n knowledge-graph-analytics

# Check services
kubectl get services -n knowledge-graph-analytics

# Check ingress
kubectl get ingress -n knowledge-graph-analytics

# Test application endpoints
curl -I https://analytics.yourdomain.com
curl -I https://api.yourdomain.com/health
```

---

## Monitoring and Observability

### 1. Access Grafana Dashboard

```bash
# Get Grafana admin password
kubectl get secret monitoring-credentials -n monitoring -o jsonpath='{.data.grafana-admin-password}' | base64 -d

# Port forward to access Grafana locally
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:3000

# Open http://localhost:3000 in your browser
# Login with admin user and the password retrieved above
```

### 2. Key Dashboards

- **System Overview**: General cluster health and resource usage
- **Application Performance**: Application-specific metrics and performance
- **Business Metrics**: Business KPIs and user engagement metrics
- **Database Performance**: PostgreSQL, Redis, Neo4j, and Qdrant metrics

### 3. Alert Configuration

Critical alerts are configured for:
- Pod failures and restarts
- High CPU/memory usage
- Database connection issues
- Application error rates
- Disk space shortages

Monitor alerts via:
- Email: devops@yourcompany.com
- Slack: #alerts-critical channel

### 4. Log Aggregation

- **Loki**: Centralized log storage
- **Promtail**: Log collection from pods
- **Grafana**: Log visualization and querying

Access logs through Grafana Explore or query directly:
```bash
# Port forward Loki
kubectl port-forward -n monitoring svc/monitoring-loki 3100:3100

# Query logs
curl -G -s "http://localhost:3100/loki/api/v1/query_range" \
    --data-urlencode 'query="{app=\"knowledge-graph-backend\"}"' \
    --data-urlencode 'start=2023-12-01T00:00:00Z' \
    --data-urlencode 'end=2023-12-01T23:59:59Z'
```

---

## Backup and Disaster Recovery

### 1. Automated Backups

The system implements multiple backup strategies:

#### AWS Backup Service
- **RDS**: Daily snapshots with 30-day retention
- **EKS**: Daily Velero backups with 30-day retention
- **Cross-region replication**: Backups replicated to us-east-1

#### Application-Level Backups
```bash
# Run manual backup
cd scripts
./backup-and-restore.sh backup

# List available backups
./backup-and-restore.sh list

# Restore from backup
./backup-and-restore.sh restore 20231201_120000
```

### 2. Disaster Recovery Procedures

#### Scenario 1: Single Pod Failure
```bash
# Check pod status
kubectl get pods -n knowledge-graph-analytics

# Restart failed pod
kubectl delete pod <pod-name> -n knowledge-graph-analytics

# Monitor recovery
kubectl get pods -w -n knowledge-graph-analytics
```

#### Scenario 2: Database Issues
```bash
# Check database status
kubectl exec -n knowledge-graph-analytics deployment/postgres -- pg_isready

# View database logs
kubectl logs -n knowledge-graph-analytics deployment/postgres

# Restart database
kubectl rollout restart deployment/postgres -n knowledge-graph-analytics
```

#### Scenario 3: Full Cluster Recovery
```bash
# Restore from Velero backup
velero restore create --from-backup <backup-name> --namespace knowledge-graph-analytics

# Restore application data
./backup-and-restore.sh restore <backup-id>

# Verify application functionality
kubectl get pods -n knowledge-graph-analytics
```

### 3. Backup Testing

Regularly test backup integrity:
```bash
# Create test restore environment
kubectl create namespace backup-test

# Restore database to test environment
# (implementation depends on your specific setup)

# Verify data integrity
# (implementation depends on your specific setup)

# Clean up test environment
kubectl delete namespace backup-test
```

---

## Troubleshooting

### Common Issues

#### 1. Pod Not Starting
```bash
# Check pod status and events
kubectl describe pod <pod-name> -n knowledge-graph-analytics

# Check logs
kubectl logs <pod-name> -n knowledge-graph-analytics

# Common causes:
# - Resource constraints
# - Image pull issues
# - Configuration errors
# - Secret/ConfigMap missing
```

#### 2. Service Not Accessible
```bash
# Check service endpoints
kubectl get endpoints -n knowledge-graph-analytics

# Check service configuration
kubectl describe service <service-name> -n knowledge-graph-analytics

# Check network policies
kubectl get networkpolicies -n knowledge-graph-analytics
```

#### 3. Database Connection Issues
```bash
# Test database connectivity
kubectl exec -n knowledge-graph-analytics deployment/backend -- python -c "
import psycopg2
try:
    conn = psycopg2.connect('postgresql://raguser:password@postgres:5432/ragdb')
    print('Database connection successful')
    conn.close()
except Exception as e:
    print(f'Database connection failed: {e}')
"

# Check database logs
kubectl logs -n knowledge-graph-analytics deployment/postgres
```

#### 4. High Resource Usage
```bash
# Check resource usage
kubectl top pods -n knowledge-graph-analytics
kubectl top nodes

# Identify resource-heavy pods
kubectl exec -n knowledge-graph-analytics <pod-name> -- top

# Scale resources if needed
kubectl patch deployment <deployment-name> -n knowledge-graph-analytics -p '{"spec":{"template":{"spec":{"containers":[{"name":"<container-name>","resources":{"limits":{"memory":"4Gi"}}}]}}}}'
```

### Performance Issues

#### 1. Slow Database Queries
```bash
# Check active queries
kubectl exec -n knowledge-graph-analytics deployment/postgres -- psql -U raguser -d ragdb -c "
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;"

# Check database locks
kubectl exec -n knowledge-graph-analytics deployment/postgres -- psql -U raguser -d ragdb -c "
SELECT blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement,
       blocking_activity.query AS current_statement_in_blocking_process
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;"
```

#### 2. High Memory Usage
```bash
# Check memory usage by pod
kubectl exec -n knowledge-graph-analytics <pod-name> -- cat /sys/fs/cgroup/memory/memory.usage_in_bytes

# Check for memory leaks
kubectl exec -n knowledge-graph-analytics <pod-name> -- ps aux --sort=-%mem

# Restart pod if needed
kubectl delete pod <pod-name> -n knowledge-graph-analytics
```

---

## Maintenance Procedures

### 1. Regular Maintenance Tasks

#### Daily
- Check backup completion
- Review system alerts
- Monitor resource usage
- Check application logs

#### Weekly
- Update dependencies
- Review security patches
- Clean up old logs
- Test backup restoration

#### Monthly
- Perform full system health check
- Review and update documentation
- Conduct security audit
- Plan capacity scaling

### 2. Update Procedures

#### Application Updates
```bash
# Update application version
helm upgrade knowledge-graph-analytics ./infrastructure/helm/knowledge-graph-analytics \
    --namespace knowledge-graph-analytics \
    --values values-prod.yaml \
    --set frontend.image.tag=v1.1.0 \
    --set backend.image.tag=v1.1.0

# Monitor rollout status
kubectl rollout status deployment/knowledge-graph-analytics-frontend -n knowledge-graph-analytics
kubectl rollout status deployment/knowledge-graph-analytics-backend -n knowledge-graph-analytics
```

#### Infrastructure Updates
```bash
cd infrastructure/terraform

# Review changes
terraform plan

# Apply changes during maintenance window
terraform apply
```

### 3. Scaling Procedures

#### Horizontal Scaling
```bash
# Scale application
kubectl scale deployment knowledge-graph-analytics-backend --replicas=5 -n knowledge-graph-analytics

# Enable autoscaling
kubectl autoscale deployment knowledge-graph-analytics-backend \
    --cpu-percent=70 \
    --min=3 \
    --max=10 \
    -n knowledge-graph-analytics
```

#### Vertical Scaling
```bash
# Update resource limits
kubectl patch deployment knowledge-graph-analytics-backend -n knowledge-graph-analytics -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "backend",
          "resources": {
            "limits": {
              "memory": "4Gi",
              "cpu": "2000m"
            }
          }
        }]
      }
    }
  }
}'
```

### 4. Security Maintenance

#### Certificate Rotation
```bash
# Check certificate expiration
kubectl get certificates -n knowledge-graph-analytics

# Force certificate renewal
kubectl delete certificate <cert-name> -n knowledge-graph-analytics
```

#### Secret Rotation
```bash
# Rotate secrets
./scripts/setup-secrets.sh rotate

# Restart applications to use new secrets
kubectl rollout restart deployment/knowledge-graph-analytics-backend -n knowledge-graph-analytics
```

---

## Support and Emergency Contacts

### Emergency Contacts
- **DevOps Team**: devops@yourcompany.com
- **On-call Engineer**: +1-XXX-XXX-XXXX
- **Infrastructure Team**: infrastructure@yourcompany.com

### Documentation
- **Architecture Guide**: [docs/architecture/ARCHITECTURE.md](../architecture/ARCHITECTURE.md)
- **API Documentation**: [docs/api/README.md](../api/README.md)
- **Security Guide**: [docs/security/SECURITY_GUIDE.md](../security/SECURITY_GUIDE.md)

### Monitoring Links
- **Grafana Dashboard**: https://grafana.yourdomain.com
- **Prometheus**: https://prometheus.yourdomain.com
- **Application**: https://analytics.yourdomain.com

---

This deployment guide should be used in conjunction with the architecture documentation and runbooks for complete system management.