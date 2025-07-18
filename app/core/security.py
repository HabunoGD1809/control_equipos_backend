from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional, Set, List

from jose import jwt, JWTError
from pydantic import ValidationError
import logging

from app.core.config import settings
from app.schemas.token import TokenPayload
from app.models.usuario import Usuario

logger = logging.getLogger(__name__)

ALGORITHM = settings.ALGORITHM

def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Crea un nuevo token de acceso JWT.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Crea un nuevo token de refresco JWT.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.REFRESH_TOKEN_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[TokenPayload]:
    """
    Decodifica un token de acceso, valida su estructura y expiración.
    """
    try:
        payload_dict = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        return TokenPayload(**payload_dict)
    except (JWTError, ValidationError, KeyError) as e:
        logger.error(f"Error decodificando token de acceso: {e}")
        return None

def decode_refresh_token(token: str) -> Optional[TokenPayload]:
    """
    Decodifica un token de refresco, valida su estructura y expiración.
    """
    try:
        payload_dict = jwt.decode(
            token, settings.REFRESH_TOKEN_SECRET_KEY, algorithms=[ALGORITHM]
        )
        return TokenPayload(**payload_dict)
    except (JWTError, ValidationError, KeyError) as e:
        logger.error(f"Error decodificando token de refresco: {e}")
        return None


def user_has_permissions(user: Usuario, required_permissions: Union[List[str], Set[str]]) -> bool:
    """
    Verifica si un usuario tiene AL MENOS UNO de los permisos requeridos.
    """
    if not user or not user.rol or not user.rol.permisos:
        logger.warning(f"user_has_permissions: Usuario '{user.nombre_usuario if user else 'Desconocido'}' no tiene rol o permisos cargados.")
        return False
    
    user_permissions = {p.nombre for p in user.rol.permisos}
    
    # Se convierte la entrada a un set para que .isdisjoint() siempre funcione.
    required_set = set(required_permissions)
    
    # Devuelve True si hay al menos un permiso en común
    return not required_set.isdisjoint(user_permissions)
