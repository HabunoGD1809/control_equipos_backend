import datetime
from typing import Optional, List, Union, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, text, exc as sqlalchemy_exc
from fastapi import HTTPException, status
import logging

try:
    from psycopg import errors as psycopg_errors
    PG_RaiseException: type[Exception] = psycopg_errors.RaiseException
except ImportError:
    class DummyRaiseException(Exception):
        pass
    PG_RaiseException: type[Exception] = DummyRaiseException

from app.models.movimiento import Movimiento
from app.models.usuario import Usuario
from app.schemas.movimiento import MovimientoCreate, MovimientoUpdate
from .base_service import BaseService

logger = logging.getLogger(__name__)

class MovimientoService(BaseService[Movimiento, MovimientoCreate, MovimientoUpdate]):
    """
    Servicio para gestionar los Movimientos de equipos.
    Utiliza la función de base de datos 'registrar_movimiento_equipo' para la creación.
    """

    def _apply_load_options_for_movimiento(self, statement):
        """Aplica opciones de carga eager comunes para movimientos."""
        return statement.options(
            selectinload(Movimiento.equipo),
            selectinload(Movimiento.usuario_registrador),
            selectinload(Movimiento.usuario_autorizador)
        )

    def get(self, db: Session, id: Any) -> Optional[Movimiento]:
        """Obtiene un movimiento con sus relaciones principales cargadas."""
        statement = select(self.model).where(self.model.id == id)
        statement = self._apply_load_options_for_movimiento(statement)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Movimiento]:
        """Obtiene múltiples movimientos con sus relaciones principales cargadas."""
        statement = select(self.model).order_by(self.model.fecha_hora.desc()).offset(skip).limit(limit)
        statement = self._apply_load_options_for_movimiento(statement)
        result = db.execute(statement)
        return list(result.scalars().all())

    def create_movimiento_via_db_func(
        self,
        db: Session,
        *,
        obj_in: MovimientoCreate,
        registrado_por_usuario: Usuario,
        autorizado_por_id: Optional[UUID] = None
    ) -> Movimiento:
        """
        Crea un nuevo movimiento LLAMANDO a la función de base de datos 'registrar_movimiento_equipo'.
        Esta función ahora maneja la lógica de bloqueo para evitar race conditions.
        NO realiza db.commit().
        """
        logger.info(f"Usuario '{registrado_por_usuario.nombre_usuario}' intentando registrar movimiento tipo '{obj_in.tipo_movimiento}' para equipo ID '{obj_in.equipo_id}'.")

        tipo_movimiento_valor_str = obj_in.tipo_movimiento.value if hasattr(obj_in.tipo_movimiento, 'value') else obj_in.tipo_movimiento

        try:
            stmt = text(
                """
                SELECT control_equipos.registrar_movimiento_equipo(
                    p_equipo_id => :equipo_id,
                    p_usuario_id => :usuario_id,
                    p_tipo_movimiento => :tipo_movimiento,
                    p_origen => :origen,
                    p_destino => :destino,
                    p_proposito => :proposito,
                    p_fecha_prevista_retorno => :fecha_prevista_retorno,
                    p_recibido_por => :recibido_por,
                    p_observaciones => :observaciones,
                    p_autorizado_por => :autorizado_por
                ) AS nuevo_movimiento_id;
                """
            )

            result = db.execute(stmt, {
                "equipo_id": obj_in.equipo_id,
                "usuario_id": registrado_por_usuario.id,
                "tipo_movimiento": tipo_movimiento_valor_str,
                "origen": obj_in.origen,
                "destino": obj_in.destino,
                "proposito": obj_in.proposito,
                "fecha_prevista_retorno": obj_in.fecha_prevista_retorno,
                "recibido_por": obj_in.recibido_por,
                "observaciones": obj_in.observaciones,
                "autorizado_por": autorizado_por_id,
            })
            nuevo_movimiento_id = result.scalar_one_or_none()

            if nuevo_movimiento_id is None:
                logger.error("Error al registrar el movimiento: La función de BD no devolvió un ID.")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error interno al registrar el movimiento: no se obtuvo ID de la función de base de datos.",
                )
            
            db_movimiento = self.get(db, id=nuevo_movimiento_id)
            
            if not db_movimiento:
                logger.error(f"Error crítico: Movimiento con ID {nuevo_movimiento_id} no encontrado después de ser creado por la función de BD.")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error crítico al recuperar el movimiento registrado después de su creación.",
                )
            
            logger.info(f"Movimiento ID {nuevo_movimiento_id} preparado para ser creado (registrado vía función DB).")
            return db_movimiento

        except sqlalchemy_exc.DBAPIError as db_err:
            original_exc = getattr(db_err, 'orig', None)

            if isinstance(original_exc, PG_RaiseException):
                diag_message = getattr(getattr(original_exc, 'diag', None), 'message_primary', str(original_exc))
                logger.warning(f"Error de lógica de negocio desde la BD: '{diag_message}'")
                error_lower = diag_message.lower()
                
                if "equipo no encontrado" in error_lower:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=diag_message)
                if any(msg in error_lower for msg in ["obligatorio para", "obligatorios para", "tipo de movimiento no válido"]):
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=diag_message)
                if "no permite movimientos actualmente" in error_lower or "equipo bloqueado" in error_lower:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=diag_message)
                if "requiere autorización previa" in error_lower:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=diag_message)
                
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=diag_message)
            else:
                logger.error(f"Error de base de datos no controlado: {db_err}", exc_info=True)
                raise db_err

    def create(self, db: Session, *, obj_in: MovimientoCreate) -> Movimiento:
        logger.error("Llamada directa a MovimientoService.create() está deshabilitada. Usar create_movimiento_via_db_func.")
        raise NotImplementedError("Debe usar 'create_movimiento_via_db_func' para crear movimientos y asegurar la lógica de negocio de la base de datos.")

    def update(
        self,
        db: Session,
        *,
        db_obj: Movimiento,
        obj_in: Union[MovimientoUpdate, Dict[str, Any]]
    ) -> Movimiento:
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        mov_id = db_obj.id
        logger.debug(f"Intentando actualizar movimiento ID {mov_id} con datos: {update_data}")
        
        if db_obj.estado == "Cancelado":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pueden modificar movimientos cancelados.")

        if db_obj.estado == "Completado":
            allowed_fields = {"observaciones", "recibido_por"}
            for field in update_data:
                if field not in allowed_fields:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"No se pueden modificar el campo '{field}' de un movimiento en estado 'Completado'."
                    )
        
        allowed_update_fields = ["observaciones", "fecha_retorno", "recibido_por"]
        filtered_update_data = {k: v for k, v in update_data.items() if k in allowed_update_fields}

        if not filtered_update_data:
            logger.info(f"No hay campos válidos para actualizar en movimiento ID {mov_id}. Devolviendo objeto sin cambios.")
            return db_obj

        if "fecha_retorno" in filtered_update_data and filtered_update_data["fecha_retorno"]:
            if filtered_update_data["fecha_retorno"] < db_obj.fecha_hora:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha de retorno no puede ser anterior a la fecha del movimiento.")

        updated_db_movimiento = super().update(db, db_obj=db_obj, obj_in=filtered_update_data)
        logger.info(f"Movimiento ID {mov_id} preparado para ser actualizado.")
        return updated_db_movimiento

    def cancel_movimiento(self, db: Session, *, movimiento: Movimiento, current_user: Usuario) -> Movimiento:
        mov_id = movimiento.id
        logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando cancelar movimiento ID: {mov_id}")

        cancelables_states = ['Pendiente', 'Autorizado', 'Programado']

        if movimiento.estado not in cancelables_states:
            logger.warning(f"Intento de cancelar movimiento ID {mov_id} en estado no permitido: '{movimiento.estado}'.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No se puede cancelar un movimiento en estado '{movimiento.estado}'."
            )
        
        cancel_notes = f"Cancelado por {current_user.nombre_usuario} el {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}."
        new_observaciones = f"{movimiento.observaciones or ''} ({cancel_notes})".strip()

        update_data = {
            "estado": "Cancelado",
            "observaciones": new_observaciones,
        }
        
        updated_movimiento = super().update(db, db_obj=movimiento, obj_in=update_data)
        logger.info(f"Movimiento ID {mov_id} preparado para ser cancelado (estado cambiado a 'Cancelado').")
        return updated_movimiento

    def get_multi_by_equipo(
        self, db: Session, *, equipo_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Movimiento]:
        logger.debug(f"Listando movimientos para equipo ID: {equipo_id} (skip: {skip}, limit: {limit}).")
        statement = (
            select(self.model)
            .where(self.model.equipo_id == equipo_id)
            .order_by(self.model.fecha_hora.desc())
            .offset(skip)
            .limit(limit)
        )
        statement = self._apply_load_options_for_movimiento(statement)
        result = db.execute(statement)
        return list(result.scalars().all())

movimiento_service = MovimientoService(Movimiento)
