import uuid
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field

# --- Schema Base ---
class TipoDocumentoBase(BaseModel):
    nombre: str = Field(..., max_length=100, description="Nombre del tipo de documento (ej: Factura, Manual)")
    descripcion: Optional[str] = Field(None, description="Descripción detallada")
    requiere_verificacion: bool = Field(False, description="¿Este tipo de documento necesita ser verificado?")
    formato_permitido: Optional[List[str]] = Field(None, description="Lista de extensiones permitidas (ej: ['pdf', 'jpg'])")

# --- Schema para Creación ---
class TipoDocumentoCreate(TipoDocumentoBase):
    pass # Coincide con la base

# --- Schema para Actualización ---
class TipoDocumentoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = None
    requiere_verificacion: Optional[bool] = None
    formato_permitido: Optional[List[str]] = None

# --- Schema Interno DB ---
class TipoDocumentoInDBBase(TipoDocumentoBase):
    id: uuid.UUID
    created_at: datetime

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API ---
class TipoDocumento(TipoDocumentoInDBBase):
    # Devuelve todos los campos
    pass
