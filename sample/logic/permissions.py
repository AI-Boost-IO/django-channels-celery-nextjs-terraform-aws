"""
Strawberry GraphQL permission classes.

Each class inherits BasePermission and implements has_permission().
Strawberry evaluates permissions before the resolver runs and returns the
`message` string as a GraphQL error if the check fails.

Usage — attach to a field or mutation in gql/query.py or gql/mutation.py:

    @strawberry.type
    class Query:
        my_field: MyType = strawberry.field(
            resolver=my_resolver,
            permission_classes=[IsAuthenticated],
        )

Add new classes here as your authorisation requirements grow
(e.g. IsStaff, IsOwner, HasScope).
"""

from __future__ import annotations

from strawberry.permission import BasePermission
from strawberry.types import Info


class IsAuthenticated(BasePermission):
    """Deny access to unauthenticated users."""

    message = "You must be logged in to access this resource."

    async def has_permission(
        self, source: object, info: Info, **kwargs: object
    ) -> bool:
        request = info.context.get("request")
        if request is None:
            return False
        return bool(request.user.is_authenticated)
