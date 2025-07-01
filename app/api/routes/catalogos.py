import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api import deps
# Importar Schemas específicos
from app.schemas.estado_equipo import EstadoEquipo as EstadoEquipoSchema, EstadoEquipoCreate, EstadoEquipoUpdate
from app.schemas.tipo_documento import TipoDocumento as TipoDocumentoSchema, TipoDocumentoCreate, TipoDocumentoUpdate
from app.schemas.tipo_mantenimiento import TipoMantenimiento as TipoMantenimientoSchema, TipoMantenimientoCreate, TipoMantenimientoUpdate
from app.schemas.common import Msg
# Importar Servicios específicos
from app.services.estado_equipo import estado_equipo_service
from app.services.tipo_documento import tipo_documento_service
from app.services.tipo_mantenimiento import tipo_mantenimiento_service
from app.models.usuario import Usuario as UsuarioModel

logger = logging.getLogger(__name__)
router = APIRouter()

# Permisos
PERM_ADMIN_CATALOGOS = "administrar_catalogos"
# Usar dependencia directa para lectura por cualquier usuario autenticado
PERM_VER_CATALOGOS = Depends(deps.get_current_active_user)

# ==============================================================================
# Endpoints para ESTADOS DE EQUIPO
# ==============================================================================

@router.post("/estados-equipo/",
             response_model=EstadoEquipoSchema,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_CATALOGOS]))],
             summary="Crear Nuevo Estado de Equipo",
             response_description="El estado de equipo creado.")
