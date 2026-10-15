import logging
from typing import Any, Optional, List
from uuid import UUID

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func as sql_func
from fastapi import HTTPException, status

from app.models.inventario_stock import InventarioStock
from app.schemas.inventario_stock import InventarioStockUpdate
from .base_service import BaseService 

logger = logging.getLogger(__name__) 

class InventarioStockService(BaseService[InventarioStock, Any, InventarioStockUpdate]):
    """
    Servicio para CONSULTAR y realizar actualizaciones menores en InventarioStock.
    """
    def __init__(self):
        super().__init__(InventarioStock)
        
    def get_multi_by_filters(
        self,
        db: Session,
        *,
        tipo_item_id: Optional[UUID] = None,
        ubicacion_id: Optional[UUID] = None,
        lote: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[InventarioStock]:
        """
        Obtiene una lista de registros de stock aplicando filtros opcionales.
        """
        logger.debug(
            f"Listando stock con filtros: tipo_item_id='{tipo_item_id}', "
            f"ubicacion_id='{ubicacion_id}', lote='{lote}', skip={skip}, limit={limit}"
        )
        # FIX: Cargamos la relación de la ubicación para que Pydantic pueda leer el nombre
        statement = select(self.model).options(joinedload(self.model.ubicacion_fisica))

        if tipo_item_id:
            statement = statement.where(self.model.tipo_item_id == tipo_item_id)
        if ubicacion_id:
            statement = statement.where(self.model.ubicacion_id == ubicacion_id)
        if lote:
            # Usamos 'ilike' para búsquedas case-insensitive y parciales
            statement = statement.where(self.model.lote.ilike(f"%{lote}%"))

        statement = (
            statement.order_by(self.model.ubicacion_id, self.model.tipo_item_id, self.model.lote, self.model.id)
            .offset(skip)
            .limit(limit)
        )

        result = db.execute(statement)
        return list(result.scalars().all())
    
    def get_stock_record(
        self, db: Session, *, tipo_item_id: UUID, ubicacion_id: UUID, lote: Optional[str] = None
    ) -> Optional[InventarioStock]:
        """
        Obtiene un registro de stock específico por item, ubicación y lote.
        """
        lote_a_buscar = lote if lote is not None else 'N/A'
        
        logger.debug(f"Buscando stock: TipoItem ID {tipo_item_id}, Ubicación ID '{ubicacion_id}', Lote '{lote_a_buscar}'")
        
        statement = select(self.model).options(joinedload(self.model.ubicacion_fisica)).where(
            self.model.tipo_item_id == tipo_item_id,
            self.model.ubicacion_id == ubicacion_id,
            self.model.lote == lote_a_buscar
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
            .options(joinedload(self.model.ubicacion_fisica))
            .where(self.model.tipo_item_id == tipo_item_id)
            .order_by(self.model.ubicacion_id, self.model.lote)
            .offset(skip)
            .limit(limit)
        )
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_stock_by_location(
        self, db: Session, *, ubicacion_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[InventarioStock]:
        """Obtiene todos los registros de stock para una ubicación."""
        logger.debug(f"Listando stock para Ubicación ID: '{ubicacion_id}' (skip: {skip}, limit: {limit}).")
        statement = (
            select(self.model)
            .options(joinedload(self.model.ubicacion_fisica))
            .where(self.model.ubicacion_id == ubicacion_id)
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
        """
        update_data = obj_in.model_dump(exclude_unset=True)
        stock_record = db.scalar(select(self.model).where(self.model.id == stock_record.id)
            .with_for_update(of=self.model).execution_options(populate_existing=True))
        if stock_record is None:
            raise HTTPException(404, "No se encontró el registro de stock.")
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

        if "lote" in fields_to_update:
            lote = (fields_to_update["lote"] or "N/A").strip() or "N/A"
            if lote != stock_record.lote:
                raise HTTPException(409, "Para corregir un lote, registre una transferencia al lote correcto en la misma ubicación. Así se conserva el kardex.")
            fields_to_update["lote"] = lote

        for field, value in fields_to_update.items():
             setattr(stock_record, field, value)

        db.add(stock_record)
        logger.info(f"Detalles de stock ID {stock_id} preparados para ser actualizados.")
        return stock_record

inventario_stock_service = InventarioStockService()
