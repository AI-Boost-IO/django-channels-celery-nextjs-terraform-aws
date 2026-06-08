"""
Celery application for myproject.

This module declares the Celery app and connects it to Django settings.
It is imported in config/__init__.py so Celery is loaded when Django starts,
which is required for @shared_task decorators to register correctly.

Usage:
    config/__init__.py:
        from .celery import app as celery_app
        __all__ = ("celery_app",)

Replace 'myproject' with your project name.
See docs/04-celery-workers.md for full configuration details.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Create the Celery application with the project name as the main module identifier.
# This name appears in task names and in the Celery worker log headers.
app = Celery("myproject")

# Read all CELERY_* settings from Django's settings module.
# Using a namespace keeps Celery settings clearly separated from Django settings.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover tasks from the logic/ package.
# autodiscover_tasks(["logic"]) imports logic.tasks, which in turn imports
# all task submodules via logic/tasks/__init__.py.
#
# Do NOT pass "logic.tasks" here — that tells Celery to look for
# logic.tasks.tasks (a file that doesn't exist) and discovers nothing.
app.autodiscover_tasks(["logic"])
