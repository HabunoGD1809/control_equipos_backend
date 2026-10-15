import logging
from typing import List
from uuid import UUID as PyUUID
from pathlib import Path
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.reporte import ReporteRequest, ReporteResponse
from app.models.usuario import Usuario as UsuarioModel
from app.models.reporte import Reporte
from app.core import permissions as perms
from app.worker import celery_app
from app.core.storage import UPLOAD_DIR
from app.core.config import settings
from app.core.security import user_has_permissions

logger = logging.getLogger(__name__)
router = APIRouter()

EXT_MAP = {"excel": "xlsx", "pdf": "pdf", "csv": "csv"}

@router.post("/",
             response_model=dict,
             dependencies=[Depends(deps.PermissionChecker([perms.PERM_GENERAR_REPORTES]))],
             summary="Registra y encola la generación de un reporte")
def generar_reporte(
    payload: ReporteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user)
) -> dict:

    module_permissions = {
        "equipos": perms.PERM_VER_EQUIPOS,
        "mantenimientos": perms.PERM_VER_MANTENIMIENTOS,
        "movimientos": perms.PERM_VER_MOVIMIENTOS,
        "auditoria": perms.PERM_VER_AUDITORIA,
        "inventario": perms.PERM_VER_INVENTARIO,
        "kardex": perms.PERM_VER_INVENTARIO,
        "licencias": perms.PERM_VER_LICENCIAS,
    }
    required = module_permissions.get(payload.tipo_reporte)
    if not required or not user_has_permissions(current_user, {required}):
        raise HTTPException(403, "No tiene permiso para exportar los datos de este módulo.")
    parametros_json = {
        "fecha_inicio": payload.fecha_inicio.isoformat(),
        "fecha_fin": payload.fecha_fin.isoformat()
    }

    nuevo_reporte = Reporte(
        usuario_id=current_user.id,
        tipo_reporte=payload.tipo_reporte,
        formato=payload.formato,
        parametros=parametros_json,
        estado="pendiente"
    )
    db.add(nuevo_reporte)
    db.commit()
    db.refresh(nuevo_reporte)

    logger.info(f"Reporte {nuevo_reporte.id} registrado para usuario '{current_user.nombre_usuario}'")

    arguments = [str(nuevo_reporte.id), payload.tipo_reporte, parametros_json, payload.formato, str(current_user.id)]
    task_id = None
    if settings.REPORT_EXECUTION_MODE == "background":
        from app.tasks.report_tasks import task_generate_report
        background_tasks.add_task(task_generate_report.run, *arguments)
    else:
        try:
            # Report status and files are persisted in PostgreSQL. Do not subscribe
            # this HTTP request to Redis result events while publishing the task.
            task = celery_app.send_task("tasks.generate_report", args=arguments, retry=False, ignore_result=True)
            task_id = task.id
        except Exception:
            logger.exception("No se pudo encolar el reporte %s", nuevo_reporte.id)
            nuevo_reporte.estado = "error"
            nuevo_reporte.error_msg = "El servicio de reportes no está disponible. Intente nuevamente."
            db.commit()
            raise HTTPException(503, nuevo_reporte.error_msg)
    return {"status": "ok", "msg": "La generación del reporte ha comenzado.", "reporte_id": nuevo_reporte.id, "task_id": task_id}


@router.get("/historial",
            response_model=List[ReporteResponse],
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_GENERAR_REPORTES]))],
            summary="Obtener el historial real de reportes de la base de datos")
def obtener_historial_reportes(
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
    limit: int = Query(15, ge=1, le=100)
):
    reportes = db.query(Reporte).filter(
        Reporte.usuario_id == current_user.id
    ).order_by(Reporte.fecha_solicitud.desc()).limit(limit).all()

    return reportes


@router.get("/{report_id}/download",
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_GENERAR_REPORTES]))],
            summary="Descargar archivo físico del reporte",
            response_class=FileResponse)
def descargar_reporte(
    report_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user)
):
    db_reporte = db.query(Reporte).filter(Reporte.id == report_id).first()

    if not db_reporte:
        raise HTTPException(status_code=404, detail="Registro de reporte no encontrado.")

    if db_reporte.usuario_id != current_user.id and not getattr(current_user, 'es_superuser', False):
        raise HTTPException(status_code=403, detail="No tienes permiso para descargar este reporte.")

    if db_reporte.estado != "completado" or not db_reporte.archivo_path:
        raise HTTPException(status_code=400, detail=f"El reporte no está listo. Estado actual: {db_reporte.estado}")

    if db_reporte.fecha_completado and db_reporte.fecha_completado < datetime.now(timezone.utc) - timedelta(days=1):
        from app.tasks.report_tasks import task_cleanup_report
        task_cleanup_report.run(str(db_reporte.id), db_reporte.archivo_path)
        raise HTTPException(410, "El reporte ha expirado. Genere una nueva copia actualizada.")
    file_path = Path(db_reporte.archivo_path).resolve()
    if file_path.parent != (UPLOAD_DIR / "reportes").resolve():
        raise HTTPException(status_code=403, detail="Ruta de reporte inválida.")
    if not file_path.exists():
        db_reporte.estado = "expirado"
        db.commit()
        raise HTTPException(status_code=410, detail="El archivo del reporte ha expirado y fue eliminado del servidor.")

    logger.info(f"Usuario '{current_user.nombre_usuario}' descargando reporte {report_id}")

    formato = db_reporte.formato.lower()
    ext = EXT_MAP.get(formato, file_path.suffix.lstrip(".") or formato)
    nombre_archivo = f"Reporte_{db_reporte.tipo_reporte}_{db_reporte.fecha_solicitud.strftime('%Y%m%d')}.{ext}"

    return FileResponse(
        path=file_path,
        filename=nombre_archivo,
        media_type={"pdf": "application/pdf", "csv": "text/csv; charset=utf-8", "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}.get(formato, "application/octet-stream"),
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
