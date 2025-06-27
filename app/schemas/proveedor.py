import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, ConfigDict

# --- Schema Base ---
class ProveedorBase(BaseModel):
    """Campos base que definen un proveedor."""
    nombre: str = Field(..., min_length=2, max_length=255, description="Nombre completo o razón social del proveedor")
    descripcion: Optional[str] = Field(None, description="Descripción adicional sobre los productos o servicios que ofrece el proveedor")
    contacto: Optional[str] = Field(None, description="Información de contacto general (email, teléfono, persona de contacto)")
    direccion: Optional[str] = Field(None, description="Dirección física del proveedor")
    sitio_web: Optional[HttpUrl] = Field(None, description="URL del sitio web del proveedor (debe ser una URL válida)")
    rnc: Optional[str] = Field(None, max_length=50, description="Registro Nacional de Contribuyente u otro identificador fiscal")

# --- Schema para Creación ---
class ProveedorCreate(ProveedorBase):
    """Schema utilizado para registrar un nuevo proveedor."""
    pass

# --- Schema para Actualización ---
class ProveedorUpdate(BaseModel):
    """
    Schema para actualizar un proveedor. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    nombre: Optional[str] = Field(None, min_length=2, max_length=255)
    descripcion: Optional[str] = None
    contacto: Optional[str] = None
    direccion: Optional[str] = None
    sitio_web: Optional[HttpUrl] = None
    rnc: Optional[str] = Field(None, max_length=50)

# --- Schema Interno DB ---
class ProveedorInDBBase(ProveedorBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Schema para Respuesta API ---
class Proveedor(ProveedorInDBBase):
    """Schema para devolver al cliente. Expone todos los campos del modelo de BD."""
    pass

# --- Schema Simple ---
class ProveedorSimple(BaseModel):
    """Schema simplificado, útil para referencias en otros objetos como Licencias o Equipos."""
    id: uuid.UUID
    nombre: str

    model_config = ConfigDict(from_attributes=True)
