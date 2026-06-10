# django-channels-celery-nextjs-terraform-aws

Full-stack skeleton for Django + Strawberry GraphQL + Django Channels + Celery + Next.js 16 + Material UI v9 + Terraform/AWS — the canonical pattern for a monorepo SaaS backend on EC2 with a Vercel-deployed frontend.

## What this covers

| Doc | Topic |
|-----|-------|
| `docs/01-overview.md` | Architecture diagram, component roles, monorepo layout, shared conventions |
| `docs/02-backend-graphql.md` | Django project structure, Strawberry GraphQL schema assembly, BaseModel, permissions |
| `docs/03-realtime-channels.md` | Django Channels ASGI routing, WebSocket subscriptions, Redis pub/sub pattern |
| `docs/04-celery-workers.md` | Celery config, Beat scheduler, periodic task registration, Docker service split |
| `docs/05-frontend.md` | Next.js 16 App Router, Apollo Client 4, MUI v9, codegen workflow, email pattern |
| `docs/06-deployment.md` | Docker Compose layout, Terraform AWS, GitHub Actions CI/CD, Vercel deployment, local ops scripts |

## Sample code

| File | Description |
|------|-------------|
| `sample/backend/pyproject.toml` | uv project manifest — Django dependencies + Ruff formatter/linter config |
| `sample/backend/config/asgi.py` | ASGI routing — `GraphQLProtocolTypeRouter` + auth-aware production variant |
| `sample/backend/config/celery.py` | Celery app with Redis broker, result backend, task autodiscovery |
| `sample/backend/config/settings/common.py` | Shared Django settings — INSTALLED_APPS, CHANNEL_LAYERS, CELERY_* |
| `sample/backend/config/settings/production.py` | Production settings — secure cookies, whitenoise, CSRF for Vercel |
| `sample/backend/base/model.py` | BaseModel with UUID PK, soft-delete, and optimistic versioning |
| `sample/backend/gql/schema.py` | Strawberry schema assembly — Query, Mutation, Subscription + extensions |
| `sample/backend/gql/consumers.py` | GraphQL HTTP and WebSocket consumers with JWT auth middleware |
| `sample/backend/gql/cors_middleware.py` | ASGI CORS wrapper for the GraphQL consumer |
| `sample/logic/types.py` | Strawberry type backed by a Django model |
| `sample/logic/queries/example.py` | Example query resolver with permission check |
| `sample/logic/mutations/example.py` | Example mutation with input type |
| `sample/logic/subscriptions/example.py` | Async generator subscription reading from channel layer |
| `sample/logic/tasks/example.py` | Celery task with pub/sub + periodic task management command |
| `sample/frontend/next.config.ts` | Next.js 16 config — Turbopack is the default bundler; top-level `turbopack` block for custom rules/aliases |
| `sample/frontend/biome.json` | Biome v2 config — formatter (single quotes, 100-char lines), linter, import organiser |
| `sample/frontend/lib/apollo-client.ts` | Apollo Client 4 with HTTP + WebSocket split link, `ApolloWrapper` component for Next.js 16 |
| `sample/frontend/lib/rsc-client.ts` | Per-request Apollo client for React Server Components (`getClient`) |
| `sample/frontend/components/ThemeRegistry.tsx` | MUI v9 ThemeProvider wired for Next.js App Router SSR |
| `sample/frontend/codegen.ts` | GraphQL codegen config pointing at the Django-exported schema |
| `sample/infra/.vscode/settings.json` | VS Code format-on-save settings — Ruff for Python, Biome for TypeScript |
| `sample/infra/.vscode/extensions.json` | VS Code extension recommendations — ms-python, charliermarsh.ruff, biomejs.biome |
| `sample/infra/.docker/development/docker-compose.yaml` | Development services with hot-reload source mounts |
| `sample/infra/.docker/production/docker-compose.yaml` | Production services — API on EC2, no ui service (Vercel handles it) |
| `sample/infra/.docker/development/api/Dockerfile` | Development API image (Python 3.12 + uv) |
| `sample/infra/.docker/production/api/Dockerfile` | Production API image (multi-stage, non-root) |
| `sample/infra/terraform/main.tf` | Terraform AWS provider, VPC, EC2, EIP, S3, IAM (flat stack) |
| `sample/infra/.github-workflows/deploy.yml` | Build API image → push to GHCR → SSH deploy to EC2 |
| `sample/scripts/_common.sh` | Shared bootstrap — resolves EC2_HOST (env → Terraform output) and SSH key |
| `sample/scripts/.scripts.env.example` | Template for EC2_HOST + EC2_SSH_KEY on a new machine |
| `sample/scripts/connect.sh` | Open an interactive SSH shell on the EC2 instance |
| `sample/scripts/deploy.sh` | Manual deploy: git pull + docker compose up (mirrors CI workflow) |
| `sample/scripts/logs.sh` | Stream or dump service logs — supports `--tail N` and `--no-follow` |
| `sample/scripts/db.sh` | DB access: `psql`, `tunnel` (GUI tools), `dump`, `restore`, `query` |
| `sample/scripts/graphql-sync.sh` | Export GraphQL schema from Django + regenerate frontend types |

