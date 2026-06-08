"""
Strawberry GraphQL schema assembly.

The schema is constructed here from three root types:
  - Query      — all read operations (imported from gql/query.py)
  - Mutation   — all write operations (imported from gql/mutation.py)
  - Subscription — all real-time subscriptions (imported from gql/subscription.py)

DjangoOptimizerExtension is added globally to eliminate N+1 queries automatically.
Resolvers in logic/queries/ can return Django querysets directly; Strawberry and
the optimizer will select only the columns required for each GraphQL response field.

The schema object is imported by:
  - config/asgi.py      → mounted as the ASGI application
  - manage.py command   → export_schema writes gql/schema.graphql for codegen

Usage — export the schema SDL for frontend codegen:
    python manage.py export_schema gql.schema --path gql/schema.graphql
"""

import strawberry
from strawberry_django.optimizer import DjangoOptimizerExtension

from .mutation import Mutation
from .query import Query
from .subscription import Subscription

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    extensions=[
        # Automatically batches and defers database queries to avoid N+1.
        # No manual prefetch_related() or select_related() calls are needed in resolvers
        # as long as the Strawberry types are annotated with @strawberry_django.type.
        DjangoOptimizerExtension,
    ],
)
