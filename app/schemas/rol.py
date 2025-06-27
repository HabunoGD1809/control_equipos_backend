import uuid
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# schema de Permiso para anidarlo
from .permiso import Permiso

# --- Schema Base ---
class RolBase(BaseModel):
    """Campos base que definen un rol."""
    nombre: str = Field(..., min_length=3, max_length=100, description="Nombre clave del rol (ej: admin)")
    descripcion: Optional[str] = Field(None, description="Descripción detallada del rol")

# --- Schema para Creación ---
class RolCreate(RolBase):
    """
    Schema para crear un nuevo rol. Se puede proporcionar una lista
    de IDs de permisos para asignarlos en el mismo paso.
    """
    permiso_ids: List[uuid.UUID] = Field(default_factory=list, description="Lista de IDs de permisos a asignar a este rol")

# --- Schema para Actualización ---
class RolUpdate(BaseModel):
    """
    Schema para actualizar un rol. Todos los campos son opcionales.
    Permite cambiar el nombre, la descripción y la lista completa de permisos.
    """
    nombre: Optional[str] = Field(None, min_length=3, max_length=100)
    descripcion: Optional[str] = None
    permiso_ids: Optional[List[uuid.UUID]] = Field(None, description="Lista completa de IDs de permisos para este rol (reemplaza la existente)")

# --- Schema Interno DB ---
class RolInDBBase(RolBase):
    """Schema que refleja el modelo de la base de datos, incluyendo metadatos."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Schema para Respuestas API ---
class Rol(RolInDBBase):
    """
    Schema para devolver al cliente. Incluye la lista completa de objetos
    Permiso anidados para una respuesta rica en información.
    """
    permisos: List[Permiso] = Field(default_factory=list)
