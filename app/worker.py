import logging.config 
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
    # Incluir los módulos donde están definidas las tareas
    include=["app.tasks.maintenance_tasks", "app.tasks.notification_tasks", "app.tasks.report_tasks"]
)

# Opcional: Configuración adicional de Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Configuración de reintentos, colas, etc., 
    # task_track_started=True, # Útil para monitoreo
)

celery_app.conf.beat_schedule = {
    # Tarea para gestionar particiones de auditoría. Se ejecuta todos los días a las 2:00 AM.
    'manage-audit-partitions-daily': {
        'task': 'tasks.manage_audit_log_partitions', # El nombre
        'schedule': crontab(hour=2, minute=0), # crontab(hour=2, minute=0) -> Ejecutar a las 2:00 AM
    },
    # Añadir otras tareas programadas que necesites en el futuro.
    # Ejemplo: Refrescar vistas materializadas cada hora.
    'refresh-materialized-views-hourly': {
        'task': 'tasks.refresh_materialized_views',
        'schedule': crontab(minute=0), # Se ejecuta al inicio de cada hora
    }
}
# ------------------------------------

logger.info(f"Celery worker configurado. Broker: {settings.CELERY_BROKER_URL}")
logger.info("Planificador (Celery Beat) configurado para las tareas periódicas.")
