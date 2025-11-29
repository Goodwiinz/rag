variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name (e.g., staging, production)"
  type        = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be one of: development, staging, production."
  }
}

variable "owner" {
  description = "Owner of the infrastructure"
  type        = string
  default     = "rag-team"
}

variable "domain_name" {
  description = "Primary domain name for the application"
  type        = string
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token for DNS management"
  type        = string
  sensitive   = true
}

# Network Configuration
variable "vpc_cidr_block" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24", "10.0.13.0/24"]
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for database subnets"
  type        = list(string)
  default     = ["10.0.21.0/24", "10.0.22.0/24", "10.0.23.0/24"]
}

variable "enable_nat_gateway" {
  description = "Enable NAT gateway"
  type        = bool
  default     = true
}

variable "one_nat_gateway_per_az" {
  description = "Create one NAT gateway per availability zone"
  type        = bool
  default     = false
}

variable "enable_vpn_gateway" {
  description = "Enable VPN gateway"
  type        = bool
  default     = false
}

# Kubernetes Configuration
variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.28"
}

# Application Node Group
variable "application_node_count" {
  description = "Desired number of application nodes"
  type        = number
  default     = 3
}

variable "application_node_min_count" {
  description = "Minimum number of application nodes"
  type        = number
  default     = 2
}

variable "application_node_max_count" {
  description = "Maximum number of application nodes"
  type        = number
  default     = 10
}

variable "application_instance_types" {
  description = "Instance types for application nodes"
  type        = list(string)
  default     = ["m5.xlarge", "m5.2xlarge"]
}

# Worker Node Group
variable "worker_node_count" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 4
}

variable "worker_node_min_count" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 2
}

variable "worker_node_max_count" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 8
}

variable "worker_instance_types" {
  description = "Instance types for worker nodes"
  type        = list(string)
  default     = ["m5.2xlarge", "m5.4xlarge"]
}

# System Node Group
variable "system_node_count" {
  description = "Desired number of system nodes"
  type        = number
  default     = 2
}

variable "system_node_min_count" {
  description = "Minimum number of system nodes"
  type        = number
  default     = 1
}

variable "system_node_max_count" {
  description = "Maximum number of system nodes"
  type        = number
  default     = 3
}

variable "system_instance_types" {
  description = "Instance types for system nodes"
  type        = list(string)
  default     = ["m5.large", "m5.xlarge"]
}

# Database Configuration
variable "database_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r5.xlarge"
}

variable "database_storage_size" {
  description = "RDS storage size in GB"
  type        = number
  default     = 100
}

variable "database_max_storage_size" {
  description = "Maximum RDS storage size in GB"
  type        = number
  default     = 1000
}

variable "backup_retention_period" {
  description = "Backup retention period in days"
  type        = number
  default     = 7
}

variable "backup_window" {
  description = "Preferred backup window"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Preferred maintenance window"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

variable "database_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

# Redis Configuration
variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.r5.large"
}

variable "redis_node_count" {
  description = "Number of Redis nodes"
  type        = number
  default     = 1
}

variable "redis_auth_token" {
  description = "Redis auth token"
  type        = string
  sensitive   = true
}

# Additional Configuration
variable "additional_userdata" {
  description = "Additional user data script"
  type        = string
  default     = ""
}

variable "enable_monitoring" {
  description = "Enable CloudWatch Container Insights"
  type        = bool
  default     = true
}

variable "enable_logging" {
  description = "Enable logging"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}