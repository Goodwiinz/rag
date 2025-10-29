# Operations Runbook - Multimodal Enterprise RAG System

## 📋 Table of Contents
1. [System Overview](#system-overview)
2. [Daily Operations](#daily-operations)
3. [Monitoring Procedures](#monitoring-procedures)
4. [Incident Response](#incident-response)
5. [Maintenance Procedures](#maintenance-procedures)
6. [Scaling Operations](#scaling-operations)
7. [Backup and Recovery](#backup-and-recovery)
8. [Security Operations](#security-operations)
9. [Troubleshooting Guide](#troubleshooting-guide)
10. [Emergency Procedures](#emergency-procedures)

---

## System Overview

### Application Components
- **Frontend**: Next.js 15 application (TypeScript, Tailwind CSS)
- **Backend**: FastAPI Python services with multi-agent orchestration
- **Knowledge Graph**: Neo4j database for entity relationships
- **Vector Store**: Qdrant for semantic similarity search
- **Cache**: Redis for session and caching
- **Database**: PostgreSQL for structured metadata
- **Processing**: Celery workers for background document processing
- **File Storage**: S3 buckets for documents and models

### Key Metrics to Monitor
- **Frontend Performance**: Core Web Vitals, page load times
- **Backend Performance**: API response times, error rates
- **Database Performance**: Query latency, connection counts
- **Search Performance**: Search response times, result relevance
- **Processing Queue**: Task completion rates, queue depth
- **Resource Usage**: CPU, memory, storage, network

---

## Daily Operations

### Morning Health Checks (9:00 AM)

```bash
# Check cluster status
kubectl get nodes
kubectl get pods -n multimodal-rag-system

# Check application health
curl -f https://rag.yourdomain.com/api/health
curl -f https://api.rag.yourdomain.com/health

# Check database connectivity
kubectl exec -n multimodal-rag-system deployment/neo4j -- cypher-shell -u neo4j -p $NEO4J_PASSWORD "RETURN 1"
kubectl exec -n multimodal-rag-system deployment/qdrant -- curl http://localhost:6333/health
kubectl exec -n multimodal-rag-system deployment/redis -- redis-cli ping

# Check resource usage
kubectl top nodes
kubectl top pods -n multimodal-rag-system

# Review overnight logs
kubectl logs -n multimodal-rag-system --since=24h -l app=multimodal-rag-frontend | grep ERROR
kubectl logs -n multimodal-rag-system --since=24h -l app=multimodal-rag-backend | grep ERROR
```

### Daily Reports (10:00 AM)

```bash
# Generate daily performance report
./scripts/generate-daily-report.sh

# Check backup completion
aws backup list-backup-jobs --by-created-after $(date -d 'yesterday' +%Y-%m-%d)

# Review security alerts
aws guardduty get-findings --detector-id $(aws guardduty list-detectors --query 'DetectorIds[0]' --output text)

# Check SSL certificate expiry
kubectl get certificates -n multimodal-rag-system -o json | jq '.items[] | {name: .metadata.name, expiry: .status.notAfter}'
```

### End-of-Day Checks (5:00 PM)

```bash
# Review system performance
kubectl logs -n multimodal-rag-system --since=12h -l app=multimodal-rag-backend | grep "SLOW_QUERY"

# Check processing queue status
kubectl exec -n multimodal-rag-system deployment/celery-worker -- celery -A tasks inspect active

# Monitor disk usage
df -h
kubectl exec -n multimodal-rag-system deployment/neo4j -- df -h /data
kubectl exec -n multimodal-rag-system deployment/qdrant -- df -h /qdrant/storage
```

---

## Monitoring Procedures

### Real-time Monitoring Dashboard Access

```bash
# Grafana Dashboard
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:3000
# Access: http://localhost:3000

# Prometheus
kubectl port-forward -n monitoring svc/monitoring-prometheus 9090:9090
# Access: http://localhost:9090

# Application Metrics
kubectl port-forward -n multimodal-rag-system svc/multimodal-rag-backend 8000:8000
# Access: http://localhost:8000/metrics
```

### Key Monitoring Dashboards

#### 1. System Overview Dashboard
- **CPU Usage**: Alert if >80% for >5 minutes
- **Memory Usage**: Alert if >85% for >5 minutes
- **Disk Usage**: Alert if >90%
- **Network I/O**: Monitor bandwidth utilization
- **Pod Status**: Track restarts and failures

#### 2. Application Performance Dashboard
- **API Response Time**: P95 <2s, P99 <5s
- **Error Rate**: Alert if >5%
- **Request Rate**: Monitor traffic patterns
- **Active Users**: Track concurrent usage
- **Search Performance**: Response times and result quality

#### 3. Database Performance Dashboard
- **Neo4j Query Performance**: Slow query identification
- **Qdrant Vector Search**: Search latency and throughput
- **Redis Performance**: Hit rate and memory usage
- **PostgreSQL Performance**: Connection count and query times

#### 4. Business Metrics Dashboard
- **Document Processing**: Daily upload and processing volumes
- **Search Analytics**: Query patterns and result relevance
- **User Engagement**: Session duration and feature usage
- **Quality Metrics**: RAG Triad scores and trends

### Alert Configuration

Critical Alerts (Page):
```yaml
groups:
- name: critical-alerts
  rules:
  - alert: ApplicationDown
    expr: up{job="multimodal-rag-backend"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Multimodal RAG System is down"

  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"

  - alert: DatabaseDown
    expr: up{job=~"neo4j|qdrant|redis"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Database service is down"
```

Warning Alerts (Email):
```yaml
- alert: HighMemoryUsage
  expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.85
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High memory usage detected"

- alert: SlowDatabaseQueries
  expr: histogram_quantile(0.95, rate(sql_query_duration_seconds_bucket[5m])) > 2
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Slow database queries detected"
```

---

## Incident Response

### Incident Severity Levels

#### **P0 - Critical** (Page immediately, 15min response)
- Complete system outage
- Data loss or corruption
- Security breach
- Performance degradation affecting all users

#### **P1 - High** (Page within 30min)
- Major feature failure
- Significant performance degradation
- Partial system outage
- High error rates

#### **P2 - Medium** (Email within 2h)
- Minor feature issues
- Moderate performance impact
- Non-critical bugs
- Documentation issues

#### **P3 - Low** (Ticket within 24h)
- Cosmetic issues
- Feature enhancements
- Documentation updates
- Minor optimizations

### Incident Response Workflow

#### 1. Incident Detection
```bash
# Monitor alert channels
# Slack: #incidents-multimodal-rag
# Email: ops-team@yourcompany.com
# PagerDuty: On-call engineer

# Automated monitoring
kubectl get events -n multimodal-rag-system --sort-by='.lastTimestamp' | tail -10
```

#### 2. Initial Assessment (First 15 minutes)
```bash
# Verify scope of impact
curl -I https://rag.yourdomain.com
curl -I https://api.rag.yourdomain.com/health

# Check system status
kubectl get pods -n multimodal-rag-system
kubectl get events -n multimodal-rag-system --sort-by='.lastTimestamp'

# Review recent changes
kubectl rollout history deployment/multimodal-rag-frontend -n multimodal-rag-system
kubectl rollout history deployment/multimodal-rag-backend -n multimodal-rag-system
```

#### 3. Communication (First 30 minutes)
```bash
# Create incident Slack channel
# Update status page
# Send notification to stakeholders

# Template message:
"""
🚨 INVESTIGATING: Multimodal RAG System Issue

**Status**: Investigating
**Impact**: Users unable to access search functionality
**Started**: $(date)
**Next Update**: 30 minutes

Team is actively investigating the issue. We'll provide updates as soon as more information is available.
"""
```

#### 4. Resolution and Recovery
```bash
# Common resolution patterns:

# Restart failed services
kubectl rollout restart deployment/multimodal-rag-backend -n multimodal-rag-system

# Scale up resources
kubectl scale deployment multimodal-rag-backend --replicas=5 -n multimodal-rag-system

# Rollback to previous version
kubectl rollout undo deployment/multimodal-rag-backend -n multimodal-rag-system

# Clear cache
kubectl exec -n multimodal-rag-system deployment/redis -- redis-cli FLUSHALL
```

#### 5. Post-Incident Review
```bash
# Schedule post-mortem meeting within 24 hours
# Create incident report template
# Document timeline, impact, root cause, and prevention measures
# Update monitoring and alerting based on lessons learned
```

---

## Maintenance Procedures

### Weekly Maintenance (Sundays 2:00 AM - 4:00 AM)

#### 1. System Updates
```bash
# Check for security updates
npm audit audit --level high
pip-audit

# Update dependencies (test in staging first)
cd frontend && npm update
cd ../backend && pip install -r requirements.txt --upgrade

# Review and apply security patches
kubectl get pods -n multimodal-rag-system -o json | jq '.items[].spec.containers[].image' | sort | uniq
```

#### 2. Performance Optimization
```bash
# Database maintenance
kubectl exec -n multimodal-rag-system deployment/postgres -- psql -U postgres -c "VACUUM ANALYZE;"
kubectl exec -n multimodal-rag-system deployment/neo4j -- cypher-shell -u neo4j -p $NEO4J_PASSWORD "CALL db.stats.retrieve('GRAPH COUNTS');"

# Clear old logs
kubectl logs -n multimodal-rag-system --since=7d -l app=multimodal-rag-backend > /tmp/old-logs.log
# Archive old logs to S3
aws s3 cp /tmp/old-logs.log s3://multimodal-rag-logs/archives/
```

#### 3. Backup Verification
```bash
# Test backup restoration
./scripts/test-backup-restore.sh

# Verify backup integrity
aws backup list-backup-jobs --by-state COMPLETED --by-created-after $(date -d '7 days ago' +%Y-%m-%d)

# Document backup status
./scripts/backup-status-report.sh
```

### Monthly Maintenance

#### 1. Security Audit
```bash
# Run security scanner
kubectl get pods -n multimodal-rag-system -o json | kubectl score -

# Check for exposed secrets
kubectl get secrets -n multimodal-rag-system -o yaml | grep -i "password\|key\|token"

# Review IAM policies
aws iam list-policies --scope Local --only-attached --output table
```

#### 2. Performance Review
```bash
# Generate performance report
./scripts/performance-analysis.sh

# Review resource utilization trends
kubectl top nodes --use-protocol-buffers | awk 'NR>1 {print $2, $3}' > /tmp/cpu-usage.log
kubectl top pods -n multimodal-rag-system --use-protocol-buffers | awk 'NR>1 {print $2, $3}' > /tmp/memory-usage.log

# Plan capacity adjustments
./scripts/capacity-planning.sh
```

#### 3. Documentation Updates
```bash
# Update runbooks based on recent incidents
# Review and update architecture diagrams
# Update API documentation
# Verify contact information is current
```

---

## Scaling Operations

### Horizontal Scaling

#### Auto-scaling Configuration
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: multimodal-rag-backend-hpa
  namespace: multimodal-rag-system
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: multimodal-rag-backend
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Manual Scaling Operations
```bash
# Scale up for expected load
kubectl scale deployment multimodal-rag-backend --replicas=10 -n multimodal-rag-system

# Scale down after peak period
kubectl scale deployment multimodal-rag-backend --replicas=3 -n multimodal-rag-system

# Enable/disable auto-scaling
kubectl autoscale deployment multimodal-rag-backend \
    --cpu-percent=70 \
    --min=3 \
    --max=20 \
    -n multimodal-rag-system

kubectl delete hpa multimodal-rag-backend-hpa -n multimodal-rag-system
```

### Vertical Scaling

#### Resource Adjustment
```bash
# Monitor resource usage
kubectl top pods -n multimodal-rag-system --use-protocol-buffers

# Update resource limits
kubectl patch deployment multimodal-rag-backend -n multimodal-rag-system -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "backend",
          "resources": {
            "limits": {
              "memory": "8Gi",
              "cpu": "4000m"
            },
            "requests": {
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

### Database Scaling

#### Neo4j Scaling
```bash
# Monitor Neo4j performance
kubectl exec -n multimodal-rag-system deployment/neo4j -- cypher-shell -u neo4j -p $NEO4J_PASSWORD "CALL dbms.procedures() YIELD name WHERE name STARTS WITH 'dbms.list' RETURN name;"

# Add read replicas (cluster mode)
kubectl scale statefulset neo4j --replicas=3 -n multimodal-rag-system

# Optimize configuration
kubectl exec -n multimodal-rag-system deployment/neo4j -- cat /conf/neo4j.conf | grep -E "(memory|heap)"
```

#### Qdrant Scaling
```bash
# Monitor Qdrant performance
kubectl exec -n multimodal-rag-system deployment/qdrant -- curl http://localhost:6333/telemetry

# Scale Qdrant cluster
kubectl scale statefulset qdrant --replicas=3 -n multimodal-rag-system

# Configure sharding
kubectl exec -n multimodal-rag-system deployment/qdrant -- curl -X PUT http://localhost:6333/collections/multimodal_rag/shards -H "Content-Type: application/json" -d '{"shard_count": 3}'
```

---

## Backup and Recovery

### Automated Backup Configuration

#### Database Backups
```bash
# Neo4j backups
kubectl exec -n multimodal-rag-system deployment/neo4j -- neo4j-admin dump --database=neo4j --to=/backup/neo4j-$(date +%Y%m%d-%H%M%S).dump
aws s3 cp /backup/neo4j-$(date +%Y%m%d-%H%M%S).dump s3://multimodal-rag-backups/neo4j/

# Qdrant backups
kubectl exec -n multimodal-rag-system deployment/qdrant -- curl -X PUT http://localhost:6333/snapshots
kubectl exec -n multimodal-rag-system deployment/qdrant -- curl http://localhost:6333/snapshots | jq '.result.snapshots[-1].name' | xargs -I {} aws s3 cp /qdrant/snapshots/{} s3://multimodal-rag-backups/qdrant/

# PostgreSQL backups
kubectl exec -n multimodal-rag-system deployment/postgres -- pg_dump -U postgres ragdb | gzip > /tmp/postgres-$(date +%Y%m%d-%H%M%S).sql.gz
aws s3 cp /tmp/postgres-$(date +%Y%m%d-%H%M%S).sql.gz s3://multimodal-rag-backups/postgresql/
```

#### Application Data Backups
```bash
# S3 bucket synchronization
aws s3 sync s3://multimodal-rag-documents s3://multimodal-rag-backups/documents/ --delete

# Configuration backups
kubectl get configmaps -n multimodal-rag-system -o yaml > /tmp/configmaps-$(date +%Y%m%d).yaml
kubectl get secrets -n multimodal-rag-system -o yaml > /tmp/secrets-$(date +%Y%m%d).yaml
aws s3 cp /tmp/configmaps-$(date +%Y%m%d).yaml s3://multimodal-rag-backups/config/
aws s3 cp /tmp/secrets-$(date +%Y%m%d).yaml s3://multimodal-rag-backups/secrets/
```

### Disaster Recovery Procedures

#### Scenario 1: Single Service Failure
```bash
# Identify failed service
kubectl get pods -n multimodal-rag-system | grep -v Running

# Restart failed service
kubectl delete pod <failed-pod-name> -n multimodal-rag-system

# Monitor recovery
kubectl get pods -w -n multimodal-rag-system
```

#### Scenario 2: Database Corruption
```bash
# Stop application to prevent further damage
kubectl scale deployment multimodal-rag-backend --replicas=0 -n multimodal-rag-system

# Restore from latest backup
aws s3 cp s3://multimodal-rag-backups/neo4j/latest.dump /tmp/neo4j-restore.dump
kubectl cp /tmp/neo4j-restore.dump neo4j-0:/tmp/

# Restore database
kubectl exec -n multimodal-rag-system neo4j-0 -- neo4j-admin load --from=/tmp/neo4j-restore.dump --database=neo4j

# Restart application
kubectl scale deployment multimodal-rag-backend --replicas=3 -n multimodal-rag-system
```

#### Scenario 3: Complete Cluster Recovery
```bash
# Deploy new EKS cluster
cd infrastructure/terraform
terraform apply -var-file="disaster-recovery.tfvars"

# Configure kubectl
aws eks update-kubeconfig --name multimodal-rag-dr-cluster --region us-west-2

# Restore databases from backups
./scripts/restore-all-databases.sh

# Deploy application
helm install multimodal-rag-system ./helm/multimodal-rag-system \
    --namespace multimodal-rag-system \
    --create-namespace \
    --values values-dr.yaml

# Verify functionality
./scripts/health-check.sh
```

---

## Security Operations

### Daily Security Monitoring
```bash
# Check for security events
aws guardduty get-findings --detector-id $(aws guardduty list-detectors --query 'DetectorIds[0]' --output text)

# Review CloudTrail logs
aws logs get-log-events --log-group-name /aws/cloudtrail/aws-controltower --start-time $(date -d '24 hours ago' +%s)000

# Check for unusual activity
kubectl auth can-i --list --namespace multimodal-rag-system
kubectl get events -n multimodal-rag-system --field-selector type=Warning
```

### Security Patch Management
```bash
# Scan for vulnerabilities
trivy image --severity HIGH,CRITICAL your-registry/multimodal-rag-frontend:latest
trivy image --severity HIGH,CRITICAL your-registry/multimodal-rag-backend:latest

# Apply security patches
kubectl rollout status deployment/multimodal-rag-frontend -n multimodal-rag-system
kubectl rollout status deployment/multimodal-rag-backend -n multimodal-rag-system
```

### Access Control Management
```bash
# Review user access
aws iam list-users --query 'Users[?Status.Value==`Active`]'
kubectl get rolebindings -n multimodal-rag-system

# Rotate secrets
./scripts/rotate-secrets.sh

# Update SSL certificates
kubectl get certificates -n multimodal-rag-system
kubectl delete certificate <cert-name> -n multimodal-rag-system  # Force renewal
```

---

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. Frontend Not Loading
**Symptoms**: Blank page, 502 errors, slow loading
**Troubleshooting**:
```bash
# Check frontend pod status
kubectl get pods -n multimodal-rag-system -l app=multimodal-rag-frontend

# Check frontend logs
kubectl logs -n multimodal-rag-system -l app=multimodal-rag-frontend

# Check build process
kubectl exec -n multimodal-rag-system deployment/multimodal-rag-frontend -- ls -la /app/.next

# Restart frontend
kubectl rollout restart deployment/multimodal-rag-frontend -n multimodal-rag-system
```

#### 2. Backend API Errors
**Symptoms**: 500 errors, timeouts, authentication failures
**Troubleshooting**:
```bash
# Check backend pod status
kubectl get pods -n multimodal-rag-system -l app=multimodal-rag-backend

# Check backend logs
kubectl logs -n multimodal-rag-system -l app=multimodal-rag-backend --tail=100

# Check database connectivity
kubectl exec -n multimodal-rag-system deployment/multimodal-rag-backend -- python -c "
import psycopg2
try:
    conn = psycopg2.connect('postgresql://user:pass@postgres:5432/ragdb')
    print('PostgreSQL: OK')
except Exception as e:
    print(f'PostgreSQL: {e}')
"

# Check environment variables
kubectl exec -n multimodal-rag-system deployment/multimodal-rag-backend -- env | grep -E "(DATABASE|REDIS|NEO4J|QDRANT)"
```

#### 3. Search Performance Issues
**Symptoms**: Slow search results, timeouts, irrelevant results
**Troubleshooting**:
```bash
# Check Qdrant status
kubectl exec -n multimodal-rag-system deployment/qdrant -- curl http://localhost:6333/health

# Check collection statistics
kubectl exec -n multimodal-rag-system deployment/qdrant -- curl http://localhost:6333/collections/multimodal_rag

# Check search logs
kubectl logs -n multimodal-rag-system -l app=multimodal-rag-backend | grep "SEARCH"

# Monitor search performance
curl -X POST http://api.rag.yourdomain.com/api/search \
    -H "Content-Type: application/json" \
    -d '{"query": "test", "debug": true}' \
    -w "Response time: %{time_total}s\n"
```

#### 4. Document Processing Failures
**Symptoms**: Stuck uploads, processing errors, missing documents
**Troubleshooting**:
```bash
# Check Celery worker status
kubectl exec -n multimodal-rag-system deployment/celery-worker -- celery -A tasks inspect active

# Check processing logs
kubectl logs -n multimodal-rag-system -l app=celery-worker

# Check file storage
aws s3 ls s3://multimodal-rag-documents/

# Check processing queue
kubectl exec -n multimodal-rag-system deployment/celery-worker -- celery -A tasks inspect reserved
```

#### 5. Memory Issues
**Symptoms**: OOMKilled events, slow performance
**Troubleshooting**:
```bash
# Check memory usage
kubectl top pods -n multimodal-rag-system --use-protocol-buffers

# Check for OOM events
kubectl get events -n multimodal-rag-system --field-selector type=Warning | grep OOM

# Increase memory limits
kubectl patch deployment multimodal-rag-backend -n multimodal-rag-system -p '{
  "spec": {
    "template": {
      "spec": {
        "containers": [{
          "name": "backend",
          "resources": {
            "limits": {"memory": "8Gi"},
            "requests": {"memory": "4Gi"}
          }
        }]
      }
    }
  }
}'
```

---

## Emergency Procedures

### Complete System Outage

#### Immediate Actions (First 15 minutes)
```bash
# Declare incident
# Create Slack channel: #incident-multimodal-rag-$(date +%Y%m%d-%H%M%S)
# Page on-call engineer and team lead

# Assess scope
kubectl get pods -n multimodal-rag-system
kubectl get nodes
curl -I https://rag.yourdomain.com
curl -I https://api.rag.yourdomain.com/health

# Check recent changes
kubectl rollout history deployment/multimodal-rag-frontend -n multimodal-rag-system
kubectl rollout history deployment/multimodal-rag-backend -n multimodal-rag-system
```

#### Recovery Actions
```bash
# Attempt service restart
kubectl rollout restart deployment/multimodal-rag-frontend -n multimodal-rag-system
kubectl rollout restart deployment/multimodal-rag-backend -n multimodal-rag-system

# Check infrastructure
aws ec2 describe-instances --filters Name=tag:Environment,Values=production
aws rds describe-db-instances --db-instance-identifier multimodal-rag-db

# If needed, rollback to previous version
kubectl rollout undo deployment/multimodal-rag-frontend -n multimodal-rag-system
kubectl rollout undo deployment/multimodal-rag-backend -n multimodal-rag-system
```

### Security Incident

#### Immediate Response
```bash
# Isolate affected systems
kubectl scale deployment multimodal-rag-backend --replicas=0 -n multimodal-rag-system

# Enable audit logging
kubectl apply -f - <<EOF
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
- level: Metadata
EOF

# Preserve evidence
kubectl get events -n multimodal-rag-system --all-namespaces > /tmp/incident-events.log
kubectl logs -n multimodal-rag-system --all > /tmp/incident-logs.log

# Notify security team
# Document timeline of events
```

### Data Corruption Incident

#### Response Procedures
```bash
# Stop all writes to prevent further damage
kubectl scale deployment multimodal-rag-backend --replicas=0 -n multimodal-rag-system

# Identify affected data
./scripts/assess-data-integrity.sh

# Restore from clean backup
./scripts/emergency-restore.sh

# Verify data integrity
./scripts/verify-data-integrity.sh

# Gradually restore service
kubectl scale deployment multimodal-rag-backend --replicas=1 -n multimodal-rag-system
# Monitor for 15 minutes, then scale up gradually
```

---

## Contact Information

### Emergency Contacts
- **On-call Engineer**: +1-XXX-XXX-XXXX (PagerDuty)
- **DevOps Team Lead**: devops-lead@yourcompany.com
- **Security Team**: security@yourcompany.com
- **Management**: management@yourcompany.com

### Service Providers
- **AWS Support**: 1-800-XXX-XXXX
- **Database Support**: neo4j-support@neo4j.com
- **Monitoring Service**: grafana-support@grafana.com

### Documentation Links
- **Architecture Guide**: [Link to architecture documentation]
- **API Documentation**: [Link to API docs]
- **Runbook Repository**: [Link to runbook repo]
- **Status Page**: https://status.yourdomain.com

---

## Training and Documentation

### Operator Training Requirements
- Complete Kubernetes administration training
- Understanding of application architecture
- Familiarity with monitoring tools
- Incident response procedures

### Documentation Updates
- Review runbooks quarterly
- Update after major incidents
- Maintain change logs
- Cross-train team members

### Drills and Simulations
- Monthly fire drills
- Quarterly disaster recovery tests
- Annual security simulations
- Post-incident reviews and improvements

---

This operations runbook should be reviewed quarterly and updated as the system evolves. All team members should be familiar with emergency procedures and have access to necessary tools and credentials.