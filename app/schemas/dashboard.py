from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

# Schema auxiliar para el conteo de equipos por estado
class EquipoPorEstado(BaseModel):
    estado_id: UUID
    estado_nombre: str
    cantidad_equipos: int
    estado_color: Optional[str] = None

# Schema auxiliar para la tabla de actividad reciente
class MovimientoReciente(BaseModel):
    id: UUID
    equipo_nombre: str
    tipo_movimiento: str
    fecha_hora: datetime
    usuario_nombre: Optional[str] = "Sistema/Desconocido"

# Schema principal para los datos del dashboard
class DashboardData(BaseModel):
    total_equipos: int = Field(..., description="Número total de equipos registrados")
    total_valor_activos: float = Field(0.0, description="Suma total del valor de adquisición de todos los equipos")
    equipos_por_estado: List[EquipoPorEstado] = Field(..., description="Desglose de equipos por cada estado")
    mantenimientos_proximos_count: int = Field(..., ge=0, description="Número de mantenimientos próximos a vencer (ej: 30 días)")
    licencias_por_expirar_count: int = Field(..., ge=0, description="Número de licencias próximas a expirar (ej: 30 días)")
    items_bajo_stock_count: int = Field(..., ge=0, description="Número de items de inventario bajo el stock mínimo")
    
    # --- Nuevas Métricas Dinámicas ---
    reservas_pendientes_count: int = Field(0, description="Número de reservas esperando aprobación")
    documentos_pendientes_count: int = Field(0, description="Número de documentos esperando verificación")
    movimientos_recientes: List[MovimientoReciente] = Field(default_factory=list, description="Últimos 5 movimientos registrados en el sistema")
