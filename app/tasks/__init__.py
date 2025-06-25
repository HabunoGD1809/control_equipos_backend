# Importa las tareas para que Celery las descubra
from .maintenance_tasks import task_refresh_materialized_views
from .notification_tasks import task_send_email_notification
from .report_tasks import task_generate_report

__all__ = [
    "task_refresh_materialized_views",
    "task_send_email_notification",
    "task_generate_report",
]
