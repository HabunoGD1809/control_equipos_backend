import logging
import asyncio
from typing import List, Any, Union
from uuid import UUID
from datetime import datetime, timezone 

from sqlalchemy.orm import Session
from sqlalchemy import select, update, func as sql_func
from sqlalchemy.engine import CursorResult

from app.models.notificacion import Notificacion
from app.schemas.notificacion import NotificacionUpdate, NotificacionCreateInternal
from app.core.event_broker import broker
from .base_service import BaseService

logger = logging.getLogger(__name__)

class NotificacionService(BaseService[Notificacion, NotificacionCreateInternal, NotificacionUpdate]):

    def _notify_broker(self, db: Session, usuario_id: UUID):
        """Función auxiliar para avisar al SSE de forma asíncrona sin bloquear SQLAlchemy."""
        unread_count = self.get_unread_count_by_user(db, usuario_id=usuario_id)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(broker.publish(str(usuario_id), unread_count))
        except RuntimeError:
            # Ignorar si se ejecuta fuera de un event loop (ej. scripts síncronos de consola)
            pass

    def create_internal(self, db: Session, *, obj_in: NotificacionCreateInternal) -> Notificacion:
        logger.debug(f"Creando notificación interna para Usuario ID: {obj_in.usuario_id}, Mensaje: '{obj_in.mensaje[:30]}...'")
        if not obj_in.mensaje:
            raise ValueError("El mensaje de la notificación no puede estar vacío.")
        
        obj_in_data = obj_in.model_dump()
        obj_in_data['leido'] = False
        obj_in_data['fecha_leido'] = None
        
        temp_obj_in = NotificacionCreateInternal(**obj_in_data)
        
        db_notificacion = super().create(db, obj_in=temp_obj_in)
        logger.info(f"Notificación interna para Usuario ID {db_notificacion.usuario_id} preparada para ser creada.")
        
        # Avisar al frontend
        self._notify_broker(db, db_notificacion.usuario_id)
        return db_notificacion

    def mark_as(self, db: Session, *, db_obj: Notificacion, read_status: bool) -> Notificacion:
        notif_id = db_obj.id
        if db_obj.leido == read_status:
            logger.debug(f"Notificación ID {notif_id} ya está en estado leido={read_status}. No se realizan cambios.")
            return db_obj

        logger.info(f"Marcando notificación ID {notif_id} como leido={read_status}.")
        update_values = {
            "leido": read_status,
            "fecha_leido": datetime.now(timezone.utc) if read_status else None
        }
        
        db_obj.leido = update_values["leido"] # type: ignore
        db_obj.fecha_leido = update_values["fecha_leido"] # type: ignore
        db.add(db_obj)
        
        logger.info(f"Notificación ID {notif_id} preparada para ser actualizada a leido={read_status}.")
        
        # Avisar al frontend
        self._notify_broker(db, db_obj.usuario_id) # type: ignore
        return db_obj

    def mark_all_as_read_for_user(self, db: Session, *, usuario_id: UUID) -> int:
        logger.info(f"Marcando todas las notificaciones no leídas como leídas para Usuario ID: {usuario_id}.")
        statement = (
            update(self.model)
            .where(self.model.usuario_id == usuario_id, self.model.leido == False) # type: ignore
            .values(leido=True, fecha_leido=datetime.now(timezone.utc))
        )
        result: CursorResult = db.execute(statement)  # type: ignore
        affected_rows = result.rowcount
        logger.info(f"{affected_rows} notificación(es) para Usuario ID {usuario_id} preparadas para ser marcadas como leídas.")
        
        # Avisar al frontend si hubo cambios
        if affected_rows > 0:
            self._notify_broker(db, usuario_id)
            
        return affected_rows

    def remove(self, db: Session, *, id: Union[UUID, int]) -> Notificacion:
        """Sobrescribimos remove para avisar al frontend al borrar."""
        obj = db.query(self.model).get(id)
        if obj:
            usuario_id = obj.usuario_id # type: ignore
            obj = super().remove(db, id=id)
            self._notify_broker(db, usuario_id)
            return obj
        return super().remove(db, id=id)

    def get_multi_by_user(
        self, db: Session, *, usuario_id: UUID, solo_no_leidas: bool = False, skip: int = 0, limit: int = 50
    ) -> List[Notificacion]:
        logger.debug(f"Listando notificaciones para Usuario ID: {usuario_id}, SoloNoLeidas={solo_no_leidas} (skip: {skip}, limit: {limit}).")
        statement = select(self.model).where(self.model.usuario_id == usuario_id) # type: ignore
        if solo_no_leidas:
            statement = statement.where(self.model.leido == False) # type: ignore
        statement = statement.order_by(self.model.created_at.desc()).offset(skip).limit(limit) # type: ignore
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_unread_count_by_user(self, db: Session, *, usuario_id: UUID) -> int:
        logger.debug(f"Contando notificaciones no leídas para Usuario ID: {usuario_id}.")
        statement = select(sql_func.count(self.model.id)).where( # type: ignore
            self.model.usuario_id == usuario_id, # type: ignore
            self.model.leido == False # type: ignore
        )
        result = db.execute(statement)
        count = result.scalar_one_or_none()
        return count or 0

notificacion_service = NotificacionService(Notificacion)
