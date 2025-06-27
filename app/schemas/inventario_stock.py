import uuid
from typing import Optional
from datetime import datetime, date
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict

from .tipo_item_inventario import TipoItemInventarioSimple

# ===============================================================
# Schema Base
# ===============================================================
class InventarioStockBase(BaseModel):
    """Campos base que definen una instancia de stock en una ubicación."""
    tipo_item_id: uuid.UUID = Field(..., description="ID del Tipo de Item en inventario")
    ubicacion: str = Field(default='Almacén Principal', description="Ubicación física del stock")
    lote: Optional[str] = Field(None, max_length=100, description="Identificador de lote para trazabilidad, si aplica")
    fecha_caducidad: Optional[date] = Field(None, description="Fecha de caducidad para ítems perecederos")
    cantidad_actual: int = Field(..., ge=0, description="Cantidad actual de este ítem en esta ubicación/lote")
    costo_promedio_ponderado: Optional[Decimal] = Field(None, ge=0, decimal_places=4, description="Costo promedio ponderado para valoración de inventario")

# ===============================================================
# Schema para Actualización
# ===============================================================
class InventarioStockUpdate(BaseModel):
    """
    Schema para actualizar detalles de un registro de stock.
    Nota: La cantidad y el costo se actualizan mediante movimientos, no directamente.
    """
    lote: Optional[str] = Field(None, max_length=100)
    fecha_caducidad: Optional[date] = None

# ===============================================================
# Schema Interno DB
# ===============================================================
class InventarioStockInDBBase(InventarioStockBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos."""
    id: uuid.UUID
    ultima_actualizacion: datetime

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Respuesta API
# ===============================================================
class InventarioStock(InventarioStockInDBBase):
    """
    Schema para devolver al cliente. Incluye el objeto anidado del tipo de ítem.
    """
    tipo_item: TipoItemInventarioSimple

# ===============================================================
# Schema para Agregaciones (ej. Stock Total)
# ===============================================================
class InventarioStockTotal(BaseModel):
    """Schema para representar la cantidad total de un ítem en todas las ubicaciones."""
    tipo_item_id: uuid.UUID
    cantidad_total: int

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema Simple (para referencias)
# ===============================================================
class InventarioStockSimple(BaseModel):
    """Schema simplificado para representar un registro de stock en contextos anidados."""
    id: uuid.UUID
    ubicacion: str
    lote: Optional[str] = None
    cantidad_actual: int

    model_config = ConfigDict(from_attributes=True)
