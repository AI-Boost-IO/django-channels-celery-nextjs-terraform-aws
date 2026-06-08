"""
GraphQL Channels consumers with JWT authentication middleware.

Strawberry provides GraphQLHTTPConsumer (HTTP) and GraphQLWSConsumer (WebSocket).
This module wraps the WebSocket consumer with a custom auth middleware that reads
a JWT from the WebSocket connectionParams and attaches the user to the scope.

The HTTP consumer is wrapped separately in cors_middleware.py.

This pattern ensures that info.context["request"].user is populated in both
HTTP resolvers (via standard Django auth middleware) and WebSocket resolvers
(via JwtAuthMiddleware below).

Replace 'myapp' with your authentication app name.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from strawberry.channels import GraphQLHTTPConsumer, GraphQLWSConsumer

from .schema import schema

logger = logging.getLogger(__name__)
User = get_user_model()


class JwtAuthMiddleware:
    """
    ASGI middleware that reads a JWT from the WebSocket connectionParams
    and attaches the authenticated user to the connection scope.

    Clients send the token in connectionParams.authorization:
        createClient({
            url: WS_URL,
            connectionParams: async () => ({ authorization: `Bearer ${token}` }),
        })

    The user is then accessible in resolvers via info.context["request"].user.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        scope["user"] = await self._get_user_from_scope(scope)
        await self.app(scope, receive, send)

    @database_sync_to_async
    def _get_user_from_scope(self, scope: dict) -> Any:
        """
        Extract and validate the JWT from the connection_params in scope.
        Return the anonymous user if no valid token is found.
        """
        from django.contrib.auth.models import AnonymousUser

        connection_params: dict = scope.get("connection_params", {})
        auth_header: str = connection_params.get("authorization", "")

        if not auth_header.startswith("Bearer "):
            return AnonymousUser()

        token = auth_header.removeprefix("Bearer ").strip()

        try:
            # Replace this block with your JWT library of choice.
            # Example using PyJWT:
            #   import jwt
            #   payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            #   return User.objects.get(id=payload["user_id"])
            user = User.objects.get(auth_token=token)
            return user
        except (User.DoesNotExist, Exception):
            logger.debug("WS connection: invalid or expired JWT")
            return AnonymousUser()


# ---------------------------------------------------------------------------
# Consumer instances
# ---------------------------------------------------------------------------

# HTTP consumer — used in config/asgi.py for HTTP GraphQL requests.
# The CORS wrapper is applied around this consumer in asgi.py.
GraphQLHTTP = GraphQLHTTPConsumer.as_asgi(schema=schema)

# WebSocket consumer wrapped with JWT auth — used in config/asgi.py for subscriptions.
GraphQLWS = JwtAuthMiddleware(
    GraphQLWSConsumer.as_asgi(schema=schema)
)
