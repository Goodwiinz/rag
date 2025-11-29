# Terraform Configuration for Multimodal Enterprise RAG System
# AWS Cloud Infrastructure as Code

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }
    kubectl = {
      source  = "alekc/kubectl"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }

  backend "s3" {
    bucket         = "rag-system-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "rag-system-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "multimodal-rag-system"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

provider "kubectl" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  load_config_file       = false

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# Local values
locals {
  name_prefix = "rag-system-${var.environment}"
  common_tags = {
    Project     = "multimodal-rag-system"
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = var.owner
  }

  cluster_name = "${local.name_prefix}-cluster"
  vpc_name     = "${local.name_prefix}-vpc"

  user_data = base64encode(templatefile("${path.module}/templates/user-data.sh", {
    cluster_name     = local.cluster_name
    region           = var.aws_region
    additional_userdata = var.additional_userdata
  }))
}

# Modules
module "vpc" {
  source = "./modules/vpc"

  name               = local.vpc_name
  environment        = var.environment
  cidr_block         = var.vpc_cidr_block
  availability_zones = data.aws_availability_zones.available.names
  public_subnets     = var.public_subnet_cidrs
  private_subnets    = var.private_subnet_cidrs
  database_subnets   = var.database_subnet_cidrs

  enable_nat_gateway     = var.enable_nat_gateway
  enable_vpn_gateway     = var.enable_vpn_gateway
  one_nat_gateway_per_az = var.one_nat_gateway_per_az

  tags = merge(local.common_tags, {
    Name = local.vpc_name
  })
}

module "eks" {
  source = "./modules/eks"

  cluster_name    = local.cluster_name
  cluster_version = var.kubernetes_version
  environment     = var.environment
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnet_ids

  node_groups = {
    application = {
      desired_capacity = var.application_node_count
      max_capacity     = var.application_node_max_count
      min_capacity     = var.application_node_min_count
      instance_types   = var.application_instance_types
      subnet_ids       = module.vpc.private_subnet_ids
      k8s_labels = {
        node-type = "application"
      }
      additional_tags = merge(local.common_tags, {
        Name = "${local.name_prefix}-application-nodes"
        NodeType = "application"
      })
    }

    worker = {
      desired_capacity = var.worker_node_count
      max_capacity     = var.worker_node_max_count
      min_capacity     = var.worker_node_min_count
      instance_types   = var.worker_instance_types
      subnet_ids       = module.vpc.private_subnet_ids
      k8s_labels = {
        node-type = "worker"
      }
      additional_tags = merge(local.common_tags, {
        Name = "${local.name_prefix}-worker-nodes"
        NodeType = "worker"
      })
    }

    system = {
      desired_capacity = var.system_node_count
      max_capacity     = var.system_node_max_count
      min_capacity     = var.system_node_min_count
      instance_types   = var.system_instance_types
      subnet_ids       = module.vpc.private_subnet_ids
      k8s_labels = {
        node-type = "system"
      }
      additional_tags = merge(local.common_tags, {
        Name = "${local.name_prefix}-system-nodes"
        NodeType = "system"
      })
    }
  }

  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
    aws-efs-csi-driver = {
      most_recent = true
    }
  }

  cluster_security_group_additional_rules = {
    ingress_nodes_443 = {
      description                = "Node groups to cluster API"
      protocol                   = "tcp"
      from_port                  = 443
      to_port                    = 443
      type                       = "ingress"
      source_node_security_group = true
    }
  }

  node_security_group_additional_rules = {
    ingress_self_all = {
      description = "Node to node all ports"
      protocol    = "-1"
      from_port   = 0
      to_port     = 0
      type        = "ingress"
      self        = true
    }
  }

  tags = merge(local.common_tags, {
    Name = local.cluster_name
  })
}

module "irsa" {
  source = "./modules/irsa"

  cluster_name = local.cluster_name
  environment  = var.environment

  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.cluster_oidc_issuer_url

  service_accounts = {
    app = {
      namespace        = "rag-system"
      service_account  = "rag-system-sa"
      iam_policy_arns = [
        "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
        "arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess",
        aws_iam_policy.rag_app_policy.arn
      ]
    }
    monitoring = {
      namespace        = "rag-system-monitoring"
      service_account  = "monitoring-sa"
      iam_policy_arns = [
        "arn:aws:iam::aws:policy/CloudWatchFullAccess",
        "arn:aws:iam::aws:policy/AmazonPrometheusFullAccess"
      ]
    }
  }
}

module "rds" {
  source = "./modules/rds"

