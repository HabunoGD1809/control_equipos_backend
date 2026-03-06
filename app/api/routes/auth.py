import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.api import deps
from app.core import security
from app.core.password import verify_password, verify_token_hash, hash_token
from app.db.session import SessionLocal
from app.models.usuario import Usuario as UsuarioModel
from app.models.refresh_token import RefreshToken as RefreshTokenModel
from app.models.notificacion import Notificacion
from app.schemas.common import Msg
from app.schemas.token import Token, RefreshToken as RefreshTokenSchema, RefreshTokenCreate
from app.schemas.password import (
    PasswordChange, PasswordResetRequest, PasswordResetResponse, PasswordResetConfirm
)
from app.services.usuario import usuario_service
from app.services.login_log import login_log_service
from app.services.refresh_token import refresh_token_service

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Funcion para Tarea de Fondo (Manejo Seguro de Sesion DB) ---
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
    Crea y cierra su propia sesion de base de datos para operar de forma independiente.
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
    except IntegrityError as e:
        logger.warning(
            f"No se pudo registrar el intento de login para '{username_attempt}'. "
            f"El usuario asociado (ID: {user_id}) probablemente fue eliminado. Error: {e}"
        )
        if db:
            db.rollback()
    except SQLAlchemyError as e_sql:
        logger.error(f"ERROR de SQLAlchemy en tarea de fondo log_login_attempt_task: {e_sql}", exc_info=True)
        if db:
            db.rollback()
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
    Endpoint de login. Crea una nueva sesion y devuelve tokens.
    """
    ip_address = request.client.host if request.client else "N/A"
    user_agent = request.headers.get("user-agent", "N/A")
    username_attempt = form_data.username
    logger.info(f"Intento de login para usuario '{username_attempt}' desde IP {ip_address}")

    user = usuario_service.authenticate(
        db, username_or_email=username_attempt, password=form_data.password
    )

    if not user or not usuario_service.is_active(user):
        fail_reason = "Usuario inactivo o bloqueado" if user else "Credenciales incorrectas"
        user_id = user.id if user else None
        background_tasks.add_task(
            log_login_attempt_task,
            username_attempt=username_attempt, success=False, ip_address=ip_address,
            user_agent=user_agent, fail_reason=fail_reason, user_id=user_id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario o contrasena incorrectos, o usuario bloqueado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"Login exitoso para usuario '{username_attempt}'.")

    try:
        access_token = security.create_access_token(subject=user.id)
        refresh_token_str = security.create_refresh_token(subject=user.id)

        token_create_schema = RefreshTokenCreate(token=refresh_token_str, usuario_id=user.id)
        refresh_token_service.create_token(
            db, obj_in=token_create_schema, user_agent=user_agent, ip_address=ip_address
        )
        usuario_service.handle_successful_login(db, user=user)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error critico al crear sesion para {user.nombre_usuario}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor al procesar el login.")

    background_tasks.add_task(
        log_login_attempt_task,
        username_attempt=username_attempt, success=True,
        ip_address=ip_address, user_agent=user_agent, user_id=user.id
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "bearer"
    }


@router.post("/refresh-token", response_model=Token, summary="Refresca un Access Token")
def refresh_access_token(
    request: Request,
    token_data: RefreshTokenSchema,
    db: Session = Depends(deps.get_db),
):
    """
    Obtiene un nuevo par de tokens a partir de un refresh token valido,
    implementando la rotacion de tokens para mayor seguridad.
    """
    refresh_token_str = token_data.refresh_token
    payload = security.decode_refresh_token(refresh_token_str)

    if not payload or not payload.sub:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de refresco invalido o expirado")

    user = usuario_service.get(db, id=payload.sub)

    if not user or not usuario_service.is_active(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no encontrado o inactivo")

    # Buscar el token valido usando SHA-256 (no bcrypt)
    valid_token_found = None
    for db_token in user.refresh_tokens:
        if (
            db_token.revoked_at is None and
            db_token.expires_at > datetime.now(timezone.utc) and
            verify_token_hash(refresh_token_str, db_token.token_hash)
        ):
            valid_token_found = db_token
            break

    if not valid_token_found:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de refresco no es valido o ha sido revocado.")

    try:
        # Revocar el token viejo (pasamos el plain_token para verificacion interna)
        refresh_token_service.revoke_token(db, token_obj=valid_token_found, plain_token=refresh_token_str)

        # Crear un nuevo par de tokens
        new_access_token = security.create_access_token(subject=user.id)
        new_refresh_token_str = security.create_refresh_token(subject=user.id)

        ip_address = request.client.host if request.client else "N/A"
        user_agent = request.headers.get("user-agent", "N/A")
        new_token_create = RefreshTokenCreate(token=new_refresh_token_str, usuario_id=user.id)
        refresh_token_service.create_token(
            db, obj_in=new_token_create, user_agent=user_agent, ip_address=ip_address
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error critico al rotar el refresh token para {user.nombre_usuario}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor al refrescar el token.")

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token_str,
        "token_type": "bearer",
    }


@router.post("/logout", status_code=status.HTTP_200_OK, summary="Cerrar sesion e invalidar token")
def logout(
    token_data: RefreshTokenSchema,
    db: Session = Depends(deps.get_db)
):
    refresh_token_str = token_data.refresh_token
    payload = security.decode_refresh_token(refresh_token_str)

    if not payload or not payload.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido. Asegurate de enviar el Refresh Token, no el Access Token."
        )

    active_tokens = db.query(RefreshTokenModel).filter(
        RefreshTokenModel.usuario_id == payload.sub,
        RefreshTokenModel.revoked_at.is_(None)
    ).all()

    # Buscar el token usando SHA-256 (no bcrypt)
    valid_token_found = None
    for db_token in active_tokens:
        if verify_token_hash(refresh_token_str, db_token.token_hash):
            valid_token_found = db_token
            break

    if not valid_token_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La sesion ya fue cerrada previamente o el token no existe."
        )

    refresh_token_service.revoke_token(db, token_obj=valid_token_found, plain_token=refresh_token_str)
    db.commit()
    logger.info(f"Token revocado exitosamente durante el logout para usuario ID {payload.sub}.")

    return {"msg": "Sesion cerrada exitosamente."}


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permite al usuario logueado cambiar su contrasena"
)
def change_password_logged_in(
    *,
    password_data: PasswordChange,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user)
):
    """
    Permite al usuario que ha iniciado sesion cambiar su propia contrasena.
    Debe proporcionar su contrasena actual y la nueva.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' ha solicitado cambiar su contrasena.")
    try:
        usuario_service.change_password(db=db, user=current_user, password_data=password_data)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(
            f"Error al cambiar la contrasena para '{current_user.nombre_usuario}'. Error: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error interno al cambiar la contrasena."
        )
    return None


