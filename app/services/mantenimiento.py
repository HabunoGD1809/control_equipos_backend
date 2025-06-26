import logging
from typing import Optional, List, Union, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import select, func as sql_func
from fastapi import HTTPException, status

# Importar modelos y schemas
from app.models.mantenimiento import Mantenimiento
from app.models.equipo import Equipo # Usado a través de equipo_service
from app.models.tipo_mantenimiento import TipoMantenimiento # Usado para join
from app.schemas.mantenimiento import MantenimientoCreate, MantenimientoUpdate

# Importar la clase base y otros servicios necesarios
from .base_service import BaseService # BaseService ya está modificado
from .equipo import equipo_service
from .tipo_mantenimiento import tipo_mantenimiento_service
from .proveedor import proveedor_service

logger = logging.getLogger(__name__) # Configurar logger

class MantenimientoService(BaseService[Mantenimiento, MantenimientoCreate, MantenimientoUpdate]):
    """
    Servicio para gestionar los registros de Mantenimiento.
    Las operaciones CUD (Create, Update, Delete) NO realizan commit.
    El commit debe ser manejado en la capa de la ruta.
    """

    def create(self, db: Session, *, obj_in: MantenimientoCreate) -> Mantenimiento:
        """
        Crea un nuevo registro de mantenimiento, validando IDs relacionados.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando crear mantenimiento para Equipo ID: {obj_in.equipo_id}, TipoMant ID: {obj_in.tipo_mantenimiento_id}")

        equipo = equipo_service.get(db, id=obj_in.equipo_id)
        if not equipo:
            logger.error(f"Equipo con ID {obj_in.equipo_id} no encontrado al crear mantenimiento.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Equipo con ID {obj_in.equipo_id} no encontrado.")

        tipo_mant = tipo_mantenimiento_service.get(db, id=obj_in.tipo_mantenimiento_id)
        if not tipo_mant:
            logger.error(f"TipoMantenimiento con ID {obj_in.tipo_mantenimiento_id} no encontrado al crear mantenimiento.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"TipoMantenimiento con ID {obj_in.tipo_mantenimiento_id} no encontrado.")

        if obj_in.proveedor_servicio_id:
            proveedor = proveedor_service.get(db, id=obj_in.proveedor_servicio_id)
            if not proveedor:
                 logger.error(f"Proveedor de servicio con ID {obj_in.proveedor_servicio_id} no encontrado al crear mantenimiento.")
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor de servicio con ID {obj_in.proveedor_servicio_id} no encontrado.")

        if obj_in.fecha_inicio and obj_in.fecha_finalizacion and obj_in.fecha_inicio > obj_in.fecha_finalizacion:
            logger.warning("Intento de crear mantenimiento con fecha de inicio posterior a la fecha de finalización.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha de inicio no puede ser posterior a la fecha de finalización.")

        # super().create() ya no hace commit.
        # fecha_proximo_mantenimiento se calcula por trigger en DB. Se necesitará refresh en la ruta.
        db_mantenimiento = super().create(db, obj_in=obj_in)
        logger.info(f"Mantenimiento para equipo '{equipo.nombre}' (Tipo: '{tipo_mant.nombre}') preparado para ser creado.")
        return db_mantenimiento

    def update(
        self,
        db: Session,
        *,
        db_obj: Mantenimiento, # Objeto Mantenimiento existente
        obj_in: Union[MantenimientoUpdate, Dict[str, Any]] # Datos para actualizar
    ) -> Mantenimiento:
        """
        Actualiza un registro de mantenimiento existente.
        NO realiza db.commit(). Llama a super().update() que tampoco lo hace.
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        mant_id = db_obj.id
        logger.debug(f"Intentando actualizar mantenimiento ID {mant_id} con datos: {update_data}")

        if "proveedor_servicio_id" in update_data and update_data["proveedor_servicio_id"] != db_obj.proveedor_servicio_id:
            if update_data["proveedor_servicio_id"] is not None:
                proveedor = proveedor_service.get(db, id=update_data["proveedor_servicio_id"])
                if not proveedor:
                    logger.error(f"Proveedor de servicio con ID {update_data['proveedor_servicio_id']} no encontrado al actualizar mantenimiento {mant_id}.")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor de servicio con ID {update_data['proveedor_servicio_id']} no encontrado.")
            # Permitir establecerlo a None

        # Validar fechas si ambas están presentes en la actualización o una está y la otra ya existe en db_obj
        fecha_inicio_final = update_data.get("fecha_inicio", db_obj.fecha_inicio)
        fecha_finalizacion_final = update_data.get("fecha_finalizacion", db_obj.fecha_finalizacion)

        if fecha_inicio_final and fecha_finalizacion_final and fecha_inicio_final > fecha_finalizacion_final:
            logger.warning(f"Error de validación de fechas al actualizar mantenimiento {mant_id}: inicio posterior a fin.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha de inicio no puede ser posterior a la fecha de finalización.")
        
        # No se puede cambiar equipo_id ni tipo_mantenimiento_id directamente aquí.
        # Si se necesitara, se requeriría lógica más compleja o un endpoint dedicado.
        if "equipo_id" in update_data and update_data["equipo_id"] != db_obj.equipo_id:
            logger.error(f"Intento de cambiar equipo_id en mantenimiento ID {mant_id}. Operación no permitida por este método.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede cambiar el equipo de un mantenimiento existente.")
        if "tipo_mantenimiento_id" in update_data and update_data["tipo_mantenimiento_id"] != db_obj.tipo_mantenimiento_id:
            logger.error(f"Intento de cambiar tipo_mantenimiento_id en mantenimiento ID {mant_id}. Operación no permitida por este método.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se puede cambiar el tipo de un mantenimiento existente.")


        # super().update() ya no hace commit.
        # fecha_proximo_mantenimiento se actualiza por trigger si cambia estado a Completado. Se necesitará refresh en la ruta.
        updated_db_mantenimiento = super().update(db, db_obj=db_obj, obj_in=update_data)
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
            .order_by(self.model.fecha_programada.desc().nullslast(), self.model.created_at.desc()) # type: ignore[attr-defined]
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
        fecha_limite = datetime.now(timezone.utc) + timedelta(days=days_ahead) # Usar UTC
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
    
    # El método remove es heredado de BaseService y ya no hace commit.
    # Si se necesitara lógica específica antes de eliminar un mantenimiento (ej. verificar si tiene documentos asociados
    # y qué hacer con ellos), se debería sobreescribir remove aquí.
    
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
        
        # Filtrado por rango de fechas en 'fecha_programada'
        if start_date:
            statement = statement.where(self.model.fecha_programada >= start_date)
        if end_date:
            statement = statement.where(self.model.fecha_programada <= end_date)

        statement = statement.order_by(self.model.fecha_programada.desc().nullslast(), self.model.created_at.desc()) # type: ignore
        statement = statement.offset(skip).limit(limit)
        
        result = db.execute(statement)
        return list(result.scalars().all())

mantenimiento_service = MantenimientoService(Mantenimiento)
