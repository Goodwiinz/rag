# =============================================================================
# Outputs for DigitalOcean RAG System Deployment
# =============================================================================

# -----------------------------------------------------------------------------
# Kubernetes Cluster
# -----------------------------------------------------------------------------

output "cluster_id" {
  description = "ID of the DOKS cluster"
  value       = digitalocean_kubernetes_cluster.rag_cluster.id
}

output "cluster_name" {
  description = "Name of the DOKS cluster"
  value       = digitalocean_kubernetes_cluster.rag_cluster.name
}

output "cluster_endpoint" {
  description = "Endpoint for the DOKS cluster API server"
  value       = digitalocean_kubernetes_cluster.rag_cluster.endpoint
}

output "cluster_status" {
  description = "Status of the DOKS cluster"
  value       = digitalocean_kubernetes_cluster.rag_cluster.status
}

output "kubeconfig" {
  description = "Raw kubeconfig for the cluster"
  value       = digitalocean_kubernetes_cluster.rag_cluster.kube_config[0].raw_config
  sensitive   = true
}

# Save kubeconfig command
output "kubeconfig_command" {
  description = "Command to save kubeconfig locally"
  value       = "doctl kubernetes cluster kubeconfig save ${digitalocean_kubernetes_cluster.rag_cluster.name}"
}

# -----------------------------------------------------------------------------
# Database Connections
# -----------------------------------------------------------------------------

output "postgres_host" {
  description = "PostgreSQL private host"
  value       = digitalocean_database_cluster.postgres.private_host
}

output "postgres_port" {
  description = "PostgreSQL port"
  value       = digitalocean_database_cluster.postgres.port
}

output "postgres_database" {
  description = "PostgreSQL database name"
  value       = digitalocean_database_db.rag_db.name
}

output "postgres_user" {
  description = "PostgreSQL user"
  value       = digitalocean_database_user.rag_user.name
}

output "postgres_connection_string" {
  description = "PostgreSQL connection string (private)"
  value       = "postgresql://${digitalocean_database_user.rag_user.name}:PASSWORD@${digitalocean_database_cluster.postgres.private_host}:${digitalocean_database_cluster.postgres.port}/${digitalocean_database_db.rag_db.name}?sslmode=require"
  sensitive   = false
}

output "redis_host" {
  description = "Redis private host"
  value       = digitalocean_database_cluster.valkey.private_host
}

output "redis_port" {
  description = "Redis port"
  value       = digitalocean_database_cluster.valkey.port
}

output "redis_connection_string" {
  description = "Redis connection string (private)"
  value       = "rediss://:PASSWORD@${digitalocean_database_cluster.valkey.private_host}:${digitalocean_database_cluster.valkey.port}"
  sensitive   = false
}

# -----------------------------------------------------------------------------
# Object Storage
# -----------------------------------------------------------------------------

output "spaces_bucket_name" {
  description = "Spaces bucket name for uploads"
  value       = digitalocean_spaces_bucket.uploads.name
}

output "spaces_bucket_domain" {
  description = "Spaces bucket domain"
  value       = digitalocean_spaces_bucket.uploads.bucket_domain_name
}

output "spaces_endpoint" {
  description = "Spaces endpoint URL"
  value       = "https://${var.spaces_region}.digitaloceanspaces.com"
}

output "backups_bucket_name" {
  description = "Spaces bucket name for backups"
  value       = digitalocean_spaces_bucket.backups.name
}

# -----------------------------------------------------------------------------
# Container Registry
# -----------------------------------------------------------------------------

output "registry_endpoint" {
  description = "Container registry endpoint"
  value       = digitalocean_container_registry.rag_registry.endpoint
}

output "registry_name" {
  description = "Container registry name"
  value       = digitalocean_container_registry.rag_registry.name
}

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------

output "vpc_id" {
  description = "VPC ID"
  value       = digitalocean_vpc.rag_vpc.id
}

output "load_balancer_ip" {
  description = "Reserved IP for load balancer"
  value       = digitalocean_reserved_ip.lb_ip.ip_address
}

# -----------------------------------------------------------------------------
# DNS Records (if managed)
# -----------------------------------------------------------------------------

output "api_url" {
  description = "API endpoint URL"
  value       = var.manage_dns ? "https://api.${var.domain_name}" : "https://${digitalocean_reserved_ip.lb_ip.ip_address}"
}

output "app_url" {
  description = "Application URL"
  value       = var.manage_dns ? "https://app.${var.domain_name}" : "https://${digitalocean_reserved_ip.lb_ip.ip_address}"
}

output "grafana_url" {
  description = "Grafana dashboard URL"
  value       = var.manage_dns ? "https://grafana.${var.domain_name}" : "https://${digitalocean_reserved_ip.lb_ip.ip_address}/grafana"
}

# -----------------------------------------------------------------------------
# Helm Values File Location
# -----------------------------------------------------------------------------

output "helm_values_path" {
  description = "Path to generated Helm values file"
  value       = "${path.module}/../helm/values-digitalocean.yaml"
}

# -----------------------------------------------------------------------------
# Next Steps
# -----------------------------------------------------------------------------

output "next_steps" {
  description = "Next steps after Terraform apply"
  value       = <<-EOT

    ========================================
    RAG System Deployment Complete!
    ========================================

    1. Configure kubectl:
       ${digitalocean_kubernetes_cluster.rag_cluster.name != "" ? "doctl kubernetes cluster kubeconfig save ${digitalocean_kubernetes_cluster.rag_cluster.name}" : ""}

    2. Verify cluster access:
       kubectl get nodes
       kubectl get pods -n rag-system

    3. Deploy the application with Helm:
       helm upgrade --install rag-system ./deployment/helm/rag-system \
         -f ./infrastructure/digitalocean/helm/values-digitalocean.yaml \
         -n rag-system

    4. Access the application:
       API: ${var.manage_dns ? "https://api.${var.domain_name}" : "https://${digitalocean_reserved_ip.lb_ip.ip_address}"}
       App: ${var.manage_dns ? "https://app.${var.domain_name}" : "https://${digitalocean_reserved_ip.lb_ip.ip_address}"}

    5. Monitor resources:
       doctl kubernetes cluster list
       doctl databases list

    ========================================
  EOT
}
