/**
 * Terraform — variables.tf
 *
 * All input variables for the stack.
 * Values are provided via terraform.tfvars or CI environment variables.
 * Sensitive values (ssh_public_key, domain) should be passed via
 * -var flags or a .tfvars file that is NOT committed to the repository.
 */

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Short project slug used in resource names and tags"
  type        = string
  default     = "myproject"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,19}$", var.project_name))
    error_message = "project_name must be 3-20 lowercase letters, digits, or hyphens."
  }
}

variable "environment" {
  description = "Deployment environment — used in resource names and tags"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be 'staging' or 'production'."
  }
}

variable "instance_type" {
  description = "EC2 instance type for the API server"
  type        = string
  default     = "t3.small"
}

variable "ssh_public_key" {
  description = "SSH public key content for the EC2 key pair (used by CI for deployment)"
  type        = string
  sensitive   = true
}

variable "domain" {
  description = "Primary domain (e.g. example.com) — used for CORS, Traefik routing"
  type        = string
}

variable "vercel_domain" {
  description = "Vercel deployment domain (e.g. myapp.vercel.app) — added to CORS/CSRF allowed origins"
  type        = string
  default     = ""
}
