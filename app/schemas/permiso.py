import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

# ===============================================================
# Schema Base
# ===============================================================
class PermisoBase(BaseModel):
    """Campos base que definen un permiso en el sistema."""
    nombre: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Nombre clave del permiso (ej: ver_equipos)"
    )
    descripcion: Optional[str] = Field(
        None,
        description="Descripción detallada de lo que este permiso autoriza"
    )

# ===============================================================
# Schema para Creación
# ===============================================================
class PermisoCreate(PermisoBase):
    """Schema utilizado para crear un nuevo permiso."""
    pass  # Hereda todos los campos y validaciones.

# ===============================================================
# Schema para Actualización
# ===============================================================
class PermisoUpdate(BaseModel):
    """
    Schema para actualizar un permiso. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    nombre: Optional[str] = Field(None, min_length=3, max_length=100, description="Nuevo nombre clave del permiso")
    descripcion: Optional[str] = Field(None, description="Nueva descripción del permiso")

# ===============================================================
# Schema Interno DB
# ===============================================================
class PermisoInDBBase(PermisoBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos."""
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Respuesta API
# ===============================================================
class Permiso(PermisoInDBBase):
    """Schema para devolver al cliente. Expone todos los campos del modelo de BD."""
    pass
