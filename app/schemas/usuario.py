import uuid
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional, List

# ===============================================================
# Schema para Rol - Para respuestas anidadas
# ===============================================================
class Rol(BaseModel):
    """Schema que representa la información pública de un Rol."""
    id: uuid.UUID
    nombre: str
    descripcion: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ===============================================================
# Schemas para Usuario
# ===============================================================
class UsuarioBase(BaseModel):
    """Campos base que comparte un usuario."""
    nombre_usuario: str = Field(..., min_length=3, max_length=50, description="Nombre de usuario único")
    email: Optional[EmailStr] = Field(None, description="Correo electrónico del usuario")

class UsuarioCreate(UsuarioBase):
    """Schema para crear un nuevo usuario. Requiere contraseña y rol."""
    password: str = Field(..., min_length=8, description="Contraseña para el nuevo usuario")
    rol_id: uuid.UUID = Field(..., description="ID del rol a asignar al usuario")

class UsuarioUpdate(BaseModel):
    """
    Schema para actualizar un usuario. Todos los campos son opcionales,
    permitiendo actualizaciones parciales.
    """
    nombre_usuario: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, description="Proporcionar solo si se desea cambiar la contraseña")
    rol_id: Optional[uuid.UUID] = None
    intentos_fallidos: Optional[int] = None
    bloqueado: Optional[bool] = None
    requiere_cambio_contrasena: Optional[bool] = None

class UsuarioInDBBase(UsuarioBase):
    """Schema base que refleja el modelo de la base de datos, incluyendo campos privados."""
    id: uuid.UUID
    rol_id: uuid.UUID
    hashed_password: str  # Nombre consistente con el modelo ORM
    token_temporal: Optional[uuid.UUID] = None
    token_expiracion: Optional[datetime] = None
    intentos_fallidos: int
    bloqueado: bool
    ultimo_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    requiere_cambio_contrasena: bool

    model_config = ConfigDict(from_attributes=True)

class Usuario(UsuarioBase):
    """
    Schema para devolver al cliente. Excluye datos sensibles como la contraseña
    e incluye el objeto Rol anidado para respuestas más completas.
    """
    id: uuid.UUID
    rol_id: uuid.UUID
    bloqueado: bool
    ultimo_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    requiere_cambio_contrasena: bool
    rol: Rol

    model_config = ConfigDict(from_attributes=True)

class UsuarioInDB(UsuarioInDBBase):
    """Schema completo para uso interno, representa una fila de la BD."""
    pass

class UsuarioSimple(BaseModel):
    """Schema simplificado, útil para mostrar información del autor de un movimiento, etc."""
    id: uuid.UUID
    nombre_usuario: str
    email: Optional[EmailStr] = None

    model_config = ConfigDict(from_attributes=True)
