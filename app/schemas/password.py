import uuid
from pydantic import BaseModel, Field

class PasswordResetRequest(BaseModel):
    """
    Schema para la petición que hace un administrador para iniciar el reseteo
    de contraseña de otro usuario.
    """
    username: str = Field(..., description="Nombre de usuario del cual se reseteará la contraseña.")


class PasswordResetResponse(BaseModel):
    """
    Schema para la respuesta que recibe el administrador, conteniendo el token
    temporal que debe comunicar al usuario.
    """
    username: str
    reset_token: uuid.UUID
    expires_at: str


class PasswordResetConfirm(BaseModel):
    """
    Schema para la petición que hace el usuario final para confirmar el cambio
    de contraseña usando el token.
    """
    username: str = Field(..., description="Tu nombre de usuario.")
    token: uuid.UUID = Field(..., description="El token de reseteo que te proporcionó el administrador.")
    new_password: str = Field(..., min_length=8, description="Tu nueva contraseña.")


class PasswordChange(BaseModel):
    """
    Schema para el cambio de contraseña de un usuario autenticado.
    """
    current_password: str = Field(..., description="La contraseña actual del usuario.")
    new_password: str = Field(..., min_length=8, description="La nueva contraseña para el usuario.")
