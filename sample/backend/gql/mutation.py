"""
Root Mutation type — aggregates all mutation fields from logic/mutations/.

HOW TO ADD A NEW MUTATION
--------------------------
1. Write a plain async resolver function in logic/mutations/<your_app>.py.
   Example signature:
       async def create_my_thing(self: object, info: Info, input: MyInput) -> MyType:
           ...

2. Import it here and declare a field with strawberry.mutation(resolver=...).

3. Set permission_classes HERE, not on the resolver function.
   Decorating a resolver with @strawberry.mutation and then passing it as
   resolver= below creates a double-wrapped StrawberryField that raises
   a TypeError at schema build time.

Example:
    from logic.mutations.myapp import create_my_thing
    from logic.types import MyType, MyInput

    @strawberry.type
    class Mutation:
        create_my_thing: MyType = strawberry.mutation(
            resolver=create_my_thing,
            description="Create a new MyThing.",
            permission_classes=[IsAuthenticated],
        )
"""

import strawberry

from logic.mutations.example import (
    create_example_item,
    delete_example_item,
    update_example_item,
)
from logic.permissions import IsAuthenticated
from logic.types import ExampleItemType


@strawberry.type
class Mutation:
    # ---------- ExampleItem mutations ----------

    create_example_item: ExampleItemType = strawberry.mutation(
        resolver=create_example_item,
        description="Create a new ExampleItem owned by the authenticated user.",
        permission_classes=[IsAuthenticated],
    )

    update_example_item: ExampleItemType = strawberry.mutation(
        resolver=update_example_item,
        description="Partially update an ExampleItem. Only supplied fields are written.",
        permission_classes=[IsAuthenticated],
    )

    delete_example_item: bool = strawberry.mutation(
        resolver=delete_example_item,
        description="Soft-delete an ExampleItem. Returns True on success.",
        permission_classes=[IsAuthenticated],
    )
