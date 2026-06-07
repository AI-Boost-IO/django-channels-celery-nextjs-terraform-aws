# 04 — Celery Workers + Beat Scheduler

## Celery application setup

```python
# config/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("myproject")

# Read Celery config from Django settings — all keys prefixed with CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover tasks from logic/tasks/ — keeps tasks out of Django apps
app.autodiscover_tasks(["logic.tasks"])
```

```python
# config/__init__.py — ensures Celery is loaded when Django starts
from .celery import app as celery_app

__all__ = ("celery_app",)
```

## Key settings

```python
# config/settings/common.py
import os

_redis_host = os.environ.get("CACHE_URL", "localhost")

# Broker on DB 0, results on DB 1 — separate DBs avoid key collisions
CELERY_BROKER_URL = f"redis://{_redis_host}:6379/0"
CELERY_RESULT_BACKEND = f"redis://{_redis_host}:6379/1"

# Use DB-backed scheduler so tasks survive restarts and are visible in admin
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

# acks_late = True: task is acknowledged only after it completes successfully.
# If the worker crashes mid-task, the broker re-queues it automatically.
CELERY_TASK_ACKS_LATE = True

# Reject tasks and re-queue on worker loss (requires acks_late)
CELERY_TASK_REJECT_ON_WORKER_LOST = True

CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXPIRES = 60 * 60 * 24  # 24 hours
```

## Periodic task registration via management command

Periodic tasks are registered in the `PeriodicTask` database table at Beat startup — **not hardcoded in settings**. This approach means:

- Tasks survive DB resets (re-registering is idempotent)
- They are visible and editable in Django admin
- Adding/changing a schedule only requires an entrypoint restart, not a code change

```python
# apps/core/management/commands/register_periodic_tasks.py
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask
import json


class Command(BaseCommand):
    help = "Register or update periodic Celery tasks in the DB scheduler"

    def handle(self, *args, **options) -> None:
        self._register_hourly_cleanup()
        self._register_daily_report()
        self.stdout.write(self.style.SUCCESS("Periodic tasks registered."))

    def _register_hourly_cleanup(self) -> None:
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=60,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.update_or_create(
            name="Hourly cleanup",
            defaults={
                "task": "tasks.cleanup_stale_sessions",
                "interval": schedule,
                "args": json.dumps([]),
            },
        )

    def _register_daily_report(self) -> None:
        schedule, _ = CrontabSchedule.objects.get_or_create(
            hour=7, minute=0,
            day_of_week="*", day_of_month="*", month_of_year="*",
        )
        PeriodicTask.objects.update_or_create(
            name="Daily usage report",
            defaults={
                "task": "tasks.send_daily_report",
                "crontab": schedule,
                "args": json.dumps([]),
            },
        )
```

The Beat entrypoint calls `python manage.py register_periodic_tasks` before starting `celery beat`:

```sh
# .docker/development/api-beat/entrypoint.sh
#!/bin/sh
set -e
python manage.py register_periodic_tasks
exec celery -A config beat --loglevel=info
```

## Three Docker services, one image

All three services share the **same Docker image** — they differ only in their entrypoint script. This avoids image drift: a worker always runs the identical code as the API server.

```
.docker/
├── development/
│   ├── api/
│   │   ├── Dockerfile      # One image for all three roles
│   │   └── entrypoint.sh   # migrate + daphne
│   ├── api-beat/
│   │   └── entrypoint.sh   # register_periodic_tasks + celery beat
│   └── api-worker/
│       └── entrypoint.sh   # celery worker
└── production/
    ├── api/
    │   ├── Dockerfile      # Multi-stage production build
    │   └── entrypoint.sh
    ├── api-beat/
    │   └── entrypoint.sh
    └── api-worker/
        └── entrypoint.sh
```

```yaml
# .docker/development/docker-compose.yaml (relevant services)
services:
  api:
    build:
      context: ../../api
      dockerfile: ../.docker/development/api/Dockerfile
    command: /entrypoint.sh

  api-beat:
    image: ${COMPOSE_PROJECT_NAME}-api  # Reuse the api image — no separate build
    command: /entrypoint-beat.sh

  api-worker:
    image: ${COMPOSE_PROJECT_NAME}-api
    command: /entrypoint-worker.sh
```

## Task categories

| Category | Examples | Notes |
|----------|---------|-------|
| LLM | `generate_summary`, `classify_document` | Long-running; may use `celery.result.AsyncResult` to poll from frontend |
| Email | `send_welcome_email`, `send_daily_digest` | Calls Next.js `/api/emails/` route for HTML rendering via React Email |
| Pub/sub broadcast | `process_and_broadcast` | Calls `channel_layer.group_send()` after completing work |
| Scheduled | `cleanup_stale_sessions`, `send_daily_report` | Registered via management command; run by Beat |
| File processing | `transcode_upload`, `extract_text_from_pdf` | May chain tasks; stores results in S3 |

## Example task with error handling

```python
# logic/tasks/example.py
import logging
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    acks_late=True,
    name="tasks.process_example",
    max_retries=3,
    default_retry_delay=60,  # seconds before first retry
)
def process_example(self, example_id: str) -> dict:
    """
    Process an example resource. Retries up to 3 times on transient errors.
    """
    try:
        # ... fetch, process, and store results ...
        result = {"status": "complete", "example_id": example_id}
        logger.info("Processed example %s", example_id)
        return result
    except Exception as exc:
        logger.warning("Task failed for example %s: %s", example_id, exc)
        try:
            raise self.retry(exc=exc, countdown=self.default_retry_delay * (self.request.retries + 1))
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded for example %s", example_id)
            raise
```

## Calling tasks from resolvers

Tasks are dispatched asynchronously from Strawberry mutation resolvers using `.delay()`:

```python
# logic/mutations/example.py
from logic.tasks.example import process_example


@strawberry.mutation(permission_classes=[IsAuthenticated])
async def trigger_processing(self, info: Info, example_id: strawberry.ID) -> str:
    # .delay() dispatches to the Celery worker queue immediately
    # The resolver returns without waiting for the task to complete
    task = process_example.delay(str(example_id))
    return task.id  # Return task ID so the client can poll or subscribe for completion
```
