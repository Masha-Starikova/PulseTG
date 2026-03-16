from celery import Celery

from backend.core.config import settings

celery_app = Celery(
    "pulsetg",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.services.tasks"],
)

# Базовая production-настройка сериализации и очередей.
celery_app.conf.update(
    task_default_queue="audits",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    enable_utc=True,
    timezone="UTC",
    task_track_started=True,
)
