import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field

# --- Schema Base ---
class TipoMantenimientoBase(BaseModel):
    nombre: str = Field(..., max_length=100, description="Nombre del tipo de mantenimiento (ej: Preventivo Anual)")
    descripcion: Optional[str] = Field(None, description="Descripción detallada")
    periodicidad_dias: Optional[int] = Field(None, gt=0, description="Días entre mantenimientos (si es periódico > 0)") # Mayor que 0
    requiere_documentacion: bool = Field(False, description="¿Es obligatorio adjuntar documento al completar?")
    es_preventivo: bool = Field(False, description="¿Es un mantenimiento de tipo preventivo?")

# --- Schema para Creación ---
class TipoMantenimientoCreate(TipoMantenimientoBase):
    pass # Coincide con la base

# --- Schema para Actualización ---
class TipoMantenimientoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = None
    periodicidad_dias: Optional[int] = Field(None, gt=0) # Mayor que 0
    requiere_documentacion: Optional[bool] = None
    es_preventivo: Optional[bool] = None

# --- Schema Interno DB ---
class TipoMantenimientoInDBBase(TipoMantenimientoBase):
    id: uuid.UUID
    created_at: datetime

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API ---
class TipoMantenimiento(TipoMantenimientoInDBBase):
    # Devuelve todos los campos
    pass
