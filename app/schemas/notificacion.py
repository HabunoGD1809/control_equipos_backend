import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field

# CORRECCIÓN: Importar el Enum para usarlo directamente
from .enums import TipoNotificacionEnum

# --- Schema Base ---
# Define la estructura fundamental de una notificación.
class NotificacionBase(BaseModel):
    mensaje: str = Field(..., description="Contenido del mensaje de notificación")
    # CORRECCIÓN: Usar el Enum para el tipo, con un valor por defecto.
    tipo: TipoNotificacionEnum = Field(default=TipoNotificacionEnum.INFO, description="Categoría de la notificación.")
    urgencia: int = Field(default=0, ge=0, le=2, description="Nivel de urgencia (0=Baja, 1=Media, 2=Alta)")
    referencia_id: Optional[uuid.UUID] = Field(None, description="ID del objeto relacionado (Equipo, Mantenimiento, etc.)")
    referencia_tabla: Optional[str] = Field(None, description="Nombre de la tabla del objeto relacionado")


# --- Schema para Creación (INTERNA) ---
# Generalmente, las notificaciones se crean internamente por la lógica de negocio o tareas,
# no directamente desde un endpoint de API genérico. Si se necesitara un endpoint, sería así:
class NotificacionCreateInternal(NotificacionBase):
    usuario_id: uuid.UUID = Field(..., description="ID del usuario que recibirá la notificación")
    mensaje: str = Field(..., description="Contenido del mensaje de notificación")
    # Los siguientes campos son opcionales en la creación, se usarán valores por defecto si no se proveen.
    tipo: TipoNotificacionEnum = Field(default=TipoNotificacionEnum.INFO, description="Categoría de la notificación.")
    urgencia: int = Field(default=0, ge=0, le=2, description="Nivel de urgencia (0=Baja, 1=Media, 2=Alta)")
    referencia_id: Optional[uuid.UUID] = None
    referencia_tabla: Optional[str] = None


# --- Schema para Actualización ---
# La única acción común desde la API es marcar como leída/no leída.
class NotificacionUpdate(BaseModel):
    leido: bool = Field(..., description="Establecer el estado leído/no leído")

# --- Schema Interno DB ---
class NotificacionInDBBase(NotificacionBase):
    id: uuid.UUID
    usuario_id: uuid.UUID
    leido: bool = Field(..., description="Indica si la notificación ha sido leída")
    created_at: datetime
    fecha_leido: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

# --- Schema para Respuesta API ---
# Lo que se devuelve al usuario cuando consulta sus notificaciones
class Notificacion(NotificacionInDBBase):
    # No necesitamos anidar el usuario, ya que se consultan las del propio usuario
    # usuario: UsuarioSimple
    pass