def create_estado_equipo(
    *,
    db: Session = Depends(deps.get_db),
    estado_in: EstadoEquipoCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Crea un nuevo estado para los equipos.
    Requiere el permiso: `administrar_catalogos`.
    """
    logger.info(f"Intento de creación de estado equipo '{estado_in.nombre}' por usuario {current_user.nombre_usuario}")
    
    existing = estado_equipo_service.get_by_nombre(db, nombre=estado_in.nombre)
    if existing:
        logger.warning(f"Intento de crear estado duplicado: {estado_in.nombre}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un estado de equipo con el nombre '{estado_in.nombre}'.",
        )
    try:
        estado = estado_equipo_service.create(db=db, obj_in=estado_in)
        db.commit()
        db.refresh(estado)
        logger.info(f"Estado de equipo creado: {estado.nombre} (ID: {estado.id}) por {current_user.nombre_usuario}")
        return estado
    except IntegrityError as e:
        db.rollback()
        if "uq_estados_equipo_nombre" in str(e.orig).lower():
            logger.warning(f"Error de integridad (nombre duplicado) al crear estado equipo '{estado_in.nombre}': {e.orig}", exc_info=False)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflicto: Ya existe un estado de equipo con el nombre '{estado_in.nombre}'.",
            )
        logger.error(f"Error de integridad no esperado al crear estado equipo '{estado_in.nombre}': {e.orig}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de base de datos al crear el estado de equipo.",
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando estado equipo '{estado_in.nombre}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al crear estado equipo."
        )

@router.get("/estados-equipo/",
            response_model=List[EstadoEquipoSchema],
            dependencies=[PERM_VER_CATALOGOS],
            summary="Listar Estados de Equipo",
            response_description="Una lista de todos los estados de equipo.")
def read_estados_equipo(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """Obtiene la lista de todos los estados de equipo."""
    estados = estado_equipo_service.get_multi(db, skip=skip, limit=limit)
    return estados

@router.get("/estados-equipo/{estado_id}",
            response_model=EstadoEquipoSchema,
            dependencies=[PERM_VER_CATALOGOS],
            summary="Obtener Estado de Equipo por ID",
            response_description="Información detallada del estado.")
def read_estado_equipo_by_id(
    estado_id: PyUUID,
    db: Session = Depends(deps.get_db),
) -> Any:
    """Obtiene un estado de equipo específico."""
    estado = estado_equipo_service.get_or_404(db, id=estado_id)
    return estado

@router.put("/estados-equipo/{estado_id}",
            response_model=EstadoEquipoSchema,
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_CATALOGOS]))],
            summary="Actualizar Estado de Equipo",
            response_description="El estado de equipo actualizado.")
def update_estado_equipo(
    *,
    db: Session = Depends(deps.get_db),
    estado_id: PyUUID,
    estado_in: EstadoEquipoUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Actualiza un estado de equipo existente."""
    logger.info(f"Intento de actualización estado equipo ID {estado_id} por usuario {current_user.nombre_usuario} con datos: {estado_in.model_dump(exclude_unset=True)}")
    db_estado = estado_equipo_service.get_or_404(db, id=estado_id)

    if estado_in.nombre and estado_in.nombre != db_estado.nombre:
        existing = estado_equipo_service.get_by_nombre(db, nombre=estado_in.nombre)
        if existing and existing.id != estado_id:
            logger.warning(f"Conflicto de nombre al actualizar estado ID {estado_id} a '{estado_in.nombre}'. Ya existe.")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe un estado de equipo con el nombre '{estado_in.nombre}'.")
    try:
        updated_estado = estado_equipo_service.update(db=db, db_obj=db_estado, obj_in=estado_in)
        db.commit()
        db.refresh(updated_estado)
        logger.info(f"Estado de equipo actualizado: {updated_estado.nombre} (ID: {estado_id}) por {current_user.nombre_usuario}")
        return updated_estado
    except IntegrityError as e:
        db.rollback()
        if "uq_estados_equipo_nombre" in str(e.orig).lower():
            logger.warning(f"Error de integridad (nombre duplicado) al actualizar estado equipo ID {estado_id}: {e.orig}", exc_info=False)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflicto: Ya existe un estado de equipo con el nombre proporcionado.",
            )
        logger.error(f"Error de integridad no esperado al actualizar estado equipo ID {estado_id}: {e.orig}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error de base de datos al actualizar estado: {getattr(e, 'orig', e)}")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando estado equipo {estado_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar estado equipo.")

@router.delete("/estados-equipo/{estado_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_CATALOGOS]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar Estado de Equipo",
               response_description="Mensaje de confirmación o error.")
def delete_estado_equipo(
    *,
    db: Session = Depends(deps.get_db),
    estado_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Elimina un estado de equipo.
    No se permite si el estado está asignado a algún equipo (la BD lo previene con FK Restrict).
    Requiere el permiso: `administrar_catalogos`.
    """
    logger.warning(f"Intento de eliminación estado equipo ID: {estado_id} por usuario {current_user.nombre_usuario}")
    
    estado_nombre_para_log = "desconocido"
    try:
        db_estado = estado_equipo_service.get_or_404(db, id=estado_id)
        estado_nombre_para_log = db_estado.nombre
        
        estado_equipo_service.remove(db=db, id=estado_id)
        db.commit()
        logger.info(f"Estado de equipo '{estado_nombre_para_log}' (ID: {estado_id}) eliminado por {current_user.nombre_usuario}.")
        return {"msg": f"Estado de equipo '{estado_nombre_para_log}' eliminado correctamente."}
    except IntegrityError as e:
        db.rollback()
        logger.warning(f"Intento de eliminar estado equipo '{estado_nombre_para_log}' (ID: {estado_id}) en uso: {e.orig}", exc_info=False)
        if "violates foreign key constraint" in str(e.orig).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No se puede eliminar el estado '{estado_nombre_para_log}' porque está asignado a uno o más equipos."
            )
        logger.error(f"Error de integridad no esperado al eliminar estado equipo '{estado_nombre_para_log}' (ID: {estado_id}): {e.orig}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error de base de datos al eliminar el estado '{estado_nombre_para_log}'.",
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando estado equipo '{estado_nombre_para_log}' (ID: {estado_id}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar el estado.")


# ==============================================================================
# Endpoints para TIPOS DE DOCUMENTO
# ==============================================================================
@router.post("/tipos-documento/",
             response_model=TipoDocumentoSchema,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_CATALOGOS]))],
             summary="Crear Tipo de Documento",
             )
def create_tipo_documento(
    *,
    db: Session = Depends(deps.get_db),
    tipo_in: TipoDocumentoCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Crea un nuevo tipo de documento."""
    logger.info(f"Intento de creación tipo documento '{tipo_in.nombre}' por usuario {current_user.nombre_usuario}")
    existing = tipo_documento_service.get_by_name(db, name=tipo_in.nombre)
    if existing:
        logger.warning(f"Intento de crear tipo documento duplicado: {tipo_in.nombre}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe un tipo de documento con el nombre '{tipo_in.nombre}'.")
    try:
        tipo_doc = tipo_documento_service.create(db=db, obj_in=tipo_in)
        db.commit()
        db.refresh(tipo_doc)
        logger.info(f"Tipo de documento creado: {tipo_doc.nombre} (ID: {tipo_doc.id}) por {current_user.nombre_usuario}")
        return tipo_doc
    except IntegrityError as e:
        db.rollback()
        if "uq_tipos_documento_nombre" in str(e.orig).lower():
            logger.warning(f"Error de integridad (nombre duplicado) al crear tipo documento '{tipo_in.nombre}': {e.orig}", exc_info=False)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto: Ya existe un tipo de documento con el nombre '{tipo_in.nombre}'.")
        logger.error(f"Error de integridad no esperado al crear tipo documento '{tipo_in.nombre}': {e.orig}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear el tipo de documento.")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando tipo documento '{tipo_in.nombre}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")

@router.get("/tipos-documento/",
            response_model=List[TipoDocumentoSchema],
            dependencies=[PERM_VER_CATALOGOS],
            summary="Listar Tipos de Documento",
            )
def read_tipos_documento(
    db: Session = Depends(deps.get_db), skip: int = 0, limit: int = 100,
) -> Any:
    """Obtiene la lista de todos los tipos de documento."""
    return tipo_documento_service.get_multi(db, skip=skip, limit=limit)

# ==========================================================
# ======> RUTA GET BY ID AÑADIDA PARA TIPOS DE DOCUMENTO <=====
# ==========================================================
@router.get("/tipos-documento/{tipo_id}",
            response_model=TipoDocumentoSchema,
            dependencies=[PERM_VER_CATALOGOS],
            summary="Obtener Tipo de Documento por ID")
def read_tipo_documento_by_id(
    tipo_id: PyUUID,
    db: Session = Depends(deps.get_db)
) -> Any:
    """Obtiene un tipo de documento específico por su ID."""
    tipo_doc = tipo_documento_service.get_or_404(db, id=tipo_id)
    return tipo_doc

@router.put("/tipos-documento/{tipo_id}",
            response_model=TipoDocumentoSchema,
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_CATALOGOS]))],
            summary="Actualizar Tipo de Documento",
            )
