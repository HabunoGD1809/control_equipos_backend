import uuid
from typing import Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, computed_field

from .enums import TipoMovimientoEquipoEnum, EstadoMovimientoEquipoEnum
from .equipo import EquipoSimple
from .usuario import UsuarioSimple
from .empleado import EmpleadoSimple

# --- Schema Base ---
class MovimientoBase(BaseModel):
    """Campos base que definen un movimiento de equipo."""
    equipo_id: uuid.UUID = Field(..., description="ID del equipo que se mueve")
    tipo_movimiento: TipoMovimientoEquipoEnum = Field(..., description="Tipo de movimiento realizado.")
    fecha_prevista_retorno: Optional[datetime] = Field(None, description="Fecha prevista de retorno (para Salida Temporal)")
    ubicacion_origen_id: Optional[uuid.UUID] = Field(None, description="ID de la ubicación origen")
    ubicacion_destino_id: Optional[uuid.UUID] = Field(None, description="ID de la ubicación destino")
    proposito: Optional[str] = Field(None, description="Motivo o propósito del movimiento")
    empleado_destino_id: Optional[uuid.UUID] = Field(None, description="ID del Empleado (Custodio) al que se le asigna el equipo")
    recibido_por: Optional[str] = Field(None, description="Nombre en texto libre solo para recepciones externas")
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

# --- Schema para Cambio de Estado (Máquina de Estados) ---
class MovimientoEstadoUpdate(BaseModel):
    """Schema específico para autorizar, rechazar o confirmar recepción de un movimiento."""
    estado: EstadoMovimientoEquipoEnum = Field(..., description="El nuevo estado del movimiento")
    observaciones: Optional[str] = Field(None, description="Justificación de la decisión")

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
    empleado_destino: Optional[EmpleadoSimple] = None
    
    ubicacion_origen: Optional[Any] = Field(default=None, exclude=True)
    ubicacion_destino: Optional[Any] = Field(default=None, exclude=True)
    
    @computed_field
    def ubicacion_origen_nombre(self) -> Optional[str]:
        if self.ubicacion_origen:
            return getattr(self.ubicacion_origen, "nombre", None)
        return None

    @computed_field
    def ubicacion_destino_nombre(self) -> Optional[str]:
        if self.ubicacion_destino:
            return getattr(self.ubicacion_destino, "nombre", None)
        return None
