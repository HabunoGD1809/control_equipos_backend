import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID

from fastapi import APIRouter, Body, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.schemas.usuario import Usuario, UsuarioCreate, UsuarioUpdate # Usaremos UsuarioUpdate también para /me
from app.schemas.common import Msg
from app.services.usuario import usuario_service
from app.models.usuario import Usuario as UsuarioModel

logger = logging.getLogger(__name__)
router = APIRouter()

PERM_ADMIN_USUARIOS = "administrar_usuarios"

@router.post("/",
             response_model=Usuario,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_USUARIOS]))],
             summary="Crear un nuevo Usuario",
             response_description="El usuario creado.")
def create_usuario(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UsuarioCreate,
    current_user_admin: UsuarioModel = Depends(deps.get_current_active_user)
) -> Any:
    """
    Crea un nuevo usuario en el sistema.
    Requiere el permiso: `administrar_usuarios`.
    """
    logger.info(f"Intento de creación de usuario '{user_in.nombre_usuario}' por admin '{current_user_admin.nombre_usuario}'")
    try:
        user = usuario_service.create(db=db, obj_in=user_in)
        db.commit()
        db.refresh(user)
        db.refresh(user, attribute_names=['rol'])
        logger.info(f"Usuario '{user.nombre_usuario}' (ID: {user.id}) creado exitosamente por '{current_user_admin.nombre_usuario}'.")
        return user
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al crear usuario '{user_in.nombre_usuario}': {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        pgcode = getattr(getattr(e, 'orig', None), 'pgcode', None)
        logger.error(f"Error de integridad al crear usuario '{user_in.nombre_usuario}'. PGCode: {pgcode}. Detalle: {error_detail}", exc_info=True)
        if pgcode == '23505': # unique_violation
            if "usuarios_nombre_usuario_key" in error_detail or "uq_usuarios_nombre_usuario" in error_detail:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: El nombre de usuario ya existe.")
            if "usuarios_email_key" in error_detail or "uq_usuarios_email" in error_detail:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: El correo electrónico ya existe.")
        elif pgcode == '23503': # foreign_key_violation
             if ("fk_usuarios_rol" in error_detail or "usuarios_rol_id_fkey" in error_detail) and user_in.rol_id:
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"El Rol con ID '{user_in.rol_id}' no fue encontrado.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear el usuario.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando usuario '{user_in.nombre_usuario}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el usuario.")


@router.get("/me",
            response_model=Usuario,
            summary="Obtener perfil del usuario actual",
            response_description="Información del usuario autenticado.")
