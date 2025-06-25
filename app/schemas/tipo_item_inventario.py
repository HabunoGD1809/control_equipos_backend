import uuid
from typing import Optional, List 

from pydantic import BaseModel, Field 

from .enums import UnidadMedidaEnum
from .proveedor import ProveedorSimple

# ==============================================================================
# Esquema Base del Tipo de Item de Inventario
# ==============================================================================
class TipoItemInventarioBase(BaseModel): 
    nombre: str = Field(..., max_length=100, description="Nombre descriptivo del item (ej: Cable HDMI 2m, Toner HP 85A)")
    descripcion: Optional[str] = Field(None, description="Descripción más detallada del item")
    unidad_medida: UnidadMedidaEnum = Field(..., description="Unidad de medida (ej: Unidad, Metro, Kg, Litro)")
    stock_minimo: int = Field(default=0, ge=0, description="Nivel mínimo de stock antes de generar alerta")
    
    # --- CORRECCIÓN: 'categoria' es un campo requerido en la BD ---
    categoria: str = Field(..., max_length=100, description="Categoría para agrupar items (ej: Cables, Consumibles Impresión)")
    # ----------------------------------------------------------------

    # --- CAMPOS AÑADIDOS A LA BASE PARA EVITAR ATTRIBUTEERROR EN CREATE ---
    sku: Optional[str] = Field(None, max_length=100, description="Stock Keeping Unit (SKU) único para el ítem.")
    codigo_barras: Optional[str] = Field(None, max_length=100, description="Código de barras del ítem.")
    marca: Optional[str] = Field(None, max_length=100, description="Marca del ítem.") 
    modelo: Optional[str] = Field(None, max_length=100, description="Modelo específico del ítem.")
    proveedor_preferido_id: Optional[uuid.UUID] = Field(None, description="ID del proveedor preferido para este ítem.")


    # Campos que podrías tener en tu modelo y que también deberían estar aquí si se usan en create/update
    # stock_maximo: Optional[Decimal] = Field(None, ge=0, description="Nivel máximo de stock recomendado.")
    # perecedero: bool = Field(False, description="Indica si el ítem es perecedero.")
    # dias_vida_util: Optional[int] = Field(None, ge=0, description="Días de vida útil si es perecedero.")
    # requiere_numero_serie: bool = Field(False, description="Indica si los ítems individuales de este tipo requieren número de serie.")

    # Ejemplo de validador que podrías necesitar
    # @root_validator(skip_on_failure=True) # Pydantic v2
    # def check_stock_levels(cls, values):
    #     stock_min, stock_max = values.get('stock_minimo'), values.get('stock_maximo')
    #     if stock_min is not None and stock_max is not None and stock_min > stock_max: # Asegúrate que stock_maximo esté en la base
    #         raise ValueError("El stock mínimo no puede ser mayor que el stock máximo.")
    #     return values

# ==============================================================================
# Esquema para la Creación de un Tipo de Item de Inventario
# ==============================================================================
class TipoItemInventarioCreate(TipoItemInventarioBase):
    # Hereda todos los campos de TipoItemInventarioBase.
    # Si el servicio create necesita validar/usar sku, codigo_barras, etc.,
    # ahora estarán disponibles en el objeto obj_in.
    pass

# ==============================================================================
# Esquema para la Actualización de un Tipo de Item de Inventario
# ==============================================================================
class TipoItemInventarioUpdate(BaseModel): # No hereda de Base para definir todos como opcionales explícitamente
    nombre: Optional[str] = Field(None, max_length=100)
    descripcion: Optional[str] = None
    unidad_medida: Optional[UnidadMedidaEnum] = None
    stock_minimo: Optional[int] = Field(None, ge=0)
    categoria: Optional[str] = Field(None, max_length=100)

    # Campos para actualización, ya los tenías aquí, lo cual es correcto para PATCH
    sku: Optional[str] = Field(None, max_length=100) # unique y index no aplican en Pydantic, son de BD/ORM
    codigo_barras: Optional[str] = Field(None, max_length=100)
    marca: Optional[str] = Field(None, max_length=100)
    modelo: Optional[str] = Field(None, max_length=100)
    proveedor_preferido_id: Optional[uuid.UUID] = None


# ==============================================================================
# Esquema Interno DB (Respuesta de API con campos de auditoría si los tienes)
# ==============================================================================
# class TipoItemInventarioInDBBase(TipoItemInventarioBase, Auditable): # Descomenta si usas Auditable
class TipoItemInventarioInDBBase(TipoItemInventarioBase):
    id: uuid.UUID

    model_config = {
        "from_attributes": True
    }

# ==============================================================================
# Esquema para Respuesta API (Puede incluir relaciones)
# ==============================================================================
class TipoItemInventario(TipoItemInventarioInDBBase):
    # Ejemplo de relación, si tu modelo la tiene y quieres cargarla:
    proveedor_preferido: Optional[ProveedorSimple] = None # Asegúrate que ProveedorSimple esté definido
    pass

# ==============================================================================
# Esquema Simple para Listas o referencias
# ==============================================================================
class TipoItemInventarioSimple(BaseModel):
    id: uuid.UUID
    nombre: str
    unidad_medida: UnidadMedidaEnum
    sku: Optional[str] = None # Incluir SKU si es relevante en la vista simple

    model_config = {
        "from_attributes": True
    }

# ==============================================================================
# Esquemas para Respuestas de API Estructuradas (Opcional, pero buena práctica)
# ==============================================================================
class TipoItemInventarioResponse(BaseModel):
    message: str
    data: Optional[TipoItemInventario] = None

class TipoItemInventarioListResponse(BaseModel):
    message: str
    data: List[TipoItemInventario] = [] # Default a lista vacía
    total: int = 0
    page: Optional[int] = None
    size: Optional[int] = None
