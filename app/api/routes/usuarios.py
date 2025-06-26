import logging
from typing import Any, List
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.schemas import Usuario, UsuarioCreate, UsuarioUpdate, Msg
from app.services.usuario import usuario_service
from app.models import Usuario as UsuarioModel

logger = logging.getLogger(__name__)
router = APIRouter()

PERM_ADMIN_USUARIOS = "administrar_usuarios"

@router.post(
    "/",
    response_model=Usuario,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(deps.PermissionChecker(PERM_ADMIN_USUARIOS))],
    summary="Crear un nuevo Usuario",
    response_description="El usuario creado."
)
def create_usuario(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UsuarioCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user)
) -> Any:
    """
    Crea un nuevo usuario en el sistema.
    Requiere el permiso: `administrar_usuarios`.
    """
    logger.info(f"Intento de creación de usuario '{user_in.nombre_usuario}' por admin '{current_user.nombre_usuario}'")
    
    try:
        user = usuario_service.create(db=db, obj_in=user_in)
        # CORRECCIÓN: Se realiza commit y refresh aquí para asegurar que los datos
        # generados por la BD (como el ID) se carguen en el objeto antes de retornarlo.
        db.commit()
        db.refresh(user)
        db.refresh(user, attribute_names=['rol']) # Cargar explícitamente la relación de rol
        
        logger.info(f"Usuario '{user.nombre_usuario}' (ID: {user.id}) creado exitosamente por '{current_user.nombre_usuario}'.")
        return user
    except HTTPException as http_exc:
        db.rollback()
        logger.warning(f"Error HTTP al crear usuario '{user_in.nombre_usuario}': {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        # Este bloque maneja errores de la base de datos, como duplicados.
        # El servicio ya debería haber validado esto, pero es una salvaguarda.
        error_detail = str(getattr(e, 'orig', e)).lower()
        if "usuarios_nombre_usuario_key" in error_detail or "uq_usuarios_nombre_usuario" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese nombre de usuario.")
        if "usuarios_email_key" in error_detail or "uq_usuarios_email" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese correo electrónico.")
        logger.error(f"Error de integridad no manejado al crear usuario: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear el usuario.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando usuario '{user_in.nombre_usuario}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el usuario.")


@router.get(
    "/me",
    response_model=Usuario,
    summary="Obtener perfil del usuario actual",
    response_description="Información del usuario autenticado."
)
def read_usuario_me(
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Obtiene la información del usuario que realiza la petición (autenticado)."""
    return current_user


@router.put(
    "/me",
    response_model=Usuario,
    summary="Actualizar perfil del usuario actual",
    response_description="Información actualizada del usuario autenticado."
)
def update_usuario_me(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UsuarioUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza la información del propio usuario autenticado.
    No permite cambiar rol o estado de bloqueo por esta vía.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' actualizando su propio perfil.")
    
    update_data = user_in.model_dump(exclude_unset=True)
    
    restricted_fields = ["rol_id", "bloqueado", "nombre_usuario"]
    for field in restricted_fields:
        if field in update_data:
            logger.warning(f"Usuario '{current_user.nombre_usuario}' intentó modificar campo restringido '{field}' en /me. Será ignorado.")
            del update_data[field]
    
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se proporcionaron datos válidos para actualizar.")

    try:
        updated_user = usuario_service.update(db=db, db_obj=current_user, obj_in=update_data)
        db.commit()
        db.refresh(updated_user)
        logger.info(f"Perfil de '{current_user.nombre_usuario}' actualizado exitosamente.")
        return updated_user
    except HTTPException as http_exc:
        db.rollback()
        logger.warning(f"Error HTTP al actualizar perfil de '{current_user.nombre_usuario}': {http_exc.detail}")
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando perfil de '{current_user.nombre_usuario}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el perfil.")


@router.get(
    "/",
    response_model=List[Usuario],
    dependencies=[Depends(deps.PermissionChecker(PERM_ADMIN_USUARIOS))],
    summary="Listar todos los Usuarios",
    response_description="Una lista de usuarios."
)
def read_usuarios(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene una lista de todos los usuarios registrados.
    Requiere el permiso: `administrar_usuarios`.
    """
    logger.info(f"Admin '{current_user.nombre_usuario}' listando usuarios.")
    users = usuario_service.get_multi(db, skip=skip, limit=limit)
    return users


@router.get(
    "/{user_id}",
    response_model=Usuario,
    dependencies=[Depends(deps.PermissionChecker(PERM_ADMIN_USUARIOS))],
    summary="Obtener un Usuario por ID",
    response_description="Información detallada del usuario."
)
def read_usuario_by_id(
    user_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene la información de un usuario específico por su ID.
    Requiere el permiso: `administrar_usuarios`.
    """
    logger.info(f"Admin '{current_user.nombre_usuario}' solicitando usuario ID: {user_id}")
    user = usuario_service.get_or_404(db=db, id=user_id)
    return user


@router.put(
    "/{user_id}",
    response_model=Usuario,
    dependencies=[Depends(deps.PermissionChecker(PERM_ADMIN_USUARIOS))],
    summary="Actualizar un Usuario por ID (Admin)",
    response_description="Información actualizada del usuario."
)
def update_usuario(
    *,
    db: Session = Depends(deps.get_db),
    user_id: PyUUID,
    user_in: UsuarioUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza la información de un usuario específico (acción de administrador).
    Requiere el permiso: `administrar_usuarios`.
    """
    logger.info(f"Admin '{current_user.nombre_usuario}' actualizando usuario ID: {user_id}")
    user_to_update = usuario_service.get_or_404(db, id=user_id)

    if user_to_update.id == current_user.id:
        update_data = user_in.model_dump(exclude_unset=True)
        if "rol_id" in update_data or "bloqueado" in update_data:
            logger.warning(f"Admin '{current_user.nombre_usuario}' intentó auto-modificar rol/bloqueo por vía general. Denegado.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Un administrador no puede cambiar su propio rol o estado de bloqueo por esta vía.")

    try:
        updated_user = usuario_service.update(db=db, db_obj=user_to_update, obj_in=user_in)
        db.commit()
        db.refresh(updated_user)
        logger.info(f"Usuario '{updated_user.nombre_usuario}' (ID: {user_id}) actualizado por '{current_user.nombre_usuario}'.")
        return updated_user
    except HTTPException as http_exc:
        db.rollback()
        logger.warning(f"Error HTTP al actualizar usuario ID {user_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando usuario ID {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar usuario.")

@router.delete(
    "/{user_id}",
    response_model=Msg,
    dependencies=[Depends(deps.PermissionChecker(PERM_ADMIN_USUARIOS))],
    status_code=status.HTTP_200_OK,
    summary="Eliminar un Usuario por ID (Admin)",
    response_description="Mensaje de confirmación."
)
def delete_usuario(
    *,
    db: Session = Depends(deps.get_db),
    user_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Elimina un usuario específico del sistema.
    Un administrador no puede eliminarse a sí mismo.
    Requiere el permiso: `administrar_usuarios`.
    """
    logger.warning(f"Admin '{current_user.nombre_usuario}' intentando eliminar usuario ID: {user_id}.")

    if user_id == current_user.id:
        logger.error(f"Admin '{current_user.nombre_usuario}' intentó eliminarse a sí mismo. Operación denegada.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes eliminar tu propia cuenta de administrador.")
    
    try:
        user_to_delete = usuario_service.remove(db=db, id=user_id)
        db.commit()
        logger.info(f"Usuario '{user_to_delete.nombre_usuario}' (ID: {user_id}) eliminado por '{current_user.nombre_usuario}'.")
        return {"msg": f"Usuario '{user_to_delete.nombre_usuario}' (ID: {user_id}) eliminado correctamente."}
    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except IntegrityError:
        db.rollback()
        logger.error(f"Error de integridad al intentar eliminar usuario ID: {user_id}. Probablemente tiene datos asociados.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede eliminar el usuario porque tiene registros asociados."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando usuario ID {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar el usuario.")