def read_usuario_me(
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Obtiene la información del usuario que realiza la petición (autenticado)."""
    return current_user


@router.put("/me",
            response_model=Usuario,
            summary="Actualizar perfil del usuario actual",
            response_description="Información actualizada del usuario autenticado.")
def update_usuario_me(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UsuarioUpdate, # Usamos UsuarioUpdate, y filtraremos los campos no permitidos
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza la información del propio usuario autenticado.
    No permite cambiar rol, estado bloqueado o intentos fallidos por esta vía.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' (ID: {current_user.id}) actualizando su propio perfil.")
    
    update_data_dict = user_in.model_dump(exclude_unset=True)
    
    # Campos que un usuario NO puede modificarse a sí mismo explícitamente.
    # El schema UsuarioUpdate permite estos campos, pero aquí los restringimos para /me.
    restricted_fields_for_me = ["rol_id", "bloqueado", "intentos_fallidos", "requiere_cambio_contrasena"]
    
    # Si se intenta modificar un campo restringido, se lanza un error o se ignora.
    # En este caso, vamos a ignorarlos silenciosamente para no romper el flujo si el frontend envía el objeto completo.
    # Si se prefiere un error explícito, se podría lanzar una HTTPException aquí.
    
    valid_update_data = {}
    for key, value in update_data_dict.items():
        if key not in restricted_fields_for_me:
            valid_update_data[key] = value
        elif key in update_data_dict: # Solo loguear si se intentó enviar explícitamente
            logger.warning(f"Usuario '{current_user.nombre_usuario}' intentó modificar campo restringido '{key}' en su perfil. Será ignorado para esta operación.")

    if "nombre_usuario" in valid_update_data and valid_update_data["nombre_usuario"] != current_user.nombre_usuario:
        logger.warning(f"Usuario '{current_user.nombre_usuario}' intentó modificar su nombre de usuario a '{valid_update_data['nombre_usuario']}'. Esta operación no está permitida en /me. Será ignorado.")
        del valid_update_data["nombre_usuario"]

    # Si después de filtrar campos no permitidos, no queda nada, o solo campos vacíos.
    if not valid_update_data or all(value is None for value in valid_update_data.values()):
        logger.info(f"Usuario '{current_user.nombre_usuario}' intentó actualizar perfil sin datos válidos o modificables permitidos para /me.")
        # Aquí podrías devolver el usuario actual sin cambios o un error 400.
        # Devolver el usuario actual sin cambios puede ser confuso si el frontend espera un 200 solo si hubo cambio.
        # Un 400 es más explícito si no hay nada que hacer.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se proporcionaron datos válidos para actualizar el perfil.")

    try:
        # El servicio `usuario_service.update` se encargará de hashear la contraseña si se provee
        # y de validar la unicidad del email si cambia.
        updated_user = usuario_service.update(db=db, db_obj=current_user, obj_in=valid_update_data)
        db.commit()
        db.refresh(updated_user)
        db.refresh(updated_user, attribute_names=['rol']) # Asegurar carga del rol
        logger.info(f"Usuario '{current_user.nombre_usuario}' actualizó su perfil exitosamente.")
        return updated_user
    except HTTPException as http_exc:
        # Si el servicio lanza una excepción por validación (ej: email duplicado)
        logger.warning(f"Error HTTP al actualizar perfil de '{current_user.nombre_usuario}': {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        pgcode = getattr(getattr(e, 'orig', None), 'pgcode', None)
        logger.error(f"Error de integridad actualizando perfil de '{current_user.nombre_usuario}'. PGCode: {pgcode}. Detalle: {error_detail}", exc_info=True)
        if pgcode == '23505': # unique_violation
            if "usuarios_email_key" in error_detail or "uq_usuarios_email" in error_detail:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: El correo electrónico ya está en uso.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar el perfil.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando perfil de '{current_user.nombre_usuario}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el perfil.")


@router.get("/",
            response_model=List[Usuario],
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_USUARIOS]))],
            summary="Listar todos los Usuarios",
            response_description="Una lista de usuarios.")
def read_usuarios(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user_admin: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene una lista de todos los usuarios registrados.
    Requiere el permiso: `administrar_usuarios`.
    """
    logger.info(f"Admin '{current_user_admin.nombre_usuario}' listando usuarios.")
    users = usuario_service.get_multi(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}",
            response_model=Usuario,
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_USUARIOS]))],
            summary="Obtener un Usuario por ID",
            response_description="Información detallada del usuario.")
