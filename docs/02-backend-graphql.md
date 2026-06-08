# 02 — Backend: Django + Strawberry GraphQL

## Django project structure

The core principle: **apps own models; `logic/` owns everything else.**

```
api/
├── config/                         # Django project package
│   ├── settings/
│   │   ├── common.py               # Shared: INSTALLED_APPS, middleware, Channels, Celery
│   │   ├── development.py          # Local overrides: DEBUG, permissive CORS, local Postgres
│   │   ├── production.py           # S3 storage, secure cookies, domain CORS, whitenoise
│   │   └── ci.py                   # InMemoryChannelLayer, CELERY_TASK_ALWAYS_EAGER
│   ├── asgi.py                     # ASGI entry point and URL routing
│   ├── celery.py                   # Celery application instance
│   └── urls.py                     # Django URL conf (admin + webhooks only — GraphQL is ASGI)
├── apps/
│   ├── authentication/             # User, Profile, Token models
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   └── profile.py
│   │   ├── admin.py
│   │   └── migrations/
│   └── <domain>/                   # e.g. stories, documents, workspaces
│       ├── models/
│       └── migrations/
├── logic/
│   ├── queries/                    # @strawberry.field resolver functions
│   ├── mutations/                  # Mutation classes with @strawberry.mutation fields
│   ├── subscriptions/              # Async generator subscriptions
│   ├── tasks/                      # @shared_task Celery functions
│   ├── email/                      # Email dispatch helpers (HTTP call to Next.js route)
│   └── types.py                    # All @strawberry_django.type definitions
├── gql/
│   ├── schema.py                   # Root Schema — wire Query + Mutation + Subscription
│   ├── query.py                    # Root Query type aggregating logic/queries/
│   ├── mutation.py                 # Root Mutation type aggregating logic/mutations/
│   ├── subscription.py             # Root Subscription type
│   ├── consumers.py                # Channels HTTP + WS consumers
│   ├── cors_middleware.py          # ASGI CORS wrapper
│   └── schema.graphql              # Exported SDL — source of truth for frontend codegen
├── base/
│   ├── model.py                    # BaseModel (UUID PK, soft-delete, version)
│   └── type.py                     # BaseType for queryset-level access control
└── utilities/
    ├── s3.py                       # Presigned URLs, multipart upload helpers
    └── prompt/                     # Abstracted LLM client (OpenAI / Anthropic)
```

## INSTALLED_APPS

`daphne` **must be listed first** — it patches Django's dev server to accept ASGI connections.

```python
# config/settings/common.py
INSTALLED_APPS = [
    "daphne",                        # Must be first — overrides Django's WSGI runserver
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "channels",                      # WebSocket support
    "corsheaders",                   # CORS headers middleware
    "strawberry_django",             # Strawberry + Django integration
    "django_celery_beat",            # DB-backed periodic task scheduler
    "storages",                      # S3 via django-storages
    # Local apps
    "apps.authentication",
    "apps.yourapp",
]
```

## Key settings blocks

See `sample/backend/config/settings/common.py` for the full annotated file.

```python
# ASGI application entry point
ASGI_APPLICATION = "config.asgi.application"

# Channel layer — Redis pub/sub for subscriptions
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [(os.environ.get("CACHE_URL", "localhost"), 6379)]},
    }
}

# Celery — broker on Redis DB 0, results on Redis DB 1
CELERY_BROKER_URL = f"redis://{os.environ.get('CACHE_URL', 'localhost')}:6379/0"
CELERY_RESULT_BACKEND = f"redis://{os.environ.get('CACHE_URL', 'localhost')}:6379/1"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_ACKS_LATE = True        # Task is acknowledged only after completion — safe retry on crash

# Custom user model
AUTH_USER_MODEL = "authentication.User"
```

## Strawberry schema assembly

Four files in `gql/` assemble the schema; resolvers live in `logic/`.

```
gql/
├── schema.py        # Root Schema — wires Query + Mutation + Subscription + extensions
├── query.py         # Root Query type — re-exports fields from logic/queries/
├── mutation.py      # Root Mutation type
├── subscription.py  # Root Subscription type
└── schema.graphql   # Exported SDL — written by `manage.py export_schema`
```

