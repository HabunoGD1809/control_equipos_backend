import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.backup_log import BackupLog as BackupLogSchema
from app.services.backup_log import backup_log_service # Servicio ya revisado
from app.models.usuario import Usuario as UsuarioModel # Para el usuario actual

logger = logging.getLogger(__name__)
PERM_ADMIN_SISTEMA = "administrar_sistema"

router = APIRouter()

@router.get("/",
            response_model=List[BackupLogSchema], # Usar el schema renombrado
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_SISTEMA]))],
            summary="Consultar Logs de Backup",
            response_description="Una lista de registros de operaciones de backup.")
def read_backup_logs(
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user), # Para logging
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200), # Límite ajustado
    backup_status: Optional[str] = Query(None, description="Filtrar por estado (ej: Iniciado, Completado, Fallido)"), # Nombre de param actualizado
    backup_type: Optional[str] = Query(None, description="Filtrar por tipo (ej: Full, Incremental, BD, Archivos)"),    # Nombre de param actualizado
    start_time: Optional[datetime] = Query(None, description="Fecha/hora mínima del registro (formato ISO)"),
    end_time: Optional[datetime] = Query(None, description="Fecha/hora máxima del registro (formato ISO)"),
) -> Any:
    """
    Obtiene una lista de registros del log de backups, permitiendo aplicar filtros.
    Requiere el permiso: `administrar_sistema`.
    """
    logger.info(
        f"Usuario '{current_user.nombre_usuario}' consultando logs de backup con filtros: "
        f"Status='{backup_status}', Type='{backup_type}', Rango='{start_time}-{end_time}', "
        f"Skip={skip}, Limit={limit}"
    )

    if start_time and end_time and end_time <= start_time:
        logger.warning("Consulta de logs de backup rechazada: fecha_fin debe ser posterior a fecha_inicio.")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha de fin debe ser posterior a la fecha de inicio para el filtro.")

    try:
        logs = backup_log_service.get_multi(
            db,
            skip=skip,
            limit=limit,
            backup_status=backup_status, # Usar nombre de param actualizado
            backup_type=backup_type,     # Usar nombre de param actualizado
            start_time=start_time,
            end_time=end_time
        )
        logger.info(f"Consulta de logs de backup devolvió {len(logs)} registro(s).")
        return logs
    except Exception as e: # Captura genérica, el servicio no debería lanzar errores inesperados aquí
        logger.error(f"Error inesperado al consultar logs de backup: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al consultar los logs de backup.")


@router.get("/{log_id}",
            response_model=BackupLogSchema, # Usar el schema renombrado
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_SISTEMA]))],
            summary="Obtener Log de Backup por ID",
            response_description="Información detallada del log de backup.")
def read_backup_log_by_id(
    log_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user), # Para logging
) -> Any:
    """Obtiene un log de backup específico por su ID."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando log de backup ID: {log_id}.")
    log = backup_log_service.get(db, id=log_id)
    if not log:
        logger.warning(f"Log de backup con ID {log_id} no encontrado.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Log de backup con ID {log_id} no encontrado.")
    return log
