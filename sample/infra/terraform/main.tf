/**
 * Terraform — main.tf
 *
 * AWS provider, backend, and project-level locals.
 * All resources are tagged via the provider's default_tags block.
 *
 * Replace:
 *   myorg       → your GitHub org or company name
 *   myproject   → your project slug
 *   eu-west-1   → your preferred AWS region
 *
 * Backend: state is stored in S3. Create the state bucket manually before
 * running `terraform init`, or use a local backend for getting started.
 *
 * Usage:
 *   terraform init
 *   terraform plan -var-file=terraform.tfvars
 *   terraform apply -var-file=terraform.tfvars
 */

terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Remote state in S3 — create this bucket manually before `terraform init`
  backend "s3" {
    bucket  = "myorg-terraform-state"
    key     = "myproject/terraform.tfstate"
    region  = "eu-west-1"
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region

  # Default tags applied to every resource created by this stack.
  # Enables cost attribution, automated cleanup, and audit trails.
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Repository  = "github.com/myorg/v1-mono"
    }
  }
}

# ---------------------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------------------

# Look up the latest Amazon Linux 2023 AMI so compute.tf stays distribution-agnostic
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

# Caller identity — used to construct ARNs without hardcoding account IDs
data "aws_caller_identity" "current" {}
