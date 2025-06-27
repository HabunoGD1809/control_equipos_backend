import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from .enums import TipoNotificacionEnum

# ===============================================================
# Schema Base
# ===============================================================
class NotificacionBase(BaseModel):
    """Campos base que definen una notificación."""
    mensaje: str = Field(..., description="Contenido del mensaje de la notificación")
    tipo: TipoNotificacionEnum = Field(default=TipoNotificacionEnum.INFO, description="Categoría de la notificación")
    urgencia: int = Field(default=0, ge=0, le=2, description="Nivel de urgencia (0=Baja, 1=Media, 2=Alta)")
    referencia_id: Optional[uuid.UUID] = Field(None, description="ID del objeto relacionado (ej: Equipo, Mantenimiento)")
    referencia_tabla: Optional[str] = Field(None, description="Nombre de la tabla del objeto relacionado (ej: equipos, mantenimiento)")


# ===============================================================
# Schema para Creación Interna
# ===============================================================
class NotificacionCreateInternal(NotificacionBase):
    """
    Schema para crear una notificación desde la lógica de negocio (servicios, tareas).
    No está pensado para ser expuesto directamente en un endpoint de API genérico.
    """
    usuario_id: uuid.UUID = Field(..., description="ID del usuario que recibirá la notificación")


# ===============================================================
# Schema para Actualización
# ===============================================================
class NotificacionUpdate(BaseModel):
    """
    Schema específico para la única acción de actualización común:
    marcar una notificación como leída o no leída.
    """
    leido: bool = Field(..., description="Establecer el estado de 'leído' de la notificación")


# ===============================================================
# Schema Interno DB
# ===============================================================
class NotificacionInDBBase(NotificacionBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos y FKs."""
    id: uuid.UUID
    usuario_id: uuid.UUID
    leido: bool
    created_at: datetime
    fecha_leido: Optional[datetime] = None

    # Configuración moderna para Pydantic v2
    model_config = ConfigDict(from_attributes=True)


# ===============================================================
# Schema para Respuesta API
# ===============================================================
class Notificacion(NotificacionInDBBase):
    """
    Schema para devolver al cliente cuando consulta sus notificaciones.
    Expone todos los campos relevantes.
    """
    pass
