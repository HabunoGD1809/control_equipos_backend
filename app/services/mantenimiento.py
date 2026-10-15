import logging
from typing import Optional, List, Union, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, func as sql_func
from fastapi import HTTPException, status

from app.models.mantenimiento import Mantenimiento
from app.models.estado_equipo import EstadoEquipo
from app.models.movimiento import Movimiento
from app.models.reserva_equipo import ReservaEquipo
from app.models.inventario_movimiento import InventarioMovimiento
from app.models.equipo import Equipo 
from app.models.tipo_mantenimiento import TipoMantenimiento 
from app.core.equipment_states import EquipmentStateCode
from app.schemas.mantenimiento import MantenimientoCreate, MantenimientoUpdate

from .asset_custody import physical_group, ensure_free, snapshot, propagate, lock_topology
from .base_service import BaseService 
from .equipo import equipo_service
from .tipo_mantenimiento import tipo_mantenimiento_service
from .tecnico import tecnico_service

logger = logging.getLogger(__name__)

class MantenimientoService(BaseService[Mantenimiento, MantenimientoCreate, MantenimientoUpdate]):
    """
    Servicio para gestionar los registros de Mantenimiento.
    Las operaciones CUD (Create, Update, Delete) NO realizan commit.
    El commit debe ser manejado en la capa de la ruta.
    """

    def _apply_asset_state(self, db, maintenance, equipo, state):
        active = {"En Proceso", "Pausado", "Requiere Piezas"}
        if state in active:
            members = physical_group(db, equipo.id)
            ensure_free(db, members, exclude_maintenance=maintenance.id)
            if not maintenance.componentes_origen:
                maintenance.componentes_origen = snapshot(members, equipo.id)
            competing = db.scalar(select(Mantenimiento.id).where(Mantenimiento.equipo_id == equipo.id, Mantenimiento.id != maintenance.id, Mantenimiento.estado.in_(active)).limit(1))
            pending = db.scalar(select(Movimiento.id).where(Movimiento.equipo_id == equipo.id, Movimiento.estado.in_(["Pendiente", "Autorizado", "En Proceso"])).limit(1))
            loan = db.scalar(select(ReservaEquipo.id).where(ReservaEquipo.equipo_id == equipo.id, ReservaEquipo.estado == "En Curso").limit(1))
            if competing or pending or loan:
                raise HTTPException(409, "El equipo tiene una entrega, préstamo o mantenimiento en curso.")
            current = db.get(EstadoEquipo, equipo.estado_id)
            if current and current.es_estado_final:
                raise HTTPException(409, "Un equipo dado de baja no puede entrar en mantenimiento.")
            if not maintenance.estado_equipo_anterior_id:
                maintenance.estado_equipo_anterior_id = equipo.estado_id
            target = db.scalar(select(EstadoEquipo).where(EstadoEquipo.codigo == EquipmentStateCode.MAINTENANCE))
            if not target: raise HTTPException(409, "Falta el estado En Mantenimiento. Ejecute bootstrap.")
            equipo.estado_id = target.id
            maintenance.fecha_inicio = maintenance.fecha_inicio or datetime.now(timezone.utc)
        elif state in {"Completado", "Cancelado"} and maintenance.estado_equipo_anterior_id:
            equipo.estado_id = maintenance.estado_equipo_anterior_id
        if state == "Completado":
            maintenance.fecha_finalizacion = maintenance.fecha_finalizacion or datetime.now(timezone.utc)
        if state in active:
            propagate(db, equipo, maintenance.componentes_origen)
        elif state in {"Completado", "Cancelado"}:
            propagate(db, equipo, maintenance.componentes_origen, restore=True)
        db.add(equipo)

    def remove(self, db: Session, *, id):
        maintenance = self.get_or_404(db, id=id)
        if maintenance.estado not in {"Programado", "Pendiente Aprobacion", "Cancelado"} or maintenance.documentos or maintenance.items_usados:
            raise HTTPException(409, "Conserve el historial de mantenimiento; solo se pueden eliminar programaciones sin trabajos ni documentos asociados.")
        return super().remove(db, id=id)

    def create(self, db: Session, *, obj_in: MantenimientoCreate) -> Mantenimiento:
        """
        Crea un nuevo registro de mantenimiento, validando IDs relacionados.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando crear mantenimiento para Equipo ID: {obj_in.equipo_id}, TipoMant ID: {obj_in.tipo_mantenimiento_id}")

        lock_topology(db)
        equipo = equipo_service.get(db, id=obj_in.equipo_id)
        if not equipo:
            logger.error(f"Equipo con ID {obj_in.equipo_id} no encontrado al crear mantenimiento.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Equipo con ID {obj_in.equipo_id} no encontrado.")

        db.execute(select(Equipo.id).where(Equipo.id == equipo.id).with_for_update())
        db.refresh(equipo)
        tipo_mant = tipo_mantenimiento_service.get(db, id=obj_in.tipo_mantenimiento_id)
        if not tipo_mant:
            logger.error(f"TipoMantenimiento con ID {obj_in.tipo_mantenimiento_id} no encontrado al crear mantenimiento.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"TipoMantenimiento con ID {obj_in.tipo_mantenimiento_id} no encontrado.")

        tecnico = tecnico_service.get(db, id=obj_in.tecnico_id)
        if not tecnico:
            logger.error(f"Técnico con ID {obj_in.tecnico_id} no encontrado al crear mantenimiento.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Técnico con ID {obj_in.tecnico_id} no encontrado.")
        if not tecnico.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El técnico seleccionado está inactivo y no puede asignarse a nuevos mantenimientos.")

        if obj_in.fecha_inicio and obj_in.fecha_finalizacion and obj_in.fecha_inicio > obj_in.fecha_finalizacion:
            logger.warning("Intento de crear mantenimiento con fecha de inicio posterior a la fecha de finalización.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La fecha de inicio no puede ser posterior a la fecha de finalización.")

        db_mantenimiento = super().create(db, obj_in=obj_in)
        db.flush()
        self._apply_asset_state(db, db_mantenimiento, equipo, obj_in.estado.value)
        logger.info(f"Mantenimiento para equipo '{equipo.nombre}' (Tipo: '{tipo_mant.nombre}') preparado para ser creado.")
        return db_mantenimiento

    def update(
        self,
        db: Session,
        *,
        db_obj: Mantenimiento, 
        obj_in: Union[MantenimientoUpdate, Dict[str, Any]] 
    ) -> Mantenimiento:
        """
        Actualiza un registro de mantenimiento existente.
        NO realiza db.commit(). Llama a super().update() que tampoco lo hace.
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        lock_topology(db)
        db.execute(select(Mantenimiento.id).where(Mantenimiento.id == db_obj.id).with_for_update())
        db.refresh(db_obj)
        equipo = db.scalar(select(Equipo).where(Equipo.id == db_obj.equipo_id).with_for_update(of=Equipo).execution_options(populate_existing=True))
        if db_obj.estado in {"Completado", "Cancelado"} and update_data.get("estado", db_obj.estado) != db_obj.estado:
            raise HTTPException(409, "Un mantenimiento finalizado no puede reabrirse; programe uno nuevo.")
        previous_state = db_obj.estado
        mant_id = db_obj.id
        logger.debug(f"Intentando actualizar mantenimiento ID {mant_id} con datos: {update_data}")

        if "tecnico_id" in update_data and update_data["tecnico_id"] != db_obj.tecnico_id:
            if update_data["tecnico_id"] is not None:
                tecnico = tecnico_service.get(db, id=update_data["tecnico_id"])
                if not tecnico or not tecnico.is_active:
                    logger.error(f"Técnico con ID {update_data['tecnico_id']} no encontrado al actualizar mantenimiento {mant_id}.")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Técnico con ID {update_data['tecnico_id']} no encontrado.")

        fecha_inicio_final = update_data.get("fecha_inicio", db_obj.fecha_inicio)
        fecha_finalizacion_final = update_data.get("fecha_finalizacion", db_obj.fecha_finalizacion)

        if fecha_inicio_final and fecha_finalizacion_final and fecha_inicio_final > fecha_finalizacion_final:
            logger.warning(f"Error de validación de fechas al actualizar mantenimiento {mant_id}: inicio posterior a fin.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La fecha de inicio no puede ser posterior a la fecha de finalización.")
        
        if "equipo_id" in update_data and update_data["equipo_id"] != db_obj.equipo_id:
            logger.error(f"Intento de cambiar equipo_id en mantenimiento ID {mant_id}. Operación no permitida por este método.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede cambiar el equipo de un mantenimiento existente.")
        if "tipo_mantenimiento_id" in update_data and update_data["tipo_mantenimiento_id"] != db_obj.tipo_mantenimiento_id:
            logger.error(f"Intento de cambiar tipo_mantenimiento_id en mantenimiento ID {mant_id}. Operación no permitida por este método.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede cambiar el tipo de un mantenimiento existente.")

        updated_db_mantenimiento = super().update(db, db_obj=db_obj, obj_in=update_data)
        # Group locking refreshes equipment and its loaded relationships. Persist the
        # maintenance changes first so that refresh cannot discard pending fields.
        db.flush()
        state = updated_db_mantenimiento.estado
        state = state.value if hasattr(state, "value") else state
        if state != previous_state:
            self._apply_asset_state(db, updated_db_mantenimiento, equipo, state)
        logger.info(f"Mantenimiento ID {mant_id} preparado para ser actualizado.")
        return updated_db_mantenimiento

    def get_multi_by_equipo(
        self, db: Session, *, equipo_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Mantenimiento]:
        """Obtiene el historial de mantenimientos de un equipo específico."""
        logger.debug(f"Listando mantenimientos para equipo ID: {equipo_id} (skip: {skip}, limit: {limit}).")
        statement = (
            select(self.model)
            .where(self.model.equipo_id == equipo_id)
            .order_by(self.model.fecha_programada.desc().nullslast(), self.model.created_at.desc()) 
            .offset(skip)
            .limit(limit)
        )
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_proximos_mantenimientos(
        self, db: Session, *, days_ahead: int = 30, skip: int = 0, limit: int = 100
    ) -> List[Mantenimiento]:
        """
        Obtiene mantenimientos programados o cuya próxima fecha (para preventivos)
        está dentro del rango especificado.
        """
        logger.debug(f"Buscando próximos mantenimientos para los siguientes {days_ahead} días (skip: {skip}, limit: {limit}).")
        fecha_limite = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        statement = (
            select(self.model)
            .join(self.model.tipo_mantenimiento)
            .where(
                self.model.estado.in_(['Programado', 'Pendiente Aprobacion', 'Requiere Piezas', 'Pausado']),
                sql_func.coalesce(self.model.fecha_programada, self.model.fecha_proximo_mantenimiento) <= fecha_limite, 
                (
                    (TipoMantenimiento.es_preventivo == True) | (self.model.fecha_proximo_mantenimiento != None)
                )
            )
            .order_by(
                sql_func.coalesce(self.model.fecha_proximo_mantenimiento, self.model.fecha_programada).asc()
            )
            .offset(skip)
            .limit(limit)
        )
        result = db.execute(statement)
        return list(result.scalars().all())
    
    def get_multi_with_filters(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        equipo_id: Optional[UUID] = None,
        estado: Optional[str] = None,
        tipo_mantenimiento_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Mantenimiento]:
        """
        Obtiene una lista de mantenimientos aplicando filtros dinámicos.
        """
        statement = select(self.model)

        if equipo_id:
            statement = statement.where(self.model.equipo_id == equipo_id)
        if estado:
            statement = statement.where(self.model.estado == estado)
        if tipo_mantenimiento_id:
            statement = statement.where(self.model.tipo_mantenimiento_id == tipo_mantenimiento_id)
        
        if start_date:
            statement = statement.where(self.model.fecha_programada >= start_date)
        
        if end_date:
            end_of_day = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, 999999)
            statement = statement.where(self.model.fecha_programada <= end_of_day)

        statement = statement.order_by(self.model.fecha_programada.desc().nullslast(), self.model.created_at.desc())
        statement = statement.offset(skip).limit(limit)
        
        result = db.execute(statement)
        return list(result.scalars().all())

mantenimiento_service = MantenimientoService(Mantenimiento)