**`gql/schema.py`**
```python
import strawberry
from strawberry_django.optimizer import DjangoOptimizerExtension
from .query import Query
from .mutation import Mutation
from .subscription import Subscription

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    extensions=[
        # Automatically selects only the DB columns needed for each response field.
        # Eliminates N+1 queries without manual prefetch_related() calls.
        DjangoOptimizerExtension,
    ],
)
```

**`gql/query.py`**
```python
import strawberry
from logic.permissions import IsAuthenticated
from logic.queries.example import example_item, example_items
from logic.types import ExampleItemType

@strawberry.type
class Query:
    # Declare permission_classes here — NOT on the resolver function.
    # Decorating the resolver with @strawberry.field and also passing it as
    # resolver= below double-wraps the field and crashes at schema build time.
    example_item: ExampleItemType | None = strawberry.field(
        resolver=example_item,
        permission_classes=[IsAuthenticated],
    )
    example_items: list[ExampleItemType] = strawberry.field(
        resolver=example_items,
        permission_classes=[IsAuthenticated],
    )
```

## BaseModel

Every domain model inherits `BaseModel` for consistent PKs, soft-delete, and concurrency control.

```python
# base/model.py
import uuid
from django.db import models

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    # Soft-delete: filter active records with .filter(date_deleted__isnull=True)
    date_deleted = models.DateTimeField(null=True, blank=True)
    # Optimistic concurrency: increment on every save; compare before updates
    version = models.IntegerField(default=0)

    class Meta:
        abstract = True
```

Soft-delete convention: never call `.delete()` — set `date_deleted = timezone.now()` and save. Active records are filtered at the queryset level via a custom manager.

## Permissions

Permission classes live in `logic/permissions.py` and inherit `BasePermission`.

```python
# logic/permissions.py
from strawberry.permission import BasePermission
from strawberry.types import Info

class IsAuthenticated(BasePermission):
    """Deny access to unauthenticated users."""
    message = "You must be logged in to access this resource."

    async def has_permission(self, source: object, info: Info, **kwargs: object) -> bool:
        request = info.context.get("request")
        if request is None:
            return False
        return bool(request.user.is_authenticated)


class IsAdmin(BasePermission):
    """Restrict to staff or admin users."""
    message = "Admin access required."

    async def has_permission(self, source: object, info: Info, **kwargs: object) -> bool:
        request = info.context.get("request")
        if request is None:
            return False
        return bool(request.user.is_authenticated and request.user.is_staff)
```

Apply `permission_classes` in the type declaration in `gql/query.py` or `gql/mutation.py` — **not** on the resolver function itself. Decorating a resolver with `@strawberry.field` and then passing it as `resolver=` double-wraps the field and raises a `TypeError` at schema build time.

```python
# gql/query.py
@strawberry.type
class Query:
    my_field: MyType | None = strawberry.field(
        resolver=my_resolver,           # plain function, no @strawberry.field decorator
        permission_classes=[IsAuthenticated],
    )
```

## Formatting and linting

Ruff replaces Black, Flake8, and isort with a single Rust-based tool configured in `api/pyproject.toml`.

```toml
# api/pyproject.toml
[tool.ruff]
line-length = 88
target-version = "py312"
# Django migration files are auto-generated and contain patterns Ruff would flag.
exclude = ["**/migrations/**"]

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # Pyflakes — undefined names, unused imports
    "I",   # isort — import ordering
    "B",   # flake8-bugbear — likely bugs and design problems
    "UP",  # pyupgrade — modernise syntax for the target Python version
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
docstring-code-format = true
```

**Common commands (run from `api/`):**

```bash
uv run ruff format .          # Format all Python files
uv run ruff check .           # Lint — report only
uv run ruff check --fix .     # Lint + apply auto-fixes
```

The VS Code Ruff extension (`charliermarsh.ruff`) reads `[tool.ruff]` directly from `pyproject.toml` and applies format-on-save and inline lint diagnostics automatically — no separate editor config needed. Install it via `.vscode/extensions.json` recommendations.

## Schema export + codegen

After changing the schema, run the export and regenerate types:

```bash
# In the api/ directory
python manage.py export_schema gql.schema --path gql/schema.graphql

# Sync to the ui/ directory (run from monorepo root)
./scripts/graphql-sync.sh

# In the ui/ directory
bun run codegen
```

The generated types under `ui/src/__generated__/` are committed to the repo. The GitHub Actions CI job runs `tsc --noEmit` which fails if the schema changed but types were not regenerated — catching drift early.
