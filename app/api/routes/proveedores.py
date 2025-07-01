import logging
from typing import Any, List
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError # Importar IntegrityError para manejo específico

from app.api import deps
from app.schemas.proveedor import Proveedor, ProveedorCreate, ProveedorUpdate
from app.schemas.common import Msg
from app.services.proveedor import proveedor_service
from app.models.usuario import Usuario as UsuarioModel
from app.models.equipo import Equipo

logger = logging.getLogger(__name__)
router = APIRouter()

# Permisos actualizados
PERM_GESTIONAR_PROVEEDORES = "administrar_catalogos" # Cambiado de administrar_proveedores
PERM_VER_PROVEEDORES = "ver_proveedores" # Este ya estaba bien

@router.post("/",
             response_model=Proveedor,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_GESTIONAR_PROVEEDORES]))], # Usar el permiso actualizado
             summary="Crear un nuevo Proveedor",
             response_description="El proveedor creado.")
def create_proveedor(
    *,
    db: Session = Depends(deps.get_db),
    proveedor_in: ProveedorCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Crea un nuevo proveedor.
    Requiere el permiso: `administrar_catalogos`.
    """
    logger.info(f"Intento de creación de proveedor '{proveedor_in.nombre}' por usuario {current_user.nombre_usuario}")
    try:
        proveedor = proveedor_service.create(db=db, obj_in=proveedor_in)
        db.commit()
        db.refresh(proveedor)
        logger.info(f"Proveedor '{proveedor.nombre}' (ID: {proveedor.id}) creado exitosamente por {current_user.nombre_usuario}.")
        return proveedor
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al crear proveedor '{proveedor_in.nombre}': {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al crear proveedor '{proveedor_in.nombre}': {error_detail}", exc_info=True)
        if "proveedores_nombre_key" in error_detail or "uq_proveedores_nombre" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto: Ya existe un proveedor con el nombre '{proveedor_in.nombre}'.")
        if "proveedores_rnc_key" in error_detail or "uq_proveedores_rnc" in error_detail:
             raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto: Ya existe un proveedor con el RNC '{proveedor_in.rnc}'.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear el proveedor.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando proveedor '{proveedor_in.nombre}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el proveedor.")


@router.get("/",
            response_model=List[Proveedor],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_PROVEEDORES]))], # Solo se necesita ver_proveedores
            summary="Listar Proveedores",
            response_description="Una lista de proveedores.")
def read_proveedores(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Obtiene una lista de proveedores.
    Requiere el permiso: `ver_proveedores`.
    """
    proveedores = proveedor_service.get_multi(db, skip=skip, limit=limit)
    return proveedores


@router.get("/{proveedor_id}",
            response_model=Proveedor,
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_PROVEEDORES]))], # Solo se necesita ver_proveedores
            summary="Obtener un Proveedor por ID",
            response_description="Información detallada del proveedor.")
def read_proveedor_by_id(
    proveedor_id: PyUUID,
    db: Session = Depends(deps.get_db),
) -> Any:
    """
    Obtiene la información de un proveedor específico por su ID.
    Requiere el permiso: `ver_proveedores`.
    """
    proveedor = proveedor_service.get_or_404(db, id=proveedor_id)
    return proveedor


@router.put("/{proveedor_id}",
            response_model=Proveedor,
            dependencies=[Depends(deps.PermissionChecker([PERM_GESTIONAR_PROVEEDORES]))], # Usar el permiso actualizado
            summary="Actualizar un Proveedor",
            response_description="Información actualizada del proveedor.")
def update_proveedor(
    *,
    db: Session = Depends(deps.get_db),
    proveedor_id: PyUUID,
    proveedor_in: ProveedorUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza un proveedor existente.
    Requiere el permiso: `administrar_catalogos`.
    """
    logger.info(f"Intento de actualización de proveedor ID {proveedor_id} por usuario {current_user.nombre_usuario} con datos: {proveedor_in.model_dump(exclude_unset=True)}")
    proveedor_db = proveedor_service.get_or_404(db, id=proveedor_id)

    try:
        updated_proveedor = proveedor_service.update(db=db, db_obj=proveedor_db, obj_in=proveedor_in)
        db.commit()
        db.refresh(updated_proveedor)
        logger.info(f"Proveedor '{updated_proveedor.nombre}' (ID: {proveedor_id}) actualizado exitosamente por {current_user.nombre_usuario}.")
        return updated_proveedor
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al actualizar proveedor ID {proveedor_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al actualizar proveedor ID {proveedor_id}: {error_detail}", exc_info=True)
        if "proveedores_nombre_key" in error_detail or "uq_proveedores_nombre" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: Ya existe un proveedor con el nombre proporcionado.")
        if "proveedores_rnc_key" in error_detail or "uq_proveedores_rnc" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: Ya existe un proveedor con el RNC proporcionado.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar el proveedor.")
    except Exception as e:
         db.rollback()
         logger.error(f"Error inesperado actualizando proveedor ID {proveedor_id}: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el proveedor.")


@router.delete("/{proveedor_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_GESTIONAR_PROVEEDORES]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar un Proveedor",
               response_description="Mensaje de confirmación.")
def delete_proveedor(
    *,
    db: Session = Depends(deps.get_db),
    proveedor_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Elimina un proveedor. No se permite si está asociado a algún equipo.
    Requiere el permiso: `administrar_catalogos`.
    """
    logger.warning(f"Intento de eliminación de proveedor ID: {proveedor_id} por usuario {current_user.nombre_usuario}")

    proveedor_db = proveedor_service.get_or_404(db, id=proveedor_id)
    proveedor_nombre_para_log = proveedor_db.nombre

    # CORRECCIÓN: Añadir validación manual de integridad
    equipos_asociados = db.query(Equipo).filter(Equipo.proveedor_id == proveedor_id).first()
    if equipos_asociados:
        logger.warning(f"Intento de eliminar proveedor '{proveedor_nombre_para_log}' que está asociado al equipo ID {equipos_asociados.id}.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede eliminar el proveedor '{proveedor_nombre_para_log}' porque está asociado a uno o más equipos."
        )

    # Si pasa la validación, proceder con la eliminación
    try:
        proveedor_service.remove(db=db, id=proveedor_id)
        db.commit()
        logger.info(f"Proveedor '{proveedor_nombre_para_log}' (ID: {proveedor_id}) eliminado exitosamente por {current_user.nombre_usuario}.")
        return {"msg": f"Proveedor '{proveedor_nombre_para_log}' eliminado correctamente."}
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando proveedor '{proveedor_nombre_para_log}' (ID: {proveedor_id}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar el proveedor.")
