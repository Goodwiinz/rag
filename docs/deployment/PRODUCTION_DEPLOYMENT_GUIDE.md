# Production Deployment Guide

## Multimodal Enterprise RAG System

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

This guide provides step-by-step instructions for deploying the **Multimodal Enterprise RAG System** to a production environment using modern cloud-native technologies. The system is built with Next.js 15 and supports multimodal document processing, knowledge graph management, and AI-powered search capabilities.

### Architecture Components

- **Frontend**: Next.js 15 application (deployed on **Vercel** at `goodwiinz.tech`)
- **Backend Services**: FastAPI Python application with multi-agent orchestration
- **Knowledge Graph**: Neo4j for entity and relationship management
- **Cache**: **DO Managed Redis** (external; in-cluster Redis subchart disabled in production)
- **Database**: **Supabase managed PostgreSQL** (`SUPABASE_DB_URL`) — not self-hosted
- **Processing**: Celery workers for background document processing
- **Monitoring**: Prometheus, Grafana, Loki, and application-specific metrics
- **Infrastructure**: **DOKS** (`rag-cluster`, `do-nyc3-rag-system-cluster`, nyc3); Helm chart at `infrastructure/helm/knowledge-graph-analytics`; GitOps via **ArgoCD**
- **Object Storage**: **DO Spaces** `rag-system-storage` nyc3 (`STORAGE_BACKEND=s3`) — not AWS S3/MinIO
- **Secrets**: **Infisical** operator (`nous-platform-pl-3-o`)
- **Auth**: **Supabase** hosted GoTrue — no backend login/register endpoints
- **Registry**: `registry.digitalocean.com/ragsystemregistry`

> **Note on Qdrant**: Qdrant is **disabled in production** (`qdrant.enabled: false` in `values-production.yaml`). Do not deploy it as a required service.
>
> **Note on Terraform**: `infrastructure/terraform/` targets AWS (`us-west-2`) and is **not the live infrastructure**. It is not used for production deployments.
>
> **Live deploy path**: `gitops-image-update.yml` commits an image SHA which **ArgoCD** then syncs to the cluster (dev/staging auto-sync from `develop`; prod requires manual sync). Running `helm upgrade` manually (e.g. via `deploy.yml`) is **not** the authoritative deploy path.

---

## Prerequisites

### Required Tools

