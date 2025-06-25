import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.audit_log import AuditLog as AuditLogSchema 
from app.services.audit_log import audit_log_service # Servicio ya revisado
from app.models.usuario import Usuario as UsuarioModel # Para el usuario actual

logger = logging.getLogger(__name__)
# Permiso requerido
PERM_VER_AUDITORIA = "ver_auditoria"

router = APIRouter()

@router.get("/",
            response_model=List[AuditLogSchema], # Usar el schema renombrado
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_AUDITORIA]))],
            summary="Consultar Logs de Auditoría",
            response_description="Una lista de registros de auditoría, filtrada opcionalmente.")
def read_audit_logs(
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user), # Para logging
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500), # Límite máximo ajustado
    table_name: Optional[str] = Query(None, description="Filtrar por nombre de tabla afectada (case-insensitive)"),
    operation: Optional[str] = Query(None, description="Filtrar por tipo de operación (INSERT, UPDATE, DELETE)"),
    username: Optional[str] = Query(None, description="Filtrar por usuario de base de datos (case-insensitive)"),
    app_user_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de usuario de la aplicación"),
    record_pk_value: Optional[str] = Query(None, description="Filtrar por valor de la clave primaria del registro afectado (búsqueda textual en JSON)"), # Nuevo filtro
    start_time: Optional[datetime] = Query(None, description="Fecha/hora mínima del registro (formato ISO)"),
    end_time: Optional[datetime] = Query(None, description="Fecha/hora máxima del registro (formato ISO)"),
) -> Any:
    """
    Obtiene una lista de registros del log de auditoría, permitiendo aplicar filtros.
    Requiere el permiso: `ver_auditoria`.
    """
    logger.info(
        f"Usuario '{current_user.nombre_usuario}' consultando logs de auditoría con filtros: "
        f"Table='{table_name}', Op='{operation}', DBUser='{username}', AppUserID='{app_user_id}', "
        f"RecordPK='{record_pk_value}', Rango='{start_time}-{end_time}', Skip={skip}, Limit={limit}"
    )

    if start_time and end_time and end_time <= start_time:
        logger.warning("Consulta de auditoría rechazada: fecha_fin debe ser posterior a fecha_inicio.")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha de fin debe ser posterior a la fecha de inicio para el filtro.")

    try:
        logs = audit_log_service.get_multi(
            db,
            skip=skip,
            limit=limit,
            table_name=table_name,
            operation=operation,
            username=username,
            app_user_id=app_user_id,
            record_pk_value=record_pk_value, # Pasar el nuevo filtro
            start_time=start_time,
            end_time=end_time
        )
        logger.info(f"Consulta de auditoría devolvió {len(logs)} registro(s).")
        return logs
    except Exception as e: # Captura genérica, el servicio no debería lanzar errores inesperados aquí
        logger.error(f"Error inesperado al consultar logs de auditoría: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al consultar los logs de auditoría.")

# Un endpoint GET para un log específico por su PK compuesta podría ser:
# /by-pk?record_id={record_id_str}&timestamp={timestamp_iso}
# Pero como la PK real de audit_log es (id, audit_timestamp) donde 'id' es la PK de la tabla auditada,
# el endpoint get del servicio ya lo maneja. Exponerlo en la API podría no ser tan útil como el get_multi.