  environment  = var.environment
  identifier   = "${local.name_prefix}-postgres"

  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.database_instance_class

  allocated_storage     = var.database_storage_size
  max_allocated_storage = var.database_max_storage_size
  storage_encrypted     = true
  storage_type          = "gp3"

  db_name  = "ragdb"
  username = "raguser"

  vpc_security_group_ids = [module.vpc.database_security_group_id]
  db_subnet_group_name   = module.vpc.database_subnet_group_name

  backup_retention_period = var.backup_retention_period
  backup_window          = var.backup_window
  maintenance_window     = var.maintenance_window

  deletion_protection = var.environment == "production"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-postgres"
  })
}

module "elasticache" {
  source = "./modules/elasticache"

  environment = var.environment
  identifier  = "${local.name_prefix}-redis"

  node_type         = var.redis_node_type
  num_cache_nodes   = var.redis_node_count
  engine_version    = "7.0"
  port              = 6379

  subnet_group_name  = module.vpc.elasticache_subnet_group_name
  security_group_ids = [module.vpc.elasticache_security_group_id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token

  automatic_failover_enabled = var.redis_node_count > 1
  multi_az_enabled          = var.redis_node_count > 1

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-redis"
  })
}

module "s3" {
  source = "./modules/s3"

  environment = var.environment

  buckets = {
    uploads = {
      bucket_prefix = "${local.name_prefix}-uploads"
      versioning    = true
      encryption    = true

      lifecycle_rules = [
        {
          id     = "uploads-lifecycle"
          status = "Enabled"
          transitions = [
            {
              days          = 30
              storage_class = "STANDARD_IA"
            },
            {
              days          = 60
              storage_class = "GLACIER"
            },
            {
              days          = 90
              storage_class = "DEEP_ARCHIVE"
            }
          ]
        }
      ]
    }

    models = {
      bucket_prefix = "${local.name_prefix}-models"
      versioning    = true
      encryption    = true

      lifecycle_rules = [
        {
          id     = "models-lifecycle"
          status = "Enabled"
          transitions = [
            {
              days          = 90
              storage_class = "STANDARD_IA"
            }
          ]
        }
      ]
    }

    backups = {
      bucket_prefix = "${local.name_prefix}-backups"
      versioning    = true
      encryption    = true

      lifecycle_rules = [
        {
          id     = "backups-lifecycle"
          status = "Enabled"
          transitions = [
            {
              days          = 7
              storage_class = "STANDARD_IA"
            },
            {
              days          = 30
              storage_class = "GLACIER"
            }
          ]
          expiration = {
            days = 365
          }
        }
      ]
    }

    logs = {
      bucket_prefix = "${local.name_prefix}-logs"
      versioning    = true
      encryption    = true

      lifecycle_rules = [
        {
          id     = "logs-lifecycle"
          status = "Enabled"
          transitions = [
            {
              days          = 14
              storage_class = "STANDARD_IA"
            },
            {
              days          = 30
              storage_class = "GLACIER"
            }
          ]
          expiration = {
            days = 90
          }
        }
      ]
    }
  }

  tags = merge(local.common_tags, {})
}

module "cloudfront" {
  source = "./modules/cloudfront"

  environment = var.environment
  domain_name = var.domain_name

  s3_bucket_domain_name = module.s3.buckets.uploads.bucket_domain_name

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-cloudfront"
  })
}

module "monitoring" {
  source = "./modules/monitoring"

  environment  = var.environment
  cluster_name = local.cluster_name

  depends_on = [module.eks]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-monitoring"
  })
}

# IAM Policies
resource "aws_iam_policy" "rag_app_policy" {
  name        = "${local.name_prefix}-app-policy"
  description = "IAM policy for RAG system application"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          module.s3.buckets.uploads.arn,
          module.s3.buckets.uploads.arn + "/*",
          module.s3.buckets.models.arn,
          module.s3.buckets.models.arn + "/*",
          module.s3.buckets.backups.arn,
          module.s3.buckets.backups.arn + "/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricData",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      }
    ]
  })

  tags = local.common_tags
}

# Outputs
output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  description = "EKS cluster certificate authority data"
  value       = module.eks.cluster_certificate_authority_data
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "database_endpoint" {
  description = "RDS database endpoint"
  value       = module.rds.instance_endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.elasticache.primary_endpoint_address
  sensitive   = true
}

output "s3_buckets" {
  description = "S3 bucket information"
  value       = module.s3.buckets
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = module.cloudfront.domain_name
}