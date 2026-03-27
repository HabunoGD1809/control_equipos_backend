import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from .departamento import DepartamentoSimple

class UbicacionBase(BaseModel):
    """Campos base que definen una ubicación en el sistema."""
    nombre: str = Field(..., description="Nombre de la ubicación (Ej: Almacén Principal)")
    edificio: Optional[str] = Field(None, description="Edificio o sucursal")
    departamento_id: Optional[uuid.UUID] = Field(None, description="ID del departamento responsable")
class UbicacionCreate(UbicacionBase):
    """Schema para crear una nueva ubicación."""
    pass

class UbicacionUpdate(BaseModel):
    """Schema para actualizar parcialmente una ubicación existente."""
    nombre: Optional[str] = None
    edificio: Optional[str] = None
    departamento_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None

class UbicacionRead(UbicacionBase):
    """Schema completo para devolver los datos de una ubicación."""
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    departamento_rel: Optional[DepartamentoSimple] = None
    
    model_config = ConfigDict(from_attributes=True)
    
class UbicacionSimple(BaseModel):
    """Schema ligero para anidar ubicaciones dentro de otras respuestas."""
    id: uuid.UUID
    nombre: str
    
    model_config = ConfigDict(from_attributes=True)
