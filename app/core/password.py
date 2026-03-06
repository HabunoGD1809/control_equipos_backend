import bcrypt
import hashlib
import logging

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica si una contraseña plana coincide con una contraseña hasheada usando bcrypt.
    SOLO usar para contraseñas de usuarios, nunca para tokens.
    """
    try:
        plain_password_bytes = plain_password.encode('utf-8')
        hashed_password_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)
    except ValueError as e:
        logger.error(f"Error verificando password (posiblemente hash inválido): {e}")
        return False
    except Exception as e:
        logger.error(f"Error inesperado verificando password: {e}")
        return False


def get_password_hash(password: str) -> str:
    """
    Genera el hash de una contraseña usando bcrypt.
    SOLO usar para contraseñas de usuarios, nunca para tokens.
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_password_bytes.decode('utf-8')


def hash_token(token: str) -> str:
    """
    Genera un hash SHA-256 de un token (refresh token, etc.).
    SHA-256 no tiene límite de longitud, es determinista y seguro para tokens.
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def verify_token_hash(plain_token: str, token_hash: str) -> bool:
    """
    Verifica si un token plano coincide con su hash SHA-256 almacenado.
    """
    return hashlib.sha256(plain_token.encode('utf-8')).hexdigest() == token_hash
