import logging
from typing import List
from uuid import UUID as PyUUID
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.reporte import ReporteRequest, ReporteResponse
from app.models.usuario import Usuario as UsuarioModel
from app.models.reporte import Reporte
from app.core import permissions as perms
from app.worker import celery_app
from app.core.storage import UPLOAD_DIR

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/",
             response_model=dict,
             dependencies=[Depends(deps.PermissionChecker([perms.PERM_GENERAR_REPORTES]))],
             summary="Registra y encola la generación de un reporte")
def generar_reporte(
    payload: ReporteRequest,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user)
) -> dict:
    
    # 1. Guardar el payload en formato compatible para JSONB
    parametros_json = {
        "fecha_inicio": payload.fecha_inicio.isoformat(),
        "fecha_fin": payload.fecha_fin.isoformat()
    }

    # 2. Crear el registro en estado "pendiente"
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
    
    # 3. Enviar a Celery pasando el ID del reporte en BD
    task = celery_app.send_task(
        "tasks.generate_report", 
        args=[str(nuevo_reporte.id), payload.tipo_reporte, parametros_json, payload.formato, str(current_user.id)]
    )
    
    return {
        "status": "ok",
        "msg": "Solicitud de reporte encolada exitosamente.",
        "reporte_id": nuevo_reporte.id,
        "task_id": task.id
    }


@router.get("/historial",
            response_model=List[ReporteResponse],
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_GENERAR_REPORTES]))],
            summary="Obtener el historial real de reportes de la base de datos")
def obtener_historial_reportes(
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
    limit: int = 15
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
        
    # Verificar propiedad (a menos que sea superuser/admin)
    if db_reporte.usuario_id != current_user.id and not getattr(current_user, 'es_superuser', False):
         raise HTTPException(status_code=403, detail="No tienes permiso para descargar este reporte.")
         
    if db_reporte.estado != "completado" or not db_reporte.archivo_path:
        raise HTTPException(status_code=400, detail=f"El reporte no está listo. Estado actual: {db_reporte.estado}")

    file_path = Path(db_reporte.archivo_path)
    if not file_path.exists():
        # Auto-healing: Si se borró del disco, actualizar BD
        db_reporte.estado = "expirado"
        db.commit()
        raise HTTPException(status_code=410, detail="El archivo del reporte ha expirado y fue eliminado del servidor.")
        
    logger.info(f"Usuario '{current_user.nombre_usuario}' descargando reporte {report_id}")
    
    return FileResponse(
        path=file_path,
        filename=f"Reporte_{db_reporte.tipo_reporte}_{db_reporte.fecha_solicitud.strftime('%Y%m%d')}{file_path.suffix}",
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="Reporte_{db_reporte.tipo_reporte}{file_path.suffix}"'}
    )
