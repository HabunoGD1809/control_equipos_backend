import bcrypt
import logging 

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica si una contraseña plana coincide con una contraseña hasheada usando bcrypt.

    Args:
        plain_password: La contraseña en texto plano.
        hashed_password: La contraseña hasheada almacenada (como string).

    Returns:
        True si las contraseñas coinciden, False en caso contrario.
    """
    try:
        plain_password_bytes = plain_password.encode('utf-8')
        # Convierte la contraseña hasheada (almacenada como string) a bytes
        hashed_password_bytes = hashed_password.encode('utf-8')

        return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)
    except ValueError as e:
        # bcrypt.checkpw puede lanzar ValueError si el hash no es válido
        logger.error(f"Error verificando password (posiblemente hash inválido): {e}")
        return False
    except Exception as e:
        # Captura cualquier otro error inesperado
        logger.error(f"Error inesperado verificando password: {e}")
        return False


def get_password_hash(password: str) -> str:
    """
    Genera el hash de una contraseña usando bcrypt.

    Args:
        password: La contraseña en texto plano a hashear.

    Returns:
        El hash de la contraseña como string.
    """
    password_bytes = password.encode('utf-8')
    # Genera un salt
    salt = bcrypt.gensalt()
    hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)
    # Decodifica el hash (bytes) a string para almacenamiento
    return hashed_password_bytes.decode('utf-8')
