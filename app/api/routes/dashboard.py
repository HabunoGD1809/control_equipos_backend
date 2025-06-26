import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.dashboard import DashboardData
from app.services.dashboard import dashboard_service
from app.models.usuario import Usuario as UsuarioModel

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get(
    "/",
    response_model=DashboardData,
    dependencies=[Depends(deps.PermissionChecker(["ver_dashboard"]))],
    summary="Obtener Datos Resumen del Dashboard",
    response_description="Un resumen de métricas clave del sistema."
)
def read_dashboard_summary(
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
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
    except Exception as e:
        logger.error(f"Error al generar el resumen del dashboard: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al generar los datos del dashboard."
        )
