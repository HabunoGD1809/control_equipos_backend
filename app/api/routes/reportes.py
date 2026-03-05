import logging
from typing import Dict, Any
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api import deps
from app.schemas.reporte import ReporteRequest
from app.models.usuario import Usuario as UsuarioModel
from app.core import permissions as perms
from app.worker import celery_app
from app.core.storage import UPLOAD_DIR

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/",
             response_model=dict,
             dependencies=[Depends(deps.PermissionChecker([perms.PERM_GENERAR_REPORTES]))],
             summary="Generar un reporte en segundo plano",
             response_description="Confirma que la tarea de reporte ha iniciado.")
def generar_reporte(
    payload: ReporteRequest,
    current_user: UsuarioModel = Depends(deps.get_current_active_user)
) -> dict:
    """
    Envía una tarea a Celery para generar un reporte en segundo plano.
    """
    tipo_reporte = payload.tipo_reporte
    if not tipo_reporte:
        raise HTTPException(status_code=400, detail="El tipo de reporte es requerido.")
        
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitó reporte '{tipo_reporte}'")
    
    # Pasamos el modelo convertido a diccionario para Celery
    task = celery_app.send_task(
        "tasks.generate_report", 
        args=[tipo_reporte, payload.model_dump(mode='json'), str(current_user.id)]
    )
    
    return {
        "status": "ok",
        "msg": f"El reporte '{tipo_reporte}' está siendo generado.",
        "task_id": task.id
    }


@router.get("/{report_id}/download",
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_GENERAR_REPORTES]))],
            summary="Descargar reporte generado",
            response_class=FileResponse)
def descargar_reporte(
    report_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user)
):
    """
    Endpoint para descargar el reporte utilizando el ID de referencia que llega en la notificación.
    """
    report_dir = UPLOAD_DIR / "reportes"
    
    # Buscamos el archivo ignorando la extensión, ya que puede ser pdf, xls, csv, etc.
    file_path = None
    for ext in [".csv", ".pdf", ".xls", ".xlsx"]:
        temp_path = report_dir / f"{report_id}{ext}"
        if temp_path.exists():
            file_path = temp_path
            break
            
    if not file_path:
        logger.warning(f"Usuario '{current_user.nombre_usuario}' intentó descargar un reporte inexistente o expirado: {report_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado, posiblemente ha expirado.")
        
    logger.info(f"Usuario '{current_user.nombre_usuario}' descargando reporte {report_id}")
    
    # Exponemos el FileResponse con cabeceras que obligan al navegador a tratarlo como una descarga.
    return FileResponse(
        path=file_path,
        filename=f"Reporte_Sistema{file_path.suffix}",
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="Reporte_Sistema{file_path.suffix}"'}
    )
