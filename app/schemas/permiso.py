import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field

# --- Schema Base ---
# Campos compartidos / Campos para creación básica si no hay 'Create' específico
class PermisoBase(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=100, description="Nombre clave del permiso (ej: ver_equipos)")
    descripcion: Optional[str] = Field(None, description="Descripción detallada del permiso")

# --- Schema para Creación ---
# Hereda de Base y añade campos específicos para la creación (si los hubiera)
class PermisoCreate(PermisoBase):
    # En este caso, coincide con PermisoBase
    pass

# --- Schema para Actualización ---
# Todos los campos son opcionales para permitir actualizaciones parciales (PATCH)
class PermisoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=3, max_length=100, description="Nuevo nombre clave del permiso")
    descripcion: Optional[str] = Field(None, description="Nueva descripción del permiso")

# --- Schema con datos de la DB ---
# Hereda de Base y añade campos que están en la DB pero no se envían en creación/update
# como id y created_at. Útil como base para el schema de respuesta.
class PermisoInDBBase(PermisoBase):
    id: uuid.UUID
    created_at: datetime

    # Configuración para Pydantic v2 (sustituye a orm_mode)
    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuestas API ---
# Hereda de InDBBase. Define exactamente qué se devuelve al cliente.
# Puede omitir campos internos o sensibles si fuera necesario.
class Permiso(PermisoInDBBase):
    # En este caso, coincide con PermisoInDBBase
    pass
