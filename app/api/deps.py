from typing import Generator, Annotated, Union, List, Set
from uuid import UUID
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import text
import logging

from app.core.config import settings
from app.db.session import SessionLocal

from app.models.usuario import Usuario
from app.models.rol import Rol

from app.schemas.token import TokenPayload
from app.services.usuario import usuario_service

logger = logging.getLogger(__name__)

# --- Constantes para Roles ---
ADMIN_ROLE_NAME = "admin"
SUPERVISOR_ROLE_NAME = "supervisor"
USER_ROLE_NAME = "usuario_regular" 

# --- Dependencia para la Sesión de Base de Datos ---
def get_db() -> Generator[Session, None, None]:
    """Dependency para obtener la sesión de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Dependencia para Autenticación ---
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login/access-token"
)

def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> Usuario:
    """Obtiene el usuario actual a partir del token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError) as e:
        logger.warning(f"Error de validación/JWT en token: {e}", exc_info=True)
        raise credentials_exception

    user = db.get(
        Usuario,
        token_data.sub, # sub es el ID del usuario (UUID)
        options=[
            selectinload(Usuario.rol).options(
                selectinload(Rol.permisos) # Carga los permisos del rol
            )
        ]
    )

    if not user:
        logger.warning(f"Usuario no encontrado para ID {token_data.sub} en token válido.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")

    # Logging de permisos cargados
    if user.rol and hasattr(user.rol, 'permisos'):
        user_permissions = {p.nombre for p in user.rol.permisos}
        logger.debug(f"get_current_user: User '{user.nombre_usuario}' (ID: {user.id}) with Role '{user.rol.nombre if user.rol else 'N/A'}' loaded. Permissions: {user_permissions}")
    elif user:
        logger.warning(f"get_current_user: User '{user.nombre_usuario}' (ID: {user.id}) loaded, but has no role or role has no permissions attribute properly loaded!")

    return user

def get_current_active_user(
    current_user: Usuario = Depends(get_current_user),
) -> Usuario:
    """Obtiene el usuario actual y verifica que esté activo."""
    if not usuario_service.is_active(current_user):
        logger.warning(f"Acceso denegado: Usuario inactivo/bloqueado {current_user.nombre_usuario} (ID: {current_user.id}).")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El usuario está inactivo o bloqueado.")
    return current_user


# ===== INICIO DE LA FUNCIÓN AÑADIDA =====
def user_has_permissions(user: Usuario, required_permissions: Union[List[str], Set[str]]) -> bool:
    """
    Función helper que verifica si un usuario tiene AL MENOS UNO de los permisos requeridos.
    Esta función no es una dependencia de FastAPI, sino una utilidad para ser llamada desde las rutas.
    """
    if not user or not user.rol or not hasattr(user.rol, 'permisos'):
        logger.warning(f"user_has_permissions: Usuario '{user.nombre_usuario if user else 'Desconocido'}' no tiene rol o permisos cargados para la verificación.")
        return False
    
    user_permissions = {p.nombre for p in user.rol.permisos}
    required_set = set(required_permissions)
    
    # Comprueba si hay alguna intersección entre los permisos del usuario y los requeridos
    return not required_set.isdisjoint(user_permissions)
# ===== FIN DE LA FUNCIÓN AÑADIDA =====


class PermissionChecker:
    """
    Clase para usar como dependencia de FastAPI para verificar permisos.
    Requiere que el usuario tenga AL MENOS UNO de los permisos de la lista (lógica OR).
    """
    def __init__(self, required_permissions: Union[str, List[str], Set[str]]):
        if isinstance(required_permissions, str):
            self.required_permissions_set = {required_permissions}
        else:
            self.required_permissions_set = set(required_permissions)
        
        if not self.required_permissions_set:
            logger.error("PermissionChecker inicializado con un conjunto de permisos vacío.")
            raise ValueError("El conjunto de permisos requeridos no puede estar vacío.")

    def __call__(self, request: Request, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_active_user)):
        """Verifica si el usuario actual tiene los permisos requeridos."""
        logger.debug(f"PermissionChecker: Verificando permisos para '{current_user.nombre_usuario}' en '{request.url.path}'. Requeridos (OR): {self.required_permissions_set}")
        
        try:
            # Establecer el ID de usuario para la auditoría en la sesión de la BD
            db.execute(text("SELECT control_equipos.set_audit_user(:user_id)"), {"user_id": current_user.id})
            logger.debug(f"Auditoría: Llamada a set_audit_user({current_user.id}) ejecutada.")
        except Exception as e:
            logger.error(f"Error al llamar a set_audit_user para auditoría: {e}", exc_info=True)
            # No fallar la request por esto, pero es un problema de auditoría.

        if not current_user.rol or not hasattr(current_user.rol, 'permisos'):
            logger.error(f"Error RBAC: Usuario '{current_user.nombre_usuario}' (ID: {current_user.id}) no tiene rol o permisos cargados. Rol: '{current_user.rol.nombre if current_user.rol else 'None'}'.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno al verificar permisos (configuración de rol/permisos).",
            )

        if not user_has_permissions(current_user, self.required_permissions_set):
            logger.warning(f"Acceso denegado a '{current_user.nombre_usuario}'. Rol: '{current_user.rol.nombre}'. Permisos requeridos (necesita uno de): {self.required_permissions_set}. Permisos del usuario: {{p.nombre for p in current_user.rol.permisos}}.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permiso para realizar esta acción."
            )
        
        logger.debug(f"PermissionChecker: Acceso concedido a '{current_user.nombre_usuario}'.")

# --- Funciones de conveniencia para roles (si se prefiere sobre permisos) ---
def require_admin(current_user: Usuario = Depends(get_current_active_user)):
    """Dependencia que requiere que el usuario activo tenga el rol 'admin'."""
    if not current_user.rol or current_user.rol.nombre != ADMIN_ROLE_NAME:
        logger.warning(f"Acceso denegado (Admin requerido) para {current_user.nombre_usuario} (Rol: {current_user.rol.nombre if current_user.rol else 'N/A'}).")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere rol de administrador.")

def require_supervisor(current_user: Usuario = Depends(get_current_active_user)):
    """Dependencia que requiere que el usuario activo tenga rol 'supervisor' o 'admin'."""
    roles_permitidos = {ADMIN_ROLE_NAME, SUPERVISOR_ROLE_NAME}
    if not current_user.rol or current_user.rol.nombre not in roles_permitidos:
        logger.warning(f"Acceso denegado (Supervisor/Admin requerido) para {current_user.nombre_usuario} (Rol: {current_user.rol.nombre if current_user.rol else 'N/A'}).")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere rol de supervisor o administrador.")