def update_tipo_documento(
    *,
    db: Session = Depends(deps.get_db),
    tipo_id: PyUUID,
    tipo_in: TipoDocumentoUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Actualiza un tipo de documento existente."""
    logger.info(f"Intento de actualización tipo documento ID {tipo_id} por usuario {current_user.nombre_usuario} con datos: {tipo_in.model_dump(exclude_unset=True)}")
    db_tipo = tipo_documento_service.get_or_404(db, id=tipo_id)
    if tipo_in.nombre and tipo_in.nombre != db_tipo.nombre:
        existing = tipo_documento_service.get_by_name(db, name=tipo_in.nombre)
        if existing and existing.id != tipo_id:
            logger.warning(f"Conflicto de nombre al actualizar tipo documento ID {tipo_id} a '{tipo_in.nombre}'. Ya existe.")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe un tipo de documento con el nombre '{tipo_in.nombre}'.")
    try:
        updated_tipo = tipo_documento_service.update(db=db, db_obj=db_tipo, obj_in=tipo_in)
        db.commit()
        db.refresh(updated_tipo)
        logger.info(f"Tipo de documento actualizado: {updated_tipo.nombre} (ID: {tipo_id}) por {current_user.nombre_usuario}")
        return updated_tipo
    except IntegrityError as e:
        db.rollback()
        if "uq_tipos_documento_nombre" in str(e.orig).lower():
            logger.warning(f"Error de integridad (nombre duplicado) al actualizar tipo documento ID {tipo_id}: {e.orig}", exc_info=False)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto: Ya existe un tipo de documento con el nombre proporcionado.")
        logger.error(f"Error de integridad no esperado al actualizar tipo documento ID {tipo_id}: {e.orig}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar tipo de documento.")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando tipo documento ID {tipo_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")

@router.delete("/tipos-documento/{tipo_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_CATALOGOS]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar Tipo de Documento",
               )
def delete_tipo_documento(
    *,
    db: Session = Depends(deps.get_db),
    tipo_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Elimina un tipo de documento (si no está en uso)."""
    logger.warning(f"Intento de eliminación tipo documento ID: {tipo_id} por usuario {current_user.nombre_usuario}")
    tipo_nombre_para_log = "desconocido"
    try:
        db_tipo = tipo_documento_service.get_or_404(db, id=tipo_id)
        tipo_nombre_para_log = db_tipo.nombre
        
        tipo_documento_service.remove(db=db, id=tipo_id)
        db.commit()
        logger.info(f"Tipo de documento '{tipo_nombre_para_log}' (ID: {tipo_id}) eliminado por {current_user.nombre_usuario}.")
        return {"msg": f"Tipo de documento '{tipo_nombre_para_log}' eliminado correctamente."}
    except IntegrityError as e:
        db.rollback()
        logger.warning(f"Intento de eliminar tipo documento '{tipo_nombre_para_log}' (ID: {tipo_id}) en uso: {e.orig}", exc_info=False)
        if "violates foreign key constraint" in str(e.orig).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede eliminar el tipo de documento '{tipo_nombre_para_log}' porque está en uso.")
        logger.error(f"Error de integridad no esperado al eliminar tipo documento '{tipo_nombre_para_log}' (ID: {tipo_id}): {e.orig}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al eliminar el tipo de documento.")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando tipo documento '{tipo_nombre_para_log}' (ID: {tipo_id}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")


# ==============================================================================
# Endpoints para TIPOS DE MANTENIMIENTO
# ==============================================================================
@router.post("/tipos-mantenimiento/",
             response_model=TipoMantenimientoSchema,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_CATALOGOS]))],
             summary="Crear Tipo de Mantenimiento",
             )
