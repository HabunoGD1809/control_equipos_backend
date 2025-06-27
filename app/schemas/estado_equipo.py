import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

# ===============================================================
# Schema Base
# ===============================================================
class EstadoEquipoBase(BaseModel):
    """Campos base que definen un estado de equipo."""
    nombre: str = Field(..., max_length=100, description="Nombre del estado (ej: Disponible, En Uso)")
    descripcion: Optional[str] = Field(None, description="Descripción detallada del estado")
    permite_movimientos: bool = Field(True, description="Indica si los equipos en este estado pueden moverse o ser asignados")
    requiere_autorizacion: bool = Field(False, description="Indica si se requiere autorización para mover un equipo desde este estado")
    es_estado_final: bool = Field(False, description="Indica si es un estado de fin de ciclo de vida (ej: Dado de Baja)")
    color_hex: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$", description="Color hexadecimal para la interfaz de usuario (ej: #4CAF50)")
    icono: Optional[str] = Field(None, max_length=50, description="Nombre o clase de un icono para la interfaz de usuario (ej: fa-check)")

# ===============================================================
# Schema para Creación
# ===============================================================
class EstadoEquipoCreate(EstadoEquipoBase):
    """Schema utilizado para crear un nuevo estado de equipo."""
    pass

# ===============================================================
# Schema para Actualización
# ===============================================================
class EstadoEquipoUpdate(BaseModel):
    """
    Schema para actualizar un estado de equipo. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    nombre: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = None
    permite_movimientos: Optional[bool] = None
    requiere_autorizacion: Optional[bool] = None
    es_estado_final: Optional[bool] = None
    color_hex: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    icono: Optional[str] = Field(None, max_length=50)

# ===============================================================
# Schema Interno DB
# ===============================================================
class EstadoEquipoInDBBase(EstadoEquipoBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos."""
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Respuesta API
# ===============================================================
class EstadoEquipo(EstadoEquipoInDBBase):
    """Schema para devolver al cliente. Expone todos los campos del modelo de BD."""
    pass

# ===============================================================
# Schema Simple (para referencias)
# ===============================================================
class EstadoEquipoSimple(BaseModel):
    """Schema simplificado, útil para mostrar el estado dentro del schema de Equipo."""
    id: uuid.UUID
    nombre: str
    color_hex: Optional[str] = None
    icono: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