| Tool    | Version  | Installation                                                              |
| ------- | -------- | ------------------------------------------------------------------------- |
| doctl   | >= 1.100 | [Download](https://docs.digitalocean.com/reference/doctl/how-to/install/) |
| kubectl | >= 1.28  | [Download](https://kubernetes.io/docs/tasks/tools/)                       |
| helm    | >= 3.10  | [Download](https://helm.sh/docs/intro/install/)                           |
| Docker  | >= 24.0  | [Download](https://docs.docker.com/get-docker/)                           |
| Python  | >= 3.11  | [Download](https://www.python.org/downloads/)                             |
| Node.js | >= 18.17 | [Download](https://nodejs.org/)                                           |
| npm     | >= 9.6.7 | Included with Node.js                                                     |

> **Note**: AWS CLI and Terraform are **not required** for production operations. The live infrastructure runs on DOKS (DigitalOcean Kubernetes), managed via Helm + ArgoCD. `infrastructure/terraform/` targets AWS and is not used.

### DigitalOcean Permissions

Ensure your DigitalOcean account / API token has access to:

- DOKS cluster `rag-cluster` (`do-nyc3-rag-system-cluster`, nyc3)
- Container Registry `registry.digitalocean.com/ragsystemregistry`
- Managed Redis (external cluster)
- DO Spaces bucket `rag-system-storage` (nyc3)
- ArgoCD (GitOps controller managing prod sync)

### Environment Setup

```bash
# Clone the repository
git clone https://github.com/your-org/multimodal-rag-system.git
cd multimodal-rag-system

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
cd frontend
npm install
cd ..

# Authenticate with DigitalOcean
doctl auth init

# Configure kubectl for DOKS
doctl kubernetes cluster kubeconfig save rag-cluster

# Set environment variables
export NAMESPACE=knowledge-graph-analytics

# Build and test locally
docker-compose build
docker-compose up -d
npm run test
```

---

## Infrastructure Setup

> **IMPORTANT**: The live production infrastructure runs on **DigitalOcean Kubernetes Service (DOKS)**, not AWS. The `infrastructure/terraform/` directory targets AWS (`us-west-2`) and is **not used** for production. Do not run Terraform against production.

### 1. Configure kubectl for DOKS

```bash
# Authenticate with DigitalOcean
doctl auth init

# Fetch kubeconfig for the production DOKS cluster
doctl kubernetes cluster kubeconfig save rag-cluster
# Cluster: do-nyc3-rag-system-cluster (nyc3)

# Verify cluster access
kubectl get nodes
kubectl get pods --all-namespaces
```

### 2. Confirm Managed Services

Production uses the following **externally managed** services — do not deploy in-cluster replacements:

| Service        | Provider                                    | Config key           |
| -------------- | ------------------------------------------- | -------------------- |
| PostgreSQL     | Supabase managed                            | `SUPABASE_DB_URL`    |
| Redis          | DO Managed Redis (external)                 | `REDIS_URL`          |
| Object storage | DO Spaces `rag-system-storage` nyc3         | `STORAGE_BACKEND=s3` |
| Auth           | Supabase hosted GoTrue                      | `SUPABASE_*`         |
| Secrets        | Infisical operator (`nous-platform-pl-3-o`) | —                    |

### 3. Container Registry

```bash
# Authenticate Docker with DO Container Registry
doctl registry login

# Registry: registry.digitalocean.com/ragsystemregistry
# Images are pushed by CI (gitops-image-update.yml) and synced by ArgoCD
```

### 4. DO Spaces (Object Storage)

Object storage uses **DO Spaces**, not AWS S3. The bucket `rag-system-storage` (nyc3) is pre-provisioned.
Configure the backend with S3-compatible credentials pointing to the DO Spaces endpoint:

```bash
export STORAGE_BACKEND=s3
export AWS_ACCESS_KEY_ID=<do-spaces-key>
export AWS_SECRET_ACCESS_KEY=<do-spaces-secret>
export AWS_ENDPOINT_URL=https://nyc3.digitaloceanspaces.com
export AWS_S3_BUCKET=rag-system-storage
```

---

## Application Deployment

### 1. Setup Secrets

Secrets are managed by the **Infisical** operator (`nous-platform-pl-3-o`). Ensure the Infisical operator is installed and the `InfisicalSecret` CRDs are applied to the cluster. Do not use AWS Secrets Manager.

```bash
# Verify Infisical operator is running
kubectl get pods -n infisical-operator-system

# Check InfisicalSecret resources are syncing
kubectl get infisicalsecrets -n knowledge-graph-analytics
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

> **Live deploy path**: CI pushes a new image SHA to the `gitops-image-update.yml` workflow, which commits the tag to the GitOps repo. **ArgoCD** then syncs the change to the cluster (dev/staging auto-sync; prod requires manual ArgoCD sync). Direct `helm upgrade` runs are for emergency/manual overrides only.
>
> The Helm chart is `infrastructure/helm/knowledge-graph-analytics`. The frontend is deployed on **Vercel** (`goodwiinz.tech`) — it is not an in-cluster workload.

```bash
# Build and push backend image to DO registry
doctl registry login
docker build -t registry.digitalocean.com/ragsystemregistry/backend:<sha> ./backend
docker push registry.digitalocean.com/ragsystemregistry/backend:<sha>

# Emergency/manual Helm upgrade (prod — use only when ArgoCD sync is not viable)
helm upgrade --install knowledge-graph-analytics \
    ./infrastructure/helm/knowledge-graph-analytics \
    --namespace knowledge-graph-analytics \
    --set backend.image.repository=registry.digitalocean.com/ragsystemregistry/backend \
    --set backend.image.tag=<sha>

# Verify deployment
kubectl get pods -n knowledge-graph-analytics
kubectl get services -n knowledge-graph-analytics
kubectl get deployments -n knowledge-graph-analytics

# Check pod logs
kubectl logs -n knowledge-graph-analytics -l app=knowledge-graph-analytics-backend
```

### 3.1 Deploy Additional In-Cluster Services

```bash
# Deploy Neo4j (in-cluster)
helm repo add neo4j https://helm.neo4j.com/neo4j
helm install neo4j neo4j/neo4j-enterprise \
    --namespace knowledge-graph-analytics \
    --set neo4j.password=$(openssl rand -base64 32) \
    --set acceptLicenseAgreement=yes

# NOTE: Qdrant is DISABLED in production (qdrant.enabled: false in values-production.yaml).
# Do NOT deploy Qdrant as a required service.

# NOTE: Redis uses DO Managed Redis (external). Do NOT deploy an in-cluster Redis subchart.
# Set REDIS_URL to point at the DO Managed Redis endpoint instead.
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

# Test backend health
curl -I https://api.rag.yourdomain.com/health

# Frontend is on Vercel — verify at https://goodwiinz.tech

# Check Neo4j connectivity
kubectl exec -n knowledge-graph-analytics deployment/neo4j -- cypher-shell -u neo4j -p $NEO4J_PASSWORD "RETURN 1"

# NOTE: Qdrant is disabled in production — skip Qdrant health check
# NOTE: Redis is DO Managed (external) — verify via Redis URL, not in-cluster pod

# Test file upload functionality
curl -X POST https://api.rag.yourdomain.com/api/upload \
    -H "Authorization: Bearer <token>" \
    -F "file=@test-document.pdf"

# Verify search functionality
curl -X POST https://api.rag.yourdomain.com/api/search \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer <token>" \
    -d '{"query": "test search"}'
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
- **Database Performance**: PostgreSQL (Supabase), DO Managed Redis, Neo4j metrics

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

#### Managed Service Backups

- **PostgreSQL**: Handled by Supabase (managed backups — consult Supabase dashboard for retention policy)
- **Redis**: Handled by DO Managed Redis (consult DigitalOcean dashboard for backup settings)
- **Object storage**: DO Spaces `rag-system-storage` (nyc3) — enable versioning via DO console if required
- **DOKS workloads**: Daily Velero backups with 30-day retention

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

The standard update path is via GitOps: push an image SHA via `gitops-image-update.yml` and let ArgoCD sync.
For emergency manual upgrades use `--set` flags only (do not pass `--values values-production.yaml` — it is applied by ArgoCD from the chart defaults):

```bash
# Emergency manual upgrade (prefer ArgoCD sync in normal operations)
helm upgrade knowledge-graph-analytics ./infrastructure/helm/knowledge-graph-analytics \
    --namespace knowledge-graph-analytics \
    --set backend.image.tag=v1.1.0

# Monitor rollout status
kubectl rollout status deployment/knowledge-graph-analytics-backend -n knowledge-graph-analytics
```

#### Infrastructure Updates

Infrastructure is managed via DOKS/Helm/ArgoCD — not Terraform. To make cluster-level changes:

- Update Helm chart values in `infrastructure/helm/knowledge-graph-analytics/`
- Commit to the GitOps repo; ArgoCD will apply on next sync (or trigger manually via the ArgoCD UI)

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
