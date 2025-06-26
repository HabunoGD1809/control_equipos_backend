import logging
from typing import Any, Optional, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select, func as sql_func
from fastapi import HTTPException, status

# Importar modelos y schemas
from app.models.inventario_stock import InventarioStock
from app.schemas.inventario_stock import InventarioStockUpdate
from .base_service import BaseService 

logger = logging.getLogger(__name__) 

# CORREGIDO: Heredar de BaseService
class InventarioStockService(BaseService[InventarioStock, Any, InventarioStockUpdate]):
    """
    Servicio para CONSULTAR y realizar actualizaciones menores en InventarioStock.
    La cantidad_actual es modificada por triggers/funciones de BD basados en InventarioMovimiento.
    Las operaciones que modifican datos NO realizan commit.
    El commit debe ser manejado en la capa de la ruta.
    """
    def __init__(self):
        super().__init__(InventarioStock)
        
    def get_multi_by_filters(
        self,
        db: Session,
        *,
        tipo_item_id: Optional[UUID] = None,
        ubicacion: Optional[str] = None,
        lote: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[InventarioStock]:
        """
        Obtiene una lista de registros de stock aplicando filtros opcionales.
        """
        logger.debug(
            f"Listando stock con filtros: tipo_item_id='{tipo_item_id}', "
            f"ubicacion='{ubicacion}', lote='{lote}', skip={skip}, limit={limit}"
        )
        statement = select(self.model)

        if tipo_item_id:
            statement = statement.where(self.model.tipo_item_id == tipo_item_id)
        if ubicacion:
            statement = statement.where(self.model.ubicacion.ilike(f"%{ubicacion}%"))
        if lote:
            # Usamos 'ilike' para búsquedas case-insensitive y parciales
            statement = statement.where(self.model.lote.ilike(f"%{lote}%"))

        statement = (
            statement.order_by(self.model.ubicacion, self.model.tipo_item_id)
            .offset(skip)
            .limit(limit)
        )

        result = db.execute(statement)
        return list(result.scalars().all())
    
    def get_stock_record(
        self, db: Session, *, tipo_item_id: UUID, ubicacion: str, lote: Optional[str] = None
    ) -> Optional[InventarioStock]:
        """Obtiene un registro de stock específico por item, ubicación y lote."""
        logger.debug(f"Buscando stock: TipoItem ID {tipo_item_id}, Ubicación '{ubicacion}', Lote '{lote}'")
        statement = select(self.model).where(
            self.model.tipo_item_id == tipo_item_id,
            self.model.ubicacion == ubicacion,
            self.model.lote.is_(lote) if lote is None else self.model.lote == lote
        )
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_stock_by_item(
        self, db: Session, *, tipo_item_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[InventarioStock]:
        """Obtiene todos los registros de stock para un tipo de item."""
        logger.debug(f"Listando stock para TipoItem ID: {tipo_item_id} (skip: {skip}, limit: {limit}).")
        statement = (
            select(self.model)
            .where(self.model.tipo_item_id == tipo_item_id)
            .order_by(self.model.ubicacion, self.model.lote)
            .offset(skip)
            .limit(limit)
        )
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_stock_by_location(
        self, db: Session, *, ubicacion: str, skip: int = 0, limit: int = 100
    ) -> List[InventarioStock]:
         """Obtiene todos los registros de stock para una ubicación."""
         logger.debug(f"Listando stock para Ubicación: '{ubicacion}' (skip: {skip}, limit: {limit}).")
         statement = (
            select(self.model)
            .where(self.model.ubicacion == ubicacion)
            .order_by(self.model.tipo_item_id, self.model.lote)
            .offset(skip)
            .limit(limit)
        )
         result = db.execute(statement)
         return list(result.scalars().all())

    def get_total_stock_for_item(self, db: Session, *, tipo_item_id: UUID) -> int:
        """Calcula la cantidad total de stock para un item sumando todas las ubicaciones/lotes."""
        logger.debug(f"Calculando stock total para TipoItem ID: {tipo_item_id}")
        statement = select(sql_func.sum(self.model.cantidad_actual)).where(self.model.tipo_item_id == tipo_item_id)
        result = db.execute(statement)
        total = result.scalar_one_or_none()
        return total or 0

    def update_stock_details(
        self,
        db: Session,
        *,
        stock_record: InventarioStock,
        obj_in: InventarioStockUpdate
    ) -> InventarioStock:
        """
        Actualiza campos específicos (ej. lote, fecha_caducidad) de un registro de stock.
        NO actualiza la cantidad_actual. NO realiza db.commit().
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        stock_id = stock_record.id
        logger.debug(f"Intentando actualizar detalles de stock ID {stock_id} con datos: {update_data}")

        allowed_fields = {"lote", "fecha_caducidad", "notas"}
        
        fields_to_update = {}
        for field in allowed_fields:
            if field in update_data:
                fields_to_update[field] = update_data[field]
        
        if not fields_to_update:
            logger.info(f"No se proporcionaron campos válidos o modificables para actualizar detalles de stock ID {stock_id}.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se proporcionaron campos válidos para actualizar.")

        if "lote" in fields_to_update and fields_to_update["lote"] != stock_record.lote:
            logger.debug(f"Validando nuevo lote '{fields_to_update['lote']}' para stock ID {stock_id} (Item ID: {stock_record.tipo_item_id}, Ubicación: '{stock_record.ubicacion}')")
            existing_with_new_lote = self.get_stock_record(
                db,
                tipo_item_id=stock_record.tipo_item_id,
                ubicacion=stock_record.ubicacion,
                lote=fields_to_update["lote"]
            )
            if existing_with_new_lote and existing_with_new_lote.id != stock_id:
                logger.warning(f"Conflicto al actualizar stock ID {stock_id}: Ya existe stock para este item/ubicación con el lote '{fields_to_update['lote']}'.")
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe stock para este item/ubicación con el lote especificado.")

        for field, value in fields_to_update.items():
             setattr(stock_record, field, value)

        db.add(stock_record)
        logger.info(f"Detalles de stock ID {stock_id} preparados para ser actualizados.")
        return stock_record

inventario_stock_service = InventarioStockService()