@router.post(
    "/password-recovery/request-reset",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_200_OK,
    summary="[Admin] Inicia el reseteo de contrasena para un usuario"
)
def request_password_reset(
    request_data: PasswordResetRequest,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.require_admin),
):
    """
    Endpoint solo para administradores.
    Inicia el proceso de reseteo de contrasena para un usuario especifico y le notifica.
    """
    logger.info(
        f"Admin '{current_user.nombre_usuario}' esta solicitando reseteo de "
        f"contrasena para usuario '{request_data.username}'."
    )
    try:
        user = usuario_service.initiate_password_reset(db, username=request_data.username)

        nueva_notificacion = Notificacion(
            usuario_id=user.id,
            mensaje=f"Un administrador ({current_user.nombre_usuario}) ha iniciado el reseteo de tu contrasena. Se requiere tu accion.",
            tipo="alerta",
            urgencia=1,
            referencia_id=user.id,
            referencia_tabla="usuarios"
        )
        db.add(nueva_notificacion)
        db.commit()
        db.refresh(user)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(
            f"Error al iniciar el reseteo de contrasena para '{request_data.username}'. "
            f"Admin: '{current_user.nombre_usuario}'. Error: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error al procesar la solicitud."
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
    summary="Confirma y establece una nueva contrasena"
)
def confirm_password_reset(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(deps.get_db),
):
    """
    Permite a un usuario establecer una nueva contrasena utilizando el token
    que le fue proporcionado por un administrador.
    """
    logger.info(f"Intento de confirmar reseteo de contrasena para usuario '{reset_data.username}'.")
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
            f"Error al confirmar el reseteo de contrasena para '{reset_data.username}'. Error: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrio un error al resetear la contrasena."
        )

    return Msg(msg="La contrasena ha sido actualizada exitosamente.")
