import logging
import asyncio
from typing import Any, List, Dict
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.notificacion import Notificacion, NotificacionUpdate
from app.schemas.common import Msg
from app.services.notificacion import notificacion_service
from app.models.usuario import Usuario as UsuarioModel
from app.core.event_broker import broker

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/stream")
async def stream_notificaciones(
    request: Request,
    current_user: UsuarioModel = Depends(deps.get_current_user_sse),
):
    user_id = current_user.id
    queue = broker.subscribe(str(user_id))

    def read_snapshot():
        from app.db.session import SessionLocal
        from app.models.notificacion import Notificacion as NotificationModel
        from sqlalchemy import select, func
        with SessionLocal() as session:
            user = session.get(UsuarioModel, user_id)
            if not user or user.bloqueado or user.session_version != current_user.session_version or user.requiere_cambio_contrasena:
                return None
            count = notificacion_service.get_unread_count_by_user(session, usuario_id=user_id)
            latest = session.execute(select(func.max(NotificationModel.created_at)).where(NotificationModel.usuario_id == user_id)).scalar()
            return (count, str(latest))

    async def event_generator():
        previous = None
        try:
            yield "retry: 3000\n\n"
            while not await request.is_disconnected():
                snapshot = await asyncio.to_thread(read_snapshot)
                if snapshot is None:
                    yield "event: session-expired\ndata: logout\n\n"
                    return
                if snapshot != previous:
                    yield f"event: update\ndata: {snapshot[0]}\n\n"
                    previous = snapshot
                try:
                    await asyncio.wait_for(queue.get(), timeout=15)
                    previous = None
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            broker.unsubscribe(str(user_id), queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})

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
