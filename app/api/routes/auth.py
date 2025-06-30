import logging
from datetime import timedelta
from typing import Any, Optional
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # Para capturar errores de BD en la tarea

from app.api import deps
from app.schemas.token import Token
from app.schemas.usuario import Usuario as UsuarioSchema
from app.services.usuario import usuario_service
from app.services.login_log import login_log_service # Servicio ya modificado
from app.core import security
from app.core.config import settings
from app.models.usuario import Usuario as UsuarioModel
from app.db.session import SessionLocal # Para la tarea de fondo

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Función para Tarea de Fondo (Manejo Seguro de Sesión DB) ---
def log_login_attempt_task(
    username_attempt: Optional[str],
    success: bool, # Cambiado a bool, ya que el servicio espera bool
    ip_address: Optional[str],
    user_agent: Optional[str],
    fail_reason: Optional[str] = None,
    user_id: Optional[PyUUID] = None
):
    """
    Tarea de fondo para registrar un intento de login.
    Crea y cierra su propia sesión de base de datos.
    """
    db: Optional[Session] = None # Inicializar db a None
    try:
        db = SessionLocal() # Crear nueva sesión para la tarea de fondo
        login_log_service.log_attempt( # Este método ya no hace commit
            db=db,
            username_attempt=username_attempt,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            fail_reason=fail_reason,
            user_id=user_id
        )
        db.commit() # Commit aquí para la tarea de fondo
        logger.info(f"Intento de login (UsuarioIntento: '{username_attempt}', Exito: {success}) registrado en background.")
    except SQLAlchemyError as e_sql: # Capturar errores de BD específicamente
        logger.error(f"ERROR de SQLAlchemy en tarea de fondo log_login_attempt_task: {e_sql}", exc_info=True)
        if db: # Solo hacer rollback si la sesión db fue creada
            try:
                db.rollback()
                logger.info("Rollback realizado en tarea de fondo debido a SQLAlchemyError.")
            except Exception as e_rb:
                logger.error(f"Error durante el rollback en tarea de fondo: {e_rb}", exc_info=True)
    except Exception as e_gen:
        logger.error(f"ERROR general en tarea de fondo log_login_attempt_task: {e_gen}", exc_info=True)
        # No hay rollback aquí si la sesión no es de SQLAlchemy o ya se manejó arriba.
    finally:
        if db: # Solo cerrar si la sesión db fue creada
            try:
                db.close()
                logger.debug("Sesión de DB cerrada en tarea de fondo log_login_attempt_task.")
            except Exception as e_close:
                logger.error(f"Error al cerrar sesión de DB en tarea de fondo: {e_close}", exc_info=True)


# --- Endpoints ---
@router.post("/login/access-token", response_model=Token)
def login_access_token(
    request: Request, # Para obtener IP y User-Agent
    background_tasks: BackgroundTasks, # Para registrar el log en segundo plano
    db: Session = Depends(deps.get_db), # Sesión principal para autenticación
    form_data: OAuth2PasswordRequestForm = Depends() # Datos del formulario de login
) -> Any:
    """
    Endpoint de login estándar OAuth2.
    Recibe username y password en form data.
    Devuelve un Access Token JWT.
    Registra el intento de login en segundo plano.
    """
    ip_address = request.client.host if request.client else "N/A"
    user_agent = request.headers.get("user-agent", "N/A")
    username_attempt = form_data.username # Para logs y autenticación

    logger.info(f"Intento de login para usuario '{username_attempt}' desde IP {ip_address}")

    user = usuario_service.authenticate( # Este método no modifica la BD
        db, username=username_attempt, password=form_data.password
    )

    identified_user_id: Optional[PyUUID] = user.id if user else None
    login_success = False
    fail_reason_log: Optional[str] = None

    if not user:
        logger.warning(f"Login fallido (credenciales/usuario no encontrado) para '{username_attempt}' desde IP {ip_address}.")
        fail_reason_log = "Credenciales incorrectas o usuario no encontrado"
        # NO hacer db.commit() o db.rollback() aquí para la sesión principal.
        # La tarea de fondo manejará su propia transacción para el log.
        background_tasks.add_task(
            log_login_attempt_task,
            username_attempt=username_attempt,
            success=False,
            ip_address=ip_address,
            user_agent=user_agent,
            fail_reason=fail_reason_log,
            user_id=None # No se pudo identificar al usuario
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario o contraseña incorrectos.", # Mensaje genérico por seguridad
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario_service.is_active(user):
        logger.warning(f"Login fallido (usuario inactivo/bloqueado) para '{username_attempt}' (ID: {user.id}) desde IP {ip_address}.")
        fail_reason_log = "Usuario inactivo o bloqueado"
        login_success = False # Aunque se identificó, el login no es exitoso en términos de acceso
        background_tasks.add_task(
            log_login_attempt_task,
            username_attempt=username_attempt,
            success=False, # Login no exitoso
            ip_address=ip_address,
            user_agent=user_agent,
            fail_reason=fail_reason_log,
            user_id=identified_user_id
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario inactivo o bloqueado.")

    # --- Autenticación exitosa y usuario activo ---
    login_success = True
    logger.info(f"Login exitoso para usuario '{username_attempt}' (ID: {user.id}) desde IP {ip_address}.")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        subject=str(user.id), expires_delta=access_token_expires
    )

    # Registrar intento exitoso en segundo plano
    background_tasks.add_task(
        log_login_attempt_task,
        username_attempt=username_attempt,
        success=True,
        ip_address=ip_address,
        user_agent=user_agent,
        fail_reason=None, # Sin motivo de fallo
        user_id=identified_user_id
    )
    
    # Opcional: Actualizar último login del usuario.
    # Si se hace aquí, necesitaría commit.
    # if hasattr(usuario_service, 'update_last_login_timestamp'):
    #     try:
    #         usuario_service.update_last_login_timestamp(db, user=user)
    #         db.commit() # Commit para esta actualización específica del usuario
    #         db.refresh(user) # Refrescar el objeto usuario
    #         logger.info(f"Actualizado último login para usuario '{user.nombre_usuario}'.")
    #     except Exception as e_ull:
    #         db.rollback() # Rollback si la actualización del último login falla
    #         logger.error(f"Error al actualizar último login para usuario '{user.nombre_usuario}': {e_ull}", exc_info=True)
    #         # No fallar el login por esto, pero loguearlo.

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login/test-token", response_model=UsuarioSchema) # Usar schema renombrado
def test_token(current_user: UsuarioModel = Depends(deps.get_current_active_user)) -> Any:
    """
    Endpoint para probar si un access token es válido.
    Devuelve la información del usuario si el token es válido y el usuario está activo.
    """
    logger.debug(f"Token válido para usuario: {current_user.nombre_usuario} (ID: {current_user.id})")
    return current_user
