import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError as SQLAlchemyDBAPIError

from app.api import deps
from app.schemas.movimiento import Movimiento, MovimientoCreate, MovimientoUpdate, MovimientoEstadoUpdate
from app.services.movimiento import movimiento_service
from app.models.usuario import Usuario as UsuarioModel
from app.core import permissions as perms
from app.core.security import user_has_permissions

try:
    from psycopg import errors as psycopg_errors
    PG_RaiseException = psycopg_errors.RaiseException
except ImportError:
    psycopg_errors = None  # type: ignore
    PG_RaiseException = None  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/",
    response_model=Movimiento,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_REGISTRAR_MOVIMIENTOS]))],
    summary="Registrar un nuevo Movimiento de Equipo",
    response_description="El movimiento registrado."
)
def create_movimiento(
    request: Request,
    *,
    db: Session = Depends(deps.get_db),
    movimiento_in: MovimientoCreate = Body(...),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Registra un nuevo movimiento de equipo. Extrae IP y User-Agent para auditoría forense.
    """
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando registrar movimiento. IP: {client_ip}")

    try:
        movimiento = movimiento_service.create_movimiento_via_db_func(
            db=db,
            obj_in=movimiento_in,
            registrado_por_usuario=current_user,
            ip_origen=client_ip,
            user_agent=user_agent,
            autorizado_por_id=getattr(movimiento_in, 'autorizado_por_id', None)
        )
        db.commit()
        db.refresh(movimiento, attribute_names=['equipo', 'usuario_registrador', 'usuario_autorizador'])
        logger.info(f"Movimiento ID {movimiento.id} registrado exitosamente por '{current_user.nombre_usuario}'.")
        return movimiento

    except HTTPException as http_exc:
        db.rollback()
        logger.warning(f"Error HTTP al registrar movimiento: {http_exc.status_code} - {http_exc.detail}")
        raise http_exc

    except SQLAlchemyDBAPIError as e:
        db.rollback()
        if psycopg_errors and isinstance(e.orig, psycopg_errors.RaiseException):
            error_message = str(e.orig).split('CONTEXT:')[0].strip()
            logger.warning(f"Error de lógica de negocio desde BD: {error_message}")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_message)

        logger.error(f"Error de base de datos no manejado al registrar movimiento: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al procesar la solicitud.")

    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado registrando movimiento: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")


@router.get(
    "/",
    response_model=List[Movimiento],
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_MOVIMIENTOS]))],
    summary="Listar Movimientos de Equipos",
    response_description="Una lista de movimientos registrados."
)
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
        return movimiento_service.get_multi_by_equipo(db, equipo_id=equipo_id, skip=skip, limit=limit)
    logger.debug("Listando todos los movimientos (con paginación).")
    return movimiento_service.get_multi(db, skip=skip, limit=limit)


@router.get(
    "/{movimiento_id}",
    response_model=Movimiento,
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_MOVIMIENTOS]))],
    summary="Obtener un Movimiento por ID",
    response_description="Información detallada del movimiento."
)
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
    return movimiento_service.get_or_404(db, id=movimiento_id)


@router.put(
    "/{movimiento_id}",
    response_model=Movimiento,
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_EDITAR_MOVIMIENTOS]))],
    summary="Actualizar Observaciones/Info de Retorno de un Movimiento",
    response_description="Movimiento actualizado."
)
def update_movimiento_observaciones(
    *,
    db: Session = Depends(deps.get_db),
    movimiento_id: PyUUID,
    movimiento_in: MovimientoUpdate = Body(...),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza campos permitidos de un movimiento (ej: observaciones, fecha_retorno).
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


@router.patch(
    "/{movimiento_id}/estado",
    response_model=Movimiento,
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_MOVIMIENTOS]))],
    summary="Cambiar el estado de un Movimiento (Autorizar, Rechazar, Recibir)"
)
def change_movimiento_estado(
    *,
    db: Session = Depends(deps.get_db),
    movimiento_id: PyUUID,
    estado_in: MovimientoEstadoUpdate = Body(...),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Endpoint explícito para la máquina de estados y Handoffs.
    Autorizar/Rechazar requiere permiso adicional: `autorizar_movimientos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando cambiar estado de movimiento ID: {movimiento_id} a '{estado_in.estado}'.")
    db_movimiento = movimiento_service.get_or_404(db, id=movimiento_id)

    # Verificación de permiso adicional para acciones de autorización
    if estado_in.estado in ["Autorizado", "Rechazado"]:
        if not user_has_permissions(current_user, {perms.PERM_AUTORIZAR_MOVIMIENTOS}):
            logger.warning(f"Acceso denegado: '{current_user.nombre_usuario}' intentó autorizar/rechazar movimiento sin permiso.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para autorizar o rechazar movimientos.")

    try:
        updated_movimiento = movimiento_service.cambiar_estado(
            db=db,
            movimiento=db_movimiento,
            obj_in=estado_in,
            current_user=current_user
        )
        db.commit()
        db.refresh(updated_movimiento, attribute_names=['equipo', 'usuario_registrador', 'usuario_autorizador'])
        logger.info(f"Estado de movimiento ID {movimiento_id} cambiado a '{estado_in.estado}' por '{current_user.nombre_usuario}'.")
        return updated_movimiento
    except HTTPException as http_exc:
        db.rollback()
        logger.warning(f"Error HTTP al cambiar estado de movimiento ID {movimiento_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado cambiando estado del movimiento ID {movimiento_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al procesar el estado.")


@router.post(
    "/{movimiento_id}/cancelar",
    response_model=Movimiento,
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_CANCELAR_MOVIMIENTOS]))],
    summary="Cancelar un Movimiento",
    response_description="El movimiento con estado 'Cancelado'."
)
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
