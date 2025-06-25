import uuid
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo

from .enums import EstadoReservaEnum
from .usuario import UsuarioSimple
from .equipo import EquipoSimple

class ReservaEquipoBase(BaseModel):
    equipo_id: uuid.UUID = Field(..., description="ID del equipo a reservar")
    fecha_hora_inicio: datetime = Field(..., description="Fecha y hora de inicio de la reserva")
    fecha_hora_fin: datetime = Field(..., description="Fecha y hora de fin de la reserva")
    proposito: str = Field(..., description="Propósito o motivo de la reserva")
    notas_solicitante: Optional[str] = Field(None, description="Notas adicionales del solicitante")

class ReservaEquipoCreate(ReservaEquipoBase):
    pass

class ReservaEquipoUpdate(BaseModel):
    fecha_hora_inicio: Optional[datetime] = None
    fecha_hora_fin: Optional[datetime] = None
    proposito: Optional[str] = None
    notas_solicitante: Optional[str] = None

class ReservaEquipoUpdateEstado(BaseModel):
    estado: EstadoReservaEnum = Field(..., description="Nuevo estado para la reserva")
    notas_administrador: Optional[str] = Field(None, description="Notas del gestor que aprueba/rechaza")

class ReservaEquipoCheckInOut(BaseModel):
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    notas_devolucion: Optional[str] = Field(None, description="Notas al momento de la devolución del equipo.")

    @model_validator(mode='after')
    def check_exclusive_fields(self) -> 'ReservaEquipoCheckInOut':
        if self.check_in_time is not None and self.check_out_time is not None:
            raise ValueError("Solo se puede proporcionar 'check_in_time' o 'check_out_time', no ambos.")
        if self.check_in_time is None and self.check_out_time is None:
            raise ValueError("Se debe proporcionar 'check_in_time' o 'check_out_time'.")
        return self

class ReservaEquipoInDBBase(ReservaEquipoBase):
    id: uuid.UUID
    usuario_solicitante_id: uuid.UUID
    estado: EstadoReservaEnum
    aprobado_por_id: Optional[uuid.UUID]
    fecha_aprobacion: Optional[datetime]
    check_in_time: Optional[datetime]
    check_out_time: Optional[datetime]
    notas_administrador: Optional[str]
    notas_devolucion: Optional[str]
    created_at: datetime
    updated_at: datetime
    model_config = { "from_attributes": True }

class ReservaEquipo(ReservaEquipoInDBBase):
    equipo: EquipoSimple
    usuario_solicitante: UsuarioSimple
    aprobado_por: Optional[UsuarioSimple] = None
