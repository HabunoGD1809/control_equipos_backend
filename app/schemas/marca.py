import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class MarcaBase(BaseModel):
    """Campos base que definen una marca o fabricante."""
    nombre: str = Field(..., description="Nombre de la marca (Ej: Dell, Microsoft)")

class MarcaCreate(MarcaBase):
    """Schema para crear una nueva marca."""
    pass

class MarcaUpdate(BaseModel):
    """Schema para actualizar parcialmente una marca."""
    nombre: Optional[str] = None
    is_active: Optional[bool] = None

class MarcaRead(MarcaBase):
    """Schema completo para devolver los datos de una marca."""
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
class MarcaSimple(BaseModel):
    """Schema ligero para anidar en equipos, software e inventario."""
    id: uuid.UUID
    nombre: str
    
    model_config = ConfigDict(from_attributes=True)
