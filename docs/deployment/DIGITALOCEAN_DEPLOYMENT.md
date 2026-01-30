# DigitalOcean Deployment Guide

This guide walks you through deploying the RAG System on DigitalOcean Kubernetes Service (DOKS) with Managed Databases.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DigitalOcean Cloud                           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     DOKS Cluster                              │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │                  App Node Pool                           │ │  │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐│ │  │
│  │  │  │ Backend │ │Frontend │ │ Celery  │ │   Monitoring    ││ │  │
│  │  │  │  (x3)   │ │  (x2)   │ │ Workers │ │ Prometheus/Graf ││ │  │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────────────┘│ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │                   DB Node Pool                           │ │  │
│  │  │  ┌─────────────────────┐ ┌─────────────────────┐        │ │  │
│  │  │  │    Neo4j (Graph)    │ │   Qdrant (Vector)   │        │ │  │
│  │  │  └─────────────────────┘ └─────────────────────┘        │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   DO Managed Databases                        │  │
│  │  ┌─────────────────────┐ ┌─────────────────────┐             │  │
│  │  │ PostgreSQL (HA)     │ │    Redis (HA)       │             │  │
│  │  │ Primary + Standby   │ │ Primary + Standby   │             │  │
│  │  └─────────────────────┘ └─────────────────────┘             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     DO Spaces (S3)                            │  │
│  │  ┌─────────────────────┐ ┌─────────────────────┐             │  │
│  │  │   Uploads Bucket    │ │   Backups Bucket    │             │  │
│  │  └─────────────────────┘ └─────────────────────┘             │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────┐  ┌─────────────────────────────────┐    │
│  │ Container Registry   │  │  Load Balancer + Reserved IP    │    │
│  └──────────────────────┘  └─────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. DigitalOcean Account Setup

