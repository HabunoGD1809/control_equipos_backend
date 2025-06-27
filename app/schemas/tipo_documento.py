import uuid
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

# --- Schema Base ---
class TipoDocumentoBase(BaseModel):
    """Campos base que definen un tipo de documento."""
    nombre: str = Field(
        ...,
        max_length=100,
        description="Nombre del tipo de documento (ej: Factura, Manual de Usuario)"
    )
    descripcion: Optional[str] = Field(
        None,
        description="Descripción detallada del propósito de este tipo de documento"
    )
    requiere_verificacion: bool = Field(
        False,
        description="Indica si los documentos de este tipo deben pasar por un proceso de verificación"
    )
    formato_permitido: Optional[List[str]] = Field(
        None,
        description="Lista de extensiones de archivo permitidas (ej: ['pdf', 'jpg'])"
    )

# --- Schema para Creación ---
class TipoDocumentoCreate(TipoDocumentoBase):
    """Schema utilizado para crear un nuevo tipo de documento."""
    pass

# --- Schema para Actualización ---
class TipoDocumentoUpdate(BaseModel):
    """
    Schema para actualizar un tipo de documento. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    nombre: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = None
    requiere_verificacion: Optional[bool] = None
    formato_permitido: Optional[List[str]] = None

# --- Schema Interno DB ---
class TipoDocumentoInDBBase(TipoDocumentoBase):
    """Schema que refleja el modelo completo de la base de datos, incluyendo metadatos."""
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Schema para Respuesta API ---
class TipoDocumento(TipoDocumentoInDBBase):
    """Schema para devolver al cliente. Expone todos los campos del modelo de BD."""
    pass
