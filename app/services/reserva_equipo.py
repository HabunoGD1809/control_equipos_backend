import logging
from typing import List, Union, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, func, exc as sqlalchemy_exc
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core import permissions as perms
from app.core.security import user_has_permissions
from app.models.reserva_equipo import ReservaEquipo
from app.models.equipo import Equipo
from app.models.estado_equipo import EstadoEquipo
from app.models.movimiento import Movimiento
from app.models.usuario import Usuario
from app.schemas.reserva_equipo import (
    ReservaEquipoCreate, ReservaEquipoUpdate, ReservaEquipoUpdateEstado,
    ReservaEquipoCheckInOut
)
from app.schemas.enums import EstadoReservaEnum
from app.core.equipment_states import EquipmentStateCode
from .asset_custody import physical_group, ensure_free, snapshot, propagate, lock_topology
from .base_service import BaseService
from .equipo import equipo_service

logger = logging.getLogger(__name__)

try:
    from psycopg import errors as psycopg_errors
    EXCLUSION_VIOLATION_PGCODE = "23P01"
except ImportError:
    psycopg_errors = None
    EXCLUSION_VIOLATION_PGCODE = "23P01"

class ReservaEquipoService(BaseService[ReservaEquipo, ReservaEquipoCreate, ReservaEquipoUpdate]):
    """
    Servicio para gestionar las Reservas de Equipos.
    """

    def create_with_user(self, db: Session, *, obj_in: ReservaEquipoCreate, current_user: Usuario) -> ReservaEquipo:
        """
        Crea una nueva reserva, validando equipo, disponibilidad de horario
        y estableciendo el estado inicial basado en los permisos del usuario.
        NO realiza db.commit() ni db.flush().
        """
        logger.debug(f"Usuario '{current_user.nombre_usuario}' intentando crear reserva para Equipo ID {obj_in.equipo_id} de {obj_in.fecha_hora_inicio} a {obj_in.fecha_hora_fin}")

        lock_topology(db)
        physical_group(db, obj_in.equipo_id)
        equipo = equipo_service.get_or_404(db, id=obj_in.equipo_id)
        
        if equipo.estado.codigo != EquipmentStateCode.AVAILABLE:
            logger.warning(f"Intento de reservar equipo '{equipo.nombre}' (ID: {equipo.id}) que no está disponible. Estado actual: '{equipo.estado.nombre}'.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El equipo '{equipo.nombre}' no está disponible para ser reservado (estado actual: '{equipo.estado.nombre}')."
            )
            
        if obj_in.fecha_hora_fin <= obj_in.fecha_hora_inicio:
            logger.warning("Intento de crear reserva con fecha de fin anterior o igual a la de inicio.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La fecha de fin de la reserva debe ser posterior a la fecha de inicio.")

        reserva_data = obj_in.model_dump()
        
        if user_has_permissions(current_user, {perms.PERM_APROBAR_RESERVAS}):
            reserva_data['estado'] = EstadoReservaEnum.CONFIRMADA
            reserva_data['aprobado_por_id'] = current_user.id
            reserva_data['fecha_aprobacion'] = datetime.now(timezone.utc)
            logger.info(f"Usuario '{current_user.nombre_usuario}' tiene permisos. Creando reserva como 'Confirmada'.")
        else:
            reserva_data['estado'] = EstadoReservaEnum.PENDIENTE_APROBACION
            logger.info(f"Usuario '{current_user.nombre_usuario}' no tiene permisos de aprobación. Reserva creada como 'Pendiente Aprobacion'.")

        db_obj = self.model(
            **reserva_data,
            usuario_solicitante_id=current_user.id
        )

        db.add(db_obj)
        logger.info(f"Reserva para equipo '{equipo.nombre}' (Horario: {db_obj.fecha_hora_inicio} - {db_obj.fecha_hora_fin}) preparada para ser creada.")
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ReservaEquipo,
        obj_in: Union[ReservaEquipoUpdate, Dict[str, Any]]
    ) -> ReservaEquipo:
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        reserva_id = db_obj.id
        logger.debug(f"Intentando actualizar reserva ID {reserva_id} con datos: {update_data}")
        
        estados_no_modificables = [
            EstadoReservaEnum.FINALIZADA,
            EstadoReservaEnum.CANCELADA_USUARIO,
            EstadoReservaEnum.CANCELADA_GESTOR,
            EstadoReservaEnum.RECHAZADA
        ]
        if db_obj.estado in [e.value for e in estados_no_modificables]:
            logger.warning(f"Intento de modificar reserva ID {reserva_id} en estado no modificable: '{db_obj.estado}'.")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede modificar una reserva en estado '{db_obj.estado}'.")

        nueva_fecha_inicio = update_data.get("fecha_hora_inicio", db_obj.fecha_hora_inicio)
        nueva_fecha_fin = update_data.get("fecha_hora_fin", db_obj.fecha_hora_fin)

        if nueva_fecha_fin <= nueva_fecha_inicio:
            logger.warning(f"Error de validación de fechas al actualizar reserva {reserva_id}: fin <= inicio.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La fecha de fin de la reserva debe ser posterior a la fecha de inicio.")

        if "equipo_id" in update_data and update_data["equipo_id"] != db_obj.equipo_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede cambiar el equipo de una reserva existente. Cancele y cree una nueva.")
        if "usuario_solicitante_id" in update_data and update_data["usuario_solicitante_id"] != db_obj.usuario_solicitante_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede cambiar el solicitante de una reserva existente.")

        try:
            updated_reserva = super().update(db, db_obj=db_obj, obj_in=update_data)
            logger.info(f"Reserva ID {reserva_id} preparada para ser actualizada.")
            return updated_reserva
        except sqlalchemy_exc.IntegrityError as e:
            original_exc = getattr(e, 'orig', None)
            pgcode = getattr(original_exc, 'pgcode', None) if original_exc else None
            
            logger.warning(f"Error de Integridad al actualizar reserva ID {reserva_id}. PGCode: {pgcode}. Detalle: {original_exc or str(e)}")

            if pgcode == EXCLUSION_VIOLATION_PGCODE or (original_exc and "reservas_equipo_equipo_id_tstzrange_excl" in str(original_exc).lower()):
                equipo_nombre = db_obj.equipo.nombre if db_obj.equipo else f"ID {db_obj.equipo_id}"
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Conflicto de reserva: El equipo '{equipo_nombre}' ya está reservado en el nuevo horario solicitado.",
                ) from e
            else:
                logger.error(f"Error de integridad no esperado al actualizar reserva ID {reserva_id}: {original_exc or str(e)}", exc_info=True)
                raise

    def update_estado(
        self,
        db: Session,
        *,
        db_obj: ReservaEquipo,
        estado_in: ReservaEquipoUpdateEstado,
        current_user: Usuario
    ) -> ReservaEquipo:
        """
        Actualiza el estado de una reserva.
        """
        reserva_id = db_obj.id
        nuevo_estado = estado_in.estado
        logger.info(f"Usuario '{current_user.nombre_usuario}' intentando actualizar estado de reserva ID {reserva_id} a '{nuevo_estado.value}'.")

        if db_obj.estado == nuevo_estado.value:
            if db_obj.notas_administrador != estado_in.notas_administrador:
                logger.info(f"Actualizando solo notas_administrador para reserva ID {reserva_id} (estado sin cambios: '{db_obj.estado}').")
                db_obj.notas_administrador = estado_in.notas_administrador
                db.add(db_obj)
                return db_obj
            logger.info(f"Estado de reserva ID {reserva_id} ya es '{nuevo_estado.value}'. No se realizan cambios.")
            return db_obj

        if db_obj.estado in [e.value for e in [EstadoReservaEnum.FINALIZADA, EstadoReservaEnum.CANCELADA_USUARIO, EstadoReservaEnum.CANCELADA_GESTOR, EstadoReservaEnum.RECHAZADA]]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede cambiar el estado de una reserva que ya está '{db_obj.estado}'.")

        if nuevo_estado == EstadoReservaEnum.CONFIRMADA:
            if db_obj.estado != EstadoReservaEnum.PENDIENTE_APROBACION.value:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede confirmar una reserva en estado '{db_obj.estado}'.")
            db_obj.aprobado_por_id = current_user.id
            db_obj.fecha_aprobacion = datetime.now(timezone.utc)

        if db_obj.estado == EstadoReservaEnum.EN_CURSO.value:
            raise HTTPException(409, "Registre la devolución física antes de cerrar o cancelar la reserva.")
        if nuevo_estado.value in {EstadoReservaEnum.EN_CURSO.value, EstadoReservaEnum.FINALIZADA.value}:
            raise HTTPException(409, "Use la confirmación de entrega o devolución para cambiar a ese estado.")
        db_obj.estado = nuevo_estado.value
        if estado_in.notas_administrador is not None:
            db_obj.notas_administrador = estado_in.notas_administrador
        
        db.add(db_obj)
        logger.info(f"Estado de reserva ID {reserva_id} preparado para ser actualizado a '{nuevo_estado.value}'.")
        return db_obj

    def check_in_out(self, db: Session, *, db_obj: ReservaEquipo, check_data: ReservaEquipoCheckInOut, current_user: Usuario) -> ReservaEquipo:
        lock_topology(db)
        db.execute(select(ReservaEquipo.id).where(ReservaEquipo.id == db_obj.id).with_for_update())
        db.refresh(db_obj)
        equipo = db.scalar(select(Equipo).where(Equipo.id == db_obj.equipo_id).with_for_update(of=Equipo))
        now = datetime.now(timezone.utc)
        if check_data.check_out_time:
            if db_obj.estado != EstadoReservaEnum.CONFIRMADA.value or db_obj.check_out_time:
                raise HTTPException(409, "Solo se puede entregar una reserva confirmada que no se haya entregado.")
            if equipo.estado.codigo != EquipmentStateCode.AVAILABLE:
                raise HTTPException(409, "El equipo ya no está disponible para la entrega.")
            if db.scalar(select(Movimiento.id).where(Movimiento.equipo_id == equipo.id, Movimiento.estado.in_(["Pendiente","Autorizado","En Proceso"])).limit(1)):
                raise HTTPException(409, "El equipo tiene un movimiento pendiente.")
            if db.scalar(select(ReservaEquipo.id).where(ReservaEquipo.equipo_id == equipo.id, ReservaEquipo.estado == EstadoReservaEnum.EN_CURSO.value).limit(1)):
                raise HTTPException(409, "El equipo tiene otra reserva sin devolver.")
            members = physical_group(db, equipo.id)
            ensure_free(db, members)
            db_obj.componentes_origen = snapshot(members, equipo.id)
            state = db.scalar(select(EstadoEquipo).where(EstadoEquipo.codigo == EquipmentStateCode.ON_LOAN))
            if not state: raise HTTPException(409, "Falta el estado Prestado en el catálogo.")
            equipo.estado_id = state.id
            equipo.empleado_asignado_id = db_obj.solicitante.empleado_id
            db_obj.check_out_time = now
            db_obj.estado = EstadoReservaEnum.EN_CURSO.value
        elif check_data.check_in_time:
            if db_obj.estado != EstadoReservaEnum.EN_CURSO.value or not db_obj.check_out_time or db_obj.check_in_time:
                raise HTTPException(409, "Solo se puede devolver una reserva que está en curso.")
            state = db.scalar(select(EstadoEquipo).where(EstadoEquipo.codigo == EquipmentStateCode.AVAILABLE))
            if not state: raise HTTPException(409, "Falta el estado Disponible en el catálogo.")
            equipo.estado_id = state.id
            equipo.empleado_asignado_id = None
            db_obj.check_in_time = now
            db_obj.estado = EstadoReservaEnum.FINALIZADA.value
            db_obj.notas_devolucion = check_data.notas_devolucion
        else: raise HTTPException(422, "Indique entrega o devolución.")
        propagate(db, equipo, db_obj.componentes_origen)
        db.add(db_obj)
        return db_obj

    def remove(self, db: Session, *, id):
        reservation = self.get_or_404(db, id=id)
        if reservation.check_out_time or reservation.check_in_time:
            raise HTTPException(409, "Las reservas con entregas o devoluciones se conservan como historial de custodia.")
        return super().remove(db, id=id)

    def get_multi_by_equipo_and_range(
        self, db: Session, *, equipo_id: UUID, start_time: datetime, end_time: datetime
    ) -> List[ReservaEquipo]:
        """Busca reservas para un equipo que se solapan con un rango de tiempo dado."""
        logger.debug(f"Buscando reservas para Equipo ID {equipo_id} entre {start_time} y {end_time}")
        
        existing_reservation_range = func.tstzrange(self.model.fecha_hora_inicio, self.model.fecha_hora_fin, '()')
        new_reservation_range = func.tstzrange(start_time, end_time, '()')

        statement = select(self.model).where(
            self.model.equipo_id == equipo_id,
            self.model.estado.in_([
                EstadoReservaEnum.CONFIRMADA.value,
                EstadoReservaEnum.PENDIENTE_APROBACION.value,
                EstadoReservaEnum.EN_CURSO.value
            ]),
            existing_reservation_range.op('&&')(new_reservation_range) # Operador de solapamiento
        ).order_by(self.model.fecha_hora_inicio)
        
        result = db.execute(statement)
        return list(result.scalars().all())

reserva_equipo_service = ReservaEquipoService(ReservaEquipo)
