# Kubernetes Deployment Configuration

This directory contains Kubernetes manifests and Helm charts for the Multimodal Enterprise RAG System deployment.

## Directory Structure

```
k8s/
├── base/                    # Base Kubernetes manifests
│   ├── backend/            # Backend service configuration
│   ├── frontend/           # Frontend service configuration
│   ├── database/           # Database configurations
│   └── monitoring/         # Monitoring stack
├── overlays/               # Environment-specific overlays
│   ├── development/        # Development environment
│   ├── staging/            # Staging environment
│   └── production/         # Production environment
├── charts/                 # Helm charts
│   ├── rag-backend/
│   ├── rag-frontend/
│   ├── rag-database/
│   └── rag-monitoring/
└── scripts/                # Deployment scripts
```

## Quick Start

### Prerequisites

- Kubernetes cluster (v1.23+)
- Helm v3
- kubectl
- Cert-Manager for TLS
- Prometheus Operator

### Installation

1. Install cert-manager:
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.11.0/cert-manager.yaml
```

2. Install Prometheus Operator:
```bash
kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.67.0/bundle.yaml
```

3. Install the stack:
```bash
# Install monitoring stack
helm upgrade --install monitoring ./charts/rag-monitoring/

# Install database
helm upgrade --install database ./charts/rag-database/

# Install backend
helm upgrade --install backend ./charts/rag-backend/

# Install frontend
helm upgrade --install frontend ./charts/rag-frontend/
```

### Environment-Specific Deployment

```bash
# Development
helm upgrade --install dev-frontend ./charts/rag-frontend/ --values ./overlays/development/frontend-values.yaml
helm upgrade --install dev-backend ./charts/rag-backend/ --values ./overlays/development/backend-values.yaml

# Staging
helm upgrade --install staging-frontend ./charts/rag-frontend/ --values ./overlays/staging/frontend-values.yaml
helm upgrade --install staging-backend ./charts/rag-backend/ --values ./overlays/staging/backend-values.yaml

# Production
helm upgrade --install prod-frontend ./charts/rag-frontend/ --values ./overlays/production/frontend-values.yaml
helm upgrade --install prod-backend ./charts/rag-backend/ --values ./overlays/production/backend-values.yaml
```

## Configuration

### Customization

Edit the values.yaml files in each chart directory to customize the deployment:

- `resources`: CPU/memory limits and requests
- `replicaCount`: Number of replicas
- `image`: Container image and tag
- `service`: Service type and ports
- `ingress`: Ingress configuration
- `secrets`: Secret management

### Networking

All services are deployed in the `rag-system` namespace with internal networking configured:

- Frontend: ClusterIP service, Ingress for external access
- Backend: ClusterIP service with load balancing
- Database: Headless service for internal communication
- Monitoring: ClusterIP services with port-forwarding for access

### Storage

Persistent volumes are configured for:

- PostgreSQL data
- Redis data
- Neo4j data
- Qdrant vectors
- Application logs
- Model files

## Monitoring

The monitoring stack includes:

- Prometheus for metrics collection
- Grafana for visualization
- AlertManager for alerting
- Node Exporter for node metrics
- Kubernetes Service Monitor for service discovery

Access Grafana:
```bash
kubectl port-forward svc/rag-grafana 3001:80
```

Access Prometheus:
```bash
kubectl port-forward svc/rag-prometheus 9090:9090
```

## Security

### Network Policies

Network policies are implemented to:
- Restrict access between services
- Allow only necessary ports
- Implement ingress/egress rules

### RBAC

Service accounts and roles are configured for:
- Prometheus service
- Grafana service
- Application services

### TLS/SSL

TLS certificates are managed via cert-manager for:
- Ingress encryption
- Service-to-service communication

## Scaling

### Horizontal Pod Autoscaling

HPA is configured for:
- Frontend: CPU and memory based scaling
- Backend: Request-based scaling
- Workers: Queue-based scaling

### Vertical Scaling

Resource limits can be adjusted in values.yaml for:
- CPU limits and requests
- Memory limits and requests
- Persistent volume sizes

## Backup and Recovery

### Database Backups

PostgreSQL backups are configured with:
- Daily automated backups
- Point-in-time recovery
- Encryption at rest

### Application Data

Application data is backed up via:
- Persistent volume snapshots
- ConfigMap exports
- Secret exports

## Troubleshooting

### Common Issues

1. **Pods not starting**: Check events and logs
```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

2. **Service not accessible**: Check service configuration and network policies
```bash
kubectl get services
kubectl get endpoints
kubectl describe networkpolicy <policy-name>
```

3. **Performance issues**: Check resource limits and HPA
```bash
kubectl top pods
kubectl get hpa
```

### Debug Mode

Enable debug mode for troubleshooting:
```bash
kubectl set env deployment/backend DEBUG=true
kubectl set env deployment/frontend DEBUG=true
```

## Cleanup

To uninstall the complete stack:
```bash
helm uninstall frontend backend database monitoring
kubectl delete namespace rag-system
```

## Maintenance

### Updates

Update deployments using Helm:
```bash
helm dependency update ./charts/rag-backend/
helm upgrade --install backend ./charts/rag-backend/
```

### Rolling Updates

Update deployments with rolling updates:
```bash
kubectl set image deployment/backend backend=my-new-image:tag
```

### Health Checks

Health checks are configured for all services:
- Liveness probes
- Readiness probes
- Startup probes

## Support

For issues and questions:
- Check the troubleshooting section
- Review the logs and metrics
- Contact the DevOps team