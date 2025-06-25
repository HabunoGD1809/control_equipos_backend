import uuid
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field

# Importar schema simple de Usuario
from .usuario import UsuarioSimple

# --- Schema Base (para lectura) ---
class LoginLogBase(BaseModel):
    nombre_usuario_intento: Optional[str] = Field(None, description="Nombre de usuario utilizado en el intento")
    intento: datetime = Field(..., description="Fecha y hora del intento")
    exito: Optional[bool] = Field(None, description="Indica si el intento fue exitoso (True), fallido (False) o indeterminado (Null)")
    ip_origen: Optional[str] = Field(None, description="Dirección IP desde donde se realizó el intento")
    user_agent: Optional[str] = Field(None, description="Información del cliente/navegador")
    motivo_fallo: Optional[str] = Field(None, description="Razón del fallo (si exito=False)")

# --- Schema Interno DB ---
class LoginLogInDBBase(LoginLogBase):
    id: uuid.UUID
    usuario_id: Optional[uuid.UUID] # El ID del usuario si se pudo identificar

    model_config = {
       "from_attributes": True
    }

# --- Schema para Respuesta API ---
# Devuelve la información del log, incluyendo datos básicos del usuario si se encontró
class LoginLog(LoginLogInDBBase):
    usuario: Optional[UsuarioSimple] = None # Anidar info básica del usuario si existe
