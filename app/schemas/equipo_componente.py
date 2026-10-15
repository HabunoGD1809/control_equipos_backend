import uuid
from typing import Optional, TYPE_CHECKING
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, AliasChoices

from .enums import TipoRelacionComponenteEnum

if TYPE_CHECKING:
    from .equipo import EquipoSimple

# ===============================================================
# Schema Base de la Relación
# ===============================================================
class EquipoComponenteBase(BaseModel):
    """Campos base que definen una relación entre un equipo padre y un componente."""
    equipo_padre_id: uuid.UUID = Field(..., description="ID del equipo principal o ensamblaje")
    equipo_componente_id: uuid.UUID = Field(..., description="ID del equipo que actúa como componente")
    tipo_relacion: TipoRelacionComponenteEnum = Field(default=TipoRelacionComponenteEnum.COMPONENTE, description="Tipo de vínculo entre los equipos")
    cantidad: int = Field(default=1, ge=1, le=1, description="Cada equipo con número de serie representa una unidad.")
    notas: Optional[str] = Field(None, description="Observaciones sobre esta relación específica")

# ===============================================================
# Schema para Creación (usado por el servicio)
# ===============================================================
class EquipoComponenteCreate(EquipoComponenteBase):
    """Schema para pasar los datos al método de creación del servicio."""
    pass

# ===============================================================
# Schema para el Cuerpo de la Solicitud POST
# ===============================================================
class EquipoComponenteBodyCreate(BaseModel):
    """
    Define el cuerpo JSON para la solicitud POST /equipos/{equipo_id}/componentes.
    No incluye equipo_padre_id, ya que se toma del path de la URL.
    """
    equipo_componente_id: uuid.UUID = Field(..., description="ID del equipo componente a añadir")
    tipo_relacion: TipoRelacionComponenteEnum = Field(default=TipoRelacionComponenteEnum.COMPONENTE, description="Tipo de vínculo entre los equipos")
    cantidad: int = Field(default=1, ge=1, le=1, description="Cada equipo con número de serie representa una unidad.")
    notas: Optional[str] = Field(None, description="Notas adicionales sobre esta relación")

# ===============================================================
# Schema para Actualización de la Relación
# ===============================================================
class EquipoComponenteUpdate(BaseModel):
    """
    Schema para actualizar una relación existente. Todos los campos son opcionales.
    """
    tipo_relacion: Optional[TipoRelacionComponenteEnum] = None
    cantidad: Optional[int] = Field(None, ge=1, le=1, description="Cada equipo con número de serie representa una unidad.")
    notas: Optional[str] = None

# ===============================================================
# Schema Interno DB y de Respuesta
# ===============================================================
class EquipoComponenteInDBBase(EquipoComponenteBase):
    """Schema que refleja el modelo de la BD, incluyendo el ID de la relación."""
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EquipoComponente(EquipoComponenteInDBBase):
    """Schema de respuesta completo que anida la información del padre y del componente."""
    equipo_padre: Optional["EquipoSimple"] = None
    equipo_componente: Optional["EquipoSimple"] = None

# ===============================================================
# Schemas Específicos para Listas
# ===============================================================
class ComponenteInfo(BaseModel):
    """Schema para mostrar la información de un componente asociado a un equipo padre."""
    id_relacion: uuid.UUID = Field(..., validation_alias=AliasChoices("id_relacion", "id"), serialization_alias="id")
    componente: "EquipoSimple" = Field(validation_alias=AliasChoices("componente", "equipo_componente"))
    tipo_relacion: TipoRelacionComponenteEnum
    cantidad: int
    notas: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PadreInfo(BaseModel):
    """Schema para mostrar la información de un equipo padre al que este equipo pertenece."""
    id_relacion: uuid.UUID = Field(..., validation_alias=AliasChoices("id_relacion", "id"), serialization_alias="id")
    padre: "EquipoSimple" = Field(validation_alias=AliasChoices("padre", "equipo_padre"))
    tipo_relacion: TipoRelacionComponenteEnum
    cantidad_en_padre: int = Field(..., validation_alias=AliasChoices("cantidad_en_padre", "cantidad"), serialization_alias="cantidad")
    notas: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
