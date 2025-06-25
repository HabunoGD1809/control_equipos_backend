import logging
from typing import List, Union, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, text, exc as sqlalchemy_exc, and_, or_, func as sql_func
from sqlalchemy.dialects.postgresql import TSTZRANGE
from fastapi import HTTPException, status

EXCLUSION_VIOLATION_PGCODE = "23P01"

# Importar modelos y schemas
from app.models.reserva_equipo import ReservaEquipo
from app.models.usuario import Usuario
from app.schemas.reserva_equipo import (
    ReservaEquipoCreate, ReservaEquipoUpdate, ReservaEquipoUpdateEstado, 
    ReservaEquipoCheckInOut
)
# CORRECCIÓN: Importar el Enum directamente para usarlo
from app.schemas.enums import EstadoReservaEnum

# Importar la clase base y otros servicios necesarios
from .base_service import BaseService
from .equipo import equipo_service

logger = logging.getLogger(__name__)

class ReservaEquipoService(BaseService[ReservaEquipo, ReservaEquipoCreate, ReservaEquipoUpdate]):
    """
    Servicio para gestionar las Reservas de Equipos.
    """

    def create_with_user(self, db: Session, *, obj_in: ReservaEquipoCreate, current_user: Usuario) -> ReservaEquipo:
        """
        Crea una nueva reserva, validando equipo y manejando solapamientos (via DB constraint).
        NO realiza db.commit().
        """
        logger.debug(f"Usuario '{current_user.nombre_usuario}' intentando crear reserva para Equipo ID: {obj_in.equipo_id} de {obj_in.fecha_hora_inicio} a {obj_in.fecha_hora_fin}")

        equipo = equipo_service.get_or_404(db, id=obj_in.equipo_id)

        if obj_in.fecha_hora_fin <= obj_in.fecha_hora_inicio:
            logger.warning("Intento de crear reserva con fecha de fin anterior o igual a la de inicio.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha de fin de la reserva debe ser posterior a la fecha de inicio.")

        reserva_data = obj_in.model_dump()
        db_obj = self.model(
            **reserva_data,
            usuario_solicitante_id=current_user.id
        )

        try:
            db.add(db_obj)
            logger.info(f"Reserva para equipo '{equipo.nombre}' (Horario: {db_obj.fecha_hora_inicio} - {db_obj.fecha_hora_fin}) preparada para ser creada.")
            return db_obj
        except sqlalchemy_exc.IntegrityError as e:
            original_exc = getattr(e, 'orig', None)
            pgcode = getattr(original_exc, 'pgcode', None) if original_exc else None
            
            logger.warning(f"Error de Integridad al crear reserva. PGCode: {pgcode}. Detalle: {original_exc or str(e)}")

            if pgcode == EXCLUSION_VIOLATION_PGCODE or (original_exc and "reservas_equipo_equipo_id_periodo_reserva_excl" in str(original_exc).lower()):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Conflicto de reserva: El equipo '{equipo.nombre}' ya está reservado o no disponible en el horario solicitado.",
                ) from e
            else:
                logger.error(f"Error de integridad no esperado al crear reserva: {original_exc or str(e)}", exc_info=True)
                raise

    def update(
        self,
        db: Session,
        *,
        db_obj: ReservaEquipo,
        obj_in: Union[ReservaEquipoUpdate, Dict[str, Any]]
    ) -> ReservaEquipo:
        """
        Actualiza campos permitidos de una reserva (ej: horario, propósito, notas).
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        reserva_id = db_obj.id
        logger.debug(f"Intentando actualizar reserva ID {reserva_id} con datos: {update_data}")
        
        estados_no_modificables = [
            EstadoReservaEnum.COMPLETADA.value, 
            EstadoReservaEnum.CANCELADA_USUARIO.value,
            EstadoReservaEnum.RECHAZADA.value
        ]
        if db_obj.estado in estados_no_modificables:
            logger.warning(f"Intento de modificar reserva ID {reserva_id} en estado no modificable: '{db_obj.estado}'.")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede modificar una reserva en estado '{db_obj.estado}'.")

        nueva_fecha_inicio = update_data.get("fecha_hora_inicio", db_obj.fecha_hora_inicio)
        nueva_fecha_fin = update_data.get("fecha_hora_fin", db_obj.fecha_hora_fin)

        if nueva_fecha_fin <= nueva_fecha_inicio:
            logger.warning(f"Error de validación de fechas al actualizar reserva {reserva_id}: fin <= inicio.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha de fin de la reserva debe ser posterior a la fecha de inicio.")

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

            if pgcode == EXCLUSION_VIOLATION_PGCODE or (original_exc and "reservas_equipo_equipo_id_periodo_reserva_excl" in str(original_exc).lower()):
                equipo_nombre = db_obj.equipo.nombre if db_obj.equipo else f"ID {db_obj.equipo_id}"
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Conflicto de reserva: El equipo '{equipo_nombre}' ya está reservado o no disponible en el nuevo horario solicitado.",
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

        if db_obj.estado == EstadoReservaEnum.COMPLETADA.value and nuevo_estado != EstadoReservaEnum.COMPLETADA:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se puede cambiar el estado de una reserva ya completada.")
        
        if db_obj.estado == EstadoReservaEnum.CANCELADA_USUARIO.value and nuevo_estado != EstadoReservaEnum.CANCELADA_USUARIO:
             raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se puede cambiar el estado de una reserva ya cancelada.")

        update_payload: Dict[str, Any] = {"estado": nuevo_estado.value}
        if estado_in.notas_administrador is not None:
            update_payload["notas_administrador"] = estado_in.notas_administrador

        if nuevo_estado == EstadoReservaEnum.CONFIRMADA:
             if db_obj.estado != EstadoReservaEnum.PENDIENTE_APROBACION.value:
                 raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede confirmar una reserva en estado '{db_obj.estado}'.")
             update_payload['aprobado_por_id'] = current_user.id
             update_payload['fecha_aprobacion'] = datetime.now(timezone.utc)
        elif nuevo_estado in [EstadoReservaEnum.CANCELADA_USUARIO, EstadoReservaEnum.RECHAZADA]:
             update_payload['aprobado_por_id'] = None
             update_payload['fecha_aprobacion'] = None

        updated_reserva = super().update(db, db_obj=db_obj, obj_in=update_payload)
        logger.info(f"Estado de reserva ID {reserva_id} preparado para ser actualizado a '{nuevo_estado.value}'.")
        return updated_reserva

    def check_in_out(
        self,
        db: Session,
        *,
        db_obj: ReservaEquipo,
        check_data: ReservaEquipoCheckInOut,
        current_user: Usuario
    ) -> ReservaEquipo:
        """
        Registra el check-in (recogida) o check-out (devolución) de una reserva.
        """
        reserva_id = db_obj.id
        update_payload: Dict[str, Any] = {}
        accion = ""

        if check_data.check_in_time is not None:
              logger.info(f"Usuario '{current_user.nombre_usuario}' realizando check-in para reserva ID {reserva_id}.")
              accion = "check-in"
              if db_obj.estado != EstadoReservaEnum.CONFIRMADA.value:
                  raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Solo se puede hacer check-in de reservas en estado 'Confirmada'. Estado actual: '{db_obj.estado}'.")
              if db_obj.check_in_time is not None:
                  raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta reserva ya tiene un check-in registrado.")
              
              update_payload["check_in_time"] = check_data.check_in_time
              update_payload["estado"] = EstadoReservaEnum.EN_CURSO.value

        elif check_data.check_out_time is not None:
              logger.info(f"Usuario '{current_user.nombre_usuario}' realizando check-out para reserva ID {reserva_id}.")
              accion = "check-out"
              if db_obj.estado != EstadoReservaEnum.EN_CURSO.value:
                  raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Solo se puede hacer check-out de reservas en estado 'En Curso'. Estado actual: '{db_obj.estado}'.")
              if db_obj.check_out_time is not None:
                  raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta reserva ya tiene un check-out registrado.")

              update_payload["check_out_time"] = check_data.check_out_time
              update_payload["estado"] = EstadoReservaEnum.COMPLETADA.value
              if check_data.notas_devolucion is not None:
                  update_payload["notas_devolucion"] = check_data.notas_devolucion
        else:
            logger.warning(f"Intento de check-in/out para reserva ID {reserva_id} sin especificar tiempo de check-in o check-out.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Debe proporcionar check_in_time o check_out_time.")

        if not update_payload:
             return db_obj

        updated_reserva = super().update(db, db_obj=db_obj, obj_in=update_payload)
        logger.info(f"Reserva ID {reserva_id} preparada para {accion} (nuevo estado: '{updated_reserva.estado}').")
        return updated_reserva

    def get_multi_by_equipo_and_range(
        self, db: Session, *, equipo_id: UUID, start_time: datetime, end_time: datetime
    ) -> List[ReservaEquipo]:
        """Busca reservas para un equipo que solapan con un rango de tiempo dado."""
        logger.debug(f"Buscando reservas para Equipo ID {equipo_id} entre {start_time} y {end_time}")
        
        existing_reservation_range = sql_func.tstzrange(self.model.fecha_hora_inicio, self.model.fecha_hora_fin, '()')
        
        # CORRECCIÓN: Usar sql_func.tstzrange para construir el rango a partir de las variables.
        # Esto genera la función de PostgreSQL en la consulta, que es la forma correcta.
        new_reservation_range = sql_func.tstzrange(start_time, end_time, '()')

        statement = select(self.model).where(
            self.model.equipo_id == equipo_id,
            self.model.estado.in_([
                EstadoReservaEnum.CONFIRMADA.value, 
                EstadoReservaEnum.PENDIENTE_APROBACION.value, 
                EstadoReservaEnum.EN_CURSO.value
            ]),
            existing_reservation_range.op('&&')(new_reservation_range)
        ).order_by(self.model.fecha_hora_inicio)
        
        result = db.execute(statement)
        return list(result.scalars().all())

reserva_equipo_service = ReservaEquipoService(ReservaEquipo)
