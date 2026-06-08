"""
Task package — imports all task modules so Celery's autodiscover_tasks can find them.

config/celery.py calls:
    app.autodiscover_tasks(["logic"])

Celery resolves this by importing `logic.tasks` (this file). Each task module
must be imported here so that @shared_task decorators run and register the tasks.

When you add a new task file (e.g. logic/tasks/billing.py), add a line:
    from . import billing  # noqa: F401
"""

from . import example  # noqa: F401
