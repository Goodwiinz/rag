# =============================================================================
# Variables for DigitalOcean RAG System Deployment
# =============================================================================

# -----------------------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------------------

variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "spaces_access_key_id" {
  description = "DigitalOcean Spaces access key ID"
  type        = string
  sensitive   = true
}

variable "spaces_secret_access_key" {
  description = "DigitalOcean Spaces secret access key"
  type        = string
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Project Configuration
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Name of the project (used for resource naming)"
  type        = string
  default     = "rag-system"
}

variable "environment" {
  description = "Environment (development, staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be one of: development, staging, production."
  }
}

variable "region" {
  description = "DigitalOcean region for resources"
  type        = string
  default     = "nyc3"

  validation {
    condition = contains([
      "nyc1", "nyc3", "sfo3", "ams3", "sgp1",
      "lon1", "fra1", "tor1", "blr1", "syd1"
    ], var.region)
    error_message = "Region must be a valid DigitalOcean region."
  }
}

variable "spaces_region" {
  description = "DigitalOcean Spaces region"
  type        = string
  default     = "nyc3"
}

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.10.0.0/16"
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "example.com"
}

variable "manage_dns" {
  description = "Whether to manage DNS records in DigitalOcean"
  type        = bool
  default     = false
}

variable "cors_allowed_origins" {
  description = "Allowed CORS origins for Spaces bucket"
  type        = list(string)
  default     = ["*"]
}

# -----------------------------------------------------------------------------
# Kubernetes Cluster
# -----------------------------------------------------------------------------

variable "kubernetes_version" {
  description = "Kubernetes version for DOKS cluster"
  type        = string
  default     = "1.29.1-do.0"  # Check available versions: doctl kubernetes options versions
}

# Application Node Pool
variable "app_node_size" {
  description = "Droplet size for application nodes"
  type        = string
  default     = "s-4vcpu-8gb"  # $48/month per node

  # Available sizes (check current pricing):
  # s-2vcpu-4gb    - $24/mo  - Basic workloads
  # s-4vcpu-8gb    - $48/mo  - Standard workloads (recommended)
  # s-8vcpu-16gb   - $96/mo  - Memory-intensive
  # c-4            - $84/mo  - CPU-optimized
  # g-4vcpu-16gb   - $126/mo - General purpose
}

variable "app_min_nodes" {
  description = "Minimum number of application nodes"
  type        = number
  default     = 2
}

variable "app_max_nodes" {
  description = "Maximum number of application nodes"
  type        = number
  default     = 10
}

# Database Node Pool (for Neo4j, Qdrant)
variable "db_node_size" {
  description = "Droplet size for database nodes"
  type        = string
  default     = "s-4vcpu-8gb"
}

variable "db_min_nodes" {
  description = "Minimum number of database nodes"
  type        = number
  default     = 2
}

variable "db_max_nodes" {
  description = "Maximum number of database nodes"
  type        = number
  default     = 5
}

# -----------------------------------------------------------------------------
# Managed PostgreSQL
# -----------------------------------------------------------------------------

variable "postgres_size" {
  description = "PostgreSQL cluster size"
  type        = string
  default     = "db-s-2vcpu-4gb"  # $60/month

  # Available sizes:
  # db-s-1vcpu-1gb   - $15/mo  - Dev/Test
  # db-s-1vcpu-2gb   - $30/mo  - Small
  # db-s-2vcpu-4gb   - $60/mo  - Standard (recommended)
  # db-s-4vcpu-8gb   - $120/mo - Large
  # db-s-8vcpu-16gb  - $240/mo - High performance
}

variable "postgres_node_count" {
  description = "Number of PostgreSQL nodes (1=single, 2+=HA)"
  type        = number
  default     = 2  # HA with standby

  validation {
    condition     = var.postgres_node_count >= 1 && var.postgres_node_count <= 3
    error_message = "PostgreSQL node count must be between 1 and 3."
  }
}

variable "database_name" {
  description = "Name of the application database"
  type        = string
  default     = "multimodal_rag"
}

variable "database_user" {
  description = "Database user name"
  type        = string
  default     = "raguser"
}

# -----------------------------------------------------------------------------
# Managed Redis
# -----------------------------------------------------------------------------

variable "redis_size" {
  description = "Redis cluster size"
  type        = string
  default     = "db-s-1vcpu-2gb"  # $30/month

  # Available sizes:
  # db-s-1vcpu-1gb  - $15/mo
  # db-s-1vcpu-2gb  - $30/mo (recommended)
  # db-s-2vcpu-4gb  - $60/mo
}

variable "redis_node_count" {
  description = "Number of Redis nodes (1=single, 2+=HA)"
  type        = number
  default     = 2  # HA with standby

  validation {
    condition     = var.redis_node_count >= 1 && var.redis_node_count <= 3
    error_message = "Redis node count must be between 1 and 3."
  }
}

# -----------------------------------------------------------------------------
# Container Registry
# -----------------------------------------------------------------------------

variable "registry_tier" {
  description = "Container registry subscription tier"
  type        = string
  default     = "basic"  # $5/month, 5GB storage

  # Available tiers:
  # starter     - Free, 500MB
  # basic       - $5/mo, 5GB (recommended)
  # professional - $20/mo, 50GB
}

# -----------------------------------------------------------------------------
# Application Configuration
# -----------------------------------------------------------------------------

variable "backend_replicas" {
  description = "Number of backend replicas"
  type        = number
  default     = 2
}

variable "frontend_replicas" {
  description = "Number of frontend replicas"
  type        = number
  default     = 2
}

variable "celery_replicas" {
  description = "Number of Celery worker replicas"
  type        = number
  default     = 2
}

# -----------------------------------------------------------------------------
# Security & SSL
# -----------------------------------------------------------------------------

variable "enable_ssl" {
  description = "Enable SSL/TLS with Let's Encrypt"
  type        = bool
  default     = true
}

variable "letsencrypt_email" {
  description = "Email for Let's Encrypt certificate notifications"
  type        = string
  default     = "admin@example.com"
}

# -----------------------------------------------------------------------------
# Monitoring
# -----------------------------------------------------------------------------

variable "enable_monitoring" {
  description = "Enable Prometheus/Grafana monitoring stack"
  type        = bool
  default     = true
}

variable "grafana_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
  default     = "admin"  # Change in production!
}

# -----------------------------------------------------------------------------
# Cost Estimation (Monthly, approximate)
# -----------------------------------------------------------------------------

# With default values:
# - DOKS Cluster (control plane): $0 (free)
# - App Node Pool (2x s-4vcpu-8gb): ~$96
# - DB Node Pool (2x s-4vcpu-8gb): ~$96
# - Managed PostgreSQL (2 nodes): ~$120
# - Managed Redis (2 nodes): ~$60
# - Spaces (depends on usage): ~$5-20
# - Container Registry (basic): ~$5
# - Load Balancer: ~$12
# - Reserved IP: ~$4
# Total: ~$400-450/month

# Cost-optimized configuration:
# - 1 app node (s-2vcpu-4gb): ~$24
# - 1 db node (s-2vcpu-4gb): ~$24
# - PostgreSQL (1 node, db-s-1vcpu-2gb): ~$30
# - Redis (1 node, db-s-1vcpu-1gb): ~$15
# Total: ~$120/month (without HA)
