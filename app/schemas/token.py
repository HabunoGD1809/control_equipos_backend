import uuid
from typing import Optional

from pydantic import BaseModel

# Schema para la respuesta del endpoint de login
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer" # Siempre 'bearer' para JWT estándar
    # Podrías añadir aquí el refresh_token si lo implementas

# Schema para los datos contenidos dentro del JWT (payload)
class TokenPayload(BaseModel):
    # 'sub' (subject) es el estándar para el identificador del usuario
    sub: uuid.UUID | str # Puede ser UUID o string (ej: nombre_usuario)
    # Podrías añadir aquí otros claims estándar o personalizados:
    # exp: Optional[int] = None # Tiempo de expiración (timestamp UNIX)
    # iat: Optional[int] = None # Tiempo de emisión (timestamp UNIX)
    # roles: Optional[List[str]] = None # Roles del usuario
    # permissions: Optional[List[str]] = None # Permisos del usuario
