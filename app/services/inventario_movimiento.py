import logging
from typing import Optional, List, Union, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, text, exc as sqlalchemy_exc, or_

try:
    from psycopg import errors as psycopg_errors
    PG_RaiseException = psycopg_errors.RaiseException
except ImportError:
    psycopg_errors = None
    PG_RaiseException = None # type: ignore

from app.models.inventario_movimiento import InventarioMovimiento
from app.models.usuario import Usuario
from app.schemas.inventario_movimiento import InventarioMovimientoCreate, InventarioMovimientoUpdate
from .base_service import BaseService
from .tipo_item_inventario import tipo_item_inventario_service
from .equipo import equipo_service
from .mantenimiento import mantenimiento_service

logger = logging.getLogger(__name__)

class InventarioMovimientoService(BaseService[InventarioMovimiento, InventarioMovimientoCreate, InventarioMovimientoUpdate]):
    def __init__(self):
        super().__init__(InventarioMovimiento)

    def _apply_load_options(self, statement):
        return statement.options(
            selectinload(self.model.usuario_registrador),
            selectinload(self.model.tipo_item)
        )

    def create_movimiento(self, db: Session, *, obj_in: InventarioMovimientoCreate, current_user: Usuario) -> InventarioMovimiento:
        logger.info(f"Usuario '{current_user.nombre_usuario}' intentando crear movimiento de inventario: {obj_in.tipo_movimiento.value} para TipoItem ID {obj_in.tipo_item_id}, Cantidad: {obj_in.cantidad}.")
        
        tipo_item_inventario_service.get_or_404(db, id=obj_in.tipo_item_id)
        if obj_in.equipo_asociado_id:
            equipo_service.get_or_404(db, id=obj_in.equipo_asociado_id)
        if obj_in.mantenimiento_id:
            mantenimiento_service.get_or_404(db, id=obj_in.mantenimiento_id)

        tipo_mov_valor = obj_in.tipo_movimiento.value

        if tipo_mov_valor in ['Salida Uso', 'Salida Descarte', 'Ajuste Negativo', 'Transferencia Salida', 'Devolucion Proveedor', 'Devolucion Interna'] and not obj_in.ubicacion_origen:
             raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Ubicación de origen es requerida para el tipo de movimiento '{tipo_mov_valor}'.")
        if tipo_mov_valor in ['Entrada Compra', 'Ajuste Positivo', 'Transferencia Entrada', 'Devolucion Interna'] and not obj_in.ubicacion_destino:
             raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Ubicación de destino es requerida para el tipo de movimiento '{tipo_mov_valor}'.")
        if tipo_mov_valor in ['Ajuste Positivo', 'Ajuste Negativo'] and not obj_in.motivo_ajuste:
             raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Motivo es requerido para movimientos de ajuste.")
        if obj_in.cantidad <= 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La cantidad del movimiento debe ser mayor que cero.")

        try:
            movimiento_data = obj_in.model_dump()
            db_obj = self.model(**movimiento_data, usuario_id=current_user.id)
            db.add(db_obj)
            logger.info(f"Movimiento de inventario (TipoItem ID: {db_obj.tipo_item_id}, Cant: {db_obj.cantidad}) preparado para ser creado.")
            return db_obj
        except sqlalchemy_exc.DBAPIError as db_err:
            original_exc = getattr(db_err, 'orig', None)
            error_message_from_db = str(original_exc if original_exc else db_err)
            diag_message_primary = None

            if psycopg_errors and original_exc and hasattr(original_exc, 'diag'):
                diag = getattr(original_exc, 'diag', None)
                if diag: diag_message_primary = getattr(diag, 'message_primary', None)
            
            final_error_message_for_client = diag_message_primary or error_message_from_db
            
            logger.error(f"Error DBAPIError al crear movimiento de inventario: '{final_error_message_for_client}'", exc_info=False)
            
            is_pg_raise_exception = PG_RaiseException and original_exc and isinstance(original_exc, PG_RaiseException)
            error_lower_client = final_error_message_for_client.lower()

            if is_pg_raise_exception:
                if "stock insuficiente" in error_lower_client:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=final_error_message_for_client)
                else:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error en lógica de inventario: {final_error_message_for_client}")
            else:
                logger.error(f"Error de base de datos no manejado como RaiseException en create_movimiento: {final_error_message_for_client}", exc_info=True)
                raise db_err

    def create(self, db: Session, *, obj_in: InventarioMovimientoCreate) -> InventarioMovimiento:
        logger.error("Llamada directa a InventarioMovimientoService.create() está deshabilitada.")
        raise NotImplementedError("Debe usar 'create_movimiento' que maneja el usuario actual y la lógica específica de movimientos de inventario.")

    def update(self, db: Session, *, db_obj: InventarioMovimiento, obj_in: Union[InventarioMovimientoUpdate, Dict[str, Any]]) -> InventarioMovimiento:
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        mov_id = db_obj.id
        logger.debug(f"Intentando actualizar movimiento de inventario ID {mov_id} con datos: {update_data}")
        
        allowed_fields = {"notas", "referencia_externa"}
        
        filtered_update_data = {k: v for k, v in update_data.items() if k in allowed_fields and hasattr(db_obj, k)}
        
        if not filtered_update_data:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se proporcionaron campos válidos o modificables para actualizar.")

        updated_db_movimiento = super().update(db, db_obj=db_obj, obj_in=filtered_update_data)
        logger.info(f"Movimiento de inventario ID {mov_id} preparado para ser actualizado.")
        return updated_db_movimiento

    def remove(self, db: Session, *, id: Union[UUID, int]) -> InventarioMovimiento:
        logger.warning(f"Intento de eliminar movimiento de inventario ID {id}. Operación no permitida.")
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail="No se permite eliminar movimientos de inventario. Cree un movimiento de ajuste para corregir."
        )

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[InventarioMovimiento]:
        logger.debug(f"Listando movimientos de inventario (skip: {skip}, limit: {limit}).")
        statement = select(self.model).order_by(self.model.fecha_hora.desc()).offset(skip).limit(limit)
        statement = self._apply_load_options(statement)
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_multi_by_item(self, db: Session, *, tipo_item_id: UUID, skip: int = 0, limit: int = 100) -> List[InventarioMovimiento]:
        logger.debug(f"Listando movimientos de inventario para TipoItem ID: {tipo_item_id} (skip: {skip}, limit: {limit}).")
        statement = select(self.model).where(self.model.tipo_item_id == tipo_item_id).order_by(self.model.fecha_hora.desc()).offset(skip).limit(limit)
        statement = self._apply_load_options(statement)
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_multi_by_equipo_asociado(self, db: Session, *, equipo_id: UUID, skip: int = 0, limit: int = 100) -> List[InventarioMovimiento]:
        logger.debug(f"Listando movimientos de inventario para Equipo Asociado ID: {equipo_id} (skip: {skip}, limit: {limit}).")
        statement = select(self.model).where(self.model.equipo_asociado_id == equipo_id).order_by(self.model.fecha_hora.desc()).offset(skip).limit(limit)
        statement = self._apply_load_options(statement)
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_multi_with_filters(
        self, db: Session, *,
        skip: int = 0, limit: int = 100,
        tipo_item_id: Optional[UUID] = None,
        ubicacion: Optional[str] = None,
        tipo_movimiento: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        usuario_id: Optional[UUID] = None,
        equipo_asociado_id: Optional[UUID] = None, # CORREGIDO
        mantenimiento_id: Optional[UUID] = None    # CORREGIDO
    ) -> List[InventarioMovimiento]:
        logger.debug(f"Buscando movimientos de inventario con filtros: TipoItem={tipo_item_id}, Ubicacion='{ubicacion}', TipoMov='{tipo_movimiento}', RangoFechas='{start_date}-{end_date}', UsuarioID={usuario_id}")
        statement = select(self.model)
        if tipo_item_id:
            statement = statement.where(self.model.tipo_item_id == tipo_item_id)
        if ubicacion:
            statement = statement.where(
                or_(self.model.ubicacion_origen.ilike(f"%{ubicacion}%"), self.model.ubicacion_destino.ilike(f"%{ubicacion}%"))
            )
        if tipo_movimiento:
            statement = statement.where(self.model.tipo_movimiento == tipo_movimiento)
        if start_date:
            statement = statement.where(self.model.fecha_hora >= start_date)
        if end_date:
            end_date_inclusive = end_date + timedelta(days=1, microseconds=-1) if isinstance(end_date, datetime) else end_date
            statement = statement.where(self.model.fecha_hora <= end_date_inclusive)
        if usuario_id:
            statement = statement.where(self.model.usuario_id == usuario_id)
        if equipo_asociado_id: # CORREGIDO
            statement = statement.where(self.model.equipo_asociado_id == equipo_asociado_id)
        if mantenimiento_id: # CORREGIDO
            statement = statement.where(self.model.mantenimiento_id == mantenimiento_id)

        statement = self._apply_load_options(statement.order_by(self.model.fecha_hora.desc()).offset(skip).limit(limit))
        result = db.execute(statement)
        return list(result.scalars().all())

inventario_movimiento_service = InventarioMovimientoService()
