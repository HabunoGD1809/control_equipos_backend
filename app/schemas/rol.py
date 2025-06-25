import uuid
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field

# Importar el schema de Permiso para anidarlo en la respuesta
from .permiso import Permiso

# --- Schema Base ---
class RolBase(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=100, description="Nombre clave del rol (ej: admin)")
    descripcion: Optional[str] = Field(None, description="Descripción detallada del rol")

# --- Schema para Creación ---
class RolCreate(RolBase):
    # Al crear/actualizar un rol, podemos querer asignar permisos inmediatamente.
    # Pasamos una lista de IDs de permisos. Esto no está en el modelo Rol directamente,
    # pero lo usaremos en el endpoint/servicio para gestionar la tabla de asociación.
    permiso_ids: List[uuid.UUID] = Field(default_factory=list, description="Lista de IDs de permisos a asignar a este rol")

# --- Schema para Actualización ---
class RolUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=3, max_length=100)
    descripcion: Optional[str] = None
    # Permitir actualizar la lista de permisos también
    permiso_ids: Optional[List[uuid.UUID]] = Field(None, description="Lista completa de IDs de permisos para este rol (reemplaza la existente)")

# --- Schema con datos de la DB ---
class RolInDBBase(RolBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuestas API ---
class Rol(RolInDBBase):
    # Incluimos la lista de objetos Permiso completos en la respuesta
    permisos: List[Permiso] = [] # Por defecto lista vacía