1. Create a DigitalOcean account at [cloud.digitalocean.com](https://cloud.digitalocean.com)
2. Generate API tokens:
   - Go to **API** → **Tokens/Keys**
   - Create a new **Personal Access Token** with read/write scope
   - Create **Spaces Access Keys** for object storage

### 2. Install Required Tools

```bash
# Install doctl (DigitalOcean CLI)
# macOS
brew install doctl

# Linux
snap install doctl

# Windows
scoop install doctl

# Authenticate doctl
doctl auth init

# Install Terraform
brew install terraform  # or appropriate method for your OS

# Install kubectl
brew install kubectl

# Install Helm
brew install helm
```

### 3. Configure doctl

```bash
# Authenticate with your API token
doctl auth init

# Verify authentication
doctl account get
```

## Deployment Steps

### Step 1: Configure Terraform Variables

```bash
cd infrastructure/digitalocean/terraform

# Copy example configuration
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

**Required variables to set:**

| Variable | Description | Where to get it |
|----------|-------------|-----------------|
| `do_token` | DigitalOcean API token | API → Tokens |
| `spaces_access_key_id` | Spaces access key | API → Spaces Keys |
| `spaces_secret_access_key` | Spaces secret key | API → Spaces Keys |
| `domain_name` | Your domain | Your DNS provider |
| `letsencrypt_email` | SSL certificate email | Your email |
| `grafana_password` | Monitoring password | Choose secure password |

### Step 2: Initialize and Apply Terraform

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply infrastructure
terraform apply
```

This creates:
- DOKS Kubernetes cluster with 2 node pools
- Managed PostgreSQL database (HA)
- Managed Redis database (HA)
- Spaces buckets for uploads and backups
- Container Registry
- VPC and networking
- Load Balancer with Reserved IP

**Expected time:** 15-20 minutes

### Step 3: Configure kubectl

```bash
# Get kubeconfig (output from Terraform)
doctl kubernetes cluster kubeconfig save rag-system-cluster

# Verify connection
kubectl get nodes
kubectl get pods -A
```

### Step 4: Build and Push Docker Images

```bash
# Log in to DO Container Registry
doctl registry login

# Get registry name
REGISTRY=$(terraform output -raw registry_endpoint)

# Build and push backend
cd backend
docker build -t $REGISTRY/backend:latest -f docker/Dockerfile .
docker push $REGISTRY/backend:latest

# Build and push frontend
cd ../frontend
docker build -t $REGISTRY/frontend:latest -f Dockerfile .
docker push $REGISTRY/frontend:latest
```

### Step 5: Create Application Secrets

```bash
# Create namespace
kubectl create namespace rag-system

# Create application secrets
kubectl create secret generic app-secrets \
  --namespace=rag-system \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=JWT_SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=OPENAI_API_KEY="your-openai-key" \
  --from-literal=ANTHROPIC_API_KEY="your-anthropic-key"
```

### Step 6: Deploy with Helm

```bash
# Update Helm values with your domain
nano infrastructure/digitalocean/helm/values-digitalocean.yaml

# Deploy the application
helm upgrade --install rag-system ./deployment/helm/rag-system \
  --namespace rag-system \
  --values ./infrastructure/digitalocean/helm/values-digitalocean.yaml \
  --wait \
  --timeout 15m

# Verify deployment
kubectl get pods -n rag-system
kubectl get svc -n rag-system
kubectl get ingress -n rag-system
```

### Step 7: Configure DNS

Point your domain to the Load Balancer IP:

```bash
# Get Load Balancer IP
kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

Add these DNS records:

| Type | Name | Value |
|------|------|-------|
| A | api | `<LOAD_BALANCER_IP>` |
| A | app | `<LOAD_BALANCER_IP>` |
| A | grafana | `<LOAD_BALANCER_IP>` |

### Step 8: Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n rag-system

# Check services
kubectl get svc -n rag-system

# Check ingress and SSL
kubectl get ingress -n rag-system
kubectl get certificates -n rag-system

# Test API health
curl https://api.yourdomain.com/health

# Test frontend
curl https://app.yourdomain.com
```

## GitHub Actions CI/CD Setup

### 1. Add Repository Secrets

Go to your repository → Settings → Secrets and variables → Actions

Add these secrets:

| Secret | Description |
|--------|-------------|
| `DIGITALOCEAN_ACCESS_TOKEN` | DO API token |
| `SECRET_KEY` | Application secret key |
| `SECRET_KEY_PROD` | Production secret key |
| `JWT_SECRET_KEY` | JWT signing key |
| `JWT_SECRET_KEY_PROD` | Production JWT key |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `PRODUCTION_DOMAIN` | Your production domain |
| `POSTGRES_CLUSTER_ID` | DO PostgreSQL cluster ID |

### 2. Create GitHub Environments

Create two environments:
- `staging` - for develop branch deployments
- `production` - for main branch deployments (add required reviewers)

### 3. Push to Deploy

```bash
# Deploy to staging
git push origin develop

# Deploy to production
git push origin main
```

## Cost Breakdown

### Production Setup (High Availability)

| Resource | Configuration | Monthly Cost |
|----------|---------------|--------------|
| DOKS Control Plane | Free | $0 |
| App Node Pool | 2x s-4vcpu-8gb | ~$96 |
| DB Node Pool | 2x s-4vcpu-8gb | ~$96 |
| Managed PostgreSQL | 2 nodes, db-s-2vcpu-4gb | ~$120 |
| Managed Redis | 2 nodes, db-s-1vcpu-2gb | ~$60 |
| Spaces (estimate) | ~50GB + transfers | ~$10 |
| Container Registry | Basic tier | ~$5 |
| Load Balancer | Standard | ~$12 |
| Reserved IP | 1 IP | ~$4 |
| **Total** | | **~$403/month** |

### Development/Staging Setup (Cost-Optimized)

| Resource | Configuration | Monthly Cost |
|----------|---------------|--------------|
| DOKS Control Plane | Free | $0 |
| App Node Pool | 1x s-2vcpu-4gb | ~$24 |
| DB Node Pool | 1x s-2vcpu-4gb | ~$24 |
| Managed PostgreSQL | 1 node, db-s-1vcpu-2gb | ~$30 |
| Managed Redis | 1 node, db-s-1vcpu-1gb | ~$15 |
| Spaces (estimate) | ~10GB | ~$5 |
| Container Registry | Starter (free) | $0 |
| Load Balancer | Standard | ~$12 |
| Reserved IP | 1 IP | ~$4 |
| **Total** | | **~$114/month** |

## Monitoring & Maintenance

### Access Grafana Dashboard

```bash
# Get Grafana URL
echo "https://grafana.$(terraform output -raw domain_name)"

# Default credentials
# Username: admin
# Password: (from your terraform.tfvars)
```

### View Logs

```bash
# Backend logs
kubectl logs -f deployment/rag-backend -n rag-system

# Frontend logs
kubectl logs -f deployment/rag-frontend -n rag-system

# Celery worker logs
kubectl logs -f deployment/rag-celery-worker -n rag-system
```

### Scale Deployments

```bash
# Scale backend
kubectl scale deployment/rag-backend --replicas=5 -n rag-system

# Check HPA status
kubectl get hpa -n rag-system
```

### Database Access

```bash
# Get PostgreSQL connection string
terraform output postgres_connection_string

# Connect to PostgreSQL
doctl databases connection <cluster-id> --format Host,Port,User,Database

# Get Redis connection
terraform output redis_connection_string
```

## Backup & Recovery

### Database Backups

DigitalOcean Managed Databases automatically include:
- Daily automatic backups
- Point-in-time recovery
- 7-day backup retention

To restore:
1. Go to DO Console → Databases → Your cluster
2. Click "Restore from Backup"
3. Select the backup point

### Manual Backup to Spaces

```bash
# Backup PostgreSQL to Spaces
kubectl exec -n rag-system deployment/rag-backend -- \
  pg_dump -Fc $DATABASE_URL > backup.dump

# Upload to Spaces
doctl spaces put backup.dump spaces://rag-system-backups/db/$(date +%Y%m%d).dump
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n rag-system

# Check events
kubectl get events -n rag-system --sort-by='.lastTimestamp'
```

### Database Connection Issues

```bash
# Verify database firewall allows DOKS
doctl databases firewalls list <cluster-id>

# Test connection from a pod
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
  psql "postgresql://user:pass@host:port/db?sslmode=require"
```

### SSL Certificate Issues

```bash
# Check cert-manager logs
kubectl logs -f deployment/cert-manager -n cert-manager

# Check certificate status
kubectl describe certificate -n rag-system

# Force certificate renewal
kubectl delete secret rag-api-tls -n rag-system
```

### Load Balancer Not Getting IP

```bash
# Check Load Balancer status
doctl compute load-balancer list

# Check ingress controller logs
kubectl logs -f deployment/ingress-nginx-controller -n ingress-nginx
```

## Cleanup

To destroy all resources:

```bash
# Delete Helm release
helm uninstall rag-system -n rag-system

# Delete namespaces
kubectl delete namespace rag-system
kubectl delete namespace ingress-nginx
kubectl delete namespace monitoring

# Destroy Terraform resources
cd infrastructure/digitalocean/terraform
terraform destroy
```

**Warning:** This will delete all data including databases. Make sure to backup first!

## Security Checklist

- [ ] API tokens stored in GitHub Secrets
- [ ] Database passwords are strong and unique
- [ ] SSL/TLS enabled for all endpoints
- [ ] Database firewalls configured
- [ ] Network policies enabled
- [ ] Secrets encrypted at rest
- [ ] Regular backup verification
- [ ] Monitoring alerts configured
- [ ] Access logs enabled
