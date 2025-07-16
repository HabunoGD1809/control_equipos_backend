import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from psycopg.errors import ExclusionViolation

from app.api import deps
from app.core import permissions as perms
from app.schemas.reserva_equipo import (
    ReservaEquipo, ReservaEquipoCreate, ReservaEquipoUpdate,
    ReservaEquipoUpdateEstado, ReservaEquipoCheckInOut, EstadoReservaEnum
)
from app.schemas.common import Msg
from app.services.reserva_equipo import reserva_equipo_service
from app.models.usuario import Usuario as UsuarioModel

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "/",
    response_model=ReservaEquipo,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(deps.PermissionChecker([perms.PERM_RESERVAR_EQUIPOS]))],
    summary="Crear una nueva Reserva de Equipo",
    response_description="La reserva creada."
)
def create_reserva(
    *,
    db: Session = Depends(deps.get_db),
    reserva_in: ReservaEquipoCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Crea una nueva reserva para un equipo."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' creando reserva para Equipo ID {reserva_in.equipo_id}")

    try:
        reserva = reserva_equipo_service.create_with_user(db=db, obj_in=reserva_in, current_user=current_user)
        db.commit() # Intenta confirmar la transacción
        db.refresh(reserva, attribute_names=['equipo', 'solicitante', 'aprobado_por'])
        return reserva
    except IntegrityError as e:
        db.rollback()
        # Comprueba si el error es por la restricción de exclusión
        if isinstance(e.orig, ExclusionViolation):
            logger.warning(f"Conflicto de reserva detectado para equipo {reserva_in.equipo_id}.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conflicto de reserva: El equipo ya está reservado en el horario solicitado.",
            )
        # Si no, relanza la excepción para que el manejador de errores general la capture
        raise e
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado al crear reserva para equipo {reserva_in.equipo_id}: {e}", exc_info=True)
        # Esto será capturado por el manejador de errores genérico
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al procesar la solicitud."
        )

@router.get("/",
            response_model=List[ReservaEquipo],
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_RESERVAS]))],
            summary="Listar Reservas de Equipos")
def read_reservas(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    equipo_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de equipo"),
    usuario_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de usuario solicitante"),
    estado: Optional[EstadoReservaEnum] = Query(None, description="Filtrar por estado de la reserva"),
    start_date: Optional[datetime] = Query(None, description="Fecha de inicio del rango a consultar"),
    end_date: Optional[datetime] = Query(None, description="Fecha de fin del rango a consultar"),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene una lista de reservas, con filtros opcionales.
    Requiere el permiso: `ver_reservas`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando reservas con filtros.")
    # TODO implementar el filtrado en el servicio o aquí mismo
    reservas = reserva_equipo_service.get_multi(db, skip=skip, limit=limit)
    return reservas

@router.get("/{reserva_id}",
            response_model=ReservaEquipo,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_RESERVAS]))],
            summary="Obtener Reserva por ID")
def read_reserva_by_id(
    reserva_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Obtiene la información detallada de una reserva específica."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando reserva ID: {reserva_id}.")
    return reserva_equipo_service.get_or_404(db, id=reserva_id)

@router.put("/{reserva_id}",
            response_model=ReservaEquipo,
            summary="Actualizar una Reserva")
