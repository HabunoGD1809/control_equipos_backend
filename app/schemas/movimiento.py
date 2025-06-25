import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field

# Importar schemas simples para referencias anidadas
from .equipo import EquipoSimple
from .usuario import UsuarioSimple

# Lista de tipos de movimiento válidos (debe coincidir con el CHECK de la DB)
TIPOS_MOVIMIENTO_VALIDOS = [
    'Salida Temporal', 'Salida Definitiva', 'Entrada',
    'Asignacion Interna', 'Transferencia Bodega'
]

# Lista de estados de movimiento válidos (debe coincidir con el CHECK de la DB)
ESTADOS_MOVIMIENTO_VALIDOS = [
    'Pendiente', 'Autorizado', 'En Proceso', 'Completado', 'Cancelado', 'Rechazado'
]


# --- Schema Base ---
# Campos comunes o que se proporcionan al crear (algunos serán opcionales según el tipo)
class MovimientoBase(BaseModel):
    equipo_id: uuid.UUID = Field(..., description="ID del equipo que se mueve")
    # El usuario_id (quien registra) normalmente se obtiene del usuario autenticado, no se envía en el payload.
    # El autorizado_por se maneja en la lógica si es necesario.
    tipo_movimiento: str = Field(..., description=f"Tipo de movimiento realizado. Valores válidos: {TIPOS_MOVIMIENTO_VALIDOS}")
    fecha_prevista_retorno: Optional[datetime] = Field(None, description="Fecha prevista de retorno (solo para Salida Temporal)")
    origen: Optional[str] = Field(None, description="Ubicación/Usuario origen (requerido para Entrada, Asignacion, Transferencia)")
    destino: Optional[str] = Field(None, description="Ubicación/Usuario destino (requerido para Salida, Asignacion, Transferencia)")
    proposito: Optional[str] = Field(None, description="Motivo o propósito del movimiento")
    recibido_por: Optional[str] = Field(None, description="Nombre de la persona que recibe físicamente (si aplica)")
    observaciones: Optional[str] = Field(None, description="Notas u observaciones adicionales")

    # Validación a nivel de schema (ejemplo, se puede hacer lógica más compleja en endpoints/servicios)
    # @field_validator('tipo_movimiento')
    # def tipo_movimiento_valido(cls, v):
    #     if v not in TIPOS_MOVIMIENTO_VALIDOS:
    #         raise ValueError(f"Tipo de movimiento inválido. Válidos: {TIPOS_MOVIMIENTO_VALIDOS}")
    #     return v
    # Validaciones más complejas (ej: destino obligatorio para salida) se manejan mejor
    # en la lógica del endpoint/servicio o idealmente en la función de base de datos.


# --- Schema para Creación ---
# Datos específicos que la API espera para crear un movimiento.
# Nota: usuario_id y autorizado_por se gestionarán en el servicio/endpoint.
class MovimientoCreate(MovimientoBase):
    # Podríamos añadir aquí autorizado_por si quisiéramos pasarlo explícitamente en la API
    # autorizado_por_id: Optional[uuid.UUID] = None
    pass # Por ahora coincide con la base, la lógica de negocio añade el resto


# --- Schema para Actualización ---
# Campos que podrían actualizarse en un movimiento existente (ej: estado, fecha retorno real)
class MovimientoUpdate(BaseModel):
    # estado: Optional[str] = Field(None, description=f"Nuevo estado. Válidos: {ESTADOS_MOVIMIENTO_VALIDOS}")
    fecha_retorno: Optional[datetime] = Field(None, description="Fecha real en que retornó el equipo")
    recibido_por: Optional[str] = Field(None, description="Actualizar quién recibió en la devolución")
    observaciones: Optional[str] = Field(None, description="Añadir/modificar observaciones")
    # Actualizar otros campos suele ser menos común, se podría cancelar y crear uno nuevo.

# --- Schema Interno DB ---
# Representa todos los campos del modelo ORM
class MovimientoInDBBase(MovimientoBase):
    id: uuid.UUID
    usuario_id: Optional[uuid.UUID] # Quién registró
    autorizado_por: Optional[uuid.UUID] # Quién autorizó
    fecha_hora: datetime # Timestamp de creación/registro del movimiento
    fecha_retorno: Optional[datetime] # Fecha real retorno (actualizable)
    estado: str # Estado actual del movimiento
    created_at: datetime

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API ---
# Lo que se devuelve al cliente
class Movimiento(MovimientoInDBBase):
    # Anidar información relevante de objetos relacionados
    equipo: EquipoSimple # Info básica del equipo
    usuario_registrador: Optional[UsuarioSimple] = None # Info básica de quién registró
    usuario_autorizador: Optional[UsuarioSimple] = None # Info básica de quién autorizó (si aplica)
