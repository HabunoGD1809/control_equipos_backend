import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from .usuario import UsuarioSimple

# ===============================================================
# Schema Base (para lectura)
# ===============================================================
class LoginLogBase(BaseModel):
    """Campos base que definen un registro de intento de login."""
    nombre_usuario_intento: Optional[str] = Field(None, description="Nombre de usuario utilizado en el intento")
    intento: datetime = Field(..., description="Fecha y hora del intento de login")
    exito: Optional[bool] = Field(None, description="Indica si el intento fue exitoso")
    ip_origen: Optional[str] = Field(None, description="Dirección IP desde donde se realizó el intento")
    user_agent: Optional[str] = Field(None, description="Información del cliente/navegador del usuario")
    motivo_fallo: Optional[str] = Field(None, description="Razón específica del fallo (si exito=False)")

# ===============================================================
# Schema Interno DB
# ===============================================================
class LoginLogInDBBase(LoginLogBase):
    """Schema que refleja el modelo completo de la BD, incluyendo metadatos y FKs."""
    id: uuid.UUID
    usuario_id: Optional[uuid.UUID]  # El ID del usuario si se pudo identificar

    model_config = ConfigDict(from_attributes=True)

# ===============================================================
# Schema para Respuesta API
# ===============================================================
class LoginLog(LoginLogInDBBase):
    """
    Schema para devolver al cliente. Incluye un objeto anidado con la
    información básica del usuario si fue identificado durante el intento.
    """
    usuario: Optional[UsuarioSimple] = None
