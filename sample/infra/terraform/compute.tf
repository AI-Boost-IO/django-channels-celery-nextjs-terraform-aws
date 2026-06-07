/**
 * Terraform — compute.tf
 *
 * EC2 instance, Elastic IP, and SSH key pair.
 *
 * The instance runs all backend services via Docker Compose:
 *   db, cache, api, api-beat, api-worker, traefik
 *
 * user_data.sh bootstraps Docker and Docker Compose on first boot.
 *
 * An Elastic IP ensures the DNS record (managed outside Terraform) does not
 * need to change when the instance is stopped and restarted.
 */

# ---------------------------------------------------------------------------
# SSH key pair — import from the public key in var.ssh_public_key
# ---------------------------------------------------------------------------

resource "aws_key_pair" "deployer" {
  key_name   = "${var.project_name}-${var.environment}-deployer"
  public_key = var.ssh_public_key
}

# ---------------------------------------------------------------------------
# IAM instance profile — grants the EC2 instance access to S3
# (see storage.tf for the IAM role and policy)
# ---------------------------------------------------------------------------

# Referenced from storage.tf — declared here for readability
# aws_iam_instance_profile.ec2 is defined in storage.tf

# ---------------------------------------------------------------------------
# EC2 instance
# ---------------------------------------------------------------------------

resource "aws_instance" "api" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type  # e.g. t3.small
  key_name               = aws_key_pair.deployer.key_name
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web.id, aws_security_group.ssh.id]

  # Attach the IAM instance profile so Docker containers can access S3 via IAM role
  # without embedding AWS credentials in environment variables.
  iam_instance_profile = aws_iam_instance_profile.ec2.name

  # Bootstrap script: installs Docker and Docker Compose on first boot.
  # The deploy.yml workflow handles subsequent deployments via SSH.
  user_data = file("${path.module}/user_data.sh")

  # Use gp3 for better IOPS/throughput than gp2 at the same price
  root_block_device {
    volume_type = "gp3"
    volume_size = 30   # GB — adjust based on DB growth expectations
    encrypted   = true
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-api"
  }

  # Allow Terraform to replace the instance if the AMI or user_data changes,
  # rather than modifying it in place (Docker state would be lost anyway).
  lifecycle {
    create_before_destroy = true
  }
}

# ---------------------------------------------------------------------------
# Elastic IP — stable public IP regardless of instance stop/start
# ---------------------------------------------------------------------------

resource "aws_eip" "api" {
  instance = aws_instance.api.id
  domain   = "vpc"

  tags = {
    Name = "${var.project_name}-${var.environment}-api-eip"
  }

  # EIP must be released before the IGW is destroyed
  depends_on = [aws_internet_gateway.main]
}
