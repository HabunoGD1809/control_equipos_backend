import logging
from typing import Any, List, Dict # Dict se usa en /count/unread
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body # Body se usa en mark_notification
from sqlalchemy.orm import Session
# IntegrityError no es comúnmente esperado aquí a menos que haya constraints inesperadas.
# from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.schemas.notificacion import Notificacion, NotificacionUpdate # NotificacionUpdate se usa para marcar como leída/no leída
from app.schemas.common import Msg
from app.services.notificacion import notificacion_service # Servicio ya modificado
from app.models.usuario import Usuario as UsuarioModel

logger = logging.getLogger(__name__)
router = APIRouter()

# Permisos (las notificaciones suelen ser específicas del usuario,
# por lo que la mayoría de las validaciones son sobre si el current_user es el propietario)
# No se suelen necesitar permisos de rol específicos para leer/marcar las propias notificaciones.
# Se podría añadir un permiso si un admin necesitara ver/gestionar notificaciones de otros.

@router.get("/",
            response_model=List[Notificacion], # Devuelve lista de notificaciones completas
            summary="Listar Notificaciones del Usuario Actual",
            response_description="Una lista de notificaciones para el usuario autenticado.")
def read_notificaciones_usuario_actual( # Renombrado para claridad
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
    solo_no_leidas: bool = Query(False, description="Mostrar solo las notificaciones no leídas"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100), # Límite más bajo para notificaciones
) -> Any:
    """
    Obtiene las notificaciones para el usuario actualmente autenticado.
    Permite filtrar para ver solo las no leídas.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando sus notificaciones (SoloNoLeidas: {solo_no_leidas}).")
    notificaciones = notificacion_service.get_multi_by_user(
        db,
        usuario_id=current_user.id,
        solo_no_leidas=solo_no_leidas,
        skip=skip,
        limit=limit
    )
    return notificaciones

@router.get("/count/unread",
            response_model=Dict[str, int], # Devuelve {'unread_count': X}
            summary="Contar Notificaciones No Leídas del Usuario Actual",
            response_description="Número de notificaciones no leídas para el usuario actual.")
def count_notificaciones_no_leidas_usuario_actual( # Renombrado
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene la cantidad de notificaciones no leídas para el usuario actual.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando conteo de notificaciones no leídas.")
    count = notificacion_service.get_unread_count_by_user(db, usuario_id=current_user.id)
    return {"unread_count": count}

@router.post("/marcar-todas-leidas",
             response_model=Msg, # Devuelve un mensaje de confirmación
             summary="Marcar todas las Notificaciones del Usuario Actual como Leídas",
             response_description="Mensaje de confirmación con el número de notificaciones actualizadas.")
def mark_all_notificaciones_as_read_usuario_actual( # Renombrado
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Marca todas las notificaciones no leídas del usuario actual como leídas.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' marcando todas sus notificaciones como leídas.")
    try:
        # El servicio .mark_all_as_read_for_user() ya NO hace commit.
        # Devuelve el número de filas que serían afectadas.
        affected_rows = notificacion_service.mark_all_as_read_for_user(db, usuario_id=current_user.id)
        if affected_rows > 0: # Solo hacer commit si algo cambió
            db.commit()
            logger.info(f"Usuario '{current_user.nombre_usuario}' marcó {affected_rows} notificación(es) como leídas.")
        else:
            logger.info(f"Usuario '{current_user.nombre_usuario}' no tenía notificaciones no leídas para marcar.")
        
        # No es necesario db.refresh() aquí ya que no devolvemos los objetos notificación.
        return {"msg": f"{affected_rows} notificación(es) marcada(s) como leída(s)."}
    except Exception as e: # Error inesperado
        db.rollback() # Rollback en caso de error durante el proceso
        logger.error(f"Error al marcar todas las notificaciones como leídas para usuario '{current_user.nombre_usuario}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al marcar las notificaciones como leídas.")

@router.put("/{notificacion_id}/marcar",
            response_model=Notificacion, # Devuelve la notificación actualizada
            summary="Marcar una Notificación como Leída/No Leída",
            response_description="La notificación con su estado actualizado.")
def mark_notificacion_leida_no_leida( # Renombrado
    *,
    db: Session = Depends(deps.get_db),
    notificacion_id: PyUUID,
    update_in: NotificacionUpdate, # Schema que espera {'leido': true/false}
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Marca una notificación específica como leída o no leída.
    Solo el usuario propietario de la notificación puede hacerlo.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando marcar notificación ID: {notificacion_id} como leido={update_in.leido}.")
    db_notificacion = notificacion_service.get_or_404(db, id=notificacion_id) # Lanza 404 si no existe

    if db_notificacion.usuario_id != current_user.id:
        logger.warning(f"Usuario '{current_user.nombre_usuario}' (ID: {current_user.id}) intentó marcar notificación {notificacion_id} que pertenece a usuario ID {db_notificacion.usuario_id}.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permiso para modificar esta notificación.")

    try:
        # El servicio .mark_as() ya NO hace commit.
        updated_notification = notificacion_service.mark_as(db=db, db_obj=db_notificacion, read_status=update_in.leido)
        
        if db.is_modified(updated_notification): # Verificar si el objeto fue modificado por el servicio
            db.commit()
            db.refresh(updated_notification) # Refrescar para obtener la fecha_leido actualizada.
            logger.info(f"Notificación ID {notificacion_id} marcada como {'leída' if update_in.leido else 'no leída'} por usuario '{current_user.nombre_usuario}'.")
        else:
            logger.info(f"Notificación ID {notificacion_id} no requirió cambios de estado (ya estaba leido={update_in.leido}).")
            # No es necesario commit ni refresh si no hubo cambios.
            
        return updated_notification
    except Exception as e: # Error inesperado
        db.rollback()
        logger.error(f"Error al marcar notificación ID {notificacion_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al marcar la notificación.")


@router.delete("/{notificacion_id}",
               response_model=Msg,
               status_code=status.HTTP_200_OK, # O HTTP_204_NO_CONTENT si no se devuelve cuerpo
               summary="Eliminar una Notificación",
               response_description="Mensaje de confirmación.")
def delete_notificacion_propia( # Renombrado
    *,
    db: Session = Depends(deps.get_db),
    notificacion_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Elimina una notificación específica.
    Solo el propietario puede eliminar su notificación.
    """
    logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando eliminar notificación ID: {notificacion_id}.")
    db_notificacion = notificacion_service.get_or_404(db, id=notificacion_id) # Lanza 404

    if db_notificacion.usuario_id != current_user.id:
        logger.warning(f"Usuario '{current_user.nombre_usuario}' (ID: {current_user.id}) intentó borrar notificación {notificacion_id} que pertenece a usuario ID {db_notificacion.usuario_id}.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permiso para eliminar esta notificación.")

    try:
        # El servicio .remove() (heredado de BaseService) ya NO hace commit.
        notificacion_service.remove(db=db, id=notificacion_id)
        db.commit()
        logger.info(f"Notificación ID {notificacion_id} eliminada por su propietario '{current_user.nombre_usuario}'.")
        return {"msg": f"Notificación (ID: {notificacion_id}) eliminada."}
    # IntegrityError no es común al eliminar notificaciones a menos que tengan FKs raras.
    except Exception as e: # Error inesperado
        db.rollback()
        logger.error(f"Error eliminando notificación ID {notificacion_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al eliminar la notificación.")
