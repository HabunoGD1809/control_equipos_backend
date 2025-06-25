import uuid
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

# Importar schema simple del tipo de item
from .tipo_item_inventario import TipoItemInventarioSimple

# --- Schema Base ---
class InventarioStockBase(BaseModel):
    tipo_item_id: uuid.UUID = Field(..., description="ID del Tipo de Item en inventario")
    ubicacion: str = Field(default='Almacén Principal', description="Ubicación física del stock")
    lote: Optional[str] = Field(None, max_length=100, description="Identificador de lote (si aplica)")
    fecha_caducidad: Optional[date] = Field(None, description="Fecha de caducidad (si aplica)")
    cantidad_actual: int = Field(..., ge=0, description="Cantidad actual en esta ubicación/lote")
    costo_promedio_ponderado: Optional[Decimal] = Field(None, ge=0, decimal_places=4, description="Costo promedio ponderado (opcional)")

# --- Schema para Actualización ---
class InventarioStockUpdate(BaseModel):
    # Permitir actualizar detalles menores como lote o caducidad
    lote: Optional[str] = Field(None, max_length=100)
    fecha_caducidad: Optional[date] = None
    # La cantidad y el costo se actualizan mediante movimientos, no directamente aquí.

# --- Schema Interno DB ---
class InventarioStockInDBBase(InventarioStockBase):
    id: uuid.UUID
    ultima_actualizacion: datetime

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API ---
class InventarioStock(InventarioStockInDBBase):
    tipo_item: TipoItemInventarioSimple

# --- Schema para Stock Total ---
class InventarioStockTotal(BaseModel):
    tipo_item_id: uuid.UUID
    cantidad_total: int

    model_config = {
        "from_attributes": True
    }

# --- NUEVO: Schema Simple para Stock ---
class InventarioStockSimple(BaseModel):
    """Schema simple para representar un registro de stock en contextos anidados."""
    id: uuid.UUID
    ubicacion: str
    lote: Optional[str] = None
    cantidad_actual: int # Incluir cantidad actual puede ser útil

    model_config = {
        "from_attributes": True
    }
# --- FIN NUEVO SCHEMA ---
