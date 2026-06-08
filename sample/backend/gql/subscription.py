"""
Root Subscription type — re-exported from logic/subscriptions/.

Subscriptions are async generators that must live inside a @strawberry.type class,
so the Subscription class is defined in logic/subscriptions/example.py rather than
as standalone functions. This file re-exports it so schema.py has a single
consistent import pattern across Query, Mutation, and Subscription.

HOW TO ADD A NEW SUBSCRIPTION
-------------------------------
1. Add a new async generator method to the Subscription class (or a new class)
   in logic/subscriptions/<your_app>.py, following the pattern in example.py.

2. If you add a second Subscription class for a different app, merge the fields
   into a single class here rather than passing two Subscription types to
   strawberry.Schema — Strawberry only accepts one root Subscription type.
"""

from logic.subscriptions.example import Subscription

__all__ = ["Subscription"]
