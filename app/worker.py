import logging
from celery import Celery
from celery.schedules import crontab 
from app.core.config import settings
from app.core.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)
logger.info("Configurando Celery worker...")

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.maintenance_tasks", 
        "app.tasks.notification_tasks", 
        "app.tasks.report_tasks"
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    'manage-audit-partitions-daily': {
        'task': 'tasks.manage_audit_log_partitions',
        'schedule': crontab(hour=2, minute=0),
    },
    'refresh-materialized-views-hourly': {
        'task': 'tasks.refresh_materialized_views', 
        'schedule': crontab(minute=0),
    }
}

logger.info(f"Celery configurado exitosamente. Broker: {settings.CELERY_BROKER_URL}")
