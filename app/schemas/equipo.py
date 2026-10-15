import uuid
from typing import Any, Dict, Optional, List
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from .estado_equipo import EstadoEquipoSimple
from .proveedor import ProveedorSimple
from .marca import MarcaSimple
from .ubicacion import UbicacionSimple
from .empleado import EmpleadoSimple
from .ficha_tecnica import FichaTecnica, TipoActivoEnum

# ===============================================================
# Schema Base
# ===============================================================
class EquipoBase(BaseModel):
    """Campos base que definen un equipo."""
    nombre: str = Field(..., max_length=255, description="Nombre descriptivo del equipo")
    tipo_activo: TipoActivoEnum = TipoActivoEnum.EQUIPO
    especificaciones_tecnicas: FichaTecnica = Field(default_factory=dict)
    numero_serie: str = Field(..., min_length=1, max_length=100, description="Número de serie único del fabricante")
    @field_validator("numero_serie", mode="before")
    @classmethod
    def strip_serial(cls, value):
        return value.strip() if isinstance(value, str) else value

    codigo_interno: Optional[str] = Field(None, max_length=100, description="Código de activo fijo de la empresa")
    estado_id: uuid.UUID = Field(..., description="ID del estado actual del equipo")
    ubicacion_id: Optional[uuid.UUID] = None
    empleado_asignado_id: Optional[uuid.UUID] = Field(None, description="ID del Empleado (Custodio) que tiene el equipo")
    marca_id: Optional[uuid.UUID] = None
    modelo: Optional[str] = Field(None, max_length=100)
    fecha_adquisicion: Optional[date] = None
    fecha_puesta_marcha: Optional[date] = Field(None, description="Fecha en que el equipo entró en operación")
    fecha_garantia_expiracion: Optional[date] = None
    valor_adquisicion: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2, description="Costo de compra del equipo")
    proveedor_id: Optional[uuid.UUID] = Field(None, description="ID del proveedor que suministró el equipo")
    centro_costo: Optional[str] = Field(None, max_length=100, description="Departamento o proyecto asociado")
    notas: Optional[str] = Field(None, description="Campo libre para observaciones generales")

# ===============================================================
# Schema para Creación
# ===============================================================
class EquipoCreate(EquipoBase):
    """Schema utilizado para registrar un nuevo equipo."""
    @model_validator(mode="after")
    def assignment_requires_movement(self):
        if self.empleado_asignado_id:
            raise ValueError("Registra primero el equipo y asígnalo mediante Movimientos para conservar custodio, responsable y recepción.")
        return self

# ===============================================================
# Schema para Actualización
# ===============================================================
class EquipoUpdate(BaseModel):
    """
    Schema para actualizar un equipo. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    nombre: Optional[str] = Field(None, max_length=255)
    tipo_activo: TipoActivoEnum = None
    especificaciones_tecnicas: FichaTecnica = Field(default_factory=dict)
    estado_id: Optional[uuid.UUID] = None
    ubicacion_id: Optional[uuid.UUID] = None
    empleado_asignado_id: Optional[uuid.UUID] = None
    marca_id: Optional[uuid.UUID] = None
    modelo: Optional[str] = Field(None, max_length=100)
    fecha_adquisicion: Optional[date] = None
    fecha_puesta_marcha: Optional[date] = None
    fecha_garantia_expiracion: Optional[date] = None
    valor_adquisicion: Optional[Decimal] = Field(None, ge=0, max_digits=12, decimal_places=2)
    proveedor_id: Optional[uuid.UUID] = None
    centro_costo: Optional[str] = Field(None, max_length=100)
    notas: Optional[str] = None

# ===============================================================
# Schema Interno DB
# ===============================================================
class EquipoInDBBase(EquipoBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Lectura (Respuesta API)
# ===============================================================
class EquipoRead(EquipoInDBBase):
    """
    Schema para devolver al cliente. Incluye objetos anidados para una respuesta rica.
    """
    estado: Optional[EstadoEquipoSimple] = None
    proveedor: Optional[ProveedorSimple] = None
    marca_rel: Optional[MarcaSimple] = None
    ubicacion: Optional[UbicacionSimple] = None
    empleado_asignado: Optional[EmpleadoSimple] = None
    ubicacion_actual: Optional[str] = None 

# ===============================================================
# Schema Simple (para listas o referencias)
# ===============================================================
class EquipoSimple(BaseModel):
    """Schema simplificado, útil para vistas de lista o referencias en otros objetos."""
    id: uuid.UUID
    nombre: str
    numero_serie: str
    marca_id: Optional[uuid.UUID] = None
    modelo: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schemas para Búsqueda y Operaciones Masivas
# ===============================================================
class EquipoSearchResult(BaseModel):
    """Schema para los resultados de búsqueda específicos de equipos."""
    id: uuid.UUID
    nombre: str
    numero_serie: str
    marca_id: Optional[uuid.UUID] = None
    modelo: Optional[str] = None
    ubicacion_actual: Optional[str] = None
    estado_nombre: Optional[str] = None
    relevancia: float

    model_config = ConfigDict(from_attributes=True)

class GlobalSearchResult(BaseModel):
    """Schema para los resultados de la búsqueda global en múltiples tablas."""
    tipo: str
    id: uuid.UUID
    titulo: str
    descripcion: Optional[str] = None
    relevancia: float
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

class EquipoBulkResult(BaseModel):
    """Resultados de una operación de carga masiva por CSV."""
    total_procesados: int
    insertados: int
    errores: List[str]
