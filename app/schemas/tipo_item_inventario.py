import uuid
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from .enums import UnidadMedidaEnum
from .proveedor import ProveedorSimple
from .marca import MarcaSimple


# ===============================================================
# Schema Base: Campos comunes para un tipo de ítem de inventario
# ===============================================================
class TipoItemInventarioBase(BaseModel):
    """Campos base que definen un tipo de ítem de inventario."""
    nombre: str = Field(
        ...,
        max_length=100,
        description="Nombre descriptivo del ítem (ej: Toner HP 85A)"
    )
    categoria: str = Field(
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
class TipoItemInventarioUpdate(BaseModel):
    """
    Schema para actualizar un tipo de ítem. Todos los campos son opcionales
    para permitir actualizaciones parciales (PATCH).
    """
    nombre: Optional[str] = Field(None, max_length=100)
    categoria: Optional[str] = Field(None, max_length=100)
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
class TipoItemInventarioSimple(BaseModel):
    """Schema simplificado, útil para vistas de lista o referencias en otros objetos."""
    id: uuid.UUID
    nombre: str
    unidad_medida: UnidadMedidaEnum
    sku: Optional[str] = None
    marca_id: Optional[uuid.UUID] = None
    modelo: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para la respuesta de items con bajo stock
# ===============================================================
class TipoItemInventarioConStock(TipoItemInventario):
    """Extiende el schema base para incluir el stock total actual en la respuesta."""
    stock_total_actual: int
