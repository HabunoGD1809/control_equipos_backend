import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError # Para manejo de errores de BD

from app.api import deps
from app.schemas.mantenimiento import Mantenimiento, MantenimientoCreate, MantenimientoUpdate
from app.schemas.common import Msg
from app.services.mantenimiento import mantenimiento_service # Servicio ya modificado
from app.models.usuario import Usuario as UsuarioModel

logger = logging.getLogger(__name__)
router = APIRouter()

# Permisos (ajustar según los nombres exactos en la BD)
PERM_PROGRAMAR_MANTENIMIENTOS = "programar_mantenimientos"
PERM_EDITAR_MANTENIMIENTOS = "editar_mantenimientos"
PERM_ELIMINAR_MANTENIMIENTOS = "eliminar_mantenimientos"
PERM_VER_MANTENIMIENTOS = "ver_mantenimientos"

@router.post("/",
             response_model=Mantenimiento,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_PROGRAMAR_MANTENIMIENTOS]))],
             summary="Registrar un nuevo Mantenimiento",
             response_description="El registro de mantenimiento creado.")
def create_mantenimiento(
    *,
    db: Session = Depends(deps.get_db),
    mantenimiento_in: MantenimientoCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Crea un nuevo registro de mantenimiento para un equipo.
    Requiere el permiso: `programar_mantenimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando crear mantenimiento para equipo ID: {mantenimiento_in.equipo_id}.")
    try:
        # El servicio .create() ya no hace commit y maneja validaciones de FKs.
        mantenimiento = mantenimiento_service.create(db=db, obj_in=mantenimiento_in)
        db.commit()
        # Es crucial refrescar aquí para obtener fecha_proximo_mantenimiento si es calculado por trigger
        db.refresh(mantenimiento)
        logger.info(f"Mantenimiento ID {mantenimiento.id} para equipo ID {mantenimiento.equipo_id} creado exitosamente por '{current_user.nombre_usuario}'.")
        return mantenimiento
    except HTTPException as http_exc:
        # Errores de validación del servicio (ej. 404 por equipo_id no encontrado)
        logger.warning(f"Error HTTP al crear mantenimiento para equipo ID {mantenimiento_in.equipo_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e: # Fallback por si el servicio no valida todo
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al crear mantenimiento para equipo ID {mantenimiento_in.equipo_id}: {error_detail}", exc_info=True)
        # Aquí se podría intentar ser más específico si hay constraints de unicidad en Mantenimiento
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear el mantenimiento.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando mantenimiento para equipo ID {mantenimiento_in.equipo_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el mantenimiento.")

@router.get("/",
            response_model=List[Mantenimiento],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_MANTENIMIENTOS]))],
            summary="Listar Mantenimientos",
            response_description="Una lista de registros de mantenimiento.")
def read_mantenimientos(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    equipo_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de equipo"),
    proximos: Optional[bool] = Query(False, description="Listar solo mantenimientos próximos o programados a vencer"),
    dias_vista: int = Query(30, ge=1, le=365, description="Número de días hacia adelante para buscar próximos mantenimientos (si proximos=True)"),
    # estado: Optional[str] = Query(None, description="Filtrar por estado"), # TODO: Implementar filtro por estado en servicio
    # tipo_mantenimiento_id: Optional[PyUUID] = Query(None, description="Filtrar por tipo de mantenimiento ID"), # TODO: Implementar
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene una lista de registros de mantenimiento.
    Requiere el permiso: `ver_mantenimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando mantenimientos.")
    if proximos:
        logger.debug(f"Listando próximos mantenimientos (días vista: {dias_vista}).")
        mantenimientos = mantenimiento_service.get_proximos_mantenimientos(db, days_ahead=dias_vista, skip=skip, limit=limit)
    elif equipo_id:
        logger.debug(f"Listando mantenimientos para equipo ID: {equipo_id}.")
        mantenimientos = mantenimiento_service.get_multi_by_equipo(db, equipo_id=equipo_id, skip=skip, limit=limit)
    else:
        # Aquí se podría implementar una lógica de filtrado más avanzada en el servicio
        # que combine estado, tipo_mantenimiento_id, etc. si se proporcionan.
        # Por ahora, solo get_multi general.
        logger.debug("Listando todos los mantenimientos (con paginación).")
        mantenimientos = mantenimiento_service.get_multi(db, skip=skip, limit=limit)
    return mantenimientos


@router.get("/{mantenimiento_id}",
            response_model=Mantenimiento,
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_MANTENIMIENTOS]))],
            summary="Obtener un Mantenimiento por ID",
            response_description="Información detallada del mantenimiento.")
