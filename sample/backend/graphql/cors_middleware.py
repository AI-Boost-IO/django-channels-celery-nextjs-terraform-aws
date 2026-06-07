"""
ASGI CORS middleware for the GraphQL HTTP consumer.

Django's CorsMiddleware (from django-cors-headers) works at the WSGI/Django layer
and does not apply to ASGI consumers mounted via ProtocolTypeRouter. This thin ASGI
wrapper applies CORS headers directly to GraphQL HTTP responses.

It reads CORS_ALLOWED_ORIGINS from Django settings so the same list of allowed
origins governs both the standard Django views and the GraphQL consumer.

Usage in config/asgi.py:
    from graphql.cors_middleware import CorsMiddleware
    gql_http = CorsMiddleware(GraphQLHTTPConsumer.as_asgi(schema=schema))

For pre-flight OPTIONS requests the middleware responds immediately with a 200
so browsers do not block cross-origin GraphQL mutations.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings


class CorsMiddleware:
    """ASGI middleware that adds CORS headers to HTTP responses from the GraphQL consumer."""

    def __init__(self, app: Any) -> None:
        self.app = app
        # Read allowed origins once at initialisation time.
        self._allowed_origins: list[str] = getattr(settings, "CORS_ALLOWED_ORIGINS", [])

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            # Pass non-HTTP scopes (e.g. WebSocket lifespan events) straight through.
            await self.app(scope, receive, send)
            return

        origin = self._get_origin(scope)
        is_allowed = origin in self._allowed_origins

        if self._is_preflight(scope):
            # Respond to OPTIONS pre-flight immediately — do not forward to the consumer.
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": self._cors_headers(origin, is_allowed),
            })
            await send({"type": "http.response.body", "body": b""})
            return

        # Wrap `send` to inject CORS headers into every response from the consumer.
        async def send_with_cors(event: dict) -> None:
            if event["type"] == "http.response.start" and is_allowed:
                headers: list[tuple[bytes, bytes]] = list(event.get("headers", []))
                headers.extend(self._cors_headers(origin, is_allowed))
                event = {**event, "headers": headers}
            await send(event)

        await self.app(scope, receive, send_with_cors)

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def _get_origin(scope: dict) -> str:
        for name, value in scope.get("headers", []):
            if name == b"origin":
                return value.decode("latin-1")
        return ""

    @staticmethod
    def _is_preflight(scope: dict) -> bool:
        return scope.get("method", "").upper() == "OPTIONS"

    @staticmethod
    def _cors_headers(origin: str, is_allowed: bool) -> list[tuple[bytes, bytes]]:
        if not is_allowed:
            return []
        return [
            (b"access-control-allow-origin", origin.encode()),
            (b"access-control-allow-credentials", b"true"),
            (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
            (b"access-control-allow-headers", b"Authorization, Content-Type"),
            (b"access-control-max-age", b"86400"),
        ]