def read_usuario_by_id(
    user_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user_admin: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene la información de un usuario específico por su ID.
    Requiere el permiso: `administrar_usuarios`.
    """
    logger.info(f"Admin '{current_user_admin.nombre_usuario}' solicitando usuario ID: {user_id}")
    user = usuario_service.get_or_404(db, id=user_id)
    return user


@router.put("/{user_id}",
            response_model=Usuario,
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_USUARIOS]))],
            summary="Actualizar un Usuario por ID (Admin)",
            response_description="Información actualizada del usuario.")
def update_usuario(
    *,
    db: Session = Depends(deps.get_db),
    user_id: PyUUID,
    user_in: UsuarioUpdate,
    current_user_admin: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza la información de un usuario específico (acción de administrador).
    Permite cambiar rol, estado de bloqueo, etc.
    Requiere el permiso: `administrar_usuarios`.
    """
    logger.info(f"Admin '{current_user_admin.nombre_usuario}' actualizando usuario ID: {user_id} con datos: {user_in.model_dump(exclude_unset=True)}")
    user_db = usuario_service.get_or_404(db, id=user_id)

    if user_db.id == current_user_admin.id:
        # Un admin no debería poder cambiar su propio rol o bloquearse a sí mismo por esta vía general.
        # Podría haber endpoints específicos para estas acciones con más salvaguardas.
        update_data_admin_self = user_in.model_dump(exclude_unset=True)
        if "rol_id" in update_data_admin_self and update_data_admin_self["rol_id"] != user_db.rol_id:
            logger.warning(f"Admin '{current_user_admin.nombre_usuario}' intentó cambiar su propio rol. Operación denegada por esta vía.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Un administrador no puede cambiar su propio rol usando este endpoint.")
        if "bloqueado" in update_data_admin_self and update_data_admin_self["bloqueado"] is True and not user_db.bloqueado:
            logger.warning(f"Admin '{current_user_admin.nombre_usuario}' intentó bloquearse a sí mismo. Operación denegada.")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Un administrador no puede bloquearse a sí mismo.")

    try:
        updated_user = usuario_service.update(db=db, db_obj=user_db, obj_in=user_in)
        db.commit()
        db.refresh(updated_user)
        db.refresh(updated_user, attribute_names=['rol'])
        logger.info(f"Usuario '{updated_user.nombre_usuario}' (ID: {user_id}) actualizado exitosamente por '{current_user_admin.nombre_usuario}'.")
        return updated_user
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al actualizar usuario ID {user_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        pgcode = getattr(getattr(e, 'orig', None), 'pgcode', None)
        logger.error(f"Error de integridad al actualizar usuario ID {user_id}. PGCode: {pgcode}. Detalle: {error_detail}", exc_info=True)
        if pgcode == '23505':
            if "usuarios_nombre_usuario_key" in error_detail or "uq_usuarios_nombre_usuario" in error_detail:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: El nombre de usuario ya está en uso.")
            if "usuarios_email_key" in error_detail or "uq_usuarios_email" in error_detail:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: El correo electrónico ya está en uso.")
        elif pgcode == '23503':
             if ("fk_usuarios_rol" in error_detail or "usuarios_rol_id_fkey" in error_detail) and user_in.rol_id:
                 raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"El Rol con ID '{user_in.rol_id}' no fue encontrado.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar el usuario.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando usuario ID {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el usuario.")


@router.delete("/{user_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_USUARIOS]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar un Usuario por ID (Admin)",
               response_description="Mensaje de confirmación.")
def delete_usuario(
    *,
    db: Session = Depends(deps.get_db),
    user_id: PyUUID,
    current_user_admin: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Elimina un usuario específico del sistema.
    Un administrador no puede eliminarse a sí mismo por esta vía.
    Requiere el permiso: `administrar_usuarios`.
    """
    logger.warning(f"Admin '{current_user_admin.nombre_usuario}' intentando eliminar usuario ID: {user_id}.")

    if user_id == current_user_admin.id:
        logger.error(f"Admin '{current_user_admin.nombre_usuario}' intentó eliminarse a sí mismo (ID: {user_id}). Operación no permitida.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes eliminar tu propia cuenta de administrador.")

    user_to_delete = usuario_service.get_or_404(db, id=user_id)
    user_nombre_para_log = user_to_delete.nombre_usuario
    
    try:
        usuario_service.remove(db=db, id=user_id)
        db.commit()
        logger.info(f"Usuario '{user_nombre_para_log}' (ID: {user_id}) eliminado exitosamente por '{current_user_admin.nombre_usuario}'.")
        return {"msg": f"Usuario '{user_nombre_para_log}' eliminado correctamente."}
    except HTTPException as http_exc:
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al eliminar usuario '{user_nombre_para_log}' (ID: {user_id}): {error_detail}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede eliminar el usuario '{user_nombre_para_log}' porque tiene registros asociados que lo referencian."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando usuario '{user_nombre_para_log}' (ID: {user_id}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar el usuario.")
