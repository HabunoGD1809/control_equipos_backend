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
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=3,
    broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 5},
)

celery_app.conf.beat_schedule = {
    'recover-reports': {'task': 'tasks.recover_reports', 'schedule': 60.0},
    'check-overdue-loans-hourly': {'task': 'tasks.check_overdue_loans', 'schedule': crontab(minute=10)},
    'manage-audit-partitions-daily': {
        'task': 'tasks.manage_audit_log_partitions',
        'schedule': crontab(hour=2, minute=0),
    },
    'refresh-materialized-views-hourly': {
        'task': 'tasks.refresh_materialized_views', 
        'schedule': crontab(minute=0),
    }
}

logger.info("Celery configurado exitosamente.")
