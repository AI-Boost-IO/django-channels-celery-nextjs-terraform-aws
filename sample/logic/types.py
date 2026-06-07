"""
Strawberry type definitions for the GraphQL schema.

All types that back Django models are defined here using @strawberry_django.type.
This centralises the schema's type surface and keeps logic/ isolated from apps/.

Naming conventions:
  - Django model ExampleItem → Strawberry type ExampleItemType
  - Input types for mutations → ExampleItemInput
  - Subscription event types → ExampleItemEventType

DjangoOptimizerExtension (set globally in schema.py) automatically selects only
the columns referenced by each field, so you can annotate all model fields here
without worrying about over-fetching.

Replace 'myapp' and 'ExampleItem' with your app and model names.
"""

from __future__ import annotations

import strawberry
import strawberry_django
from strawberry import auto

from apps.myapp.models import ExampleItem


# ---------------------------------------------------------------------------
# Model-backed type
# ---------------------------------------------------------------------------

@strawberry_django.type(ExampleItem)
class ExampleItemType:
    """
    GraphQL representation of ExampleItem.

    Fields annotated with `auto` are automatically mapped to the corresponding
    Django model field type by strawberry-graphql-django.
    """

    id: auto           # UUID → strawberry.ID
    name: auto         # CharField → str
    description: auto  # TextField → str | None
    status: auto       # CharField with choices → str
    date_created: auto
    date_updated: auto
    # date_deleted is intentionally excluded — clients never see deleted records


# ---------------------------------------------------------------------------
# Subscription event type
# ---------------------------------------------------------------------------

@strawberry.type
class ExampleItemEventType:
    """
    Payload delivered to WebSocket subscribers when an ExampleItem changes.

    This is a plain Strawberry type (not model-backed) because subscription
    events are assembled in the Celery task, not fetched from the DB.
    """

    id: strawberry.ID
    event: str          # e.g. "created" | "updated" | "deleted"
    item: ExampleItemType | None = None  # Full item on create/update; None on delete


# ---------------------------------------------------------------------------
# Input types (used by mutations)
# ---------------------------------------------------------------------------

@strawberry_django.input(ExampleItem)
class ExampleItemInput:
    """Input for creating or updating an ExampleItem."""

    name: auto
    description: auto
    status: auto


@strawberry.input
class ExampleItemUpdateInput:
    """
    Partial update input — all fields optional except the ID.
    Use when the client can update individual fields without sending the full object.
    """

    id: strawberry.ID
    name: str | None = None
    description: str | None = None
    status: str | None = None
