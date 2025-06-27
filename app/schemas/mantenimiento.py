import uuid
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict

from .enums import EstadoMantenimientoEnum
from .equipo import EquipoSimple
from .tipo_mantenimiento import TipoMantenimiento
from .proveedor import ProveedorSimple


# ===============================================================
# Schema Base
# ===============================================================
class MantenimientoBase(BaseModel):
    """Campos base que definen un registro de mantenimiento."""
    equipo_id: uuid.UUID = Field(..., description="ID del equipo al que se realiza el mantenimiento")
    tipo_mantenimiento_id: uuid.UUID = Field(..., description="ID del tipo de mantenimiento a realizar")
    fecha_programada: Optional[datetime] = Field(None, description="Fecha y hora en que el mantenimiento está programado para iniciar")
    fecha_inicio: Optional[datetime] = Field(None, description="Fecha y hora real en que se inició el trabajo")
    fecha_finalizacion: Optional[datetime] = Field(None, description="Fecha y hora real en que finalizó el trabajo")
    costo_estimado: Optional[Decimal] = Field(None, ge=0, decimal_places=2, description="Costo estimado del mantenimiento")
    costo_real: Optional[Decimal] = Field(None, ge=0, decimal_places=2, description="Costo final real del mantenimiento")
    tecnico_responsable: str = Field(..., description="Nombre del técnico o empresa responsable de realizar el mantenimiento")
    proveedor_servicio_id: Optional[uuid.UUID] = Field(None, description="ID del proveedor de servicio externo, si aplica")
    estado: EstadoMantenimientoEnum = Field(default=EstadoMantenimientoEnum.PROGRAMADO, description="Estado actual del proceso de mantenimiento")
    prioridad: int = Field(default=0, ge=0, le=2, description="Prioridad del mantenimiento (0=Baja, 1=Media, 2=Alta)")
    observaciones: Optional[str] = Field(None, description="Notas, diagnósticos u observaciones sobre el mantenimiento")


# ===============================================================
# Schema para Creación
# ===============================================================
class MantenimientoCreate(MantenimientoBase):
    """Schema utilizado para programar un nuevo mantenimiento."""
    pass # Hereda todos los campos y validaciones.


# ===============================================================
# Schema para Actualización
# ===============================================================
class MantenimientoUpdate(BaseModel):
    """
    Schema para actualizar un mantenimiento. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    fecha_programada: Optional[datetime] = None
    fecha_inicio: Optional[datetime] = None
    fecha_finalizacion: Optional[datetime] = None
    costo_estimado: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    costo_real: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    tecnico_responsable: Optional[str] = None
    proveedor_servicio_id: Optional[uuid.UUID] = None
    estado: Optional[EstadoMantenimientoEnum] = None
    prioridad: Optional[int] = Field(None, ge=0, le=2)
    observaciones: Optional[str] = None


# ===============================================================
# Schema Interno DB
# ===============================================================
class MantenimientoInDBBase(MantenimientoBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos."""
    id: uuid.UUID
    fecha_proximo_mantenimiento: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===============================================================
# Schema para Respuesta API
# ===============================================================
class Mantenimiento(MantenimientoInDBBase):
    """
    Schema para devolver al cliente. Incluye objetos anidados para una respuesta rica.
    """
    equipo: EquipoSimple
    tipo_mantenimiento: TipoMantenimiento
    proveedor_servicio: Optional[ProveedorSimple] = None


# ===============================================================
# Schema Simple (para listas o referencias)
# ===============================================================
class MantenimientoSimple(BaseModel):
    """Schema simplificado, útil para vistas de lista o referencias rápidas."""
    id: uuid.UUID
    # Para estos campos, es preferible que el servicio que prepara la respuesta
    # los aplane antes de pasarlos al schema, en lugar de usar alias complejos.
    # Por ejemplo: `tipo_mantenimiento_nombre = mantenimiento.tipo_mantenimiento.nombre`
    tipo_mantenimiento_nombre: Optional[str] = None
    equipo_nombre: Optional[str] = None
    fecha_programada: Optional[datetime] = None
    fecha_finalizacion: Optional[datetime] = None
    estado: EstadoMantenimientoEnum

    model_config = ConfigDict(from_attributes=True)
