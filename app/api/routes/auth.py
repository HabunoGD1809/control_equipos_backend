import logging
from datetime import timedelta
from typing import Any, Optional, Callable
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.usuario import Usuario as UsuarioModel
from app.schemas.common import Msg
from app.schemas.token import Token
from app.schemas.usuario import Usuario as UsuarioSchema
from app.schemas.password import (
    PasswordResetRequest, PasswordResetResponse, PasswordResetConfirm
)
from app.services.usuario import usuario_service
from app.services.login_log import login_log_service

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Función para Tarea de Fondo (Manejo Seguro de Sesión DB) ---
def log_login_attempt_task(
    username_attempt: Optional[str],
    success: bool,
    ip_address: Optional[str],
    user_agent: Optional[str],
    fail_reason: Optional[str] = None,
    user_id: Optional[PyUUID] = None
):
    """
    Tarea de fondo para registrar un intento de login.
    Crea y cierra su propia sesión de base de datos para operar de forma independiente.
    Esta función está diseñada para ser resiliente y no fallar si el usuario
    es eliminado antes de que el log se escriba.
    """
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        
        login_log_service.log_attempt(
            db=db,
            username_attempt=username_attempt,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            fail_reason=fail_reason,
            user_id=user_id
        )
        
        db.commit()
        logger.info(f"Intento de login (UsuarioIntento: '{username_attempt}', Exito: {success}) registrado en background.")

    # Capturamos específicamente el error de integridad (ForeignKeyViolation).
    # Esto sucede en las pruebas si el usuario es eliminado antes de que esta tarea se complete.
    # Al capturarlo, evitamos que el error se propague y registramos una advertencia en su lugar.
    except IntegrityError as e:
        logger.warning(
            f"No se pudo registrar el intento de login para '{username_attempt}'. "
            f"El usuario asociado (ID: {user_id}) probablemente fue eliminado antes de que el log pudiera ser escrito. "
            f"Este es un comportamiento esperado en tests y no es un error crítico. Error original: {e}"
        )
        if db:
            db.rollback()
    
    # Capturamos otros errores de base de datos de forma general.
    except SQLAlchemyError as e_sql:
        logger.error(f"ERROR de SQLAlchemy en tarea de fondo log_login_attempt_task: {e_sql}", exc_info=True)
        if db:
            db.rollback()
    
    # Capturamos cualquier otra excepción inesperada.
    except Exception as e_gen:
        logger.error(f"ERROR general en tarea de fondo log_login_attempt_task: {e_gen}", exc_info=True)
        if db:
            db.rollback()
    finally:
        if db:
            db.close()

# --- Rutas de Login ---
@router.post("/login/access-token", response_model=Token)
def login_access_token(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    Endpoint de login estándar OAuth2.
    """
    ip_address = request.client.host if request.client else "N/A"
    user_agent = request.headers.get("user-agent", "N/A")
    username_attempt = form_data.username

    logger.info(f"Intento de login para usuario '{username_attempt}' desde IP {ip_address}")

    user = usuario_service.authenticate(
        db, username=username_attempt, password=form_data.password
    )

    if not user:
        logger.warning(f"Login fallido (credenciales/usuario no encontrado) para '{username_attempt}'.")
        background_tasks.add_task(
            log_login_attempt_task,
            username_attempt=username_attempt,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            fail_reason="Credenciales incorrectas o usuario no encontrado",
            user_id=None
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario_service.is_active(user):
        logger.warning(f"Login fallido (usuario inactivo/bloqueado) para '{username_attempt}'.")
        background_tasks.add_task(
            log_login_attempt_task,
            username_attempt=username_attempt,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            fail_reason="Usuario inactivo o bloqueado",
            user_id=user.id
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario inactivo o bloqueado.")

    logger.info(f"Login exitoso para usuario '{username_attempt}'.")

    try:
        usuario_service.handle_successful_login(db, user=user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        logger.error(f"Error al guardar datos de login exitoso para {user.nombre_usuario}: {e}")
        db.rollback()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=str(user.id), expires_delta=access_token_expires
    )

    background_tasks.add_task(
        log_login_attempt_task,
        username_attempt=username_attempt,
        success=True,
        ip_address=ip_address,
        user_agent=user_agent,
        fail_reason=None,
        user_id=user.id
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login/test-token", response_model=UsuarioSchema)
def test_token(current_user: UsuarioModel = Depends(deps.get_current_active_user)) -> Any:
    """
    Endpoint para probar si un access token es válido.
    """
    logger.debug(f"Token válido para usuario: {current_user.nombre_usuario} (ID: {current_user.id})")
    return current_user

# --- Rutas de Reseteo de Contraseña ---

@router.post(
    "/password-recovery/request-reset",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="[Admin] Inicia el reseteo de contraseña para un usuario"
)
def request_password_reset(
    request_data: PasswordResetRequest,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.require_admin),
):
    """
    **Endpoint solo para administradores.**

    Inicia el proceso de reseteo de contraseña para un usuario específico.
    """
    logger.info(
        f"Admin '{current_user.nombre_usuario}' está solicitando reseteo de "
        f"contraseña para usuario '{request_data.username}'."
    )
    try:
        user = usuario_service.initiate_password_reset(db, username=request_data.username)
        db.commit()
        db.refresh(user)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(
            f"Error al iniciar el reseteo de contraseña para '{request_data.username}'. "
            f"Admin: '{current_user.nombre_usuario}'. Error: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error al procesar la solicitud."
        )
    
    if not user.token_temporal or not user.token_expiracion:
        raise HTTPException(status_code=500, detail="Error al generar el token.")

    return PasswordResetResponse(
        username=user.nombre_usuario,
        reset_token=user.token_temporal,
        expires_at=user.token_expiracion.isoformat()
    )


@router.post(
    "/password-recovery/confirm-reset",
    response_model=Msg,
    status_code=status.HTTP_200_OK,
    summary="Confirma y establece una nueva contraseña"
)
def confirm_password_reset(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(deps.get_db),
):
    """
    **Endpoint público.**

    Permite a un usuario establecer una nueva contraseña utilizando el token
    que le fue proporcionado por un administrador.
    """
    logger.info(f"Intento de confirmar reseteo de contraseña para usuario '{reset_data.username}'.")
    try:
        usuario_service.confirm_password_reset(
            db,
            username=reset_data.username,
            token=reset_data.token,
            new_password=reset_data.new_password
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(
            f"Error al confirmar el reseteo de contraseña para '{reset_data.username}'. Error: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error al resetear la contraseña."
        )
        
    return Msg(msg="La contraseña ha sido actualizada exitosamente.")
