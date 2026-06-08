"""
Example GraphQL query resolvers.

Resolvers are plain async functions that return Django querysets or model instances.
DjangoOptimizerExtension (registered on the schema) handles N+1 optimisation
automatically, so resolvers do not need manual prefetch_related() calls.

IMPORTANT — do NOT decorate these functions with @strawberry.field.
Doing so turns them into StrawberryField objects; if you then pass them as
resolver= in gql/query.py you get a double-wrapped field that crashes at startup.
Permission classes are declared in gql/query.py, not here.

These functions are imported by gql/query.py and attached to the Query type.

Replace 'myapp' and 'ExampleItem' with your app and model names.
"""

from __future__ import annotations

import strawberry
from strawberry.types import Info
from strawberry_django.auth.utils import get_current_user

from apps.myapp.models import ExampleItem
from logic.types import ExampleItemType


async def example_item(self: object, info: Info, id: strawberry.ID) -> ExampleItemType | None:
    """
    Return a single ExampleItem by ID, or None if not found.

    The resolver returns a queryset value that Strawberry maps to ExampleItemType.
    DjangoOptimizerExtension defers column selection until Strawberry resolves
    the actual fields requested in the GraphQL query.
    """
    try:
        # `.objects` uses ActiveManager — soft-deleted records are excluded automatically.
        item = await ExampleItem.objects.aget(id=id)
    except ExampleItem.DoesNotExist:
        return None

    # Authorisation: verify the authenticated user owns this resource.
    user = await get_current_user(info)
    if item.owner_id != user.id:
        # Return None rather than raising a permission error to avoid resource
        # enumeration — callers cannot distinguish "not found" from "not allowed".
        return None

    return item  # type: ignore[return-value]  # strawberry maps queryset instances


async def example_items(self: object, info: Info) -> list[ExampleItemType]:
    """
    Return all ExampleItems belonging to the authenticated user.

    Returns a queryset — DjangoOptimizerExtension resolves it lazily.
    """
    user = await get_current_user(info)
    # Filter at the queryset level so the DB does the work, not Python.
    return ExampleItem.objects.filter(owner=user)  # type: ignore[return-value]
