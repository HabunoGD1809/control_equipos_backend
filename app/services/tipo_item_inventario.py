import logging
from typing import Optional, List, Union, Dict, Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sql_func, Row

from app.models.tipo_item_inventario import TipoItemInventario
from app.models.inventario_stock import InventarioStock
from app.schemas.tipo_item_inventario import (
    TipoItemInventarioCreate, TipoItemInventarioUpdate
)

from .base_service import BaseService
from .proveedor import proveedor_service

logger = logging.getLogger(__name__)

class TipoItemInventarioService(BaseService[TipoItemInventario, TipoItemInventarioCreate, TipoItemInventarioUpdate]):
    """
    Servicio para gestionar los Tipos de Item de Inventario (catálogo).
    """

    def get_by_name(self, db: Session, *, name: str) -> Optional[TipoItemInventario]:
        """Obtiene un tipo de item por su nombre."""
        logger.debug(f"Buscando tipo de item por nombre: '{name}'")
        statement = select(self.model).where(self.model.nombre == name)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_by_sku(self, db: Session, *, sku: str) -> Optional[TipoItemInventario]:
        """Obtiene un tipo de item por su SKU."""
        if not sku:
            return None
        logger.debug(f"Buscando tipo de item por SKU: '{sku}'")
        statement = select(self.model).where(self.model.sku == sku)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_by_codigo_barras(self, db: Session, *, codigo_barras: str) -> Optional[TipoItemInventario]:
        """Obtiene un tipo de item por su código de barras."""
        if not codigo_barras:
            return None
        logger.debug(f"Buscando tipo de item por Código de Barras: '{codigo_barras}'")
        statement = select(self.model).where(self.model.codigo_barras == codigo_barras)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def create(self, db: Session, *, obj_in: TipoItemInventarioCreate) -> TipoItemInventario:
        """
        Crea un nuevo tipo de item, validando unicidad y FKs.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando crear tipo de item: Nombre='{obj_in.nombre}', SKU='{obj_in.sku}'")
        
        if self.get_by_name(db, name=obj_in.nombre):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nombre de item ya existe.")
        if obj_in.sku and self.get_by_sku(db, sku=obj_in.sku):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU ya existe.")
        if obj_in.codigo_barras and self.get_by_codigo_barras(db, codigo_barras=obj_in.codigo_barras):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Código de barras ya existe.")

        if obj_in.proveedor_preferido_id:
            if not proveedor_service.get(db, id=obj_in.proveedor_preferido_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor preferido con ID {obj_in.proveedor_preferido_id} no encontrado.")

        db_tipo_item = super().create(db, obj_in=obj_in)
        logger.info(f"Tipo de item '{db_tipo_item.nombre}' (SKU: {db_tipo_item.sku}) preparado para ser creado.")
        return db_tipo_item

    def update(
        self,
        db: Session,
        *,
        db_obj: TipoItemInventario,
        obj_in: Union[TipoItemInventarioUpdate, Dict[str, Any]]
    ) -> TipoItemInventario:
        """
        Actualiza un tipo de item, validando unicidad y FKs si cambian.
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        tipo_item_id = db_obj.id
        logger.debug(f"Intentando actualizar tipo de item ID {tipo_item_id} con datos: {update_data}")

        if "nombre" in update_data and update_data["nombre"] != db_obj.nombre:
            existing_name = self.get_by_name(db, name=update_data["nombre"])
            if existing_name and existing_name.id != tipo_item_id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nombre de item ya existe.")
        
        if "sku" in update_data and update_data["sku"] != db_obj.sku and update_data["sku"] is not None:
            existing_sku = self.get_by_sku(db, sku=update_data["sku"])
            if existing_sku and existing_sku.id != tipo_item_id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU ya existe.")
        
        if "codigo_barras" in update_data and update_data["codigo_barras"] != db_obj.codigo_barras and update_data["codigo_barras"] is not None:
            existing_cb = self.get_by_codigo_barras(db, codigo_barras=update_data["codigo_barras"])
            if existing_cb and existing_cb.id != tipo_item_id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Código de barras ya existe.")

        if "proveedor_preferido_id" in update_data and update_data["proveedor_preferido_id"] != db_obj.proveedor_preferido_id:
            if update_data["proveedor_preferido_id"] is not None:
                if not proveedor_service.get(db, id=update_data["proveedor_preferido_id"]):
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor preferido con ID {update_data['proveedor_preferido_id']} no encontrado.")

        updated_db_tipo_item = super().update(db, db_obj=db_obj, obj_in=update_data)
        logger.info(f"Tipo de item ID {tipo_item_id} ('{updated_db_tipo_item.nombre}') preparado para ser actualizado.")
        return updated_db_tipo_item

    def get_low_stock_items(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[TipoItemInventario]:
        """
        Devuelve una lista de objetos TipoItemInventario a los que se les ha añadido
        un atributo 'stock_total_actual'.
        """
        logger.debug(f"Obteniendo items con bajo stock (skip: {skip}, limit: {limit}).")
        
        subquery_stock_total = (
            select(
                InventarioStock.tipo_item_id,
                sql_func.sum(InventarioStock.cantidad_actual).label("stock_total_actual")
            )
            .group_by(InventarioStock.tipo_item_id)
            .subquery('sq_stock_total')
        )

        statement = (
            select(
                self.model,
                sql_func.coalesce(subquery_stock_total.c.stock_total_actual, 0).label("stock_total_actual")
            )
            .join(
                subquery_stock_total,
                self.model.id == subquery_stock_total.c.tipo_item_id,
                isouter=True
            )
            .where(sql_func.coalesce(subquery_stock_total.c.stock_total_actual, 0) <= self.model.stock_minimo)
            .where(self.model.stock_minimo > 0)
            .order_by(self.model.nombre)
            .offset(skip)
            .limit(limit)
        )

        result = db.execute(statement)
        rows = result.all()

        items_low_stock: List[TipoItemInventario] = []
        for item, stock_total in rows:
            # Añadimos el stock como un atributo al objeto ORM.
            # Pydantic lo leerá para poblar el schema TipoItemInventarioConStock.
            item.stock_total_actual = stock_total
            items_low_stock.append(item)

        logger.info(f"Se encontraron {len(items_low_stock)} items con bajo stock.")
        return items_low_stock

    # El método remove es heredado de BaseService y ya no hace commit.
    # La FK en inventario_stock (tipo_item_id) y en inventario_movimientos (tipo_item_id)
    # deberían ser ON DELETE RESTRICT para prevenir borrar si está en uso.
    # Esta restricción será capturada por el manejador de IntegrityError en la ruta.

tipo_item_inventario_service = TipoItemInventarioService(TipoItemInventario)
