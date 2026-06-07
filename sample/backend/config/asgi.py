"""
ASGI configuration for myproject.

Two variants are shown:
  1. Simple: GraphQLProtocolTypeRouter — use when no custom auth middleware is needed.
  2. Production: manual ProtocolTypeRouter + AuthMiddlewareStack + CorsMiddleware —
     use when WebSocket connections require JWT/session auth and CORS handling.

Replace 'myproject' with your Django project name throughout.
See docs/03-realtime-channels.md for a detailed explanation.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Call get_asgi_application() before importing anything that triggers django.setup().
# This ensures the Django application registry is ready before schema imports run.
django_asgi_app = get_asgi_application()

# ---------------------------------------------------------------------------
# Variant 1 — Simple: GraphQLProtocolTypeRouter
# ---------------------------------------------------------------------------
# Suitable for development or projects that do not need custom WS auth middleware.
# GraphQLProtocolTypeRouter routes HTTP → GraphQLHTTPConsumer and
# WebSocket → GraphQLWSConsumer automatically.
#
# from strawberry.channels import GraphQLProtocolTypeRouter
# from myproject.graphql.schema import schema
#
# application = GraphQLProtocolTypeRouter(
#     schema,
#     django_application=django_asgi_app,
# )

# ---------------------------------------------------------------------------
# Variant 2 — Production: manual routing with AuthMiddlewareStack + CorsMiddleware
# ---------------------------------------------------------------------------
# Use this variant in production. AuthMiddlewareStack reads JWT from
# connectionParams.authorization on WebSocket connect and sets request.user.
# CorsMiddleware adds CORS headers to GraphQL HTTP responses.

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.urls import re_path  # noqa: E402
from strawberry.channels import GraphQLHTTPConsumer, GraphQLWSConsumer  # noqa: E402

from myproject.graphql.cors_middleware import CorsMiddleware  # noqa: E402
from myproject.graphql.schema import schema  # noqa: E402

# Wrap the HTTP GraphQL consumer in CORS middleware so mutations from the
# Vercel-deployed frontend receive the correct Access-Control-Allow-Origin header.
gql_http_consumer = CorsMiddleware(
    AuthMiddlewareStack(
        GraphQLHTTPConsumer.as_asgi(schema=schema)
    )
)

# WebSocket consumer wrapped so info.context["request"].user is populated
# from the JWT passed in connectionParams on subscription connect.
gql_ws_consumer = AuthMiddlewareStack(
    GraphQLWSConsumer.as_asgi(schema=schema)
)

application = ProtocolTypeRouter({
    "http": URLRouter([
        # All GraphQL queries and mutations arrive here
        re_path(r"^api/v1", gql_http_consumer),
        # Everything else (admin, webhooks, health checks) falls through to Django
        re_path(r"", django_asgi_app),
    ]),
    "websocket": AuthMiddlewareStack(
        URLRouter([
            re_path(r"^api/v1", gql_ws_consumer),
        ])
    ),
})
