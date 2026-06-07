/**
 * Terraform — outputs.tf
 *
 * Values printed after `terraform apply` that are needed for:
 *   - Pointing DNS records to the EC2 public IP
 *   - Setting EC2_HOST in GitHub Actions secrets
 *   - Configuring DJANGO_SETTINGS env vars with the S3 bucket name
 */

output "ec2_public_ip" {
  description = "Elastic IP address of the EC2 instance — point your DNS A record here"
  value       = aws_eip.api.public_ip
}

output "ec2_instance_id" {
  description = "EC2 instance ID — useful for SSM Session Manager access"
  value       = aws_instance.api.id
}

output "s3_media_bucket" {
  description = "S3 bucket name for media uploads — set as AWS_S3_BUCKET_NAME env var"
  value       = aws_s3_bucket.media.bucket
}

output "s3_media_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.media.arn
}

output "iam_instance_profile_name" {
  description = "IAM instance profile name attached to the EC2 instance"
  value       = aws_iam_instance_profile.ec2.name
}
