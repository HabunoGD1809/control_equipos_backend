import datetime
from typing import Optional, List, Union, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, text, exc as sqlalchemy_exc
from fastapi import HTTPException, status
import logging

try:
    from psycopg import errors as psycopg_errors
    PG_RaiseException = psycopg_errors.RaiseException
except ImportError:
    psycopg_errors = None # type: ignore
    PG_RaiseException = None # type: ignore

from app.models.movimiento import Movimiento
from app.models.usuario import Usuario
from app.schemas.movimiento import MovimientoCreate, MovimientoUpdate
from app.schemas.enums import TipoMovimientoInvEnum 
from .base_service import BaseService

logger = logging.getLogger(__name__)

class MovimientoService(BaseService[Movimiento, MovimientoCreate, MovimientoUpdate]):
    """
    Servicio para gestionar los Movimientos de equipos.
    Utiliza la función de base de datos 'registrar_movimiento_equipo' para la creación.
    Las operaciones CUD (Create, Update, Delete) y otras que modifican datos
    NO realizan commit. El commit debe ser manejado en la capa de la ruta.
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
        statement = select(self.model).order_by(self.model.fecha_hora.desc()).offset(skip).limit(limit) # type: ignore
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
        NO realiza db.commit(). La función de BD y este método son parte de una transacción
        que se confirmará en la ruta.
        """
        logger.info(f"Usuario '{registrado_por_usuario.nombre_usuario}' intentando registrar movimiento tipo '{obj_in.tipo_movimiento}' para equipo ID '{obj_in.equipo_id}'.")

        # Validar si el tipo_movimiento es un Enum y obtener su valor string si es necesario
        # El schema MovimientoCreate debería definir tipo_movimiento. Si es un Enum:
        if isinstance(obj_in.tipo_movimiento, TipoMovimientoInvEnum):
            tipo_movimiento_valor_str = obj_in.tipo_movimiento.value
        elif isinstance(obj_in.tipo_movimiento, str):
            tipo_movimiento_valor_str = obj_in.tipo_movimiento
        else:
            # Esto no debería ocurrir si Pydantic valida bien el schema
            logger.error(f"Tipo de movimiento inesperado: {type(obj_in.tipo_movimiento)}")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tipo de movimiento inválido.")

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
                "tipo_movimiento": tipo_movimiento_valor_str, # Usar el valor string
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
                 # Este es un error del servidor porque la función de BD debería siempre devolver un ID o fallar.
                 raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error interno al registrar el movimiento: no se obtuvo ID de la función de base de datos.",
                )
            
            # Después de llamar a la función de BD, el movimiento ya existe en la tabla 'movimientos'.
            # Lo recuperamos para devolverlo.
            db_movimiento = self.get(db, id=nuevo_movimiento_id) # self.get ya usa _apply_load_options
            
            if not db_movimiento:
                 logger.error(f"Error crítico: Movimiento con ID {nuevo_movimiento_id} no encontrado después de ser creado por la función de BD.")
                 raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error crítico al recuperar el movimiento registrado después de su creación.",
                )
            
            logger.info(f"Movimiento ID {nuevo_movimiento_id} preparado para ser creado (registrado vía función DB).")
            return db_movimiento

        except sqlalchemy_exc.DBAPIError as db_err:
            # Este bloque maneja errores que vienen directamente de la ejecución de la función de BD,
            # incluyendo RAISE EXCEPTION de PostgreSQL.
            original_exc = getattr(db_err, 'orig', None)
            error_message_db = str(original_exc if original_exc else db_err)
            diag_message = None

            if psycopg_errors and original_exc and hasattr(original_exc, 'diag'):
                diag_obj = getattr(original_exc, 'diag', None)
                if diag_obj: diag_message = getattr(diag_obj, 'message_primary', None)
            
            final_error_message_for_client = diag_message or error_message_db
            
            logger.warning(f"Error DBAPIError al llamar a registrar_movimiento_equipo: '{final_error_message_for_client}'")

            is_raise_exception = PG_RaiseException and original_exc and isinstance(original_exc, PG_RaiseException)
            error_lower = final_error_message_for_client.lower()

            if is_raise_exception:
                # Mapeo de errores específicos de la lógica de negocio de la función de BD
                if "equipo no encontrado" in error_lower:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=final_error_message_for_client)
                elif any(msg in error_lower for msg in ["obligatorio para", "obligatorios para", "ubicación destino es obligatoria", "ubicación origen es obligatoria", "tipo de movimiento no válido"]):
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Datos incompletos o inválidos: {final_error_message_for_client}")
                elif "no permite movimientos actualmente" in error_lower or "estado actual del equipo no permite este movimiento" in error_lower:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=final_error_message_for_client)
                elif "requiere autorización previa" in error_lower:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=final_error_message_for_client)
                # Añadir otros mapeos si tu función PG tiene más RAISE EXCEPTION específicos
                else: # Error de lógica de negocio no mapeado específicamente
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error en la operación: {final_error_message_for_client}")
            else:
                # Otros errores de DBAPI (constraints, etc., aunque la función PG debería manejarlos o ser el punto de fallo)
                logger.error(f"Error de base de datos no manejado como PG RaiseException: {final_error_message_for_client}", exc_info=True)
                # Re-lanzar el error original de SQLAlchemy para que la ruta lo maneje como 500 o un error más genérico.
                raise db_err
        # No se captura Exception genérica aquí para permitir que la ruta maneje el rollback.


    def create(self, db: Session, *, obj_in: MovimientoCreate) -> Movimiento:
         # Sobrescribir el método base para evitar su uso directo.
         logger.error("Llamada directa a MovimientoService.create() está deshabilitada. Usar create_movimiento_via_db_func.")
         raise NotImplementedError("Debe usar 'create_movimiento_via_db_func' para crear movimientos y asegurar la lógica de negocio de la base de datos.")


    def update(
        self,
        db: Session,
        *,
        db_obj: Movimiento,
        obj_in: Union[MovimientoUpdate, Dict[str, Any]]
    ) -> Movimiento:
        """
        Actualiza campos limitados de un movimiento (ej. observaciones, fecha_retorno).
        NO realiza db.commit(). Llama a super().update() que tampoco lo hace.
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        mov_id = db_obj.id
        logger.debug(f"Intentando actualizar movimiento ID {mov_id} con datos: {update_data}")
        
        # Definir explícitamente los campos que SÍ se pueden actualizar
        # Esto debe coincidir con lo que permite el schema MovimientoUpdate
        allowed_update_fields = ["observaciones", "fecha_retorno", "recibido_por"] # 'fecha_retorno_real' fue renombrado a 'fecha_retorno' en el modelo
        
        # Filtrar los datos de entrada para solo incluir los campos permitidos
        filtered_update_data = {k: v for k, v in update_data.items() if k in allowed_update_fields}

        if not filtered_update_data:
            logger.info(f"No hay campos válidos para actualizar en movimiento ID {mov_id}. Devolviendo objeto sin cambios.")
            # Devolver el objeto sin cambios si no hay nada que actualizar.
            # Opcionalmente, se podría lanzar un HTTPException 400 si se espera que siempre haya datos.
            return db_obj

        # Validaciones adicionales antes de llamar a super().update si es necesario
        # Por ejemplo, si la fecha_retorno no puede ser anterior a la fecha_hora del movimiento.
        if "fecha_retorno" in filtered_update_data and filtered_update_data["fecha_retorno"]:
            if filtered_update_data["fecha_retorno"] < db_obj.fecha_hora: # type: ignore
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha de retorno no puede ser anterior a la fecha del movimiento.")

        updated_db_movimiento = super().update(db, db_obj=db_obj, obj_in=filtered_update_data)
        logger.info(f"Movimiento ID {mov_id} preparado para ser actualizado.")
        return updated_db_movimiento


    def cancel_movimiento(self, db: Session, *, movimiento: Movimiento, current_user: Usuario) -> Movimiento:
        """
        Cambia el estado de un movimiento a 'Cancelado'.
        NO realiza db.commit().
        """
        mov_id = movimiento.id
        logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando cancelar movimiento ID: {mov_id}")

        # Estados desde los cuales se permite cancelar
        cancelables_states = ['Pendiente', 'Autorizado', 'Programado', 'En Proceso'] # 'En Proceso' es debatible

        if movimiento.estado not in cancelables_states:
             logger.warning(f"Intento de cancelar movimiento ID {mov_id} en estado no permitido: '{movimiento.estado}'.")
             raise HTTPException(
                 status_code=status.HTTP_409_CONFLICT,
                 detail=f"No se puede cancelar un movimiento en estado '{movimiento.estado}'."
             )
        
        # Construir las notas de cancelación
        cancel_notes = f"Cancelado por {current_user.nombre_usuario} el {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}."
        new_observaciones = f"{movimiento.observaciones or ''} ({cancel_notes})".strip()

        update_data = {
            "estado": "Cancelado",
            "observaciones": new_observaciones,
            # La función de BD 'cancelar_movimiento_equipo' podría ser preferible si necesita
            # lógica más compleja como revertir el estado del equipo.
            # Si esta función de servicio es llamada, se asume que el rollback del estado del equipo
            # se maneja en otro lugar (ej. trigger) o no es necesario para este tipo de cancelación.
            # "fecha_retorno_real": datetime.now(datetime.timezone.utc) # Esto podría no ser apropiado para una cancelación
        }
        
        # Usamos super().update para aplicar los cambios al objeto y marcarlo como dirty
        updated_movimiento = super().update(db, db_obj=movimiento, obj_in=update_data)
        logger.info(f"Movimiento ID {mov_id} preparado para ser cancelado (estado cambiado a 'Cancelado').")
        return updated_movimiento


    def get_multi_by_equipo(
        self, db: Session, *, equipo_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Movimiento]:
        logger.debug(f"Listando movimientos para equipo ID: {equipo_id} (skip: {skip}, limit: {limit}).")
        statement = (
            select(self.model)
            .where(self.model.equipo_id == equipo_id) # type: ignore
            .order_by(self.model.fecha_hora.desc()) # type: ignore
            .offset(skip)
            .limit(limit)
        )
        statement = self._apply_load_options_for_movimiento(statement)
        result = db.execute(statement)
        return list(result.scalars().all())


movimiento_service = MovimientoService(Movimiento)

# todo se puse revetir 
