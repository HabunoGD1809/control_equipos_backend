import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

# --- Schema Base ---
class ProveedorBase(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=255, description="Nombre completo del proveedor")
    descripcion: Optional[str] = Field(None, description="Descripción adicional del proveedor")
    contacto: Optional[str] = Field(None, description="Información de contacto (email, teléfono, persona)")
    direccion: Optional[str] = Field(None, description="Dirección física del proveedor")
    sitio_web: Optional[HttpUrl] = Field(None, description="URL del sitio web del proveedor") # Pydantic valida URL
    rnc: Optional[str] = Field(None, max_length=50, description="Registro Nacional de Contribuyente (o similar)")

# --- Schema para Creación ---
class ProveedorCreate(ProveedorBase):
    pass # Coincide con la base

# --- Schema para Actualización ---
class ProveedorUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=255)
    descripcion: Optional[str] = None
    contacto: Optional[str] = None
    direccion: Optional[str] = None
    sitio_web: Optional[HttpUrl] = None
    rnc: Optional[str] = Field(None, max_length=50)

# --- Schema Interno DB ---
class ProveedorInDBBase(ProveedorBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API ---
class Proveedor(ProveedorInDBBase):
    # Devuelve todos los campos definidos en InDBBase
    pass

# --- Schema Simple ---
# Para referencias en otros schemas sin incluir toda la info
class ProveedorSimple(BaseModel):
    id: uuid.UUID
    nombre: str

    model_config = {
       "from_attributes": True
    }
