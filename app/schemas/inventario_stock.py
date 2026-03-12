import uuid
from typing import Optional, Any
from datetime import datetime, date
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict, model_validator

from .tipo_item_inventario import TipoItemInventarioSimple
from .ubicacion import UbicacionRead # Asumiendo que tienes este schema

# ===============================================================
# Schema Base
# ===============================================================
class InventarioStockBase(BaseModel):
    tipo_item_id: uuid.UUID = Field(..., description="ID del Tipo de Item en inventario")
    ubicacion_id: uuid.UUID = Field(..., description="ID de la Ubicación física del stock")
    lote: Optional[str] = Field(None, max_length=100)
    fecha_caducidad: Optional[date] = Field(None)
    cantidad_actual: int = Field(..., ge=0)
    costo_promedio_ponderado: Optional[Decimal] = Field(None, ge=0, decimal_places=4)

class InventarioStockUpdate(BaseModel):
    lote: Optional[str] = Field(None, max_length=100)
    fecha_caducidad: Optional[date] = None

class InventarioStockInDBBase(InventarioStockBase):
    id: uuid.UUID
    ultima_actualizacion: datetime
    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Respuesta API
# ===============================================================
class InventarioStock(InventarioStockInDBBase):
    tipo_item: TipoItemInventarioSimple
    
    # FIX: Campo virtual para no romper el Frontend
    ubicacion: str = "" 

    @model_validator(mode='before')
    @classmethod
    def extract_ubicacion_nombre(cls, data: Any) -> Any:
        if hasattr(data, 'ubicacion_fisica') and data.ubicacion_fisica:
            data.ubicacion = data.ubicacion_fisica.nombre
        # Si data es un dict
        elif isinstance(data, dict) and 'ubicacion_fisica' in data:
             data['ubicacion'] = data['ubicacion_fisica']['nombre']
        return data

class InventarioStockTotal(BaseModel):
    tipo_item_id: uuid.UUID
    cantidad_total: int
    model_config = ConfigDict(from_attributes=True)

class InventarioStockSimple(BaseModel):
    id: uuid.UUID
    ubicacion_id: uuid.UUID
    lote: Optional[str] = None
    cantidad_actual: int
    model_config = ConfigDict(from_attributes=True)
