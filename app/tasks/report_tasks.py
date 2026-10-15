import logging
import csv
import uuid
import traceback
from threading import BoundedSemaphore

from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

from app.worker import celery_app
from app.db.session import SessionLocal
from app.core.storage import UPLOAD_DIR
from app.core.config import settings
from app.models.notificacion import Notificacion
from app.models.reporte import Reporte
from app.services.reporte import reporte_service
from app.services.report_export import generar_csv, generar_pdf, generar_excel, company_identity
from sqlalchemy import text

logger = logging.getLogger(__name__)
report_workers = BoundedSemaphore(2)

@celery_app.task(name="tasks.cleanup_report")
def task_cleanup_report(report_id_str: str, filepath: str):
    """
    Elimina el archivo físico y marca el registro en BD como expirado.
    """
    db = SessionLocal()
    try:
        path = Path(filepath)
        if path.resolve().parent != (UPLOAD_DIR / "reportes").resolve():
            raise ValueError("Ruta de reporte inválida")
        if path.exists():
            path.unlink()
            
        reporte = db.query(Reporte).filter(Reporte.id == report_id_str).first()
        if reporte:
            reporte.estado = "expirado"
            db.commit()
            logger.info(f"🗑️ Reporte expirado y eliminado: {filepath}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error limpiando reporte {report_id_str}: {e}")
    finally:
        db.close()
    return True

@celery_app.task(name="tasks.generate_report")
def task_generate_report(report_id_str: str, report_type: str, filters: Dict[str, Any], formato: str, user_id: str) -> str:
    # Limit memory and DB connections when several native background jobs arrive together.
    with report_workers:
        return _generate_report(report_id_str, report_type, filters, formato, user_id)


def _generate_report(report_id_str: str, report_type: str, filters: Dict[str, Any], formato: str, user_id: str) -> str:
    """
    Genera el archivo del reporte, actualiza la BD y notifica al usuario.
    """
    logger.info(f"Iniciando tarea de reporte: {report_id_str} ({report_type})")
    db = SessionLocal()
    lock_connection = db.get_bind().connect()
    acquired = False
    try:
        acquired = bool(lock_connection.execute(text("SELECT pg_try_advisory_lock(hashtextextended(:id, 0))"), {"id": report_id_str}).scalar())
        if not acquired:
            return "El reporte ya se está procesando."
        # 1. Buscar y marcar como "procesando"
        reporte = db.query(Reporte).filter(Reporte.id == report_id_str).first()
        if not reporte:
            logger.error(f"Reporte {report_id_str} no encontrado en la base de datos.")
            return "Error: Registro no encontrado"
        if reporte.estado not in {"pendiente", "procesando"}:
            return "El reporte ya fue atendido."
            
        reporte.estado = "procesando"
        db.commit()

        # 2. Configurar rutas
        report_dir = UPLOAD_DIR / "reportes"
        report_dir.mkdir(parents=True, exist_ok=True)
        formato = formato.lower()
        extension = "xlsx" if formato == "excel" else formato
        report_path = report_dir / f"{report_id_str}.{extension}"

        # 3. Parseo de Fechas
        fecha_inicio_str = filters.get("fecha_inicio")
        fecha_fin_str = filters.get("fecha_fin")
        f_inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%d").date() if fecha_inicio_str else None
        f_fin = datetime.strptime(fecha_fin_str, "%Y-%m-%d").date() if fecha_fin_str else None

        # 4. Obtener Datos
        datos = reporte_service.obtener_datos(
            db, 
            tipo_reporte=report_type, 
            fecha_inicio=f_inicio,
            fecha_fin=f_fin
        )

        company = company_identity(db)
        title = f"Reporte de {report_type.capitalize()}"
        period = f"Período: {fecha_inicio_str} al {fecha_fin_str}"
        if report_type == "inventario":
            period = f"Existencias al cierre del {fecha_fin_str}"
        # 5. Escribir Archivo Físico
        if formato == "csv":
            generar_csv(report_path, datos)
        elif formato == "pdf":
            generar_pdf(report_path, datos, title, company, period)
        elif formato in ["excel", "xlsx"]:
            generar_excel(report_path, datos, title, company, period)
        else:
            raise NotImplementedError(f"El formato {formato} no está soportado.")

        # 6. Actualizar Registro del Reporte al tener Éxito
        archivo_size = report_path.stat().st_size if report_path.exists() else 0
        
        reporte.estado = "completado"
        reporte.archivo_path = str(report_path)
        reporte.archivo_size_bytes = archivo_size
        reporte.fecha_completado = datetime.now(timezone.utc)
        
        # 7. Crear Notificación
        nueva_notificacion = Notificacion(
            usuario_id=user_id,
            mensaje=f"Reporte de '{report_type}' ({formato.upper()}) generado con éxito.",
            tipo="info",
            urgencia=0,
            referencia_id=reporte.id, 
            referencia_tabla="reporte_generado"
        )
        db.add(nueva_notificacion)
        db.commit()

        # Periodic report recovery also expires files. A 24-hour ETA would retain
        # cleanup jobs in worker memory and exceed Redis visibility timeout.
        return f"Reporte {report_id_str} completado."

    except Exception as e:
        db.rollback()
        logger.error(f"Error reporte '{report_type}': {e}", exc_info=True)
        
        # Intentamos obtener la sesión de nuevo en caso de que haya explotado arriba
        reporte = db.query(Reporte).filter(Reporte.id == report_id_str).first()
        if reporte:
            reporte.estado = "error"
            reporte.error_msg = "No se pudo generar el reporte. Contacte al administrador para revisar el registro del servidor."
            
            notif_error = Notificacion(
                usuario_id=user_id,
                mensaje=f"Ocurrió un error al generar tu reporte de '{report_type}'.",
                tipo="error",
                urgencia=2,
                referencia_id=reporte.id,
                referencia_tabla="reporte_generado"
            )
            db.add(notif_error)
            db.commit()
            
        return "Error al generar reporte."
        
    finally:
        db.close()
        if acquired:
            lock_connection.execute(text("SELECT pg_advisory_unlock(hashtextextended(:id, 0))"), {"id": report_id_str})
        lock_connection.close()
