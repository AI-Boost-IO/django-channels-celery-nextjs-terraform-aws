"""
Example Celery tasks: async processing and WebSocket broadcast via channel layer.

Two concerns are illustrated here:
  1. Async background processing with retry logic (process_and_broadcast).
  2. A periodic task registered via management command (not hardcoded in settings).

The management command at the bottom of this file is run by the api-beat entrypoint
before starting celery beat, so periodic tasks are always up-to-date in the DB.

See docs/04-celery-workers.md for the full Celery configuration reference.
"""

from __future__ import annotations

import json
import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: publish to channel layer
# ---------------------------------------------------------------------------

def _broadcast_event(item_id: str, event: str) -> None:
    """
    Send an event to all WebSocket consumers subscribed to the `example-{item_id}` group.

    async_to_sync bridges the synchronous Celery worker context into the
    async Django Channels channel layer API.
    """
    group_name = f"example-{item_id}"
    layer = get_channel_layer()

    async_to_sync(layer.group_send)(
        group_name,
        {
            # "type" maps to the message handler method name in the consumer:
            # "example.item.event" → example_item_event() method.
            # In the subscription generator we check message["type"] directly.
            "type": "example.item.event",
            "item_id": item_id,
            "event": event,  # "created" | "updated" | "deleted"
        },
    )
    logger.debug("Broadcast event=%s for item=%s", event, item_id)


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    acks_late=True,
    name="tasks.process_and_broadcast",
    max_retries=3,
    default_retry_delay=30,  # seconds — multiplied by retry count for back-off
)
def process_and_broadcast(self, item_id: str, event: str = "updated") -> dict:
    """
    Perform processing on an ExampleItem and broadcast the result to subscribers.

    Steps:
      1. Fetch the item and do any required work (LLM call, file processing, etc.)
      2. Persist the result.
      3. Broadcast the event to connected WebSocket clients via group_send.

    Retries up to max_retries times on transient errors with exponential back-off.
    acks_late=True ensures the task is re-queued if the worker crashes mid-execution.

    Called from mutations with:
        process_and_broadcast.delay(str(item.id), event="created")
    """
    from apps.myapp.models import ExampleItem

    try:
        item = ExampleItem.objects.get(id=item_id)

        # --- Do your async work here ---
        # e.g. result = call_llm(item.prompt)
        #      item.result = result
        #      item.status = "complete"
        #      item.save(update_fields=["result", "status", "date_updated"])

        logger.info("Processed item %s (event=%s)", item_id, event)

        # Broadcast to all WebSocket subscribers watching this item.
        _broadcast_event(item_id, event)

        return {"item_id": item_id, "event": event, "status": "ok"}

    except ExampleItem.DoesNotExist:
        # Item was soft-deleted before the task ran — skip silently.
        logger.warning("Task skipped: item %s not found", item_id)
        return {"item_id": item_id, "status": "skipped"}

    except Exception as exc:
        logger.warning(
            "Task failed for item %s (attempt %d): %s",
            item_id, self.request.retries + 1, exc,
        )
        try:
            # Exponential back-off: 30s, 60s, 90s
            raise self.retry(
                exc=exc,
                countdown=self.default_retry_delay * (self.request.retries + 1),
            )
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded for item %s", item_id)
            raise


# ---------------------------------------------------------------------------
# Periodic task (registered via management command, not hardcoded in settings)
# ---------------------------------------------------------------------------

@shared_task(bind=True, acks_late=True, name="tasks.daily_cleanup")
def daily_cleanup(self) -> dict:
    """
    Example periodic task: remove stale records older than 30 days.

    Registered in the DB by the management command below, called from
    the api-beat entrypoint before `celery beat` starts.
    """
    from django.utils import timezone
    import datetime

    cutoff = timezone.now() - datetime.timedelta(days=30)

    from apps.myapp.models import ExampleItem

    deleted_count, _ = ExampleItem.all_objects.filter(
        date_deleted__lt=cutoff
    ).delete()

    logger.info("Daily cleanup: removed %d records", deleted_count)
    return {"deleted": deleted_count}


# ---------------------------------------------------------------------------
# Management command: register periodic tasks in the DB scheduler
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    """
    Register or update periodic Celery tasks in django-celery-beat's DB scheduler.

    Run from the api-beat entrypoint before starting celery beat:
        python manage.py register_periodic_tasks

    Tasks are stored in the PeriodicTask table and visible in Django admin.
    Re-running the command is idempotent — it uses update_or_create.
    """

    help = "Register periodic Celery tasks"

    def handle(self, *args, **options) -> None:
        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        schedule, _ = CrontabSchedule.objects.get_or_create(
            hour=3, minute=0,
            day_of_week="*", day_of_month="*", month_of_year="*",
        )
        PeriodicTask.objects.update_or_create(
            name="Daily cleanup",
            defaults={
                "task": "tasks.daily_cleanup",
                "crontab": schedule,
                "args": json.dumps([]),
            },
        )
        self.stdout.write(self.style.SUCCESS("Periodic tasks registered."))
