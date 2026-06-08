"""
Example GraphQL mutation resolvers.

Mutations follow this pattern:
  1. Authenticate the request via permission_classes (declared in gql/mutation.py).
  2. Validate input (Strawberry handles type coercion; add domain rules here).
  3. Mutate the database record.
  4. Dispatch a Celery task for async side-effects (email, broadcast, etc.).
  5. Return the updated type so the client can update its cache.

IMPORTANT — do NOT decorate these functions with @strawberry.mutation.
Doing so turns them into StrawberryField objects; if you then pass them as
resolver= in gql/mutation.py you get a double-wrapped field that crashes at startup.
Permission classes are declared in gql/mutation.py, not here.

These functions are imported by gql/mutation.py and collected into the Mutation type.

Replace 'myapp', 'ExampleItem', and task imports with your own.
"""

from __future__ import annotations

import strawberry
from strawberry.types import Info
from strawberry_django.auth.utils import get_current_user

from apps.myapp.models import ExampleItem
from logic.tasks.example import process_and_broadcast
from logic.types import ExampleItemInput, ExampleItemType, ExampleItemUpdateInput


async def create_example_item(
    self: object, info: Info, input: ExampleItemInput
) -> ExampleItemType:
    """
    Create a new ExampleItem owned by the authenticated user.

    After creation, dispatch an async Celery task to perform any side-effects
    (e.g. sending a welcome notification, indexing, or broadcasting the new item
    to other subscribers via group_send).
    """
    user = await get_current_user(info)

    item = await ExampleItem.objects.acreate(
        name=input.name,
        description=input.description,
        status=input.status,
        owner=user,
    )

    # Dispatch async — the mutation response is returned immediately without
    # waiting for the task to complete.
    process_and_broadcast.delay(str(item.id), event="created")

    return item  # type: ignore[return-value]


async def update_example_item(
    self: object, info: Info, input: ExampleItemUpdateInput
) -> ExampleItemType:
    """
    Partially update an ExampleItem.

    Only fields explicitly provided in the input are written to the database.
    Optimistic concurrency: if you add a `version` field to the input, compare
    input.version against item.version before saving and raise if they differ.
    """
    user = await get_current_user(info)

    try:
        item = await ExampleItem.objects.aget(id=input.id, owner=user)
    except ExampleItem.DoesNotExist as exc:
        raise ValueError("Item not found or you do not have permission.") from exc

    # Apply only the non-None fields from the partial input.
    update_fields: list[str] = []
    if input.name is not None:
        item.name = input.name
        update_fields.append("name")
    if input.description is not None:
        item.description = input.description
        update_fields.append("description")
    if input.status is not None:
        item.status = input.status
        update_fields.append("status")

    if update_fields:
        # Always include date_updated when saving a subset of fields.
        update_fields.append("date_updated")
        await item.asave(update_fields=update_fields)

    process_and_broadcast.delay(str(item.id), event="updated")

    return item  # type: ignore[return-value]


async def delete_example_item(
    self: object, info: Info, id: strawberry.ID
) -> bool:
    """
    Soft-delete an ExampleItem by setting date_deleted.

    Returns True on success, False if the item was not found or not owned
    by the current user.
    """
    user = await get_current_user(info)

    try:
        item = await ExampleItem.objects.aget(id=id, owner=user)
    except ExampleItem.DoesNotExist:
        return False

    # soft_delete() is defined on BaseModel — it sets date_deleted and saves.
    await item.asoft_delete()  # type: ignore[attr-defined]  # added in BaseModel

    process_and_broadcast.delay(str(item.id), event="deleted")

    return True
