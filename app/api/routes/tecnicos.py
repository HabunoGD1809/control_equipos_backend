import logging
from typing import Any, List
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.core import permissions as perms
from app.schemas.tecnico import Tecnico, TecnicoCreate, TecnicoUpdate
from app.services.tecnico import tecnico_service
from app.models.usuario import Usuario as UsuarioModel

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get(
    "/",
    response_model=List[Tecnico],
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_MANTENIMIENTOS]))],
    summary="Listar Técnicos de Mantenimiento",
    response_description="Una lista de técnicos (internos y externos) registrados en el sistema."
)
def read_tecnicos(
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> Any:
    """
    Obtiene la lista del catálogo de técnicos.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando técnicos (skip={skip}, limit={limit}).")
    try:
        tecnicos = tecnico_service.get_multi(db, skip=skip, limit=limit)
        return tecnicos
    except Exception as e:
        logger.error(f"Error al consultar técnicos: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al consultar el catálogo de técnicos."
        )

@router.post(
    "/",
    response_model=Tecnico,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_PROGRAMAR_MANTENIMIENTOS]))],
    summary="Registrar un nuevo Técnico"
)
def create_tecnico(
    *,
    db: Session = Depends(deps.get_db),
    tecnico_in: TecnicoCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Registra un nuevo técnico (interno o contratista externo).
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' registrando nuevo técnico: {tecnico_in.nombre_completo}.")
    
    if tecnico_in.es_externo and not tecnico_in.proveedor_id:
        raise HTTPException(status_code=422, detail="Un técnico externo debe estar asociado a un proveedor.")
        
    tecnico = tecnico_service.create(db, obj_in=tecnico_in)
    db.commit()
    db.refresh(tecnico)
    return tecnico

@router.put(
    "/{tecnico_id}",
    response_model=Tecnico,
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_PROGRAMAR_MANTENIMIENTOS]))],
    summary="Actualizar un Técnico"
)
def update_tecnico(
    *,
    db: Session = Depends(deps.get_db),
    tecnico_id: PyUUID,
    tecnico_in: TecnicoUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza la información de un técnico existente.
    """
    tecnico = tecnico_service.get(db, id=tecnico_id)
    if not tecnico:
        raise HTTPException(status_code=404, detail="Técnico no encontrado.")
        
    logger.info(f"Usuario '{current_user.nombre_usuario}' actualizando técnico ID: {tecnico_id}.")
    tecnico = tecnico_service.update(db, db_obj=tecnico, obj_in=tecnico_in)
    db.commit()
    db.refresh(tecnico)
    return tecnico
