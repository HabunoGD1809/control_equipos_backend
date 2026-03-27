import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class DepartamentoBase(BaseModel):
    """Campos base que definen un departamento."""
    nombre: str = Field(..., description="Nombre del departamento o unidad (Ej: Recursos Humanos)")
    descripcion: Optional[str] = Field(None, description="Descripción opcional")

class DepartamentoCreate(DepartamentoBase):
    """Schema para crear un nuevo departamento."""
    pass

class DepartamentoUpdate(BaseModel):
    """Schema para actualizar parcialmente un departamento."""
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    is_active: Optional[bool] = None

class DepartamentoRead(DepartamentoBase):
    """Schema completo para devolver los datos de un departamento."""
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
class DepartamentoSimple(BaseModel):
    """Schema ligero para anidar en ubicaciones o usuarios."""
    id: uuid.UUID
    nombre: str
    
    model_config = ConfigDict(from_attributes=True)
