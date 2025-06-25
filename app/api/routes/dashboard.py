import logging
from typing import Any 

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.dashboard import DashboardData
from app.services.dashboard import dashboard_service # Servicio ya revisado
from app.models.usuario import Usuario as UsuarioModel # Para el usuario actual

logger = logging.getLogger(__name__)
PERM_VER_DASHBOARD = "ver_dashboard"

router = APIRouter()

@router.get("/",
            response_model=DashboardData,
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_DASHBOARD]))],
            summary="Obtener Datos Resumen del Dashboard",
            response_description="Un resumen de métricas clave del sistema.")
def read_dashboard_summary(
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user), # Para logging
) -> Any:
    """
    Obtiene datos agregados y resúmenes para mostrar en un dashboard principal.
    Requiere el permiso: `ver_dashboard`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando datos resumen del dashboard.")
    try:
        summary_data = dashboard_service.get_summary(db)
        logger.info(f"Datos del dashboard generados exitosamente para el usuario '{current_user.nombre_usuario}'.")
        return summary_data
    except Exception as e: # Captura genérica, el servicio puede lanzar errores si las queries fallan
        logger.error(f"Error inesperado al generar datos del dashboard para el usuario '{current_user.nombre_usuario}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al generar los datos del dashboard.")
