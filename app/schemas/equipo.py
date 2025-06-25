import uuid
from typing import Any, Dict, Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field

from .estado_equipo import EstadoEquipoSimple
from .proveedor import ProveedorSimple 
# from .estado_equipo import EstadoEquipo
# Si necesitas info de componentes/padres, importa los schemas adecuados
# from .equipo_componente import ComponenteInfo, PadreInfo
# Importa otros schemas simples si los necesitas y existen
# from .movimiento import MovimientoSimple
# from .documentacion import DocumentacionSimple
# from .mantenimiento import MantenimientoSimple
# from .asignacion_licencia import AsignacionLicenciaSimple
# from .reserva_equipo import ReservaEquipoSimple
# from .inventario_movimiento import InventarioMovimientoSimple

# --- Schema Base ---
class EquipoBase(BaseModel):
    nombre: str = Field(..., max_length=255)
    numero_serie: str = Field(..., max_length=100)
    codigo_interno: Optional[str] = Field(None, max_length=100)
    estado_id: UUID
    ubicacion_actual: Optional[str] = None
    marca: Optional[str] = Field(None, max_length=100)
    modelo: Optional[str] = Field(None, max_length=100)
    fecha_adquisicion: Optional[date] = None
    fecha_puesta_marcha: Optional[date] = None
    fecha_garantia_expiracion: Optional[date] = None
    valor_adquisicion: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    proveedor_id: Optional[UUID] = None
    centro_costo: Optional[str] = Field(None, max_length=100)
    notas: Optional[str] = None

# --- Schema para Creación ---
class EquipoCreate(EquipoBase):
    pass

# --- Schema para Actualización ---
class EquipoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=255)
    estado_id: Optional[UUID] = None
    ubicacion_actual: Optional[str] = None
    marca: Optional[str] = Field(None, max_length=100)
    modelo: Optional[str] = Field(None, max_length=100)
    fecha_adquisicion: Optional[date] = None
    fecha_puesta_marcha: Optional[date] = None
    fecha_garantia_expiracion: Optional[date] = None
    valor_adquisicion: Optional[Decimal] = Field(None, max_digits=12, decimal_places=2)
    proveedor_id: Optional[UUID] = None
    centro_costo: Optional[str] = Field(None, max_length=100)
    notas: Optional[str] = None

# --- Schema Interno DB ---
class EquipoInDBBase(EquipoBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = { "from_attributes": True }

# --- Schema Mínimo ---
class EquipoSimple(BaseModel):
    id: uuid.UUID
    nombre: str
    numero_serie: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    model_config = { "from_attributes": True }

# --- Schema Búsqueda ---
class EquipoSearchResult(BaseModel):
    id: uuid.UUID
    nombre: str
    numero_serie: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    ubicacion_actual: Optional[str] = None
    estado_nombre: Optional[str] = None
    relevancia: float
    model_config = { "from_attributes": True }

# --- Schema Búsqueda Global ---
class GlobalSearchResult(BaseModel):
    tipo: str
    id: uuid.UUID
    titulo: str
    descripcion: Optional[str] = None
    relevancia: float
    metadata: Optional[Dict[str, Any]] = None
    model_config = { "from_attributes": True }

# --- Schema para Lectura (Respuesta API - SIMPLIFICADO) ---
class EquipoRead(EquipoBase): # Hereda campos base
    id: UUID
    created_at: datetime
    updated_at: datetime

    # --- Usar EstadoEquipoSimple ---
    estado: Optional[EstadoEquipoSimple] = None # <--- CAMBIADO
    proveedor: Optional[ProveedorSimple] = None
    # --- FIN CAMBIO ---


    # --- ELIMINAR o COMENTAR estas líneas ---
    # componentes: Optional[List["ComponenteInfo"]] = None
    # parte_de: Optional[List["PadreInfo"]] = None
    # --- FIN ELIMINAR/COMENTAR ---

    # Decide si necesitas incluir otras relaciones y usa schemas simples
    # Ejemplo:
    # movimientos: Optional[List[MovimientoSimple]] = None
    # documentos: Optional[List[DocumentacionSimple]] = None
    # mantenimientos: Optional[List[MantenimientoSimple]] = None
    # licencias_asignadas_a_equipo: Optional[List[AsignacionLicenciaSimple]] = None
    # reservas: Optional[List[ReservaEquipoSimple]] = None
    
    model_config = {
        "from_attributes": True
    }

# --- Schema Equipo original (AHORA SE LLAMA EquipoLegacy O SE ELIMINA) ---
# Puedes renombrar o eliminar el schema original 'Equipo' si ya no lo usas en otro lugar.
# class EquipoLegacy(EquipoBase):
#     id: UUID
#     created_at: datetime
#     updated_at: datetime
#     estado: Optional[EstadoEquipo] = None
#     proveedor: Optional[Proveedor] = None
#     model_config = { "from_attributes": True }
