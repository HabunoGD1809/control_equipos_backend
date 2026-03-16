import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from .proveedor import ProveedorSimple

class TecnicoBase(BaseModel):
    nombre_completo: str = Field(..., max_length=255, description="Nombre del técnico o empresa")
    es_externo: bool = Field(default=False, description="¿Es un contratista externo?")
    proveedor_id: Optional[uuid.UUID] = Field(None, description="ID del proveedor (si es externo)")
    telefono_contacto: Optional[str] = Field(None, max_length=50)
    email_contacto: Optional[str] = Field(None, max_length=100)
    is_active: bool = Field(default=True)

class TecnicoCreate(TecnicoBase):
    pass

class TecnicoUpdate(BaseModel):
    nombre_completo: Optional[str] = Field(None, max_length=255)
    es_externo: Optional[bool] = None
    proveedor_id: Optional[uuid.UUID] = None
    telefono_contacto: Optional[str] = Field(None, max_length=50)
    email_contacto: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None

class TecnicoInDBBase(TecnicoBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class Tecnico(TecnicoInDBBase):
    """Schema para devolver un técnico con la info de su proveedor si la tiene."""
    proveedor: Optional[ProveedorSimple] = None

class TecnicoSimple(BaseModel):
    """Schema ligero para anidar dentro de Mantenimiento."""
    id: uuid.UUID
    nombre_completo: str
    es_externo: bool
    model_config = ConfigDict(from_attributes=True)