def read_mantenimiento_by_id(
    mantenimiento_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene la información detallada de un registro de mantenimiento específico.
    Requiere el permiso: `ver_mantenimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando mantenimiento ID: {mantenimiento_id}.")
    mantenimiento = mantenimiento_service.get_or_404(db, id=mantenimiento_id) # Lanza 404 si no existe
    return mantenimiento


@router.put("/{mantenimiento_id}",
            response_model=Mantenimiento,
            dependencies=[Depends(deps.PermissionChecker([PERM_EDITAR_MANTENIMIENTOS]))],
            summary="Actualizar un Mantenimiento",
            response_description="Información actualizada del mantenimiento.")
def update_mantenimiento(
    *,
    db: Session = Depends(deps.get_db),
    mantenimiento_id: PyUUID,
    mantenimiento_in: MantenimientoUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza la información de un registro de mantenimiento existente.
    Requiere el permiso: `editar_mantenimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando actualizar mantenimiento ID: {mantenimiento_id} con datos {mantenimiento_in.model_dump(exclude_unset=True)}")
    db_mantenimiento = mantenimiento_service.get_or_404(db, id=mantenimiento_id) # Lanza 404 si no existe
    
    try:
        # El servicio .update() ya no hace commit y maneja validaciones.
        updated_mantenimiento = mantenimiento_service.update(db=db, db_obj=db_mantenimiento, obj_in=mantenimiento_in)
        db.commit()
        # Refrescar para obtener fecha_proximo_mantenimiento si fue recalculado por trigger
        # (ej. al cambiar estado a 'Completado').
        db.refresh(updated_mantenimiento)
        logger.info(f"Mantenimiento ID {mantenimiento_id} actualizado exitosamente por '{current_user.nombre_usuario}'.")
        return updated_mantenimiento
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al actualizar mantenimiento ID {mantenimiento_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e: # Poco probable si las validaciones del servicio son exhaustivas
        db.rollback()
        logger.error(f"Error de integridad al actualizar mantenimiento ID {mantenimiento_id}: {getattr(e, 'orig', e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar el mantenimiento.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando mantenimiento ID {mantenimiento_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el mantenimiento.")


@router.delete("/{mantenimiento_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_ELIMINAR_MANTENIMIENTOS]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar un Mantenimiento",
               response_description="Mensaje de confirmación.")
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
    
    # Obtener el objeto primero para el mensaje de log, el servicio remove también hace get_or_404
    mantenimiento_a_eliminar = mantenimiento_service.get_or_404(db, id=mantenimiento_id)
    mantenimiento_desc_para_log = f"para equipo ID {mantenimiento_a_eliminar.equipo_id}"
    
    try:
        # El servicio .remove() ya no hace commit.
        mantenimiento_service.remove(db=db, id=mantenimiento_id)
        db.commit()
        logger.info(f"Mantenimiento ID {mantenimiento_id} ({mantenimiento_desc_para_log}) eliminado exitosamente por '{current_user.nombre_usuario}'.")
        return {"msg": f"Registro de mantenimiento (ID: {mantenimiento_id}) eliminado correctamente."}
    except HTTPException as http_exc: # Probablemente 404 si no se encontró
        raise http_exc
    except IntegrityError as e: # Si hay FKs que impiden el borrado (ej. documentos asociados con ON DELETE RESTRICT)
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al eliminar mantenimiento ID {mantenimiento_id}: {error_detail}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede eliminar el mantenimiento (ID: {mantenimiento_id}) porque tiene registros asociados."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando mantenimiento ID {mantenimiento_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar el mantenimiento.")
