import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, ConfigDict

from .departamento import DepartamentoSimple

# --- Schema Base ---
class EmpleadoBase(BaseModel):
    nombre_completo: str = Field(..., min_length=3, max_length=255, description="Nombre completo del empleado")
    cargo: Optional[str] = Field(None, max_length=150, description="Puesto o cargo en la empresa")
    email_corporativo: Optional[EmailStr] = Field(None, description="Correo electrónico del empleado")
    departamento_id: Optional[uuid.UUID] = Field(None, description="Departamento al que pertenece")
    is_active: bool = Field(True, description="Si el empleado está activo en la empresa")

# --- Schema para Creación ---
class EmpleadoCreate(EmpleadoBase):
    pass

# --- Schema para Actualización ---
class EmpleadoUpdate(BaseModel):
    nombre_completo: Optional[str] = Field(None, min_length=3, max_length=255)
    cargo: Optional[str] = Field(None, max_length=150)
    email_corporativo: Optional[EmailStr] = None
    departamento_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None

# --- Schema Interno DB y Salida ---
class EmpleadoInDBBase(EmpleadoBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class EmpleadoRead(EmpleadoInDBBase):
    departamento_rel: Optional[DepartamentoSimple] = None

class EmpleadoSimple(BaseModel):
    """Schema ligero para dropdowns y selects en el frontend"""
    id: uuid.UUID
    nombre_completo: str
    cargo: Optional[str] = None
    email_corporativo: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
