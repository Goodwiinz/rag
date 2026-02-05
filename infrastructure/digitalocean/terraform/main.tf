# =============================================================================
# RAG System - DigitalOcean Kubernetes (DOKS) Deployment
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.34"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }

  # Use DO Spaces for remote state (configure after creating the bucket)
  # backend "s3" {
  #   endpoint                    = "nyc3.digitaloceanspaces.com"
  #   bucket                      = "rag-system-terraform-state"
  #   key                         = "terraform.tfstate"
  #   region                      = "us-east-1"  # Required but unused for DO Spaces
  #   skip_credentials_validation = true
  #   skip_metadata_api_check     = true
  #   skip_region_validation      = true
  # }
}

# =============================================================================
# DigitalOcean Provider Configuration
# =============================================================================

provider "digitalocean" {
  token             = var.do_token
  spaces_access_id  = var.spaces_access_key_id
  spaces_secret_key = var.spaces_secret_access_key
}

provider "kubernetes" {
  host                   = digitalocean_kubernetes_cluster.rag_cluster.endpoint
  token                  = digitalocean_kubernetes_cluster.rag_cluster.kube_config[0].token
  cluster_ca_certificate = base64decode(digitalocean_kubernetes_cluster.rag_cluster.kube_config[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = digitalocean_kubernetes_cluster.rag_cluster.endpoint
    token                  = digitalocean_kubernetes_cluster.rag_cluster.kube_config[0].token
    cluster_ca_certificate = base64decode(digitalocean_kubernetes_cluster.rag_cluster.kube_config[0].cluster_ca_certificate)
  }
}

# =============================================================================
# VPC Configuration
# =============================================================================

resource "digitalocean_vpc" "rag_vpc" {
  name        = "${var.project_name}-vpc"
  region      = var.region
  ip_range    = var.vpc_cidr
  description = "VPC for RAG System"
}

# =============================================================================
# DOKS Cluster Configuration
# =============================================================================

resource "digitalocean_kubernetes_cluster" "rag_cluster" {
  name         = "${var.project_name}-cluster"
  region       = var.region
  version      = var.kubernetes_version
  vpc_uuid     = digitalocean_vpc.rag_vpc.id
  auto_upgrade = true
  surge_upgrade = true

  maintenance_policy {
    start_time = "04:00"
    day        = "sunday"
  }

  # Application Node Pool (main workloads)
  node_pool {
    name       = "app-pool"
    size       = var.app_node_size
    auto_scale = true
    min_nodes  = var.app_min_nodes
    max_nodes  = var.app_max_nodes

    labels = {
      workload = "application"
      tier     = "app"
    }

    tags = ["rag-system", "app-nodes"]
  }

  tags = ["rag-system", var.environment]
}

# Database Node Pool - Disabled due to account droplet limits
# Uncomment when you have higher droplet limits or dedicated database nodes
#
# resource "digitalocean_kubernetes_node_pool" "db_pool" {
#   cluster_id = digitalocean_kubernetes_cluster.rag_cluster.id
#   name       = "db-pool"
#   size       = var.db_node_size
#   auto_scale = true
#   min_nodes  = var.db_min_nodes
#   max_nodes  = var.db_max_nodes
#
#   labels = {
#     workload = "database"
#     tier     = "data"
#   }
#
#   taint {
#     key    = "workload"
#     value  = "database"
#     effect = "NoSchedule"
#   }
#
#   tags = ["rag-system", "db-nodes"]
# }

# =============================================================================
# DigitalOcean Managed PostgreSQL Database
# =============================================================================

resource "digitalocean_database_cluster" "postgres" {
  name                 = "${var.project_name}-postgres"
  engine               = "pg"
  version              = "15"
  size                 = var.postgres_size
  region               = var.region
  node_count           = var.postgres_node_count
  private_network_uuid = digitalocean_vpc.rag_vpc.id

  maintenance_window {
    day  = "sunday"
    hour = "02:00:00"
  }

  tags = ["rag-system", "postgres"]
}

# Create the application database
resource "digitalocean_database_db" "rag_db" {
  cluster_id = digitalocean_database_cluster.postgres.id
  name       = var.database_name
}

# Create application user
resource "digitalocean_database_user" "rag_user" {
  cluster_id = digitalocean_database_cluster.postgres.id
  name       = var.database_user
}

# Configure firewall to allow only DOKS cluster
resource "digitalocean_database_firewall" "postgres_fw" {
  cluster_id = digitalocean_database_cluster.postgres.id

  rule {
    type  = "k8s"
    value = digitalocean_kubernetes_cluster.rag_cluster.id
  }
}

# =============================================================================
# DigitalOcean Managed Valkey Database (Redis-compatible)
# =============================================================================

resource "digitalocean_database_cluster" "valkey" {
  name                 = "${var.project_name}-valkey"
  engine               = "valkey"
  version              = "8"
  size                 = var.redis_size
  region               = var.region
  node_count           = var.redis_node_count
  private_network_uuid = digitalocean_vpc.rag_vpc.id

  maintenance_window {
    day  = "sunday"
    hour = "03:00:00"
  }

  tags = ["rag-system", "valkey"]
}

# Configure firewall to allow only DOKS cluster
resource "digitalocean_database_firewall" "valkey_fw" {
  cluster_id = digitalocean_database_cluster.valkey.id

  rule {
    type  = "k8s"
    value = digitalocean_kubernetes_cluster.rag_cluster.id
  }
}

# =============================================================================
# DigitalOcean Spaces (S3-compatible Object Storage)
# =============================================================================

resource "digitalocean_spaces_bucket" "uploads" {
  name   = "${var.project_name}-uploads-${random_string.bucket_suffix.result}"
  region = var.spaces_region
  acl    = "private"

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE", "HEAD"]
    allowed_origins = var.cors_allowed_origins
    max_age_seconds = 3600
  }

  lifecycle_rule {
    enabled = true
    id      = "cleanup-temp-files"

    prefix = "temp/"

    expiration {
      days = 7
    }
  }
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# Spaces bucket for backups
resource "digitalocean_spaces_bucket" "backups" {
  name   = "${var.project_name}-backups-${random_string.bucket_suffix.result}"
  region = var.spaces_region
  acl    = "private"

  versioning {
    enabled = true
  }

  lifecycle_rule {
    enabled = true
    id      = "retain-backups"

    noncurrent_version_expiration {
      days = 30
    }
  }
}

# =============================================================================
# Container Registry
# =============================================================================

resource "digitalocean_container_registry" "rag_registry" {
  name                   = "${replace(var.project_name, "-", "")}registry"
  subscription_tier_slug = var.registry_tier
  region                 = var.region
}

# Allow DOKS to pull from registry
resource "digitalocean_container_registry_docker_credentials" "rag_credentials" {
  registry_name = digitalocean_container_registry.rag_registry.name
}

# =============================================================================
# Load Balancer & DNS (managed by ingress-nginx in Helm)
# =============================================================================

# Reserved IP for the load balancer
resource "digitalocean_reserved_ip" "lb_ip" {
  region = var.region
}

# Domain configuration (if using DO DNS)
resource "digitalocean_domain" "main" {
  count = var.manage_dns ? 1 : 0
  name  = var.domain_name
}

resource "digitalocean_record" "api" {
  count  = var.manage_dns ? 1 : 0
  domain = digitalocean_domain.main[0].id
  type   = "A"
  name   = "api"
  value  = digitalocean_reserved_ip.lb_ip.ip_address
  ttl    = 300
}

resource "digitalocean_record" "app" {
  count  = var.manage_dns ? 1 : 0
  domain = digitalocean_domain.main[0].id
  type   = "A"
  name   = "app"
  value  = digitalocean_reserved_ip.lb_ip.ip_address
  ttl    = 300
}

resource "digitalocean_record" "grafana" {
  count  = var.manage_dns ? 1 : 0
  domain = digitalocean_domain.main[0].id
  type   = "A"
  name   = "grafana"
  value  = digitalocean_reserved_ip.lb_ip.ip_address
  ttl    = 300
}

# =============================================================================
# Firewall Rules
# =============================================================================

# Note: DOKS manages its own firewall rules through the cloud firewall
# This resource is commented out to avoid tag dependency issues
# Uncomment after cluster is created if you need additional firewall rules
#
# resource "digitalocean_firewall" "cluster_firewall" {
#   name = "${var.project_name}-firewall"
#   droplet_ids = []
#
#   inbound_rule {
#     protocol         = "tcp"
#     port_range       = "443"
#     source_addresses = ["0.0.0.0/0", "::/0"]
#   }
#
#   inbound_rule {
#     protocol         = "tcp"
#     port_range       = "80"
#     source_addresses = ["0.0.0.0/0", "::/0"]
#   }
#
#   outbound_rule {
#     protocol              = "tcp"
#     port_range            = "1-65535"
#     destination_addresses = ["0.0.0.0/0", "::/0"]
#   }
#
#   outbound_rule {
#     protocol              = "udp"
#     port_range            = "1-65535"
#     destination_addresses = ["0.0.0.0/0", "::/0"]
#   }
#
#   outbound_rule {
#     protocol              = "icmp"
#     destination_addresses = ["0.0.0.0/0", "::/0"]
#   }
#
#   depends_on = [digitalocean_kubernetes_cluster.rag_cluster]
# }

# =============================================================================
# Project Organization
# =============================================================================

resource "digitalocean_project" "rag_project" {
  name        = var.project_name
  description = "Multimodal Enterprise RAG System"
  purpose     = "Service or API"
  environment = var.environment

  resources = [
    digitalocean_kubernetes_cluster.rag_cluster.urn,
    digitalocean_database_cluster.postgres.urn,
    digitalocean_database_cluster.valkey.urn,
    digitalocean_spaces_bucket.uploads.urn,
    digitalocean_spaces_bucket.backups.urn,
  ]
}

# =============================================================================
# Kubernetes Namespace and Secrets
# =============================================================================

resource "kubernetes_namespace" "rag_system" {
  metadata {
    name = "rag-system"

    labels = {
      name        = "rag-system"
      environment = var.environment
    }
  }

  depends_on = [digitalocean_kubernetes_cluster.rag_cluster]
}

# Database credentials secret
resource "kubernetes_secret" "database_credentials" {
  metadata {
    name      = "database-credentials"
    namespace = kubernetes_namespace.rag_system.metadata[0].name
  }

  data = {
    POSTGRES_HOST     = digitalocean_database_cluster.postgres.private_host
    POSTGRES_PORT     = digitalocean_database_cluster.postgres.port
    POSTGRES_DB       = digitalocean_database_db.rag_db.name
    POSTGRES_USER     = digitalocean_database_user.rag_user.name
    POSTGRES_PASSWORD = digitalocean_database_user.rag_user.password
    DATABASE_URL      = "postgresql://${digitalocean_database_user.rag_user.name}:${digitalocean_database_user.rag_user.password}@${digitalocean_database_cluster.postgres.private_host}:${digitalocean_database_cluster.postgres.port}/${digitalocean_database_db.rag_db.name}?sslmode=require"
    REDIS_HOST        = digitalocean_database_cluster.valkey.private_host
    REDIS_PORT        = digitalocean_database_cluster.valkey.port
    REDIS_PASSWORD    = digitalocean_database_cluster.valkey.password
    REDIS_URL         = "rediss://:${digitalocean_database_cluster.valkey.password}@${digitalocean_database_cluster.valkey.private_host}:${digitalocean_database_cluster.valkey.port}"
  }

  type = "Opaque"

  depends_on = [kubernetes_namespace.rag_system]
}

# Spaces credentials secret
resource "kubernetes_secret" "spaces_credentials" {
  metadata {
    name      = "spaces-credentials"
    namespace = kubernetes_namespace.rag_system.metadata[0].name
  }

  data = {
    SPACES_ACCESS_KEY_ID     = var.spaces_access_key_id
    SPACES_SECRET_ACCESS_KEY = var.spaces_secret_access_key
    SPACES_BUCKET            = digitalocean_spaces_bucket.uploads.name
    SPACES_REGION            = digitalocean_spaces_bucket.uploads.region
    SPACES_ENDPOINT          = "https://${var.spaces_region}.digitaloceanspaces.com"
  }

  type = "Opaque"

  depends_on = [kubernetes_namespace.rag_system]
}

# Registry credentials for pulling images
resource "kubernetes_secret" "registry_credentials" {
  metadata {
    name      = "do-registry"
    namespace = kubernetes_namespace.rag_system.metadata[0].name
  }

  type = "kubernetes.io/dockerconfigjson"

  data = {
    ".dockerconfigjson" = digitalocean_container_registry_docker_credentials.rag_credentials.docker_credentials
  }

  depends_on = [kubernetes_namespace.rag_system]
}
