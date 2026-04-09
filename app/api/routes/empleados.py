import logging
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.schemas.empleado import EmpleadoRead, EmpleadoCreate, EmpleadoUpdate, EmpleadoSimple
from app.services.empleado import empleado_service
from app.core import permissions as perms

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/", response_model=List[EmpleadoRead], summary="Listar empleados")
def read_empleados(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user = Depends(deps.get_current_active_user)
) -> Any:
    """Obtiene el catálogo de empleados."""
    return empleado_service.get_multi(db, skip=skip, limit=limit)

@router.get("/search", response_model=List[EmpleadoSimple], summary="Buscar empleados")
def search_empleados(
    query: str = Query(..., min_length=2),
    db: Session = Depends(deps.get_db),
    current_user = Depends(deps.get_current_active_user)
) -> Any:
    """Busca empleados por nombre o correo para autocompletado."""
    return empleado_service.search(db, query=query)

@router.post("/", response_model=EmpleadoRead, status_code=status.HTTP_201_CREATED)
def create_empleado(
    *,
    db: Session = Depends(deps.get_db),
    empleado_in: EmpleadoCreate,
    current_user = Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_CATALOGOS]))
) -> Any:
    """Crea un nuevo empleado en el catálogo."""
    try:
        empleado = empleado_service.create(db=db, obj_in=empleado_in)
        db.commit()
        db.refresh(empleado)
        logger.info(f"Empleado creado: {empleado.nombre_completo} (ID: {empleado.id})")
        return empleado
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un empleado con ese correo o datos conflictivos.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando empleado: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al crear el empleado.")

@router.put("/{id}", response_model=EmpleadoRead)
def update_empleado(
    *,
    db: Session = Depends(deps.get_db),
    id: UUID,
    empleado_in: EmpleadoUpdate,
    current_user = Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_CATALOGOS]))
) -> Any:
    """Actualiza la información de un empleado."""
    db_empleado = empleado_service.get_or_404(db, id=id)
    try:
        updated_empleado = empleado_service.update(db=db, db_obj=db_empleado, obj_in=empleado_in)
        db.commit()
        db.refresh(updated_empleado)
        return updated_empleado
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto de datos. Revisa el correo corporativo.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error actualizando empleado ID {id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar el empleado.")

@router.delete("/{id}", response_model=EmpleadoRead)
def disable_empleado(
    *,
    db: Session = Depends(deps.get_db),
    id: UUID,
    current_user = Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_CATALOGOS]))
) -> Any:
    """Inactiva un empleado (borrado lógico)."""
    db_empleado = empleado_service.get_or_404(db, id=id)
    try:
        disabled_empleado = empleado_service.update(db=db, db_obj=db_empleado, obj_in={"is_active": False})
        db.commit()
        db.refresh(disabled_empleado)
        return disabled_empleado
    except Exception as e:
        db.rollback()
        logger.error(f"Error desactivando empleado ID {id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al desactivar el empleado.")
