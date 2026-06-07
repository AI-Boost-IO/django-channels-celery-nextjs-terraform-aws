# 06 — Deployment

## Split deployment topology

```
┌─────────────────────────────────────────────────────────────────┐
│  GitHub repository                                               │
│  ├── ui/              → Vercel (automatic on git push)          │
│  └── api/             → EC2 via GitHub Actions deploy.yml       │
└─────────────────────────────────────────────────────────────────┘
```

- **Frontend (Next.js)** → **Vercel**: connected to the repo's `ui/` directory via Vercel dashboard. A push to `main` triggers Vercel's build and deployment automatically — no GitHub Actions workflow step is needed for the frontend.
- **Backend (Django API)** → **AWS EC2**: `deploy.yml` builds the Docker image, pushes to GHCR, then SSH's into the EC2 instance and runs `docker compose pull && docker compose up -d`.
- Both stacks communicate exclusively over HTTPS/WSS via the public domain — they share no Docker network.

## Docker Compose folder pattern

```
.docker/
├── development/
│   ├── docker-compose.yaml         # All services + ui for local convenience
│   ├── api/
│   │   ├── Dockerfile              # Python 3.12 + uv dev image
│   │   └── entrypoint.sh          # migrate + daphne
│   ├── api-beat/
│   │   └── entrypoint.sh          # register_periodic_tasks + celery beat
│   └── api-worker/
│       └── entrypoint.sh          # celery worker
└── production/
    ├── docker-compose.yaml         # API services + Traefik; NO ui service
    ├── api/
    │   ├── Dockerfile              # Multi-stage production build
    │   └── entrypoint.sh
    ├── api-beat/
    │   └── entrypoint.sh
    └── api-worker/
        └── entrypoint.sh
```

### Development compose

```bash
docker compose -f .docker/development/docker-compose.yaml up
```

Includes: `db` (Postgres), `cache` (Redis), `api` (daphne), `api-beat`, `api-worker`, `ui` (Next.js dev server for convenience).

All services mount the source tree as a volume for hot reload. The `api` image is built from `.docker/development/api/Dockerfile`; beat and worker **reuse the same image** with a different entrypoint.

### Production compose

```bash
# Run on EC2 (automated by deploy.yml)
docker compose -f .docker/production/docker-compose.yaml pull
docker compose -f .docker/production/docker-compose.yaml up -d
```

Includes: `db`, `cache`, `api`, `api-beat`, `api-worker`, `traefik`. **No `ui` service** — Vercel handles the frontend.

Services use named volumes for persistent data. Images are pulled from GHCR (pre-built by `deploy.yml`). Traefik routes `api.example.com` → `api:8000` with automatic Let's Encrypt TLS.

## Vercel configuration

`vercel.json` contains **only security headers**. All environment variables are managed in the Vercel dashboard.

```json
// sample/infra/vercel.json
{
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" }
      ]
    }
  ]
}
```

Vercel environment variables to set in the dashboard:

| Variable | Example value |
|----------|--------------|
| `NEXT_PUBLIC_API_URL` | `https://api.example.com` |
| `NEXT_PUBLIC_WS_URL` | `wss://api.example.com` |
| `SSR_API_URL` | `https://api.example.com` |

## Terraform stack

Flat layout — all resources in one directory, separate files by concern:

```
.terraform/
├── main.tf          # Provider, backend, locals, tags
├── networking.tf    # VPC, subnet, IGW, route table, security groups
├── compute.tf       # EC2 instance, EIP, key pair
├── storage.tf       # S3 bucket, IAM role + instance profile
├── variables.tf     # Input variables
├── outputs.tf       # Public IP, S3 bucket name
└── user_data.sh     # EC2 bootstrap: Docker + Compose installation
```

```hcl
# main.tf — provider and backend
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "s3" {
    bucket = "myorg-terraform-state"
    key    = "v1-mono/terraform.tfstate"
    region = "eu-west-1"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
```

Resources created:
- VPC with public subnet, internet gateway, route table
- Security group allowing 80, 443 (Traefik) and 22 (SSH from CI)
- EC2 `t3.small` (or larger) with attached EIP
- S3 bucket for media/static with private ACL
- IAM role + instance profile granting `s3:GetObject`, `s3:PutObject` on the bucket

## GitHub Actions workflows

### `ci.yml` — runs on every PR

```yaml
on: [pull_request]
jobs:
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: bun install
        working-directory: ui
      - run: bun run codegen
        working-directory: ui
      - run: bun run typecheck
        working-directory: ui

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: bun install
        working-directory: ui
      - run: bunx biome check .
        working-directory: ui

  commitlint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: wagoid/commitlint-github-action@v6
```

### `deploy.yml` — runs on push to `main`

```yaml
on:
  push:
    branches: [main]

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push API image
        uses: docker/build-push-action@v6
        with:
          context: api
          file: .docker/production/api/Dockerfile
          push: true
          tags: ghcr.io/myorg/v1-mono-api:latest

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - name: SSH deploy to EC2
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ec2-user
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /opt/v1-mono
            docker compose -f .docker/production/docker-compose.yaml pull
            docker compose -f .docker/production/docker-compose.yaml up -d --remove-orphans
            docker image prune -f
```

Vercel deploys automatically from the same push — no additional step is needed.

## Django production settings for Vercel CORS

```python
# config/settings/production.py
import os

# Allow the Vercel deployment domain to make authenticated requests
CSRF_TRUSTED_ORIGINS = [
    f"https://{os.environ.get('DOMAIN', '')}",
    f"https://{os.environ.get('VERCEL_DOMAIN', '')}",  # e.g. myapp.vercel.app
]

CORS_ALLOWED_ORIGINS = [
    f"https://{os.environ.get('DOMAIN', '')}",
    f"https://{os.environ.get('VERCEL_DOMAIN', '')}",
]

CORS_ALLOW_CREDENTIALS = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "None"  # Required for cross-origin cookie auth
CSRF_COOKIE_SAMESITE = "None"
```
