import uuid
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field 
from .enums import EstadoMantenimientoEnum 

from .equipo import EquipoSimple
from .tipo_mantenimiento import TipoMantenimiento
from .proveedor import ProveedorSimple


# --- Schema Base ---
class MantenimientoBase(BaseModel):
    equipo_id: uuid.UUID = Field(..., description="ID del equipo al que se realiza el mantenimiento")
    tipo_mantenimiento_id: uuid.UUID = Field(..., description="ID del tipo de mantenimiento a realizar")
    fecha_programada: Optional[datetime] = Field(None, description="Fecha y hora programada para iniciar")
    fecha_inicio: Optional[datetime] = Field(None, description="Fecha y hora real de inicio")
    fecha_finalizacion: Optional[datetime] = Field(None, description="Fecha y hora real de finalización")
    costo_estimado: Optional[Decimal] = Field(None, ge=0, decimal_places=2, description="Costo estimado del mantenimiento")
    costo_real: Optional[Decimal] = Field(None, ge=0, decimal_places=2, description="Costo final real del mantenimiento")
    tecnico_responsable: str = Field(..., description="Nombre del técnico o empresa responsable")
    proveedor_servicio_id: Optional[uuid.UUID] = Field(None, description="ID del proveedor externo (si aplica)")
    estado: EstadoMantenimientoEnum = Field(default=EstadoMantenimientoEnum.PROGRAMADO, description="Estado actual del mantenimiento.")
    prioridad: int = Field(default=0, ge=0, le=2, description="Prioridad (0=Baja, 1=Media, 2=Alta)")
    observaciones: Optional[str] = Field(None, description="Notas u observaciones sobre el mantenimiento")

# --- Schema para Creación ---
class MantenimientoCreate(MantenimientoBase):
    pass

# --- Schema para Actualización ---
class MantenimientoUpdate(BaseModel):
    fecha_programada: Optional[datetime] = None
    fecha_inicio: Optional[datetime] = None
    fecha_finalizacion: Optional[datetime] = None
    costo_estimado: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    costo_real: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    tecnico_responsable: Optional[str] = None
    proveedor_servicio_id: Optional[uuid.UUID] = None
    estado: Optional[EstadoMantenimientoEnum] = Field(None, description="Nuevo estado.")
    prioridad: Optional[int] = Field(None, ge=0, le=2)
    observaciones: Optional[str] = None
    
# --- Schema Interno DB ---
class MantenimientoInDBBase(MantenimientoBase):
    id: uuid.UUID
    fecha_proximo_mantenimiento: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    model_config = { "from_attributes": True }

# --- Schema para Respuesta API ---
class Mantenimiento(MantenimientoInDBBase):
    equipo: EquipoSimple
    tipo_mantenimiento: TipoMantenimiento
    proveedor_servicio: Optional[ProveedorSimple] = None

# --- Schema Simple ---
class MantenimientoSimple(BaseModel):
    id: uuid.UUID
    tipo_mantenimiento_nombre: Optional[str] = Field(None, validation_alias='tipo_mantenimiento.nombre')
    equipo_nombre: Optional[str] = Field(None, validation_alias='equipo.nombre')
    fecha_programada: Optional[datetime] = None
    fecha_inicio: Optional[datetime] = None
    fecha_finalizacion: Optional[datetime] = None
    estado: EstadoMantenimientoEnum
    model_config = { "from_attributes": True, "populate_by_name": True }
