import uuid
from typing import Optional, List, Any
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import (
    BaseModel, Field, model_validator,
    ValidationInfo, ConfigDict
)

from .enums import TipoMovimientoInvEnum
from .usuario import UsuarioSimple
from .tipo_item_inventario import TipoItemInventarioSimple

# ===============================================================
# Schema Base del Movimiento de Inventario
# ===============================================================
class InventarioMovimientoBase(BaseModel):
    """Campos base que definen un movimiento de inventario."""
    tipo_item_id: uuid.UUID = Field(..., description="ID del tipo de ítem afectado.")
    tipo_movimiento: TipoMovimientoInvEnum = Field(..., description="Tipo de movimiento realizado.")
    cantidad: int = Field(..., gt=0, description="Cantidad movida (debe ser un entero positivo).")
    fecha_hora: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Fecha y hora UTC del movimiento.")
    ubicacion_origen: Optional[str] = Field(None, max_length=255, description="Ubicación de origen para salidas/transferencias.")
    ubicacion_destino: Optional[str] = Field(None, max_length=255, description="Ubicación de destino para entradas/transferencias.")
    lote_origen: Optional[str] = Field(None, max_length=100, description="Lote de origen, si aplica.")
    lote_destino: Optional[str] = Field(None, max_length=100, description="Lote de destino, si aplica.")
    costo_unitario: Optional[Decimal] = Field(None, ge=0, decimal_places=4, description="Costo unitario del ítem al momento del movimiento.")
    motivo_ajuste: Optional[str] = Field(None, description="Motivo requerido si el movimiento es de tipo 'Ajuste'.")
    referencia_externa: Optional[str] = Field(None, max_length=255, description="Referencia externa (ej: N° de factura, N° de devolución).")
    equipo_asociado_id: Optional[uuid.UUID] = Field(None, description="ID del equipo al que se asignó el consumible/parte.")
    mantenimiento_id: Optional[uuid.UUID] = Field(None, description="ID del mantenimiento asociado al uso del ítem.")
    referencia_transferencia: Optional[uuid.UUID] = Field(None, description="ID para enlazar movimientos de transferencia opuestos.")
    notas: Optional[str] = Field(None, description="Notas o comentarios adicionales sobre el movimiento.")

    @model_validator(mode='after')
    def check_logic_by_type(self) -> 'InventarioMovimientoBase':
        """Valida que los campos requeridos estén presentes según el tipo de movimiento."""
        tipo = self.tipo_movimiento
        
        # Movimientos que implican una salida de stock
        if tipo in [TipoMovimientoInvEnum.SALIDA_USO, TipoMovimientoInvEnum.SALIDA_DESCARTE, TipoMovimientoInvEnum.AJUSTE_NEGATIVO, TipoMovimientoInvEnum.TRANSFERENCIA_SALIDA, TipoMovimientoInvEnum.DEVOLUCION_PROVEEDOR]:
            if not self.ubicacion_origen:
                raise ValueError("ubicacion_origen es requerida para este tipo de movimiento.")

        # Movimientos que implican una entrada de stock
        if tipo in [TipoMovimientoInvEnum.ENTRADA_COMPRA, TipoMovimientoInvEnum.AJUSTE_POSITIVO, TipoMovimientoInvEnum.TRANSFERENCIA_ENTRADA, TipoMovimientoInvEnum.DEVOLUCION_INTERNA]:
            if not self.ubicacion_destino:
                raise ValueError("ubicacion_destino es requerida para este tipo de movimiento.")
        
        # Movimientos de ajuste que requieren un motivo
        if tipo in [TipoMovimientoInvEnum.AJUSTE_POSITIVO, TipoMovimientoInvEnum.AJUSTE_NEGATIVO]:
            if not self.motivo_ajuste:
                raise ValueError("motivo_ajuste es requerido para movimientos de tipo 'Ajuste'.")

        return self

# ===============================================================
# Schema para Creación (Payload API)
# ===============================================================
class InventarioMovimientoCreate(InventarioMovimientoBase):
    """Schema utilizado para registrar un nuevo movimiento de inventario."""
    pass

# ===============================================================
# Schema para Actualización
# ===============================================================
class InventarioMovimientoUpdate(BaseModel):
    """Schema para actualizar un movimiento. Típicamente solo se actualizan las notas."""
    notas: Optional[str] = Field(None, description="Añadir o corregir notas del movimiento.")

# ===============================================================
# Schema Interno DB
# ===============================================================
class InventarioMovimientoInDBBase(InventarioMovimientoBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos y FKs."""
    id: uuid.UUID
    usuario_id: Optional[uuid.UUID] = None
    
    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Respuesta API (Lectura)
# ===============================================================
class InventarioMovimiento(InventarioMovimientoInDBBase):
    """
    Schema para devolver al cliente. Incluye objetos anidados para una respuesta rica.
    """
    usuario: Optional[UsuarioSimple] = Field(None, alias='usuario_registrador')
    tipo_item: Optional[TipoItemInventarioSimple] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

# ===============================================================
# Schemas para Respuestas de API Estructuradas
# ===============================================================
class InventarioMovimientoResponse(BaseModel):
    """Wrapper estándar para respuestas de un solo objeto."""
    message: Optional[str] = None
    data: Optional[InventarioMovimiento] = None

class InventarioMovimientoListResponse(BaseModel):
    """Wrapper estándar para respuestas de listas con paginación."""
    message: Optional[str] = None
    data: List[InventarioMovimiento] = Field(default_factory=list)
    total: int = 0
    page: Optional[int] = None
    size: Optional[int] = None
