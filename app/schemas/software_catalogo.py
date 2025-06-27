import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from .enums import TipoLicenciaSoftwareEnum, MetricaLicenciamientoEnum

# ===============================================================
# Schema Base
# ===============================================================
class SoftwareCatalogoBase(BaseModel):
    """Campos base que definen un producto en el catálogo de software."""
    nombre: str = Field(..., max_length=255, description="Nombre del producto de software")
    version: Optional[str] = Field(None, max_length=50, description="Versión específica (ej: 2023, 11, CC)")
    fabricante: Optional[str] = Field(None, max_length=100, description="Fabricante del software")
    descripcion: Optional[str] = Field(None, description="Descripción detallada del software")
    categoria: Optional[str] = Field(None, max_length=100, description="Categoría (ej: Ofimática, Diseño, SO)")

    tipo_licencia: TipoLicenciaSoftwareEnum = Field(..., description="Tipo de licencia del software")
    metrica_licenciamiento: MetricaLicenciamientoEnum = Field(..., description="Métrica de licenciamiento")

# ===============================================================
# Schema para Creación
# ===============================================================
class SoftwareCatalogoCreate(SoftwareCatalogoBase):
    """Schema utilizado para registrar un nuevo software en el catálogo."""
    pass  # Hereda todos los campos y validaciones.

# ===============================================================
# Schema para Actualización
# ===============================================================
class SoftwareCatalogoUpdate(BaseModel):
    """
    Schema para actualizar un software del catálogo. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    nombre: Optional[str] = Field(None, max_length=255)
    version: Optional[str] = Field(None, max_length=50)
    fabricante: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = None
    categoria: Optional[str] = Field(None, max_length=100)
    tipo_licencia: Optional[TipoLicenciaSoftwareEnum] = None
    metrica_licenciamiento: Optional[MetricaLicenciamientoEnum] = None

# ===============================================================
# Schema Interno DB
# ===============================================================
class SoftwareCatalogoInDBBase(SoftwareCatalogoBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Respuesta API
# ===============================================================
class SoftwareCatalogo(SoftwareCatalogoInDBBase):
    """Schema para devolver al cliente. Expone todos los campos del modelo de BD."""
    pass

# ===============================================================
# Schema Simple (para listas o referencias)
# ===============================================================
class SoftwareCatalogoSimple(BaseModel):
    """Schema simplificado, útil para vistas de lista o referencias en otros objetos."""
    id: uuid.UUID
    nombre: str
    version: Optional[str] = None
    fabricante: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
