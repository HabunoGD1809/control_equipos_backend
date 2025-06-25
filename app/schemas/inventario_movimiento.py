import uuid
from typing import Optional, List, Any
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import (
    BaseModel, Field, field_validator, model_validator,
    ValidationInfo
)

from .enums import TipoMovimientoInvEnum
from .usuario import UsuarioSimple
from .tipo_item_inventario import TipoItemInventarioSimple

# ==============================================================================
# Esquema Base del Movimiento de Inventario
# ==============================================================================
class InventarioMovimientoBase(BaseModel):
    tipo_item_id: uuid.UUID = Field(..., description="ID del tipo de ítem afectado.")
    tipo_movimiento: TipoMovimientoInvEnum = Field(..., description="Tipo de movimiento realizado.")
    cantidad: int = Field(..., description="Cantidad movida (validada como positiva).")
    fecha_hora: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Fecha y hora UTC del movimiento.")
    ubicacion_origen: Optional[str] = Field(None, max_length=255, description="Ubicación origen.")
    ubicacion_destino: Optional[str] = Field(None, max_length=255, description="Ubicación destino.")
    lote_origen: Optional[str] = Field(None, max_length=100, description="Lote de origen (si aplica).")
    lote_destino: Optional[str] = Field(None, max_length=100, description="Lote de destino (si aplica).")
    costo_unitario: Optional[Decimal] = Field(None, description="Costo unitario (validado >= 0).")
    motivo_ajuste: Optional[str] = Field(None, description="Motivo si es Ajuste.")
    referencia_externa: Optional[str] = Field(None, max_length=255, description="Referencia externa.")
    equipo_asociado_id: Optional[uuid.UUID] = Field(None, description="ID Equipo asociado.")
    mantenimiento_id: Optional[uuid.UUID] = Field(None, description="ID Mantenimiento asociado.")
    referencia_transferencia: Optional[uuid.UUID] = Field(None, description="Ref. a mov. de transferencia opuesto.")
    notas: Optional[str] = Field(None, description="Notas adicionales.")

    @field_validator('cantidad', 'costo_unitario', mode='before')
    @classmethod
    def validate_numerics(cls, v: Any, info: ValidationInfo):
        field_name = info.field_name
        if v is None:
            if field_name == 'cantidad': raise ValueError("La cantidad no puede ser nula.")
            return None
        if field_name == 'cantidad':
            try:
                value = int(str(v));
                if value <= 0: raise ValueError("La cantidad debe ser un entero positivo.")
                return value
            except (ValueError, TypeError): raise ValueError(f"'{v}' no es un entero válido para {field_name}.")
        elif field_name == 'costo_unitario':
             try:
                 value = Decimal(str(v));
                 if value < 0: raise ValueError("El costo unitario no puede ser negativo.")
                 return value
             except Exception: raise ValueError(f"'{v}' no es un número decimal válido para {field_name}.")
        return v

    @model_validator(mode='after')
    def check_logic_by_type(self) -> 'InventarioMovimientoBase':
        tipo = self.tipo_movimiento
        origen = self.ubicacion_origen
        destino = self.ubicacion_destino
        motivo = self.motivo_ajuste
        is_salida_type = tipo in [TipoMovimientoInvEnum.SALIDA_USO, TipoMovimientoInvEnum.SALIDA_DESCARTE, TipoMovimientoInvEnum.AJUSTE_NEGATIVO, TipoMovimientoInvEnum.TRANSFERENCIA_SALIDA, TipoMovimientoInvEnum.DEVOLUCION_PROVEEDOR, TipoMovimientoInvEnum.DEVOLUCION_INTERNA]
        is_entrada_type = tipo in [TipoMovimientoInvEnum.ENTRADA_COMPRA, TipoMovimientoInvEnum.AJUSTE_POSITIVO, TipoMovimientoInvEnum.TRANSFERENCIA_ENTRADA, TipoMovimientoInvEnum.DEVOLUCION_INTERNA]
        is_ajuste_type = tipo in [TipoMovimientoInvEnum.AJUSTE_POSITIVO, TipoMovimientoInvEnum.AJUSTE_NEGATIVO]
        is_transfer_type = tipo in [TipoMovimientoInvEnum.TRANSFERENCIA_SALIDA, TipoMovimientoInvEnum.TRANSFERENCIA_ENTRADA]
        errors = []
        if is_salida_type and not origen: errors.append("ubicacion_origen requerida para este tipo de movimiento.")
        if is_entrada_type and not destino: errors.append("ubicacion_destino requerida para este tipo de movimiento.")
        if is_transfer_type and (not origen or not destino): errors.append("ubicacion_origen y ubicacion_destino requeridos para Transferencias.")
        if is_ajuste_type and not motivo: errors.append("motivo_ajuste requerido para Ajustes.")
        unique_errors = []
        [unique_errors.append(e) for e in errors if e not in unique_errors]
        if unique_errors: raise ValueError("; ".join(unique_errors))
        if not is_salida_type: self.ubicacion_origen = None
        if not is_entrada_type: self.ubicacion_destino = None
        if not is_ajuste_type: self.motivo_ajuste = None
        return self
    
# ==============================================================================
# Esquema para la Creación (Payload API)
# ==============================================================================
class InventarioMovimientoCreate(InventarioMovimientoBase):
    pass

# ==============================================================================
# Esquema para Actualización
# ==============================================================================
class InventarioMovimientoUpdate(BaseModel):
    notas: Optional[str] = Field(None, description="Nuevas notas.")

# ==============================================================================
# Esquema Interno DB
# ==============================================================================
class InventarioMovimientoInDBBase(InventarioMovimientoBase):
    id: uuid.UUID
    usuario_id: Optional[uuid.UUID] = None
    stock_id: Optional[uuid.UUID] = None
    model_config = { "from_attributes": True }

# ==============================================================================
# Esquema para Respuesta API (Lectura)
# ==============================================================================
class InventarioMovimiento(InventarioMovimientoInDBBase):
    usuario_registrador: Optional[UsuarioSimple] = None
    tipo_item: Optional[TipoItemInventarioSimple] = None

# ==============================================================================
# Esquemas para Respuestas de API Estructuradas (Sin cambios)
# ==============================================================================
class InventarioMovimientoResponse(BaseModel):
    message: Optional[str] = None
    data: Optional[InventarioMovimiento] = None

class InventarioMovimientoListResponse(BaseModel):
    message: Optional[str] = None
    data: List[InventarioMovimiento] = []
    total: Optional[int] = None
    page: Optional[int] = None
    size: Optional[int] = None
