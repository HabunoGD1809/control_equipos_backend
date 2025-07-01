import logging
from typing import Any, List
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.schemas.rol import Rol, RolCreate, RolUpdate
from app.schemas.permiso import Permiso as PermisoSchema
from app.schemas.common import Msg
from app.services.rol import rol_service
from app.services.permiso import permiso_service
from app.models.usuario import Usuario as UsuarioModel

logger = logging.getLogger(__name__)
router = APIRouter()

# Permisos (ajustar según los nombres exactos en la BD)
PERM_ADMIN_ROLES = "administrar_roles"
PERM_ADMIN_USUARIOS = "administrar_usuarios"

# ==============================================================================
# Endpoints para ROLES
# ==============================================================================

@router.post("/roles/",
             response_model=Rol,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_ROLES]))],
             summary="Crear un nuevo Rol",
             response_description="El rol creado con sus permisos iniciales.")
def create_rol(
    *,
    db: Session = Depends(deps.get_db),
    rol_in: RolCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Crea un nuevo rol y opcionalmente le asigna permisos iniciales.
    Requiere el permiso: `administrar_roles`.
    """
    logger.info(f"Intento de creación de rol '{rol_in.nombre}' por usuario {current_user.nombre_usuario}")
    try:
        # El servicio .create() ya no hace commit y maneja validaciones previas de unicidad.
        rol = rol_service.create(db=db, obj_in=rol_in)
        db.commit()
        db.refresh(rol)
        logger.info(f"Rol '{rol.nombre}' (ID: {rol.id}) creado exitosamente por {current_user.nombre_usuario}.")
        return rol
    except HTTPException as http_exc:
        # Si el servicio lanza HTTPException (ej. 409 por unicidad, 404 por permiso no encontrado)
        # No es necesario db.rollback() porque la excepción se lanza antes de la fase de commit.
        logger.warning(f"Error HTTP al crear rol '{rol_in.nombre}': {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al crear rol '{rol_in.nombre}': {error_detail}", exc_info=True)
        if "roles_nombre_key" in error_detail or "uq_roles_nombre" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto: Ya existe un rol con el nombre '{rol_in.nombre}'.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear el rol.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando rol '{rol_in.nombre}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el rol.")


@router.get("/roles/",
            response_model=List[Rol],
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_ROLES, PERM_ADMIN_USUARIOS]))],
            summary="Listar Roles",
            response_description="Una lista de todos los roles definidos.")
def read_roles(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    # current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene una lista de todos los roles del sistema.
    Requiere el permiso: `administrar_roles` o `administrar_usuarios`.
    """
    # logger.info(f"Usuario {current_user.nombre_usuario} listando roles.")
    roles = rol_service.get_multi(db, skip=skip, limit=limit)
    return roles


@router.get("/roles/{rol_id}",
            response_model=Rol,
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_ROLES, PERM_ADMIN_USUARIOS]))],
            summary="Obtener un Rol por ID",
            response_description="Información detallada del rol, incluyendo sus permisos.")
