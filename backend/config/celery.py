"""Celery application for asynchronous TaskCraft work."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("taskcraft")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
