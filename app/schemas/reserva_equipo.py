import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, model_validator, ConfigDict

from .enums import EstadoReservaEnum
from .usuario import UsuarioSimple
from .equipo import EquipoSimple

# ===============================================================
# Schema Base
# ===============================================================
class ReservaEquipoBase(BaseModel):
    """Campos base necesarios para definir una reserva."""
    equipo_id: uuid.UUID = Field(..., description="ID del equipo a reservar")
    fecha_hora_inicio: datetime = Field(..., description="Fecha y hora de inicio de la reserva")
    fecha_hora_fin: datetime = Field(..., description="Fecha y hora de fin de la reserva")
    proposito: str = Field(..., description="Propósito o motivo de la reserva")
    notas: Optional[str] = Field(None, description="Notas adicionales del solicitante")

# ===============================================================
# Schema para Creación
# ===============================================================
class ReservaEquipoCreate(ReservaEquipoBase):
    """Schema utilizado para crear una nueva reserva."""
    pass

# ===============================================================
# Schema para Actualización
# ===============================================================
class ReservaEquipoUpdate(BaseModel):
    """
    Schema para actualizar una reserva. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    fecha_hora_inicio: Optional[datetime] = None
    fecha_hora_fin: Optional[datetime] = None
    proposito: Optional[str] = None
    notas: Optional[str] = None

# ===============================================================
# Schemas para Acciones Específicas
# ===============================================================
class ReservaEquipoUpdateEstado(BaseModel):
    """Schema para cambiar el estado de una reserva (acción de gestor)."""
    estado: EstadoReservaEnum = Field(..., description="Nuevo estado para la reserva")
    notas_administrador: Optional[str] = Field(None, description="Notas del gestor que aprueba, rechaza o modifica el estado")

class ReservaEquipoCheckInOut(BaseModel):
    """Schema para registrar la recogida (check-in) o devolución (check-out) del equipo."""
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    notas_devolucion: Optional[str] = Field(None, description="Notas sobre el estado del equipo al momento de la devolución.")

    @model_validator(mode='after')
    def check_exclusive_fields(self) -> 'ReservaEquipoCheckInOut':
        """Valida que solo se proporcione una de las dos acciones (check-in o check-out)."""
        if self.check_in_time is not None and self.check_out_time is not None:
            raise ValueError("Solo se puede proporcionar 'check_in_time' o 'check_out_time', no ambos.")
        if self.check_in_time is None and self.check_out_time is None:
            raise ValueError("Se debe proporcionar 'check_in_time' o 'check_out_time'.")
        return self

# ===============================================================
# Schema Interno DB
# ===============================================================
class ReservaEquipoInDBBase(ReservaEquipoBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos y FKs."""
    id: uuid.UUID
    usuario_solicitante_id: uuid.UUID
    estado: EstadoReservaEnum
    aprobado_por_id: Optional[uuid.UUID] = None
    fecha_aprobacion: Optional[datetime] = None
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    notas_administrador: Optional[str] = None
    notas_devolucion: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Respuesta API
# ===============================================================
class ReservaEquipo(ReservaEquipoInDBBase):
    """
    Schema para devolver al cliente. Incluye objetos anidados para una respuesta rica.
    """
    equipo: EquipoSimple
    solicitante: UsuarioSimple
    aprobado_por: Optional[UsuarioSimple] = None
