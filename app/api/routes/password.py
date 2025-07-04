import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.models.usuario import Usuario as UsuarioModel
from app.schemas.password import (
    PasswordResetRequest, PasswordResetResponse, PasswordResetConfirm
)
from app.schemas.common import Msg
from app.services.usuario import usuario_service

router = APIRouter()
logger = logging.getLogger(__name__)

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
    Genera un token temporal y lo devuelve en la respuesta para que el
    administrador pueda comunicárselo al usuario de forma segura.
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
        # Esto no debería ocurrir si no hay excepción, pero es una salvaguarda
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
