import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DBAPIError as SQLAlchemyDBAPIError

from app.api import deps
from app.schemas.movimiento import Movimiento, MovimientoCreate, MovimientoUpdate
from app.schemas.common import Msg
from app.services.movimiento import movimiento_service
from app.models.usuario import Usuario as UsuarioModel

try:
    from psycopg import errors as psycopg_errors
    PG_RaiseException = psycopg_errors.RaiseException
except ImportError:
    psycopg_errors = None # type: ignore
    PG_RaiseException = None # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter()

PERM_REGISTRAR_MOVIMIENTOS = "registrar_movimientos"
PERM_VER_MOVIMIENTOS = "ver_movimientos"
PERM_EDITAR_MOVIMIENTOS = "editar_movimientos"
PERM_CANCELAR_MOVIMIENTOS = "cancelar_movimientos"

@router.post("/",
             response_model=Movimiento,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_REGISTRAR_MOVIMIENTOS]))],
             summary="Registrar un nuevo Movimiento de Equipo",
             response_description="El movimiento registrado.")
def create_movimiento(
    *,
    db: Session = Depends(deps.get_db),
    movimiento_in: MovimientoCreate = Body(...),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Registra un nuevo movimiento de equipo utilizando la función de base de datos
    `control_equipos.registrar_movimiento_equipo`.
    Esta función maneja la lógica de negocio, actualiza el estado/ubicación del equipo
    y crea el registro de movimiento.
    Requiere el permiso: `registrar_movimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando registrar movimiento tipo '{movimiento_in.tipo_movimiento}' para equipo ID '{movimiento_in.equipo_id}'.")
    
    autorizado_por_id_param = getattr(movimiento_in, 'autorizado_por_id', None)

    try:
        movimiento = movimiento_service.create_movimiento_via_db_func(
            db=db,
            obj_in=movimiento_in,
            registrado_por_usuario=current_user,
            autorizado_por_id=autorizado_por_id_param
        )
        db.commit()
        
        db.refresh(movimiento, attribute_names=['equipo', 'usuario_registrador', 'usuario_autorizador'])

        logger.info(f"Movimiento ID {movimiento.id} ({movimiento.tipo_movimiento}) para equipo ID {movimiento.equipo_id} registrado exitosamente por '{current_user.nombre_usuario}'.")
        return movimiento
    except HTTPException as http_exc: 
        db.rollback() 
        logger.warning(f"Error HTTP al registrar movimiento: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al registrar movimiento: {error_detail}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al registrar el movimiento (constraint).")
    except SQLAlchemyDBAPIError as e:
        db.rollback()
        original_exc = getattr(e, 'orig', None)
        error_message_for_client = str(original_exc if original_exc else e)
        logger.error(f"Error DBAPI al registrar movimiento: {error_message_for_client}", exc_info=True)
        
        if PG_RaiseException and isinstance(original_exc, PG_RaiseException):
            diag_message = getattr(getattr(original_exc, 'diag', None), 'message_primary', error_message_for_client)
            if "equipo no encontrado" in diag_message.lower():
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=diag_message)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error de base de datos al procesar: {diag_message}")

        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al registrar el movimiento.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado registrando movimiento: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al registrar el movimiento.")


@router.get("/",
            response_model=List[Movimiento],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_MOVIMIENTOS]))],
            summary="Listar Movimientos de Equipos",
            response_description="Una lista de movimientos registrados.")
def read_movimientos(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    equipo_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de equipo"),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene una lista de movimientos registrados, con filtros opcionales.
    Requiere el permiso: `ver_movimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando movimientos.")
    if equipo_id:
        logger.debug(f"Filtrando movimientos para equipo ID: {equipo_id}.")
        movimientos = movimiento_service.get_multi_by_equipo(db, equipo_id=equipo_id, skip=skip, limit=limit)
    else:
        logger.debug("Listando todos los movimientos (con paginación).")
        movimientos = movimiento_service.get_multi(db, skip=skip, limit=limit)
    return movimientos


@router.get("/{movimiento_id}",
            response_model=Movimiento,
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_MOVIMIENTOS]))],
            summary="Obtener un Movimiento por ID",
            response_description="Información detallada del movimiento.")
def read_movimiento_by_id(
    movimiento_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene la información detallada de un movimiento específico por su ID.
    Requiere el permiso: `ver_movimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando movimiento ID: {movimiento_id}.")
    movimiento = movimiento_service.get_or_404(db, id=movimiento_id)
    return movimiento


@router.put("/{movimiento_id}",
            response_model=Movimiento,
            dependencies=[Depends(deps.PermissionChecker([PERM_EDITAR_MOVIMIENTOS]))],
            summary="Actualizar Observaciones/Info de Retorno de un Movimiento",
            response_description="Movimiento actualizado.")
def update_movimiento_observaciones(
    *,
    db: Session = Depends(deps.get_db),
    movimiento_id: PyUUID,
    movimiento_in: MovimientoUpdate = Body(...),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza campos permitidos de un movimiento (ej: observaciones, fecha_retorno).
    La lógica de qué campos se pueden actualizar según el estado del movimiento
    está centralizada en el servicio `movimiento_service`.
    Requiere el permiso: `editar_movimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' actualizando movimiento ID: {movimiento_id} con datos: {movimiento_in.model_dump(exclude_unset=True)}")
    db_movimiento = movimiento_service.get_or_404(db, id=movimiento_id)
    
    try:
        updated_movimiento = movimiento_service.update(db=db, db_obj=db_movimiento, obj_in=movimiento_in)
        db.commit()
        db.refresh(updated_movimiento, attribute_names=['equipo', 'usuario_registrador', 'usuario_autorizador'])
        logger.info(f"Movimiento ID {movimiento_id} actualizado exitosamente por '{current_user.nombre_usuario}'.")
        return updated_movimiento
    except HTTPException as http_exc:
        db.rollback()
        logger.warning(f"Error HTTP al actualizar movimiento ID {movimiento_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando movimiento ID {movimiento_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el movimiento.")


@router.post("/{movimiento_id}/cancelar",
             response_model=Movimiento,
             dependencies=[Depends(deps.PermissionChecker([PERM_CANCELAR_MOVIMIENTOS]))],
             summary="Cancelar un Movimiento",
             response_description="El movimiento con estado 'Cancelado'.")
def cancel_movimiento(
    *,
    db: Session = Depends(deps.get_db),
    movimiento_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Marca un movimiento como 'Cancelado' si su estado actual lo permite.
    Requiere el permiso: `cancelar_movimientos`.
    """
    logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando cancelar movimiento ID: {movimiento_id}.")
    db_movimiento = movimiento_service.get_or_404(db, id=movimiento_id)
    
    try:
        cancelled_movimiento = movimiento_service.cancel_movimiento(db=db, movimiento=db_movimiento, current_user=current_user)
        db.commit()
        db.refresh(cancelled_movimiento, attribute_names=['equipo', 'usuario_registrador', 'usuario_autorizador'])
        
        logger.info(f"Movimiento ID {movimiento_id} cancelado exitosamente por '{current_user.nombre_usuario}'.")
        return cancelled_movimiento
    except HTTPException as http_exc:
        db.rollback()
        logger.warning(f"Error HTTP al cancelar movimiento ID {movimiento_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado cancelando movimiento ID {movimiento_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al cancelar el movimiento.")

# El DELETE de movimientos no suele ser una práctica común. Se cancelan o se completan.
# Si se necesitara, se implementaría similar a otros DELETEs, considerando si hay FKs que lo impidan.