def update_reserva(
    *,
    db: Session = Depends(deps.get_db),
    reserva_id: PyUUID,
    reserva_in: ReservaEquipoUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza los detalles de una reserva.
    - Un usuario con permiso `reservar_equipos` puede editar sus propias reservas.
    - Un usuario con permiso `aprobar_reservas` puede editar cualquier reserva.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando actualizar reserva ID: {reserva_id}")
    db_reserva = reserva_equipo_service.get_or_404(db, id=reserva_id)

    is_owner = db_reserva.usuario_solicitante_id == current_user.id
    can_manage_all = deps.user_has_permissions(current_user, {perms.PERM_APROBAR_RESERVAS})
    can_edit_own = deps.user_has_permissions(current_user, {perms.PERM_RESERVAR_EQUIPOS})
    is_editable_state = db_reserva.estado in [EstadoReservaEnum.PENDIENTE_APROBACION.value, EstadoReservaEnum.CONFIRMADA.value]

    if not (can_manage_all or (is_owner and is_editable_state and can_edit_own)):
        logger.warning(f"Usuario '{current_user.nombre_usuario}' no tiene permisos para editar reserva ID {reserva_id}.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos para modificar esta reserva.")

    try:
        updated_reserva = reserva_equipo_service.update(db=db, db_obj=db_reserva, obj_in=reserva_in)
        db.commit()
        db.refresh(updated_reserva, attribute_names=['equipo', 'solicitante', 'aprobado_por'])
        logger.info(f"Reserva ID {reserva_id} actualizada exitosamente.")
        return updated_reserva
    except HTTPException as http_exc:
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        if "reservas_equipo_equipo_id_periodo_reserva_excl" in error_detail.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: El nuevo horario se solapa con otra reserva.")
        logger.error(f"Error de Integridad al actualizar reserva {reserva_id}: {error_detail}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar la reserva.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado al actualizar reserva {reserva_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")

@router.patch("/{reserva_id}/estado",
              response_model=ReservaEquipo,
              dependencies=[Depends(deps.PermissionChecker([perms.PERM_APROBAR_RESERVAS]))],
              summary="Actualizar Estado de una Reserva (Admin/Gestor)")
def update_reserva_estado(
    *,
    db: Session = Depends(deps.get_db),
    reserva_id: PyUUID,
    estado_in: ReservaEquipoUpdateEstado,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Permite a un gestor cambiar el estado de una reserva (Confirmada, Rechazada, etc.)."""
    logger.info(f"Gestor '{current_user.nombre_usuario}' cambiando estado de reserva ID {reserva_id} a '{estado_in.estado}'.")
    db_reserva = reserva_equipo_service.get_or_404(db, id=reserva_id)
    try:
        updated_reserva = reserva_equipo_service.update_estado(db=db, db_obj=db_reserva, estado_in=estado_in, current_user=current_user)
        db.commit()
        db.refresh(updated_reserva, attribute_names=['equipo', 'solicitante', 'aprobado_por'])
        logger.info(f"Estado de reserva ID {reserva_id} cambiado a '{updated_reserva.estado}'.")
        return updated_reserva
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado cambiando estado de reserva ID {reserva_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al cambiar el estado.")

@router.post("/{reserva_id}/cancelar",
             response_model=ReservaEquipo,
             summary="Cancelar una Reserva Propia")
def cancel_reserva_propia(
    *,
    db: Session = Depends(deps.get_db),
    reserva_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Cancela una reserva propia que esté en un estado cancelable."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando cancelar su reserva ID: {reserva_id}.")
    db_reserva = reserva_equipo_service.get_or_404(db, id=reserva_id)

    if db_reserva.usuario_solicitante_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puede cancelar una reserva que no es suya.")
    
    if not deps.user_has_permissions(current_user, [perms.PERM_RESERVAR_EQUIPOS]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene el permiso necesario para cancelar reservas.")
        
    if db_reserva.estado not in ['Pendiente Aprobacion', 'Confirmada']:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Solo puede cancelar sus reservas en estado 'Pendiente Aprobacion' o 'Confirmada'. Estado actual: '{db_reserva.estado}'.")

    try:
        estado_in = ReservaEquipoUpdateEstado(estado=EstadoReservaEnum.CANCELADA_USUARIO, notas_administrador=f"Cancelada por el solicitante: {current_user.nombre_usuario}")
        updated_reserva = reserva_equipo_service.update_estado(db=db, db_obj=db_reserva, estado_in=estado_in, current_user=current_user)
        db.commit()
        db.refresh(updated_reserva, attribute_names=['equipo', 'solicitante', 'aprobado_por'])
        logger.info(f"Reserva ID {reserva_id} cancelada exitosamente.")
        return updated_reserva
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado cancelando reserva propia ID {reserva_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al cancelar la reserva.")

@router.patch("/{reserva_id}/check-in-out",
              response_model=ReservaEquipo,
              summary="Realizar Check-in o Check-out de una Reserva")
def check_in_out_reserva(
    *,
    db: Session = Depends(deps.get_db),
    reserva_id: PyUUID,
    check_data: ReservaEquipoCheckInOut,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Registra la recogida (check-in) o devolución (check-out) de un equipo.
    El solicitante o un gestor pueden realizar la acción.
    """
    db_reserva = reserva_equipo_service.get_or_404(db, id=reserva_id)
    
    is_owner = db_reserva.usuario_solicitante_id == current_user.id
    is_admin = deps.user_has_permissions(current_user, [perms.PERM_APROBAR_RESERVAS])

    if not (is_admin or (is_owner and deps.user_has_permissions(current_user, [perms.PERM_RESERVAR_EQUIPOS]))):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para realizar esta acción en esta reserva."
        )

    try:
        updated_reserva = reserva_equipo_service.check_in_out(db=db, db_obj=db_reserva, check_data=check_data, current_user=current_user)
        db.commit()
        db.refresh(updated_reserva, attribute_names=['equipo', 'solicitante', 'aprobado_por'])
        logger.info(f"Check-in/out realizado en reserva ID {reserva_id} por '{current_user.nombre_usuario}'.")
        return updated_reserva
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado en check-in/out para reserva {reserva_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")

@router.delete("/{reserva_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([perms.PERM_APROBAR_RESERVAS]))],
               summary="Eliminar una Reserva (Admin)")
def delete_reserva(
    *,
    db: Session = Depends(deps.get_db),
    reserva_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Elimina permanentemente una reserva (solo para limpieza de datos)."""
    logger.warning(f"Admin '{current_user.nombre_usuario}' intentando ELIMINAR permanentemente reserva ID: {reserva_id}")
    reserva_equipo_service.get_or_404(db, id=reserva_id)
    
    reserva_equipo_service.remove(db=db, id=reserva_id)
    db.commit()
    return {"msg": f"Reserva ID {reserva_id} eliminada permanentemente."}
