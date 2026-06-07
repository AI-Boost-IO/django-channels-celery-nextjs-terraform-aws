"""
BaseModel — abstract model inherited by every domain model in the project.

Provides:
  - UUID primary key: avoids integer ID enumeration and works across distributed systems.
  - Soft-delete via date_deleted: records are never hard-deleted; query active records
    with `.filter(date_deleted__isnull=True)` via the `objects` manager.
  - Optimistic versioning via `version`: increment on every save to detect concurrent
    writes without database-level locking.
  - Automatic timestamps: date_created and date_updated are managed by the database.

Usage:
    from base.model import BaseModel

    class YourModel(BaseModel):
        name = models.CharField(max_length=255)

        class Meta:
            db_table = "yourapp_yourmodel"
"""

import uuid

from django.db import models
from django.utils import timezone


class ActiveManager(models.Manager["BaseModel"]):
    """Default manager — filters out soft-deleted records automatically."""

    def get_queryset(self) -> models.QuerySet["BaseModel"]:
        return super().get_queryset().filter(date_deleted__isnull=True)


class AllObjectsManager(models.Manager["BaseModel"]):
    """Bypass soft-delete filter — use when you need access to deleted records."""

    def get_queryset(self) -> models.QuerySet["BaseModel"]:
        return super().get_queryset()


class BaseModel(models.Model):
    """Abstract base model for all domain entities."""

    # UUID primary key — set at Python level so the ID is known before the first
    # database write (useful for passing IDs to async tasks before committing).
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)

    # Soft-delete: set this field instead of calling .delete().
    # ActiveManager filters this out so most queries never see deleted records.
    date_deleted = models.DateTimeField(null=True, blank=True, db_index=True)

    # Optimistic concurrency control: check that version matches before saving.
    # Increment in the mutation or service layer to detect concurrent modifications.
    version = models.IntegerField(default=0)

    # Use ActiveManager as default so `.objects.all()` returns only active records.
    objects: ActiveManager = ActiveManager()
    # Explicit manager to access all records including soft-deleted ones.
    all_objects: AllObjectsManager = AllObjectsManager()

    class Meta:
        abstract = True
        # Default ordering by creation time — override in concrete models as needed.
        ordering = ["-date_created"]

    def soft_delete(self) -> None:
        """Mark the record as deleted without removing it from the database."""
        self.date_deleted = timezone.now()
        self.save(update_fields=["date_deleted", "date_updated"])

    def save(self, *args, **kwargs) -> None:
        """Increment version on every save to support optimistic locking."""
        self.version += 1
        super().save(*args, **kwargs)
