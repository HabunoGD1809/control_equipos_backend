import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

# --- Schema Base ---
class TipoMantenimientoBase(BaseModel):
    """Campos base que definen un tipo de mantenimiento."""
    nombre: str = Field(
        ...,
        max_length=100,
        description="Nombre del tipo de mantenimiento (ej: Preventivo Anual)"
    )
    descripcion: Optional[str] = Field(None, description="Descripción detallada del propósito de este tipo de mantenimiento")
    periodicidad_dias: Optional[int] = Field(
        None,
        gt=0,
        description="Días entre mantenimientos. Solo aplica si es un mantenimiento periódico."
    )
    requiere_documentacion: bool = Field(
        False,
        description="Indica si es obligatorio adjuntar un documento al completar un mantenimiento de este tipo"
    )
    es_preventivo: bool = Field(
        False,
        description="Marca si este tipo de mantenimiento es preventivo (vs. correctivo)"
    )

# --- Schema para Creación ---
class TipoMantenimientoCreate(TipoMantenimientoBase):
    """Schema utilizado para crear un nuevo tipo de mantenimiento."""
    pass

# --- Schema para Actualización ---
class TipoMantenimientoUpdate(BaseModel):
    """
    Schema para actualizar un tipo de mantenimiento. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    nombre: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = None
    periodicidad_dias: Optional[int] = Field(None, gt=0)
    requiere_documentacion: Optional[bool] = None
    es_preventivo: Optional[bool] = None

# --- Schema Interno DB ---
class TipoMantenimientoInDBBase(TipoMantenimientoBase):
    """Schema que refleja el modelo completo de la base de datos, incluyendo metadatos."""
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Schema para Respuesta API ---
class TipoMantenimiento(TipoMantenimientoInDBBase):
    """Schema para devolver al cliente. Expone todos los campos del modelo de BD."""
    pass
