import uuid
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

# --- Schemas para Roles (Necesitarás crearlos) ---
# class RolBase(BaseModel):
#     nombre: str
#     descripcion: Optional[str] = None

# class Rol(RolBase):
#     id: uuid.UUID
#     created_at: datetime
#     updated_at: datetime
#
#     model_config = {
#         "from_attributes": True
#     }
# --- Fin Schemas Rol ---

# --- Schemas Usuario Corregidos ---
class UsuarioBase(BaseModel):
    nombre_usuario: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None # Añadido

class UsuarioCreate(UsuarioBase):
    password: str = Field(..., min_length=8)
    rol_id: uuid.UUID

class UsuarioUpdate(BaseModel):
    nombre_usuario: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8) # Para actualizar contraseña
    rol_id: Optional[uuid.UUID] = None
    intentos_fallidos: Optional[int] = None
    bloqueado: Optional[bool] = None
    requiere_cambio_contrasena: Optional[bool] = None

class UsuarioInDBBase(UsuarioBase):
    id: uuid.UUID
    rol_id: uuid.UUID # Guardamos el ID
    hashed_password: str # Nombre consistente con el modelo ORM corregido
    token_temporal: Optional[uuid.UUID] = None
    token_expiracion: Optional[datetime] = None
    intentos_fallidos: int
    bloqueado: bool
    ultimo_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    requiere_cambio_contrasena: bool

    model_config = {
       "from_attributes": True
    } # Anteriormente orm_mode=True

# Schema para devolver al cliente (sin datos sensibles)
class Usuario(UsuarioBase):
    id: uuid.UUID
    rol_id: uuid.UUID # Devolver rol_id (o el objeto Rol completo si se define)
    # rol: Optional[Rol] = None # Opcional: Embeber el objeto Rol
    bloqueado: bool
    ultimo_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    requiere_cambio_contrasena: bool

    model_config = {
       "from_attributes": True
    }

# Schema interno para la base de datos
class UsuarioInDB(UsuarioInDBBase):
    pass

# --- Schema Simple ---
# Para referencias en otros schemas (ej: en respuestas de Movimiento, Documentacion, etc.)
class UsuarioSimple(BaseModel):
    id: uuid.UUID
    nombre_usuario: str
    email: Optional[EmailStr] = None

    model_config = {
       "from_attributes": True
    }
