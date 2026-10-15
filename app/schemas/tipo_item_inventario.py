import uuid
from typing import Optional, Literal, List

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .enums import UnidadMedidaEnum
from .proveedor import ProveedorSimple
from .marca import MarcaSimple


# ===============================================================
# Schema Base: Campos comunes para un tipo de ítem de inventario
# ===============================================================
class ConsumibleFields(BaseModel):
    color: Optional[Literal["Negro", "Cian", "Magenta", "Amarillo", "Tricolor", "Otro"]] = None
    tecnologia: Optional[Literal["Tóner", "Tinta", "Tambor", "Cinta", "Otro"]] = None
    rendimiento_paginas: Optional[int] = Field(default=None, gt=0)
    modelos_equipo_compatibles: Optional[List[str]] = Field(default=None, max_length=100)
    es_original: bool = True
    perecedero: bool = False
    is_active: bool = True

    @field_validator("modelos_equipo_compatibles")
    @classmethod
    def valid_compatibility(cls, value):
        if value is None:
            return value
        cleaned = [name.strip() for name in value]
        if any(not name or len(name) > 100 for name in cleaned):
            raise ValueError("Cada modelo compatible debe contener entre 1 y 100 caracteres.")
        return list(dict.fromkeys(cleaned))

class TipoItemInventarioBase(ConsumibleFields):
    """Campos base que definen un tipo de ítem de inventario."""
    nombre: str = Field(
        ...,
        max_length=100,
        description="Nombre descriptivo del ítem (ej: Toner HP 85A)"
    )
    categoria: Literal['Consumible', 'Parte Repuesto', 'Accesorio', 'Otro'] = Field(
        ...,
        max_length=100,
        description="Categoría para agrupar ítems (ej: Cables, Consumibles Impresión)"
    )
    descripcion: Optional[str] = Field(
        None,
        description="Descripción más detallada del ítem"
    )
    unidad_medida: UnidadMedidaEnum = Field(
        ...,
        description="Unidad de medida del ítem (ej: Unidad, Metro, Kg)"
    )
    stock_minimo: int = Field(
        default=0,
        ge=0,
        description="Nivel mínimo de stock antes de generar una alerta"
    )
    marca_id: Optional[uuid.UUID] = Field(None, description="ID de la marca del ítem")
    modelo: Optional[str] = Field(None, max_length=100, description="Modelo específico del ítem")
    sku: Optional[str] = Field(None, max_length=100, description="Stock Keeping Unit (SKU) único para el ítem")
    codigo_barras: Optional[str] = Field(None, max_length=100, description="Código de barras del ítem")
    proveedor_preferido_id: Optional[uuid.UUID] = Field(None, description="ID del proveedor preferido para este ítem")


# ===============================================================
# Schema para Creación
# ===============================================================
class TipoItemInventarioCreate(TipoItemInventarioBase):
    """Schema utilizado para crear un nuevo tipo de ítem de inventario."""
    pass


# ===============================================================
# Schema para Actualización
# ===============================================================
class TipoItemInventarioUpdate(ConsumibleFields):
    """
    Schema para actualizar un tipo de ítem. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    nombre: Optional[str] = Field(None, max_length=100)
    categoria: Optional[Literal['Consumible', 'Parte Repuesto', 'Accesorio', 'Otro']] = Field(None)
    descripcion: Optional[str] = None
    unidad_medida: Optional[UnidadMedidaEnum] = None
    stock_minimo: Optional[int] = Field(None, ge=0)
    marca_id: Optional[uuid.UUID] = None
    modelo: Optional[str] = Field(None, max_length=100)
    sku: Optional[str] = Field(None, max_length=100)
    codigo_barras: Optional[str] = Field(None, max_length=100)
    proveedor_preferido_id: Optional[uuid.UUID] = None


# ===============================================================
# Schema Interno DB (refleja el modelo ORM)
# ===============================================================
class TipoItemInventarioInDBBase(TipoItemInventarioBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos."""
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


# ===============================================================
# Schema para Respuestas de API
# ===============================================================
class TipoItemInventario(TipoItemInventarioInDBBase):
    """
    Schema para devolver al cliente. Puede incluir relaciones anidadas
    cargadas desde la base de datos.
    """
    proveedor_preferido: Optional[ProveedorSimple] = None
    marca_rel: Optional[MarcaSimple] = None


# ===============================================================
# Schema Simple (para listas o referencias)
# ===============================================================
class TipoItemInventarioSimple(ConsumibleFields):
    """Schema simplificado, útil para vistas de lista o referencias en otros objetos."""
    id: uuid.UUID
    nombre: str
    unidad_medida: UnidadMedidaEnum
    sku: Optional[str] = None
    marca_id: Optional[uuid.UUID] = None
    modelo: Optional[str] = None
    
    marca_rel: Optional[MarcaSimple] = None

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para la respuesta de items con bajo stock
# ===============================================================
class TipoItemInventarioConStock(TipoItemInventario):
    """Extiende el schema base para incluir el stock total actual en la respuesta."""
    stock_total_actual: int
