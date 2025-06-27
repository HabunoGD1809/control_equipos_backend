import uuid
from typing import Any, Dict, Optional
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict

# Importar schemas relacionados
from .estado_equipo import EstadoEquipoSimple
from .proveedor import ProveedorSimple

# ===============================================================
# Schema Base
# ===============================================================
class EquipoBase(BaseModel):
    """Campos base que definen un equipo."""
    nombre: str = Field(..., max_length=255, description="Nombre descriptivo del equipo")
    numero_serie: str = Field(..., max_length=100, description="Número de serie único del fabricante")
    codigo_interno: Optional[str] = Field(None, max_length=100, description="Código de activo fijo de la empresa")
    estado_id: uuid.UUID = Field(..., description="ID del estado actual del equipo")
    ubicacion_actual: Optional[str] = Field(None, description="Descripción de la ubicación actual (sala, edificio, usuario)")
    marca: Optional[str] = Field(None, max_length=100)
    modelo: Optional[str] = Field(None, max_length=100)
    fecha_adquisicion: Optional[date] = None
    fecha_puesta_marcha: Optional[date] = Field(None, description="Fecha en que el equipo entró en operación")
    fecha_garantia_expiracion: Optional[date] = None
    valor_adquisicion: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2, description="Costo de compra del equipo")
    proveedor_id: Optional[uuid.UUID] = Field(None, description="ID del proveedor que suministró el equipo")
    centro_costo: Optional[str] = Field(None, max_length=100, description="Departamento o proyecto asociado")
    notas: Optional[str] = Field(None, description="Campo libre para observaciones generales")

# ===============================================================
# Schema para Creación
# ===============================================================
class EquipoCreate(EquipoBase):
    """Schema utilizado para registrar un nuevo equipo."""
    pass

# ===============================================================
# Schema para Actualización
# ===============================================================
class EquipoUpdate(BaseModel):
    """
    Schema para actualizar un equipo. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    nombre: Optional[str] = Field(None, max_length=255)
    estado_id: Optional[uuid.UUID] = None
    ubicacion_actual: Optional[str] = None
    marca: Optional[str] = Field(None, max_length=100)
    modelo: Optional[str] = Field(None, max_length=100)
    fecha_adquisicion: Optional[date] = None
    fecha_puesta_marcha: Optional[date] = None
    fecha_garantia_expiracion: Optional[date] = None
    valor_adquisicion: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
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

# ===============================================================
# Schema Simple (para listas o referencias)
# ===============================================================
class EquipoSimple(BaseModel):
    """Schema simplificado, útil para vistas de lista o referencias en otros objetos."""
    id: uuid.UUID
    nombre: str
    numero_serie: str
    marca: Optional[str] = None
    modelo: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schemas para Búsqueda
# ===============================================================
class EquipoSearchResult(BaseModel):
    """Schema para los resultados de búsqueda específicos de equipos."""
    id: uuid.UUID
    nombre: str
    numero_serie: str
    marca: Optional[str] = None
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
