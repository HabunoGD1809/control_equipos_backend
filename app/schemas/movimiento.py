import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from .enums import TipoMovimientoEquipoEnum, EstadoMovimientoEquipoEnum
from .equipo import EquipoSimple
from .usuario import UsuarioSimple

# --- Schema Base ---
class MovimientoBase(BaseModel):
    """Campos base que definen un movimiento de equipo."""
    equipo_id: uuid.UUID = Field(..., description="ID del equipo que se mueve")
    tipo_movimiento: TipoMovimientoEquipoEnum = Field(..., description="Tipo de movimiento realizado.")
    fecha_prevista_retorno: Optional[datetime] = Field(None, description="Fecha prevista de retorno (para Salida Temporal)")
    origen: Optional[str] = Field(None, description="Ubicación/Usuario origen")
    destino: Optional[str] = Field(None, description="Ubicación/Usuario destino")
    proposito: Optional[str] = Field(None, description="Motivo o propósito del movimiento")
    recibido_por: Optional[str] = Field(None, description="Nombre de la persona que recibe físicamente (si aplica)")
    observaciones: Optional[str] = Field(None, description="Notas u observaciones adicionales")

# --- Schema para Creación ---
class MovimientoCreate(MovimientoBase):
    """Schema utilizado para registrar un nuevo movimiento de equipo."""
    pass

# --- Schema para Actualización ---
class MovimientoUpdate(BaseModel):
    """Schema para actualizar campos permitidos de un movimiento existente."""
    fecha_retorno: Optional[datetime] = None
    recibido_por: Optional[str] = None
    observaciones: Optional[str] = None

# --- Schema Interno DB ---
class MovimientoInDBBase(MovimientoBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos y FKs."""
    id: uuid.UUID
    usuario_id: Optional[uuid.UUID]
    autorizado_por: Optional[uuid.UUID]
    fecha_hora: datetime
    fecha_retorno: Optional[datetime]
    estado: EstadoMovimientoEquipoEnum
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Schema para Respuesta API ---
class Movimiento(MovimientoInDBBase):
    """Schema para devolver al cliente, con información anidada."""
    equipo: EquipoSimple
    usuario_registrador: Optional[UsuarioSimple] = None
    usuario_autorizador: Optional[UsuarioSimple] = None
