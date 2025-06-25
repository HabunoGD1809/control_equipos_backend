import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field

# --- Schema Base ---
class EstadoEquipoBase(BaseModel):
    nombre: str = Field(..., max_length=100, description="Nombre del estado (ej: Disponible, En Uso)")
    descripcion: Optional[str] = Field(None, description="Descripción detallada del estado")
    permite_movimientos: bool = Field(True, description="¿Equipos en este estado pueden moverse/asignarse?")
    requiere_autorizacion: bool = Field(False, description="¿Se requiere autorización para mover desde este estado?")
    es_estado_final: bool = Field(False, description="¿Es un estado de fin de ciclo de vida (ej: Baja)?")
    color_hex: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$", description="Color hexadecimal para UI (ej: #4CAF50)")
    icono: Optional[str] = Field(None, max_length=50, description="Nombre/Clase de un icono para UI (ej: fa-check)")

# --- Schema para Creación ---
class EstadoEquipoCreate(EstadoEquipoBase):
    pass # Coincide con la base

# --- Schema para Actualización ---
class EstadoEquipoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = None
    permite_movimientos: Optional[bool] = None
    requiere_autorizacion: Optional[bool] = None
    es_estado_final: Optional[bool] = None
    color_hex: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    icono: Optional[str] = Field(None, max_length=50)

# --- Schema Interno DB ---
class EstadoEquipoInDBBase(EstadoEquipoBase):
    id: uuid.UUID
    created_at: datetime

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API ---
class EstadoEquipo(EstadoEquipoInDBBase):
    # Devuelve todos los campos
    pass

# --- NUEVO: Schema Simple ---
class EstadoEquipoSimple(BaseModel):
    id: uuid.UUID
    nombre: str
    # Incluir otros campos si son útiles en la vista de Equipo
    color_hex: Optional[str] = None
    icono: Optional[str] = None

    model_config = { "from_attributes": True }
# --- FIN NUEVO ---
