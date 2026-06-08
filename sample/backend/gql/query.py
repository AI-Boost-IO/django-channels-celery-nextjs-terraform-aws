"""
Root Query type — aggregates all query fields from logic/queries/.

HOW TO ADD A NEW FIELD
----------------------
1. Write a plain async resolver function in logic/queries/<your_app>.py.
   Example signature:
       async def my_field(self: object, info: Info, id: strawberry.ID) -> MyType | None:
           ...

2. Import it here and declare a field with strawberry.field(resolver=...).

3. Set permission_classes HERE, not on the resolver function.
   Decorating a resolver with @strawberry.field and then passing it as
   resolver= below creates a double-wrapped StrawberryField that raises
   a TypeError at schema build time.

Example:
    from logic.queries.myapp import my_resolver
    from logic.types import MyType

    @strawberry.type
    class Query:
        my_field: MyType | None = strawberry.field(
            resolver=my_resolver,
            description="Fetch a single MyType by ID.",
            permission_classes=[IsAuthenticated],
        )
"""

import strawberry

from logic.permissions import IsAuthenticated
from logic.queries.example import example_item, example_items
from logic.types import ExampleItemType


@strawberry.type
class Query:
    # ---------- ExampleItem queries ----------

    example_item: ExampleItemType | None = strawberry.field(
        resolver=example_item,
        description="Return a single ExampleItem by ID, or None if not found.",
        permission_classes=[IsAuthenticated],
    )

    example_items: list[ExampleItemType] = strawberry.field(
        resolver=example_items,
        description="Return all ExampleItems owned by the authenticated user.",
        permission_classes=[IsAuthenticated],
    )
