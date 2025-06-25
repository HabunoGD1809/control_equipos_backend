import uuid
from typing import Optional, TYPE_CHECKING
from datetime import datetime

from pydantic import BaseModel, Field

# Usa TYPE_CHECKING para importar solo durante el chequeo de tipos
# para evitar importaciones circulares con app.schemas.equipo
if TYPE_CHECKING:
    from .equipo import EquipoSimple

# --- Schema Base de la Relación (Campos que definen la relación en la DB) ---
class EquipoComponenteBase(BaseModel):
    """
    Schema base con todos los campos que definen una relación equipo-componente.
    Este es el schema que el método `create` del servicio espera en `obj_in`
    (o un schema que herede de este, como EquipoComponenteCreate más abajo).
    """
    equipo_padre_id: uuid.UUID = Field(..., description="ID del equipo principal o ensamblaje")
    equipo_componente_id: uuid.UUID = Field(..., description="ID del equipo que actúa como componente")
    tipo_relacion: str = Field(default='componente', max_length=50, description="Tipo de vínculo (componente, conectado_a, etc.)")
    cantidad: int = Field(default=1, gt=0, description="Cantidad de este componente (ej: 2 módulos RAM)")
    notas: Optional[str] = Field(None, description="Observaciones sobre la relación")

# --- Schema que el SERVICIO EquipoComponenteService.create espera en su argumento obj_in ---
class EquipoComponenteCreate(EquipoComponenteBase):
    """
    Este schema se utiliza para pasar los datos al método `create` del servicio.
    Hereda todos los campos de EquipoComponenteBase.
    En tu servicio `equipo_componente.py`, el método `create` está tipado con:
    `obj_in: EquipoComponenteCreate` y este es el schema al que se refiere.
    """
    pass # Hereda todos los campos de EquipoComponenteBase

# --- Schema para el CUERPO (BODY) de la solicitud POST /equipos/{equipo_id}/componentes ---
class EquipoComponenteBodyCreate(BaseModel): 
    """
    Este schema define lo que se espera en el CUERPO JSON de la solicitud POST.
    NO incluye `equipo_padre_id` porque ese ID se obtiene del path de la URL.
    """
    equipo_componente_id: uuid.UUID = Field(..., description="ID del equipo que actúa como componente y se va a añadir.")
    # tipo_relacion se toma de EquipoComponenteBase si también lo quieres en el body,
    # o puedes definirlo aquí si quieres que sea diferente. Por simplicidad, lo incluimos.
    tipo_relacion: str = Field(default='componente', max_length=50, description="Tipo de vínculo (ej: 'componente', 'conectado_a')")
    cantidad: int = Field(default=1, gt=0, description="Cantidad del componente a añadir.")
    notas: Optional[str] = Field(None, description="Notas adicionales sobre esta relación componente-padre.")

# --- Schema para Actualización de la Relación (PUT a /equipos/componentes/{relacion_id}) ---
class EquipoComponenteUpdate(BaseModel):
    tipo_relacion: Optional[str] = Field(None, max_length=50)
    cantidad: Optional[int] = Field(None, gt=0) # gt=0 asegura que si se actualiza, sea positivo
    notas: Optional[str] = None

# --- Schema Interno DB y de Respuesta (para la tabla asociativa 'equipo_componentes') ---
class EquipoComponenteInDBBase(EquipoComponenteBase): # Hereda los campos de la relación
    id: uuid.UUID # ID propio de la relación en la tabla asociativa
    created_at: datetime
    # updated_at: datetime # Si tu tabla asociativa tiene updated_at

    model_config = {
        "from_attributes": True # Para Pydantic V2
    }

class EquipoComponente(EquipoComponenteInDBBase):
    """Schema de respuesta completo para una relación equipo-componente."""
    # Anidar información simple del equipo padre y componente para la respuesta
    equipo_padre: Optional["EquipoSimple"] = None
    equipo_componente: Optional["EquipoSimple"] = None

# --- Schemas específicos para listar componentes o padres ---
class ComponenteInfo(BaseModel):
    """Información de un componente asociado a un equipo padre."""
    id_relacion: uuid.UUID = Field(..., alias="id") # ID de la tabla EquipoComponente
    componente: "EquipoSimple" # Detalles del equipo que es el componente
    tipo_relacion: str
    cantidad: int
    notas: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True, # Permite que 'id' en el modelo ORM mapee a 'id_relacion'
    }

class PadreInfo(BaseModel):
    """Información de un equipo padre al que un equipo está asociado como componente."""
    id_relacion: uuid.UUID = Field(..., alias="id") # ID de la tabla EquipoComponente
    padre: "EquipoSimple" # Detalles del equipo que es el padre
    tipo_relacion: str
    cantidad_en_padre: int = Field(..., alias="cantidad") # Cantidad de este componente en ese padre
    notas: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }
