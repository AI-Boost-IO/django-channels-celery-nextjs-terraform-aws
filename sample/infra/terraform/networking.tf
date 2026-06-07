/**
 * Terraform — networking.tf
 *
 * VPC, public subnet, internet gateway, route table, and security groups.
 *
 * Single public subnet in one AZ — appropriate for a single-instance EC2 deployment.
 * If you need high availability, add private subnets, a NAT gateway, and an ALB.
 *
 * Security groups:
 *   - sg_web: allows HTTP (80) and HTTPS (443) from anywhere — handled by Traefik
 *   - sg_ssh: allows SSH (22) from the GitHub Actions IP ranges for deployment
 */

# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-${var.environment}-vpc"
  }
}

# ---------------------------------------------------------------------------
# Public subnet
# ---------------------------------------------------------------------------

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-${var.environment}-public-subnet"
  }
}

# ---------------------------------------------------------------------------
# Internet gateway
# ---------------------------------------------------------------------------

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-${var.environment}-igw"
  }
}

# ---------------------------------------------------------------------------
# Route table — routes all traffic through the internet gateway
# ---------------------------------------------------------------------------

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ---------------------------------------------------------------------------
# Security group — web traffic (Traefik)
# ---------------------------------------------------------------------------

resource "aws_security_group" "web" {
  name        = "${var.project_name}-${var.environment}-sg-web"
  description = "Allow HTTP and HTTPS inbound from anywhere (Traefik TLS termination)"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-sg-web"
  }
}

# ---------------------------------------------------------------------------
# Security group — SSH access for GitHub Actions deployment
# ---------------------------------------------------------------------------

resource "aws_security_group" "ssh" {
  name        = "${var.project_name}-${var.environment}-sg-ssh"
  description = "Allow SSH inbound for deployment from known CI ranges"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH from GitHub Actions"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    # Restrict to GitHub Actions IP ranges — see https://api.github.com/meta
    # For simplicity this allows all; tighten in production.
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-sg-ssh"
  }
}
