"""Celery application for async generation jobs."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "ai_studio_pro",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_ignore_result=False,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["app.workers"])
