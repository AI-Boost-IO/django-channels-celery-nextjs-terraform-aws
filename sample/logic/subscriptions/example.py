"""
Example GraphQL subscription using Django Channels and Redis channel layer.

Pattern:
  1. The client connects via WebSocket and calls this subscription with an ID.
  2. The subscription generator joins a Redis channel group named after the resource.
  3. A Celery task (logic/tasks/example.py) calls `group_send()` to publish events.
  4. The generator receives those events and yields them to the WebSocket client.
  5. On disconnect or cancellation, `group_discard` removes the consumer from the group.

The group naming convention `example-{id}` scopes events to a specific resource —
clients only receive events for items they explicitly subscribe to.

See docs/03-realtime-channels.md for the full pub/sub sequence diagram.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

import strawberry
from strawberry.types import Info

from logic.permissions import IsAuthenticated
from logic.types import ExampleItemEventType

logger = logging.getLogger(__name__)

# How long to wait for a channel layer message before looping.
# This prevents the generator from blocking indefinitely if the Redis connection
# drops — the timeout triggers a reconnect on the next iteration.
_RECEIVE_TIMEOUT_SECONDS = 30.0


@strawberry.type
class Subscription:
    @strawberry.subscription(permission_classes=[IsAuthenticated])
    async def on_example_item_event(
        self, info: Info, example_item_id: strawberry.ID
    ) -> AsyncGenerator[ExampleItemEventType, None]:
        """
        Yields ExampleItemEventType payloads whenever the given item changes.

        GraphQL subscription call:
            subscription OnExampleItemEvent($id: ID!) {
                onExampleItemEvent(exampleItemId: $id) {
                    id
                    event
                    item { id name status }
                }
            }
        """
        group_name = f"example-{example_item_id}"
        ws = info.context["ws"]
        channel_layer = ws.channel_layer
        channel_name = ws.channel_name

        # Join the Redis group so this WebSocket consumer receives group_send() messages.
        await channel_layer.group_add(group_name, channel_name)
        logger.debug("WS %s joined group %s", channel_name, group_name)

        try:
            while True:
                try:
                    # Block until a message arrives or the timeout expires.
                    message = await asyncio.wait_for(
                        channel_layer.receive(channel_name),
                        timeout=_RECEIVE_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    # No message within the window — loop again.
                    # This keeps the generator alive without busy-waiting.
                    continue

                if message.get("type") != "example.item.event":
                    # Skip messages intended for other handlers on this channel.
                    continue

                yield ExampleItemEventType(
                    id=message["item_id"],
                    event=message["event"],
                    # item is re-fetched by the resolver automatically via DjangoOptimizer
                    # if the client requests the `item` field in the subscription selection.
                )

        except Exception as exc:
            logger.error("Subscription error for group %s: %s", group_name, exc)
            raise
        finally:
            # Always leave the group, even if the generator is cancelled.
            await channel_layer.group_discard(group_name, channel_name)
            logger.debug("WS %s left group %s", channel_name, group_name)
