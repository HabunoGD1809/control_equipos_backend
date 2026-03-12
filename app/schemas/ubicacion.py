import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class UbicacionBase(BaseModel):
    nombre: str = Field(..., description="Nombre de la ubicación (Ej: Almacén Principal)")
    edificio: Optional[str] = Field(None, description="Edificio o sucursal")
    departamento: Optional[str] = Field(None, description="Departamento responsable")

class UbicacionCreate(UbicacionBase):
    pass

class UbicacionUpdate(BaseModel):
    nombre: Optional[str] = None
    edificio: Optional[str] = None
    departamento: Optional[str] = None
    is_active: Optional[bool] = None

class UbicacionRead(UbicacionBase):
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
