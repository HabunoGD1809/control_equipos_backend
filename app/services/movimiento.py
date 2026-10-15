import datetime
from typing import Optional, List, Union, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, text, exc as sqlalchemy_exc
from fastapi import HTTPException, status
import logging

from app.schemas.enums import TipoMovimientoEquipoEnum, EstadoMovimientoEquipoEnum
from app.core.equipment_states import EquipmentStateCode

try:
    from psycopg import errors as psycopg_errors
    PG_RaiseException: type[Exception] = psycopg_errors.RaiseException
except ImportError:
    class DummyRaiseException(Exception):
        pass
    PG_RaiseException: type[Exception] = DummyRaiseException

from app.models.movimiento import Movimiento
from app.models.equipo import Equipo
from app.models.estado_equipo import EstadoEquipo
from app.models.empleado import Empleado
from app.core.security import user_has_permissions
from app.core import permissions as perms
from app.models.usuario import Usuario
from app.schemas.movimiento import MovimientoCreate, MovimientoUpdate, MovimientoEstadoUpdate
from .asset_custody import physical_group, ensure_free, snapshot, propagate, lock_topology
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
            selectinload(Movimiento.usuario_autorizador),
            selectinload(Movimiento.ubicacion_origen),
            selectinload(Movimiento.ubicacion_destino)
        )

    def get(self, db: Session, id: Any) -> Optional[Movimiento]:
        """Obtiene un movimiento con sus relaciones principales cargadas."""
        statement = select(self.model).where(self.model.id == id)
        statement = self._apply_load_options_for_movimiento(statement)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Movimiento]:
        """Obtiene múltiples movimientos con sus relaciones principales cargadas."""
        statement = select(self.model).order_by(self.model.fecha_hora.desc(), self.model.id.desc()).offset(skip).limit(limit)
        statement = self._apply_load_options_for_movimiento(statement)
        result = db.execute(statement)
        return list(result.scalars().all())

    def create_movimiento_via_db_func(
        self,
        db: Session,
        *,
        obj_in: MovimientoCreate,
        registrado_por_usuario: Usuario,
        ip_origen: Optional[str] = None,
        user_agent: Optional[str] = None,
        autorizado_por_id: Optional[UUID] = None
    ) -> Movimiento:
        """
        Crea un nuevo movimiento LLAMANDO a la función de base de datos 'registrar_movimiento_equipo'.
        NO realiza db.commit().
        """
        logger.info(f"Usuario '{registrado_por_usuario.nombre_usuario}' intentando registrar movimiento tipo '{obj_in.tipo_movimiento}' para equipo ID '{obj_in.equipo_id}'.")
        
        if obj_in.tipo_movimiento == TipoMovimientoEquipoEnum.SALIDA_TEMPORAL and not obj_in.fecha_prevista_retorno:
            raise HTTPException(status_code=422, detail="La fecha de retorno es obligatoria para una salida temporal.")

        if obj_in.empleado_destino_id:
            employee = db.get(Empleado, obj_in.empleado_destino_id)
            if not employee or not employee.is_active:
                raise HTTPException(422, "Seleccione un custodio activo.")
        if obj_in.tipo_movimiento == TipoMovimientoEquipoEnum.ASIGNACION_INTERNA and not obj_in.empleado_destino_id:
            raise HTTPException(422, "La asignación interna requiere un empleado custodio.")
        if user_has_permissions(registrado_por_usuario, {perms.PERM_AUTORIZAR_MOVIMIENTOS}):
            autorizado_por_id = registrado_por_usuario.id
        tipo_movimiento_valor_str = obj_in.tipo_movimiento.value if hasattr(obj_in.tipo_movimiento, 'value') else obj_in.tipo_movimiento

        members = physical_group(db, obj_in.equipo_id)
        ensure_free(db, [item for item in members if item.id != obj_in.equipo_id])
        saved_components = snapshot(members, obj_in.equipo_id)
        try:
            stmt = text(
                """
                SELECT control_equipos.registrar_movimiento_equipo(
                    p_equipo_id => :equipo_id,
                    p_usuario_id => :usuario_id,
                    p_tipo_movimiento => :tipo_movimiento,
                    p_ubicacion_origen_id => :ubicacion_origen_id,
                    p_ubicacion_destino_id => :ubicacion_destino_id,
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
                "ubicacion_origen_id": obj_in.ubicacion_origen_id,
                "ubicacion_destino_id": obj_in.ubicacion_destino_id,
                "proposito": obj_in.proposito,
                "fecha_prevista_retorno": obj_in.fecha_prevista_retorno,
                "recibido_por": None,
                "observaciones": obj_in.observaciones,
                "autorizado_por": autorizado_por_id,
            })
            nuevo_movimiento_id = result.scalar_one_or_none()

            if nuevo_movimiento_id is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error interno al registrar el movimiento: no se obtuvo ID de la función de base de datos.",
                )
            
            # --- Inyectar Auditoría de Red directamente tras crear ---
            db_movimiento = db.query(Movimiento).filter(Movimiento.id == nuevo_movimiento_id).first()
            if db_movimiento:
                db_movimiento.componentes_origen = saved_components
                if db_movimiento.estado != "Pendiente":
                    root = db.get(Equipo, obj_in.equipo_id)
                    db.refresh(root)
                    propagate(db, root, saved_components)
                db_movimiento.empleado_destino_id = obj_in.empleado_destino_id
                db_movimiento.ip_origen = ip_origen
                db_movimiento.user_agent = user_agent
                db.add(db_movimiento)
            
            db_movimiento_full = self.get(db, id=nuevo_movimiento_id)
            
            if not db_movimiento_full:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error crítico al recuperar el movimiento registrado después de su creación.",
                )
            
            return db_movimiento_full

        except sqlalchemy_exc.DBAPIError as db_err:
            original_exc = getattr(db_err, 'orig', None)

            if isinstance(original_exc, PG_RaiseException):
                diag_message = getattr(getattr(original_exc, 'diag', None), 'message_primary', str(original_exc))
                logger.warning(f"Error de lógica de negocio desde la BD: '{diag_message}'")
                error_lower = diag_message.lower()
                
                if "equipo no encontrado" in error_lower:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=diag_message)
                if any(msg in error_lower for msg in ["obligatorio para", "obligatorios para", "tipo de movimiento no válido"]):
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=diag_message)
                if any(message in error_lower for message in ["no permite movimientos actualmente", "equipo bloqueado", "mantenimiento en curso"]):
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
        
        if db_obj.estado == "Cancelado":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se pueden modificar movimientos cancelados.")
        if db_obj.fecha_recepcion and "recibido_por" in update_data:
            raise HTTPException(409, "La identidad de una recepción confirmada no puede modificarse.")

        if db_obj.estado == "Completado":
            allowed_fields = {"observaciones", "recibido_por"}
            for field in update_data:
                if field not in allowed_fields:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"No se puede modificar el campo '{field}' de un movimiento en estado 'Completado'."
                    )
        
        allowed_update_fields = ["observaciones", "fecha_retorno", "recibido_por"]
        filtered_update_data = {k: v for k, v in update_data.items() if k in allowed_update_fields}

        if not filtered_update_data:
            return db_obj

        if "fecha_retorno" in filtered_update_data and filtered_update_data["fecha_retorno"]:
            if filtered_update_data["fecha_retorno"] < db_obj.fecha_hora:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La fecha de retorno no puede ser anterior a la fecha del movimiento.")

        return super().update(db, db_obj=db_obj, obj_in=filtered_update_data)

    def cambiar_estado(
        self, db: Session, *, movimiento: Movimiento, obj_in: MovimientoEstadoUpdate, current_user: Usuario
    ) -> Movimiento:
        """
        NUEVO: La Máquina de Estados para procesar autorizaciones, rechazos y recepciones (Handoffs).
        """
        lock_topology(db)
        db.execute(select(Movimiento.id).where(Movimiento.id == movimiento.id).with_for_update())
        db.refresh(movimiento)
        equipo = db.scalar(select(Equipo).where(Equipo.id == movimiento.equipo_id).with_for_update(of=Equipo))
        mov_id = movimiento.id
        estado_nuevo = obj_in.estado
        transitions = {"Pendiente": {"Autorizado", "Rechazado", "Cancelado"}, "Autorizado": {"En Proceso", "Completado", "Rechazado", "Cancelado"}, "En Proceso": {"Completado", "Rechazado", "Cancelado"}}
        if estado_nuevo.value not in transitions.get(movimiento.estado, set()):
            raise HTTPException(409, f"Transición no permitida: {movimiento.estado} → {estado_nuevo.value}.")
        
        # 1. Validar transiciones prohibidas
        estados_finales = ["Completado", "Cancelado", "Rechazado"]
        if movimiento.estado in estados_finales:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No se puede cambiar el estado de un movimiento que ya está '{movimiento.estado}'."
            )

        update_data = {"estado": estado_nuevo.value if hasattr(estado_nuevo, 'value') else estado_nuevo}
        if estado_nuevo == EstadoMovimientoEquipoEnum.RECHAZADO and movimiento.estado != "Pendiente":
            if not can_receive_movement(current_user, movimiento):
                raise HTTPException(403, "Solo el custodio o un gestor puede rechazar la recepción.")
            update_data.update(confirmado_por_id=current_user.id, fecha_recepcion=datetime.datetime.now(datetime.timezone.utc))
        
        if estado_nuevo.value in {"Autorizado", "En Proceso", "Completado"}:
            state_codes = {TipoMovimientoEquipoEnum.SALIDA_TEMPORAL: EquipmentStateCode.ON_LOAN, TipoMovimientoEquipoEnum.SALIDA_DEFINITIVA: EquipmentStateCode.RETIRED, TipoMovimientoEquipoEnum.ENTRADA: EquipmentStateCode.AVAILABLE, TipoMovimientoEquipoEnum.ASIGNACION_INTERNA: EquipmentStateCode.IN_USE}
            code = state_codes.get(movimiento.tipo_movimiento)
            if code:
                state = db.scalar(select(EstadoEquipo).where(EstadoEquipo.codigo == code))
                if not state: raise HTTPException(409, "Falta un estado requerido en el catálogo.")
                equipo.estado_id = state.id
            equipo.ubicacion_id = movimiento.ubicacion_destino_id
        if estado_nuevo.value == "Completado":
            if not can_receive_movement(current_user, movimiento):
                raise HTTPException(403, "Solo el custodio o un gestor puede confirmar la recepción.")
            receptor_id = obj_in.empleado_receptor_id or movimiento.empleado_destino_id or current_user.empleado_id
            if obj_in.recibido_por:
                if movimiento.tipo_movimiento not in {"Salida Temporal", "Salida Definitiva"} or movimiento.empleado_destino_id:
                    raise HTTPException(422, "Esta entrega requiere un receptor del catálogo de empleados.")
                update_data.update(recibido_por=obj_in.recibido_por, entidad_receptora=obj_in.entidad_receptora)
            else:
                receptor = db.get(Empleado, receptor_id) if receptor_id else None
                if not receptor or not receptor.is_active:
                    raise HTTPException(422, "Seleccione un empleado receptor activo.")
                if not user_has_permissions(current_user, {perms.PERM_REGISTRAR_MOVIMIENTOS}) and receptor.id != current_user.empleado_id:
                    raise HTTPException(403, "Solo puede confirmar su propia recepción.")
                update_data.update(empleado_receptor_id=receptor.id, recibido_por=receptor.nombre_completo, entidad_receptora=None)
            update_data.update(confirmado_por_id=current_user.id, fecha_recepcion=datetime.datetime.now(datetime.timezone.utc))
            if movimiento.tipo_movimiento == "Asignacion Interna":
                if not movimiento.empleado_destino_id: raise HTTPException(422, "Falta el empleado custodio.")
                custodio = db.get(Empleado, movimiento.empleado_destino_id)
                if not custodio or not custodio.is_active:
                    raise HTTPException(422, "El custodio asignado debe estar activo para recibir el equipo.")
                equipo.empleado_asignado_id = movimiento.empleado_destino_id
            elif movimiento.tipo_movimiento in {"Entrada", "Salida Definitiva"}:
                equipo.empleado_asignado_id = None
        if estado_nuevo.value in {"Cancelado", "Rechazado"} and movimiento.estado_origen_id:
            equipo.estado_id = movimiento.estado_origen_id
            equipo.ubicacion_id = movimiento.ubicacion_origen_id
            equipo.empleado_asignado_id = movimiento.empleado_origen_id
        # 2. Lógica específica por estado
        if estado_nuevo == EstadoMovimientoEquipoEnum.AUTORIZADO:
            update_data: Dict[str, Any] = {
                "estado": estado_nuevo.value if hasattr(estado_nuevo, 'value') else estado_nuevo
            }
            
            update_data["autorizado_por"] = current_user.id
        elif estado_nuevo == EstadoMovimientoEquipoEnum.RECHAZADO:
            if not obj_in.observaciones or len(obj_in.observaciones.strip()) < 5:
                raise HTTPException(status_code=422, detail="Debe proporcionar un motivo de al menos cinco caracteres al rechazar.")

        # 3. Concatenar Observaciones limpiamente
        if obj_in.observaciones:
            obs_actual = movimiento.observaciones or ""
            prefijo = f"[{estado_nuevo.value.upper()}] " if hasattr(estado_nuevo, 'value') else f"[{str(estado_nuevo).upper()}] "
            fecha_str = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')
            nota_formateada = f"{prefijo}- {current_user.nombre_usuario} ({fecha_str}): {obj_in.observaciones}"
            
            update_data["observaciones"] = f"{obs_actual}\n{nota_formateada}".strip()

        propagate(db, equipo, movimiento.componentes_origen, restore=estado_nuevo.value in {"Cancelado", "Rechazado"})
        if movimiento.tipo_movimiento == "Entrada" and estado_nuevo.value == "Completado":
            db.query(Movimiento).filter(Movimiento.equipo_id == equipo.id, Movimiento.tipo_movimiento == "Salida Temporal", Movimiento.fecha_retorno.is_(None), Movimiento.estado.notin_(["Pendiente", "Cancelado", "Rechazado"])).update({"fecha_retorno": datetime.datetime.now(datetime.timezone.utc), "estado": "Completado"}, synchronize_session=False)
        updated_movimiento = super().update(db, db_obj=movimiento, obj_in=update_data)
        logger.info(f"Movimiento ID {mov_id} cambió a estado '{estado_nuevo}' por '{current_user.nombre_usuario}'.")
        return updated_movimiento

    def cancel_movimiento(self, db: Session, *, movimiento: Movimiento, current_user: Usuario) -> Movimiento:
        return self.cambiar_estado(db, movimiento=movimiento,
            obj_in=MovimientoEstadoUpdate(estado=EstadoMovimientoEquipoEnum.CANCELADO, observaciones="Cancelado por el usuario autorizado."), current_user=current_user)

    def get_multi_by_equipo(
        self, db: Session, *, equipo_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Movimiento]:
        statement = (
            select(self.model)
            .where((self.model.equipo_id == equipo_id) | self.model.componentes_origen.has_key(str(equipo_id)))
            .order_by(self.model.fecha_hora.desc(), self.model.id.desc())
            .offset(skip)
            .limit(limit)
        )
        statement = self._apply_load_options_for_movimiento(statement)
        result = db.execute(statement)
        return list(result.scalars().all())

movimiento_service = MovimientoService(Movimiento)


def can_receive_movement(user: Usuario, movimiento: Movimiento) -> bool:
    return bool(user_has_permissions(user, {perms.PERM_REGISTRAR_MOVIMIENTOS}) or (user.empleado_id and user.empleado_id == movimiento.empleado_destino_id))
