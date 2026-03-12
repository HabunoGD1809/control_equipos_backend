import logging
import asyncio
from typing import Any, List, Dict
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import SessionLocal
from app.schemas.notificacion import Notificacion, NotificacionUpdate
from app.schemas.common import Msg
from app.services.notificacion import notificacion_service
from app.models.usuario import Usuario as UsuarioModel

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/stream")
async def stream_notificaciones(
    current_user: UsuarioModel = Depends(deps.get_current_user_sse),
    db: Session = Depends(deps.get_db)
):
    """
    Streaming SSE.
    Mantiene una conexión abierta y empuja un evento hacia el frontend
    cada vez que detecta un cambio en el número de notificaciones no leídas.
    """
    async def event_generator():
        last_count = -1
        while True:
            try:
                # Instanciamos un generador local para no bloquear la DB permanentemente
                with SessionLocal() as session:
                    count = notificacion_service.get_unread_count_by_user(session, usuario_id=current_user.id)
                    
                    if count != last_count:
                        yield f"event: update\ndata: {count}\n\n"
                        last_count = count
            except Exception as e:
                logger.error(f"Error en SSE Stream para el usuario {current_user.nombre_usuario}: {e}")
                
            await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/", response_model=List[Notificacion], summary="Listar Notificaciones del Usuario Actual")
def read_notificaciones_usuario_actual(
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
    solo_no_leidas: bool = Query(False, description="Mostrar solo las notificaciones no leídas"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> Any:
    return notificacion_service.get_multi_by_user(
        db, usuario_id=current_user.id, solo_no_leidas=solo_no_leidas, skip=skip, limit=limit
    )

@router.get("/count/unread", response_model=Dict[str, int])
def count_notificaciones_no_leidas_usuario_actual(
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene la cantidad de notificaciones no leídas para el usuario actual.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando conteo de notificaciones no leídas.")
    count = notificacion_service.get_unread_count_by_user(db, usuario_id=current_user.id)
    return {"unread_count": count}

@router.post("/marcar-todas-leidas", response_model=Msg)
def mark_all_notificaciones_as_read_usuario_actual(
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    try:
        affected_rows = notificacion_service.mark_all_as_read_for_user(db, usuario_id=current_user.id)
        if affected_rows > 0:
            db.commit()
            logger.info(f"Usuario '{current_user.nombre_usuario}' marcó {affected_rows} notificación(es) como leídas.")
        else:
            logger.info(f"Usuario '{current_user.nombre_usuario}' no tenía notificaciones no leídas para marcar.")
        
        return {"msg": f"{affected_rows} notificación(es) marcada(s) como leída(s)."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno al marcar las notificaciones como leídas.")

@router.put("/{notificacion_id}/marcar", response_model=Notificacion)
def mark_notificacion_leida_no_leida(
    *,
    db: Session = Depends(deps.get_db),
    notificacion_id: PyUUID,
    update_in: NotificacionUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    db_notificacion = notificacion_service.get_or_404(db, id=notificacion_id)

    if db_notificacion.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tiene permiso para modificar esta notificación.")

    try:
        updated_notification = notificacion_service.mark_as(db=db, db_obj=db_notificacion, read_status=update_in.leido)
        if db.is_modified(updated_notification):
            db.commit()
            db.refresh(updated_notification)
        return updated_notification
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno al marcar la notificación.")

@router.delete("/{notificacion_id}", response_model=Msg)
def delete_notificacion_propia(
    *,
    db: Session = Depends(deps.get_db),
    notificacion_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    db_notificacion = notificacion_service.get_or_404(db, id=notificacion_id)

    if db_notificacion.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tiene permiso para eliminar esta notificación.")

    try:
        notificacion_service.remove(db=db, id=notificacion_id)
        db.commit()
        return {"msg": f"Notificación eliminada."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno al eliminar la notificación.")