## Quick start

1. **Copy `sample/backend/`** into your monorepo as `api/`. Replace `myproject` and `myapp` placeholders with your project and app names.

2. **Copy `sample/logic/`** alongside `api/` as your resolver and task layer.

3. **Set up Python dependencies and formatting.** Copy `sample/backend/pyproject.toml` to `api/`, update the `name` field, then:
   ```bash
   uv sync --group dev
   ```
   This installs all Django dependencies and Ruff (formatter + linter) into `api/.venv`.

4. **Verify `INSTALLED_APPS`** — `daphne` must be first, followed by `channels`, `strawberry_django`, `django_celery_beat`, `corsheaders`.

5. **Copy `sample/frontend/`** into your Next.js `ui/` app and install dependencies:
   ```bash
   bun add @apollo/client @apollo/client-integration-nextjs graphql graphql-ws rxjs
   bun add @mui/material @mui/material-nextjs @emotion/react @emotion/styled
   bun add --dev --save-exact @biomejs/biome@^2.0.0
   ```
   The last line installs Biome locally — required for the VS Code extension LSP and for `bunx biome` CI commands.

   Copy `sample/frontend/next.config.ts` to `ui/next.config.ts`. Turbopack is the default bundler in Next.js 16 — no flags are needed. The `turbopack` block in the config is pre-populated with commented-out examples for custom loader rules and resolve aliases; remove entries you don't need.

6. **Set up VS Code formatting.** Copy `sample/infra/.vscode/` to `.vscode/` in your monorepo root, then open the project in VS Code. You will be prompted to install the recommended extensions (`charliermarsh.ruff` and `biomejs.biome`). Format-on-save activates immediately after installation.

7. **Copy `sample/infra/.docker/`** to `.docker/` in your monorepo root. Populate `.docker/development/api/.env` from the Key env vars table below.

8. **Start the dev environment:**
   ```bash
   docker compose -f .docker/development/docker-compose.yaml up
   ```

9. **Copy `sample/infra/terraform/`** to `.terraform/`. Edit the `locals` block in `main.tf`, then:
   ```bash
   terraform init && terraform plan && terraform apply
   ```

10. **Connect Vercel** to your repo's `ui/` directory via the Vercel dashboard. Set `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`, and `SSR_API_URL` as environment variables in Vercel — these are not in `vercel.json`.

## Key env vars

| Variable | Service | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | API | Django secret key |
| `DJANGO_SETTINGS_MODULE` | API | e.g. `config.settings.production` |
| `POSTGRES_DB` | API, compose | Database name |
| `POSTGRES_USER` | API, compose | Database user |
| `POSTGRES_PASSWORD` | API, compose | Database password |
| `POSTGRES_HOST` | API | Database host (e.g. `db` in Docker) |
| `POSTGRES_PORT` | API | Database port (default `5432`) |
| `CACHE_URL` | API, compose | Redis hostname — used by Celery broker and Channel layer |
| `DOMAIN` | API, compose | Primary domain for CORS, session cookies, and Traefik routing |
| `VERCEL_DOMAIN` | API | Vercel deployment URL added to `CSRF_TRUSTED_ORIGINS` |
| `ALLOWED_HOSTS` | API | Comma-separated allowed hostnames |
| `AWS_S3_BUCKET_NAME` | API | S3 bucket for media and static files |
| `AWS_S3_REGION_NAME` | API | S3 region |
| `OPENAI_API_KEY` | API | LLM provider — tasks degrade gracefully if unset |
| `ANTHROPIC_API_KEY` | API | LLM provider — optional |
| `NEXT_PUBLIC_API_URL` | Frontend | Browser-facing API base URL (e.g. `https://api.example.com`) |
| `NEXT_PUBLIC_WS_URL` | Frontend | WebSocket URL for subscriptions (e.g. `wss://api.example.com`) |
| `SSR_API_URL` | Frontend | Server-side API URL — internal Docker hostname in dev, same as API URL in prod |
| `ACME_EMAIL` | Traefik | Let's Encrypt certificate registration email |
| `GHCR_TOKEN` | CI | GitHub token for pushing images to GHCR |
| `EC2_HOST` | CI | EC2 public IP for SSH deploy |
| `EC2_SSH_KEY` | CI | Private key for SSH access to EC2 |
