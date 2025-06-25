from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

# Schema auxiliar para el conteo de equipos por estado
class EquipoPorEstado(BaseModel):
    estado_id: UUID
    estado_nombre: str
    cantidad_equipos: int
    estado_color: Optional[str] = None

# Schema principal para los datos del dashboard
class DashboardData(BaseModel):
    total_equipos: int = Field(..., description="Número total de equipos registrados")
    equipos_por_estado: List[EquipoPorEstado] = Field(..., description="Desglose de equipos por cada estado")
    mantenimientos_proximos_count: int = Field(..., ge=0, description="Número de mantenimientos próximos a vencer (ej: 30 días)")
    licencias_por_expirar_count: int = Field(..., ge=0, description="Número de licencias próximas a expirar (ej: 30 días)")
    items_bajo_stock_count: int = Field(..., ge=0, description="Número de items de inventario bajo el stock mínimo")
    # Añadir más métricas según sea necesario...
    # ej: reservas_activas_count: int = Field(..., ge=0)
    # ej: documentos_pendientes_verificacion_count: int = Field(..., ge=0)
