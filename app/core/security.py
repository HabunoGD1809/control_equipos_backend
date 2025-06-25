from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional

from jose import jwt, JWTError
from pydantic import ValidationError # Para errores de validación de payload

# Importar configuración
from app.core.config import settings
# Importar schema del payload (si se quiere validar al decodificar aquí también)
from app.schemas.token import TokenPayload
import logging

# Obtener logger
logger = logging.getLogger(__name__)


ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Crea un nuevo token de acceso JWT.
    'subject' suele ser el ID del usuario.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Asegurarse de que el subject sea siempre una cadena.
    subject_str = str(subject) if subject is not None else ""  # O alguna otra cadena por defecto
    to_encode = {"exp": expire, "sub": subject_str}
    # Añadir cualquier otro claim necesario aquí
    # to_encode.update({"iat": datetime.now(timezone.utc)}) # Ejemplo: Issued At

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenPayload]:
    """
    Decodifica un token, valida su estructura y expiración.
    Devuelve el payload validado o None si hay error.
    (Esta lógica se usa principalmente en deps.get_current_user)
    """
    try:
        payload_dict = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # Validar contra el schema Pydantic
        token_data = TokenPayload(**payload_dict)
        # Podríamos añadir validación extra de 'exp' aquí si no confiamos 100% en jwt.decode
        return token_data
    except (JWTError, ValidationError, KeyError) as e:
        # KeyError si falta 'sub' u otro campo requerido en TokenPayload
        logger.error(f"Error decodificando token en security.py: {e}", exc_info=True)
        return None
