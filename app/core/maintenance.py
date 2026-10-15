"""Durable report recovery and periodic alerts for installations without Celery."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, or_, and_
from app.db.session import SessionLocal
from app.models.reporte import Reporte
from app.tasks.report_tasks import task_generate_report, task_cleanup_report
from app.tasks.notification_tasks import task_check_overdue_loans
from app.tasks.maintenance_tasks import task_manage_audit_log_partitions

logger = logging.getLogger(__name__)


def maintain_reports():
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        expired = [(str(r.id), r.archivo_path) for r in db.scalars(select(Reporte).where(Reporte.estado == "completado", Reporte.fecha_completado < now-timedelta(hours=24)).limit(100))]
        pending = [(str(r.id), r.tipo_reporte, r.parametros or {}, r.formato, str(r.usuario_id)) for r in db.scalars(select(Reporte).where(or_(and_(Reporte.estado == "pendiente", Reporte.fecha_solicitud < now-timedelta(minutes=1)), and_(Reporte.estado == "procesando", Reporte.fecha_solicitud < now-timedelta(minutes=5)))).order_by(Reporte.fecha_solicitud).limit(20))]
    for report_id, path in expired:
        if path:
            task_cleanup_report.run(report_id, path)
    for args in pending:
        # Generation uses a dedicated PostgreSQL advisory lock; concurrent workers cannot duplicate a report.
        task_generate_report.run(*args)


async def maintenance_loop():
    next_alert = datetime.min.replace(tzinfo=timezone.utc)
    next_partitions = next_alert
    while True:
        try:
            await asyncio.to_thread(maintain_reports)
            if datetime.now(timezone.utc) >= next_partitions:
                await asyncio.to_thread(task_manage_audit_log_partitions.run)
                next_partitions = datetime.now(timezone.utc)+timedelta(days=1)
            if datetime.now(timezone.utc) >= next_alert:
                await asyncio.to_thread(task_check_overdue_loans.run)
                next_alert = datetime.now(timezone.utc)+timedelta(hours=1)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("No se pudo completar el mantenimiento periódico; se reintentará.")
        await asyncio.sleep(60)
