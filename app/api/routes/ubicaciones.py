import logging
from typing import Any, List
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.core import permissions as perms
from app.schemas.ubicacion import UbicacionRead, UbicacionCreate, UbicacionUpdate
from app.schemas.common import Msg
from app.services.ubicacion import ubicacion_service
from app.models.usuario import Usuario as UsuarioModel

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "/",
    response_model=UbicacionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_CATALOGOS]))]
)
def create_ubicacion(
    *,
    db: Session = Depends(deps.get_db),
    obj_in: UbicacionCreate
) -> Any:
    if ubicacion_service.get_by_nombre(db, nombre=obj_in.nombre):
        raise HTTPException(status_code=409, detail="Ya existe una ubicación con este nombre.")
    try:
        ubicacion = ubicacion_service.create(db=db, obj_in=obj_in)
        db.commit()
        db.refresh(ubicacion)
        logger.info(f"Ubicación '{obj_in.nombre}' creada exitosamente.")
        return ubicacion
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando ubicación '{obj_in.nombre}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al crear ubicación.")


@router.get(
    "/",
    response_model=List[UbicacionRead]
)
def read_ubicaciones(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
    current_user: UsuarioModel = Depends(deps.get_current_active_user)
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando ubicaciones (include_inactive={include_inactive}).")
    if include_inactive:
        return ubicacion_service.get_multi(db, skip=skip, limit=limit)
    return ubicacion_service.get_multi_active(db, skip=skip, limit=limit)


@router.put(
    "/{id}",
    response_model=UbicacionRead,
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_CATALOGOS]))]
)
def update_ubicacion(
    *,
    db: Session = Depends(deps.get_db),
    id: PyUUID,
    obj_in: UbicacionUpdate
) -> Any:
    db_obj = ubicacion_service.get_or_404(db, id=id)
    if obj_in.nombre and obj_in.nombre != db_obj.nombre:
        if ubicacion_service.get_by_nombre(db, nombre=obj_in.nombre):
            raise HTTPException(status_code=409, detail="Ya existe una ubicación con este nombre.")
    try:
        updated = ubicacion_service.update(db=db, db_obj=db_obj, obj_in=obj_in)
        db.commit()
        db.refresh(updated)
        logger.info(f"Ubicación ID {id} actualizada exitosamente.")
        return updated
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando ubicación ID {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al actualizar ubicación.")


@router.delete(
    "/{id}",
    response_model=Msg,
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_CATALOGOS]))]
)
def delete_ubicacion(
    *,
    db: Session = Depends(deps.get_db),
    id: PyUUID
) -> Any:
    """Realiza un Soft Delete de la ubicación."""
    try:
        ubicacion_service.remove(db=db, id=id)
        db.commit()
        logger.info(f"Ubicación ID {id} archivada correctamente (Soft Delete).")
        return {"msg": "Ubicación archivada correctamente (Soft Delete)."}
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando ubicación ID {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al eliminar ubicación.")
