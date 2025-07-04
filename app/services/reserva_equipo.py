import logging
from typing import List, Union, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, func, exc as sqlalchemy_exc
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core.permissions import PERM_ADMIN_RESERVAS, PERM_CREAR_RESERVAS
from app.core.security import user_has_permissions
from app.models.reserva_equipo import ReservaEquipo
from app.models.usuario import Usuario
from app.schemas.reserva_equipo import (
    ReservaEquipoCreate, ReservaEquipoUpdate, ReservaEquipoUpdateEstado,
    ReservaEquipoCheckInOut
)
from app.schemas.enums import EstadoReservaEnum
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
        NO realiza db.commit().
        """
        logger.debug(f"Usuario '{current_user.nombre_usuario}' intentando crear reserva para Equipo ID {obj_in.equipo_id} de {obj_in.fecha_hora_inicio} a {obj_in.fecha_hora_fin}")

        equipo = equipo_service.get_or_404(db, id=obj_in.equipo_id)
        
        # Validar que el equipo esté en un estado reservable
        if equipo.estado.nombre != "Disponible":
            logger.warning(f"Intento de reservar equipo '{equipo.nombre}' (ID: {equipo.id}) que no está disponible. Estado actual: '{equipo.estado.nombre}'.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El equipo '{equipo.nombre}' no está disponible para ser reservado (estado actual: '{equipo.estado.nombre}')."
            )
            
        if obj_in.fecha_hora_fin <= obj_in.fecha_hora_inicio:
            logger.warning("Intento de crear reserva con fecha de fin anterior o igual a la de inicio.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha de fin de la reserva debe ser posterior a la fecha de inicio.")

        reserva_data = obj_in.model_dump()
        
        # *** LÓGICA DE ESTADO INICIAL ***
        # Comprueba si el usuario tiene permiso para aprobar reservas.
        if user_has_permissions(current_user, {PERM_ADMIN_RESERVAS}):
            # Si tiene permiso, la reserva se crea como confirmada directamente.
            reserva_data['estado'] = EstadoReservaEnum.CONFIRMADA
            reserva_data['aprobado_por_id'] = current_user.id
            reserva_data['fecha_aprobacion'] = datetime.now(timezone.utc)
            logger.info(f"Usuario '{current_user.nombre_usuario}' tiene permisos. Creando reserva como 'Confirmada'.")
        else:
            # Si no tiene permiso, la reserva queda pendiente de aprobación.
            reserva_data['estado'] = EstadoReservaEnum.PENDIENTE_APROBACION
            logger.info(f"Usuario '{current_user.nombre_usuario}' no tiene permisos de aprobación. Reserva creada como 'Pendiente Aprobacion'.")


        db_obj = self.model(
            **reserva_data,
            usuario_solicitante_id=current_user.id
        )

        try:
            db.add(db_obj)
            db.flush() # Importante: flush para que la constraint de la DB se evalúe
            logger.info(f"Reserva para equipo '{equipo.nombre}' (Horario: {db_obj.fecha_hora_inicio} - {db_obj.fecha_hora_fin}) preparada para ser creada.")
            return db_obj
        except IntegrityError as e:
            db.rollback() # Revertimos la sesión
            original_exc = getattr(e, 'orig', None)
            pgcode = getattr(original_exc, 'pgcode', None) if original_exc else None
            
            logger.warning(f"Error de Integridad al crear reserva. PGCode: {pgcode}. Detalle: {original_exc or str(e)}")

            # Comprueba si el error es por la restricción de exclusión (solapamiento de fechas)
            if pgcode == EXCLUSION_VIOLATION_PGCODE or (original_exc and "reservas_equipo_equipo_id_periodo_reserva_excl" in str(original_exc).lower()):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Conflicto de reserva: El equipo '{equipo.nombre}' ya está reservado en el horario solicitado.",
                ) from e
            else:
                # Otros errores de integridad (e.g., FK no encontrada)
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
            EstadoReservaEnum.FINALIZADA,
            EstadoReservaEnum.CANCELADA_USUARIO,
            EstadoReservaEnum.CANCELADA_GESTOR,
            EstadoReservaEnum.RECHAZADA
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

        if db_obj.estado in [EstadoReservaEnum.FINALIZADA.value, EstadoReservaEnum.CANCELADA_USUARIO.value, EstadoReservaEnum.CANCELADA_GESTOR.value, EstadoReservaEnum.RECHAZADA.value]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede cambiar el estado de una reserva que ya está '{db_obj.estado}'.")

        if nuevo_estado == EstadoReservaEnum.CONFIRMADA:
             if db_obj.estado != EstadoReservaEnum.PENDIENTE_APROBACION.value:
                 raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede confirmar una reserva en estado '{db_obj.estado}'.")
             db_obj.aprobado_por_id = current_user.id
             db_obj.fecha_aprobacion = datetime.now(timezone.utc)

        db_obj.estado = nuevo_estado.value
        if estado_in.notas_administrador is not None:
            db_obj.notas_administrador = estado_in.notas_administrador
        
        db.add(db_obj)
        logger.info(f"Estado de reserva ID {reserva_id} preparado para ser actualizado a '{nuevo_estado.value}'.")
        return db_obj

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
        
        if check_data.check_in_time is not None:
              logger.info(f"Usuario '{current_user.nombre_usuario}' realizando check-in para reserva ID {reserva_id}.")
              if db_obj.estado != EstadoReservaEnum.CONFIRMADA.value:
                  raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Solo se puede hacer check-in de reservas en estado '{EstadoReservaEnum.CONFIRMADA.value}'. Estado actual: '{db_obj.estado}'.")
              if db_obj.check_in_time is not None:
                  raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta reserva ya tiene un check-in registrado.")
              
              db_obj.check_in_time = check_data.check_in_time
              db_obj.estado = EstadoReservaEnum.EN_CURSO.value

        elif check_data.check_out_time is not None:
              logger.info(f"Usuario '{current_user.nombre_usuario}' realizando check-out para reserva ID {reserva_id}.")
              if db_obj.estado != EstadoReservaEnum.EN_CURSO.value:
                  raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Solo se puede hacer check-out de reservas en estado '{EstadoReservaEnum.EN_CURSO.value}'. Estado actual: '{db_obj.estado}'.")
              if db_obj.check_out_time is not None:
                  raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta reserva ya tiene un check-out registrado.")

              db_obj.check_out_time = check_data.check_out_time
              db_obj.estado = EstadoReservaEnum.FINALIZADA.value
              if check_data.notas_devolucion is not None:
                  db_obj.notas_devolucion = check_data.notas_devolucion
        else:
            logger.warning(f"Intento de check-in/out para reserva ID {reserva_id} sin especificar tiempo de check-in o check-out.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Debe proporcionar check_in_time o check_out_time.")

        db.add(db_obj)
        logger.info(f"Reserva ID {reserva_id} preparada para { 'check-in' if check_data.check_in_time else 'check-out'} (nuevo estado: '{db_obj.estado}').")
        return db_obj

    def get_multi_by_equipo_and_range(
        self, db: Session, *, equipo_id: UUID, start_time: datetime, end_time: datetime
    ) -> List[ReservaEquipo]:
        """Busca reservas para un equipo que se solapan con un rango de tiempo dado."""
        logger.debug(f"Buscando reservas para Equipo ID {equipo_id} entre {start_time} y {end_time}")
        
        # Corrección: Uso de la función nativa de PostgreSQL tstzrange para el rango de tiempo
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
