import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.mantenimiento import Mantenimiento, MantenimientoCreate, MantenimientoUpdate
from app.schemas.common import Msg
from app.services.mantenimiento import mantenimiento_service
from app.models.usuario import Usuario as UsuarioModel

PERM_VER_MANTENIMIENTOS = "ver_mantenimientos"
PERM_PROGRAMAR_MANTENIMIENTOS = "programar_mantenimientos"
PERM_EDITAR_MANTENIMIENTOS = "editar_mantenimientos"
PERM_ELIMINAR_MANTENIMIENTOS = "eliminar_mantenimientos"

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/",
             response_model=Mantenimiento,
             status_code=status.HTTP_201_CREATED,
             # ===== INICIO DE LA CORRECCIÓN =====
             dependencies=[Depends(deps.PermissionChecker([PERM_PROGRAMAR_MANTENIMIENTOS]))],
             # ===== FIN DE LA CORRECCIÓN =====
             summary="Programar un Nuevo Mantenimiento",
             )
def create_mantenimiento(
    *,
    db: Session = Depends(deps.get_db),
    mantenimiento_in: MantenimientoCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Programa un nuevo mantenimiento para un equipo.
    Requiere el permiso: `programar_mantenimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando crear mantenimiento para equipo ID: {mantenimiento_in.equipo_id}.")
    try:
        mantenimiento = mantenimiento_service.create(db=db, obj_in=mantenimiento_in)
        db.commit()
        db.refresh(mantenimiento)
        db.refresh(mantenimiento, attribute_names=['equipo', 'tipo_mantenimiento', 'proveedor_servicio']) # Cargar relaciones
        logger.info(f"Mantenimiento ID {mantenimiento.id} para equipo ID {mantenimiento.equipo_id} creado exitosamente por '{current_user.nombre_usuario}'.")
        return mantenimiento
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al crear mantenimiento para equipo ID {mantenimiento_in.equipo_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando mantenimiento para equipo ID {mantenimiento_in.equipo_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el mantenimiento.")

@router.get("/",
            response_model=List[Mantenimiento],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_MANTENIMIENTOS]))],
            summary="Listar Mantenimientos",
            )
def read_mantenimientos(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    equipo_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de equipo"),
    estado: Optional[str] = Query(None, description="Filtrar por estado del mantenimiento"),
    tipo_mantenimiento_id: Optional[PyUUID] = Query(None, description="Filtrar por tipo de mantenimiento"),
    start_date: Optional[datetime] = Query(None, description="Fecha de inicio para filtrar por fecha programada"),
    end_date: Optional[datetime] = Query(None, description="Fecha de fin para filtrar por fecha programada"),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene una lista de mantenimientos, con filtros opcionales.
    Requiere el permiso: `ver_mantenimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando mantenimientos.")
    mantenimientos = mantenimiento_service.get_multi_with_filters(
        db,
        skip=skip,
        limit=limit,
        equipo_id=equipo_id,
        estado=estado,
        tipo_mantenimiento_id=tipo_mantenimiento_id,
        start_date=start_date,
        end_date=end_date
    )
    return mantenimientos

@router.get("/{mantenimiento_id}",
            response_model=Mantenimiento,
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_MANTENIMIENTOS]))],
            summary="Obtener Mantenimiento por ID",
            )
def read_mantenimiento_by_id(
    mantenimiento_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene los detalles de un mantenimiento específico.
    Requiere el permiso: `ver_mantenimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando mantenimiento ID: {mantenimiento_id}.")
    return mantenimiento_service.get_or_404(db, id=mantenimiento_id)

@router.put("/{mantenimiento_id}",
            response_model=Mantenimiento,
            dependencies=[Depends(deps.PermissionChecker([PERM_EDITAR_MANTENIMIENTOS]))],
            summary="Actualizar un Mantenimiento",
            )
def update_mantenimiento(
    *,
    db: Session = Depends(deps.get_db),
    mantenimiento_id: PyUUID,
    mantenimiento_in: MantenimientoUpdate = Body(...),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza la información de un mantenimiento existente.
    Requiere el permiso: `editar_mantenimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando actualizar mantenimiento ID: {mantenimiento_id} con datos {mantenimiento_in.model_dump(exclude_unset=True)}")
    db_mantenimiento = mantenimiento_service.get_or_404(db, id=mantenimiento_id)
    try:
        updated_mantenimiento = mantenimiento_service.update(db=db, db_obj=db_mantenimiento, obj_in=mantenimiento_in)
        db.commit()
        db.refresh(updated_mantenimiento)
        db.refresh(updated_mantenimiento, attribute_names=['equipo', 'tipo_mantenimiento', 'proveedor_servicio'])
        logger.info(f"Mantenimiento ID {mantenimiento_id} actualizado exitosamente por '{current_user.nombre_usuario}'.")
        return updated_mantenimiento
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al actualizar mantenimiento ID {mantenimiento_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando mantenimiento ID {mantenimiento_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el mantenimiento.")


@router.delete("/{mantenimiento_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_ELIMINAR_MANTENIMIENTOS]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar un Mantenimiento",
               )
def delete_mantenimiento(
    *,
    db: Session = Depends(deps.get_db),
    mantenimiento_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Elimina un registro de mantenimiento.
    Requiere el permiso: `eliminar_mantenimientos`.
    """
    logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando eliminar mantenimiento ID: {mantenimiento_id}.")
    mantenimiento_a_eliminar = mantenimiento_service.get_or_404(db, id=mantenimiento_id)
    equipo_id_log = mantenimiento_a_eliminar.equipo_id
    try:
        mantenimiento_service.remove(db=db, id=mantenimiento_id)
        db.commit()
        logger.info(f"Mantenimiento ID {mantenimiento_id} (para equipo ID {equipo_id_log}) eliminado exitosamente por '{current_user.nombre_usuario}'.")
        return {"msg": f"Mantenimiento con ID {mantenimiento_id} eliminado correctamente."}
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando mantenimiento ID {mantenimiento_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")
