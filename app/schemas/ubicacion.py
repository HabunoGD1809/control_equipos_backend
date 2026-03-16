import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class UbicacionBase(BaseModel):
    """Campos base que definen una ubicación en el sistema."""
    nombre: str = Field(..., description="Nombre de la ubicación (Ej: Almacén Principal)")
    edificio: Optional[str] = Field(None, description="Edificio o sucursal")
    departamento: Optional[str] = Field(None, description="Departamento responsable")

class UbicacionCreate(UbicacionBase):
    """Schema para crear una nueva ubicación."""
    pass

class UbicacionUpdate(BaseModel):
    """Schema para actualizar parcialmente una ubicación existente."""
    nombre: Optional[str] = None
    edificio: Optional[str] = None
    departamento: Optional[str] = None
    is_active: Optional[bool] = None

class UbicacionRead(UbicacionBase):
    """Schema completo para devolver los datos de una ubicación."""
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
class UbicacionSimple(BaseModel):
    """Schema ligero para anidar ubicaciones dentro de otras respuestas."""
    id: uuid.UUID
    nombre: str
    
    model_config = ConfigDict(from_attributes=True)
