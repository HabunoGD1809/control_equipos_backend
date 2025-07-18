import uuid
from typing import Optional

from pydantic import BaseModel

# Schema para la respuesta del endpoint de login
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

# Schema para los datos contenidos dentro del JWT (payload)
class TokenPayload(BaseModel):
    sub: uuid.UUID | str

# Schema para el cuerpo de la petición /refresh-token
class RefreshToken(BaseModel):
    refresh_token: str

# Schema para crear un registro en la BD
class RefreshTokenCreate(BaseModel):
    token: str
    usuario_id: uuid.UUID

# Schema de actualización vacío para satisfacer el tipado de BaseService
class RefreshTokenUpdate(BaseModel):
    pass

