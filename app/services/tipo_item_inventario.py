import logging
from typing import Optional, List, Union, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select, func as sql_func
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder # Para get_low_stock_items

# Importar modelos y schemas
from app.models.tipo_item_inventario import TipoItemInventario
from app.models.inventario_stock import InventarioStock # Necesario para calcular stock total
from app.schemas.tipo_item_inventario import (
    TipoItemInventarioCreate, TipoItemInventarioUpdate
)

# Importar la clase base y otros servicios necesarios
from .base_service import BaseService # BaseService ya está modificado
from .proveedor import proveedor_service # Para validar proveedor_preferido_id

logger = logging.getLogger(__name__) # Configurar logger

class TipoItemInventarioService(BaseService[TipoItemInventario, TipoItemInventarioCreate, TipoItemInventarioUpdate]):
    """
    Servicio para gestionar los Tipos de Item de Inventario (catálogo).
    Las operaciones CUD (Create, Update, Delete) heredadas o propias
    NO realizan commit. El commit debe ser manejado en la capa de la ruta.
    """

    def get_by_name(self, db: Session, *, name: str) -> Optional[TipoItemInventario]:
        """Obtiene un tipo de item por su nombre."""
        logger.debug(f"Buscando tipo de item por nombre: '{name}'")
        statement = select(self.model).where(self.model.nombre == name) # type: ignore[attr-defined]
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_by_sku(self, db: Session, *, sku: str) -> Optional[TipoItemInventario]:
        """Obtiene un tipo de item por su SKU."""
        if not sku: # Un SKU vacío o None no debería buscarse
            return None
        logger.debug(f"Buscando tipo de item por SKU: '{sku}'")
        statement = select(self.model).where(self.model.sku == sku) # type: ignore[attr-defined]
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_by_codigo_barras(self, db: Session, *, codigo_barras: str) -> Optional[TipoItemInventario]:
        """Obtiene un tipo de item por su código de barras."""
        if not codigo_barras: # Un código de barras vacío o None no debería buscarse
            return None
        logger.debug(f"Buscando tipo de item por Código de Barras: '{codigo_barras}'")
        statement = select(self.model).where(self.model.codigo_barras == codigo_barras) # type: ignore[attr-defined]
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def create(self, db: Session, *, obj_in: TipoItemInventarioCreate) -> TipoItemInventario:
        """
        Crea un nuevo tipo de item, validando unicidad y FKs.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando crear tipo de item: Nombre='{obj_in.nombre}', SKU='{obj_in.sku}'")
        
        if self.get_by_name(db, name=obj_in.nombre):
            logger.warning(f"Intento de crear tipo de item con nombre duplicado: {obj_in.nombre}")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nombre de item ya existe.")
        if obj_in.sku and self.get_by_sku(db, sku=obj_in.sku):
            logger.warning(f"Intento de crear tipo de item con SKU duplicado: {obj_in.sku}")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU ya existe.")
        if obj_in.codigo_barras and self.get_by_codigo_barras(db, codigo_barras=obj_in.codigo_barras):
            logger.warning(f"Intento de crear tipo de item con Código de Barras duplicado: {obj_in.codigo_barras}")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Código de barras ya existe.")

        if obj_in.proveedor_preferido_id:
            if not proveedor_service.get(db, id=obj_in.proveedor_preferido_id):
                logger.error(f"Proveedor preferido con ID {obj_in.proveedor_preferido_id} no encontrado al crear tipo de item.")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor preferido con ID {obj_in.proveedor_preferido_id} no encontrado.")

        # super().create() ya no hace commit.
        db_tipo_item = super().create(db, obj_in=obj_in)
        logger.info(f"Tipo de item '{db_tipo_item.nombre}' (SKU: {db_tipo_item.sku}) preparado para ser creado.")
        return db_tipo_item

    def update(
        self,
        db: Session,
        *,
        db_obj: TipoItemInventario, # Objeto TipoItemInventario existente de la BD
        obj_in: Union[TipoItemInventarioUpdate, Dict[str, Any]]
    ) -> TipoItemInventario:
        """
        Actualiza un tipo de item, validando unicidad y FKs si cambian.
        NO realiza db.commit(). Llama a super().update() que tampoco lo hace.
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        tipo_item_id = db_obj.id
        logger.debug(f"Intentando actualizar tipo de item ID {tipo_item_id} con datos: {update_data}")

        if "nombre" in update_data and update_data["nombre"] != db_obj.nombre:
            existing_name = self.get_by_name(db, name=update_data["nombre"])
            if existing_name and existing_name.id != tipo_item_id: # Asegurar que no sea el mismo objeto
                logger.warning(f"Conflicto de nombre al actualizar tipo de item ID {tipo_item_id}. Nombre '{update_data['nombre']}' ya existe.")
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nombre de item ya existe.")
        
        if "sku" in update_data and update_data["sku"] != db_obj.sku and update_data["sku"] is not None:
            existing_sku = self.get_by_sku(db, sku=update_data["sku"])
            if existing_sku and existing_sku.id != tipo_item_id:
                logger.warning(f"Conflicto de SKU al actualizar tipo de item ID {tipo_item_id}. SKU '{update_data['sku']}' ya existe.")
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU ya existe.")
        
        if "codigo_barras" in update_data and update_data["codigo_barras"] != db_obj.codigo_barras and update_data["codigo_barras"] is not None:
            existing_cb = self.get_by_codigo_barras(db, codigo_barras=update_data["codigo_barras"])
            if existing_cb and existing_cb.id != tipo_item_id:
                logger.warning(f"Conflicto de Código de Barras al actualizar tipo de item ID {tipo_item_id}. Código '{update_data['codigo_barras']}' ya existe.")
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Código de barras ya existe.")

        if "proveedor_preferido_id" in update_data and update_data["proveedor_preferido_id"] != db_obj.proveedor_preferido_id: # type: ignore
            if update_data["proveedor_preferido_id"] is not None:
                if not proveedor_service.get(db, id=update_data["proveedor_preferido_id"]):
                    logger.error(f"Proveedor preferido con ID {update_data['proveedor_preferido_id']} no encontrado al actualizar tipo de item {tipo_item_id}.")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor preferido con ID {update_data['proveedor_preferido_id']} no encontrado.")
            # Se permite setear a None para desasociar proveedor si el campo es nullable

        # super().update() ya no hace commit.
        updated_db_tipo_item = super().update(db, db_obj=db_obj, obj_in=update_data)
        logger.info(f"Tipo de item ID {tipo_item_id} ('{updated_db_tipo_item.nombre}') preparado para ser actualizado.")
        return updated_db_tipo_item

    def get_low_stock_items(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Obtiene los items cuyo stock total actual (sumando ubicaciones/lotes)
        es menor o igual a su stock mínimo definido. Devuelve una lista de diccionarios.
        """
        logger.debug(f"Obteniendo items con bajo stock (skip: {skip}, limit: {limit}).")
        
        # Subconsulta para calcular el stock total por tipo_item_id
        subquery_stock_total = (
            select(
                InventarioStock.tipo_item_id, # type: ignore[attr-defined]
                sql_func.sum(InventarioStock.cantidad_actual).label("stock_total_actual") # type: ignore[attr-defined]
            )
            .group_by(InventarioStock.tipo_item_id) # type: ignore[attr-defined]
            .subquery('sq_stock_total') # Alias para la subquery
        )
        
        # Consulta principal para unir TipoItemInventario con el stock total calculado
        statement = (
            select(
                self.model, # El objeto TipoItemInventario completo
                subquery_stock_total.c.stock_total_actual # La columna calculada de la subquery
            )
            .join(subquery_stock_total, self.model.id == subquery_stock_total.c.tipo_item_id, isouter=True) # type: ignore[attr-defined] # OUTER JOIN para incluir items sin stock
            .where(
                # Considerar stock_total_actual como 0 si no hay registros en InventarioStock para el item
                sql_func.coalesce(subquery_stock_total.c.stock_total_actual, 0) <= self.model.stock_minimo # type: ignore[attr-defined]
            )
            .order_by(self.model.nombre) # type: ignore[attr-defined]
            .offset(skip)
            .limit(limit)
        )
        
        result = db.execute(statement)
        
        items_low_stock: List[Dict[str, Any]] = []
        for tipo_item_orm, stock_total_actual_db in result.all(): # type: ignore
            item_dict = jsonable_encoder(tipo_item_orm) # Convertir el objeto ORM TipoItemInventario a dict
            # Asegurar que stock_total_actual sea un entero, y 0 si es None (por el COALESCE en la query)
            item_dict["stock_total_actual"] = int(stock_total_actual_db or 0)
            items_low_stock.append(item_dict)
            
        logger.info(f"Se encontraron {len(items_low_stock)} items con bajo stock.")
        return items_low_stock

    # El método remove es heredado de BaseService y ya no hace commit.
    # La FK en inventario_stock (tipo_item_id) y en inventario_movimientos (tipo_item_id)
    # deberían ser ON DELETE RESTRICT para prevenir borrar si está en uso.
    # Esta restricción será capturada por el manejador de IntegrityError en la ruta.

tipo_item_inventario_service = TipoItemInventarioService(TipoItemInventario)