def read_rol_by_id(
    rol_id: PyUUID,
    db: Session = Depends(deps.get_db),
    # current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Obtiene la información detallada de un rol específico por su ID.
    Requiere el permiso: `administrar_roles` o `administrar_usuarios`.
    """
    # logger.info(f"Usuario {current_user.nombre_usuario} solicitando rol ID: {rol_id}")
    rol = rol_service.get_or_404(db, id=rol_id) # Lanza 404 si no existe
    return rol


@router.put("/roles/{rol_id}",
            response_model=Rol,
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_ROLES]))],
            summary="Actualizar un Rol",
            response_description="Información actualizada del rol.")
def update_rol(
    *,
    db: Session = Depends(deps.get_db),
    rol_id: PyUUID,
    rol_in: RolUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza un rol existente, incluyendo su nombre, descripción y
    la lista COMPLETA de permisos asociados (reemplaza la anterior).
    Requiere el permiso: `administrar_roles`.
    """
    logger.info(f"Intento de actualización de rol ID {rol_id} por usuario {current_user.nombre_usuario} con datos: {rol_in.model_dump(exclude_unset=True)}")
    rol_db = rol_service.get_or_404(db, id=rol_id)

    try:
        updated_rol = rol_service.update(db=db, db_obj=rol_db, obj_in=rol_in)
        db.commit()
        db.refresh(updated_rol)
        logger.info(f"Rol '{updated_rol.nombre}' (ID: {rol_id}) actualizado exitosamente por {current_user.nombre_usuario}.")
        return updated_rol
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al actualizar rol ID {rol_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al actualizar rol ID {rol_id}: {error_detail}", exc_info=True)
        if "roles_nombre_key" in error_detail or "uq_roles_nombre" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: Ya existe un rol con el nombre proporcionado.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar el rol.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando rol ID {rol_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el rol.")


@router.delete("/roles/{rol_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_ROLES]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar un Rol",
               response_description="Mensaje de confirmación.")
def delete_rol(
    *,
    db: Session = Depends(deps.get_db),
    rol_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Elimina un rol del sistema. No se podrá eliminar si hay usuarios asignados.
    Requiere el permiso: `administrar_roles`.
    """
    logger.warning(f"Intento de eliminación de rol ID: {rol_id} por usuario {current_user.nombre_usuario}")
    
    # El servicio rol_service.remove ya incluye get_or_404 y la validación de usuarios asignados.
    # La excepción HTTPException (404 o 409) será lanzada por el servicio si aplica.
    
    # Ejemplo de lógica para no borrar roles críticos (se podría mover al servicio)
    # rol_to_delete = rol_service.get_or_404(db, id=rol_id) # Se obtiene dentro del servicio de todas formas
    # if rol_to_delete.nombre == settings.ADMIN_ROLE_NAME: # Suponiendo que settings.ADMIN_ROLE_NAME existe
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El rol administrador no puede ser eliminado.")
    
    rol_nombre_para_log = "desconocido"
    try:
        # El servicio .remove() ya no hace commit y maneja la validación de usuarios.
        # Primero obtenemos el rol para poder usar su nombre en el log si la eliminación es exitosa.
        # Esta llamada a get_or_404 también se hace dentro de rol_service.remove, es un poco redundante
        # pero útil para el mensaje de log aquí.
        rol_a_eliminar = rol_service.get_or_404(db, id=rol_id)
        rol_nombre_para_log = rol_a_eliminar.nombre

        rol_service.remove(db=db, id=rol_id)
        db.commit()
        logger.info(f"Rol '{rol_nombre_para_log}' (ID: {rol_id}) eliminado exitosamente por {current_user.nombre_usuario}.")
        return {"msg": f"Rol '{rol_nombre_para_log}' eliminado correctamente."}
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al eliminar rol ID {rol_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e: 
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al eliminar rol ID {rol_id}: {error_detail}", exc_info=True)
        if "violates foreign key constraint" in error_detail.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No se puede eliminar el rol '{rol_nombre_para_log}' porque está asignado a uno o más usuarios."
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al eliminar el rol.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando rol ID {rol_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar el rol.")

# ==============================================================================
# Endpoints para PERMISOS (Solo lectura desde aquí)
# ==============================================================================

@router.get("/permisos/",
            response_model=List[PermisoSchema],
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_ROLES]))],
            summary="Listar Permisos",
            response_description="Una lista de todos los permisos disponibles en el sistema.")
def read_permisos(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 200,
) -> Any:
    """
    Obtiene la lista de todos los permisos definidos en el sistema.
    Útil para la UI al asignar permisos a roles.
    Requiere el permiso: `administrar_roles`.
    """
    # logger.info(f"Usuario {current_user.nombre_usuario} listando permisos.")
    permisos = permiso_service.get_multi(db, skip=skip, limit=limit)
    return permisos
