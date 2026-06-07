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
├── graphql/
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

Four files in `graphql/` assemble the schema; resolvers live in `logic/`.

```
graphql/
├── schema.py        # Root Schema — wires Query + Mutation + Subscription + extensions
├── query.py         # Root Query type — re-exports fields from logic/queries/
├── mutation.py      # Root Mutation type
├── subscription.py  # Root Subscription type
└── schema.graphql   # Exported SDL — written by `manage.py export_schema`
```

**`graphql/schema.py`**
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

**`graphql/query.py`**
```python
import strawberry
from logic.queries.example import example_query

@strawberry.type
class Query:
    example: ExampleType = strawberry.field(resolver=example_query)
    # Add more fields here as the schema grows
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

Permission classes live in `logic/permissions/` and compose on resolvers.

```python
# logic/permissions/permissions.py
from strawberry_django.auth.utils import get_current_user

class IsAuthenticated:
    """Rejects unauthenticated requests at the resolver level."""
    message = "Authentication required."

    async def has_permission(self, source, info, **kwargs) -> bool:
        user = await get_current_user(info)
        return user is not None and user.is_authenticated


class IsAdmin:
    """Restricts to users with the admin role."""
    message = "Admin access required."

    async def has_permission(self, source, info, **kwargs) -> bool:
        user = await get_current_user(info)
        if user is None or not user.is_authenticated:
            return False
        return await user.profile.arole == "admin"
```

Apply at the resolver with `permission_classes`:

```python
@strawberry.field(permission_classes=[IsAuthenticated])
async def my_query(self, info: Info) -> MyType:
    ...
```

## Schema export + codegen

After changing the schema, run the export and regenerate types:

```bash
# In the api/ directory
python manage.py export_schema graphql.schema --path graphql/schema.graphql

# Sync to the ui/ directory (run from monorepo root)
./scripts/graphql-sync.sh

# In the ui/ directory
bun run codegen
```

The generated types under `ui/src/__generated__/` are committed to the repo. The GitHub Actions CI job runs `tsc --noEmit` which fails if the schema changed but types were not regenerated — catching drift early.