def create_tipo_mantenimiento(
    *,
    db: Session = Depends(deps.get_db),
    tipo_in: TipoMantenimientoCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Crea un nuevo tipo de mantenimiento."""
    logger.info(f"Intento de creación tipo mantenimiento '{tipo_in.nombre}' por usuario {current_user.nombre_usuario}")
    existing = tipo_mantenimiento_service.get_by_name(db, name=tipo_in.nombre)
    if existing:
        logger.warning(f"Intento de crear tipo mantenimiento duplicado: {tipo_in.nombre}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe un tipo de mantenimiento con el nombre '{tipo_in.nombre}'.")
    try:
        tipo_mant = tipo_mantenimiento_service.create(db=db, obj_in=tipo_in)
        db.commit()
        db.refresh(tipo_mant)
        logger.info(f"Tipo de mantenimiento creado: {tipo_mant.nombre} (ID: {tipo_mant.id}) por {current_user.nombre_usuario}")
        return tipo_mant
    except IntegrityError as e:
        db.rollback()
        if "uq_tipos_mantenimiento_nombre" in str(e.orig).lower():
            logger.warning(f"Error de integridad (nombre duplicado) al crear tipo mantenimiento '{tipo_in.nombre}': {e.orig}", exc_info=False)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto: Ya existe un tipo de mantenimiento con el nombre '{tipo_in.nombre}'.")
        logger.error(f"Error de integridad no esperado al crear tipo mantenimiento '{tipo_in.nombre}': {e.orig}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear el tipo de mantenimiento.")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando tipo mantenimiento '{tipo_in.nombre}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")

@router.get("/tipos-mantenimiento/",
            response_model=List[TipoMantenimientoSchema],
            dependencies=[PERM_VER_CATALOGOS],
            summary="Listar Tipos de Mantenimiento",
            )
def read_tipos_mantenimiento(
    db: Session = Depends(deps.get_db), skip: int = 0, limit: int = 100,
) -> Any:
    """Obtiene la lista de todos los tipos de mantenimiento."""
    return tipo_mantenimiento_service.get_multi(db, skip=skip, limit=limit)

# =============================================================
# ======> RUTA GET BY ID AÑADIDA PARA TIPOS DE MANTENIMIENTO <=====
# =============================================================
@router.get("/tipos-mantenimiento/{tipo_id}",
            response_model=TipoMantenimientoSchema,
            dependencies=[PERM_VER_CATALOGOS],
            summary="Obtener Tipo de Mantenimiento por ID")
def read_tipo_mantenimiento_by_id(
    tipo_id: PyUUID,
    db: Session = Depends(deps.get_db)
) -> Any:
    """Obtiene un tipo de mantenimiento específico por su ID."""
    tipo_mant = tipo_mantenimiento_service.get_or_404(db, id=tipo_id)
    return tipo_mant

@router.put("/tipos-mantenimiento/{tipo_id}",
            response_model=TipoMantenimientoSchema,
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_CATALOGOS]))],
            summary="Actualizar Tipo de Mantenimiento",
            )
def update_tipo_mantenimiento(
    *,
    db: Session = Depends(deps.get_db),
    tipo_id: PyUUID,
    tipo_in: TipoMantenimientoUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Actualiza un tipo de mantenimiento existente."""
    logger.info(f"Intento de actualización tipo mantenimiento ID {tipo_id} por usuario {current_user.nombre_usuario} con datos: {tipo_in.model_dump(exclude_unset=True)}")
    db_tipo = tipo_mantenimiento_service.get_or_404(db, id=tipo_id)
    if tipo_in.nombre and tipo_in.nombre != db_tipo.nombre:
        existing = tipo_mantenimiento_service.get_by_name(db, name=tipo_in.nombre)
        if existing and existing.id != tipo_id:
            logger.warning(f"Conflicto de nombre al actualizar tipo mantenimiento ID {tipo_id} a '{tipo_in.nombre}'. Ya existe.")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe un tipo de mantenimiento con el nombre '{tipo_in.nombre}'.")
    try:
        updated_tipo = tipo_mantenimiento_service.update(db=db, db_obj=db_tipo, obj_in=tipo_in)
        db.commit()
        db.refresh(updated_tipo)
        logger.info(f"Tipo de mantenimiento actualizado: {updated_tipo.nombre} (ID: {tipo_id}) por {current_user.nombre_usuario}")
        return updated_tipo
    except IntegrityError as e:
        db.rollback()
        if "uq_tipos_mantenimiento_nombre" in str(e.orig).lower():
            logger.warning(f"Error de integridad (nombre duplicado) al actualizar tipo mantenimiento ID {tipo_id}: {e.orig}", exc_info=False)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto: Ya existe un tipo de mantenimiento con el nombre proporcionado.")
        logger.error(f"Error de integridad no esperado al actualizar tipo mantenimiento ID {tipo_id}: {e.orig}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar tipo de mantenimiento.")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando tipo mantenimiento ID {tipo_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")

@router.delete("/tipos-mantenimiento/{tipo_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_CATALOGOS]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar Tipo de Mantenimiento",
               )
def delete_tipo_mantenimiento(
    *,
    db: Session = Depends(deps.get_db),
    tipo_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Elimina un tipo de mantenimiento (si no está en uso)."""
    logger.warning(f"Intento de eliminación tipo mantenimiento ID: {tipo_id} por usuario {current_user.nombre_usuario}")
    tipo_nombre_para_log = "desconocido"
    try:
        db_tipo = tipo_mantenimiento_service.get_or_404(db, id=tipo_id)
        tipo_nombre_para_log = db_tipo.nombre
        
        tipo_mantenimiento_service.remove(db=db, id=tipo_id)
        db.commit()
        logger.info(f"Tipo de mantenimiento '{tipo_nombre_para_log}' (ID: {tipo_id}) eliminado por {current_user.nombre_usuario}.")
        return {"msg": f"Tipo de mantenimiento '{tipo_nombre_para_log}' eliminado correctamente."}
    except IntegrityError as e:
        db.rollback()
        logger.warning(f"Intento de eliminar tipo mantenimiento '{tipo_nombre_para_log}' (ID: {tipo_id}) en uso: {e.orig}", exc_info=False)
        if "violates foreign key constraint" in str(e.orig).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede eliminar el tipo de mantenimiento '{tipo_nombre_para_log}' porque está en uso.")
        logger.error(f"Error de integridad no esperado al eliminar tipo mantenimiento '{tipo_nombre_para_log}' (ID: {tipo_id}): {e.orig}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al eliminar el tipo de mantenimiento.")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando tipo mantenimiento '{tipo_nombre_para_log}' (ID: {tipo_id}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")
