import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api import deps
from app.schemas.software_catalogo import SoftwareCatalogo, SoftwareCatalogoCreate, SoftwareCatalogoUpdate 
from app.schemas.licencia_software import LicenciaSoftware, LicenciaSoftwareCreate, LicenciaSoftwareUpdate 
from app.schemas.asignacion_licencia import AsignacionLicencia, AsignacionLicenciaCreate, AsignacionLicenciaUpdate
from app.schemas.common import Msg
from app.services.software_catalogo import software_catalogo_service
from app.services.licencia_software import licencia_software_service
from app.services.asignacion_licencia import asignacion_licencia_service
from app.models.usuario import Usuario as UsuarioModel

from app.core import permissions as perms

logger = logging.getLogger(__name__)

router = APIRouter(redirect_slashes=False)

# ==============================================================================
# Endpoints para SOFTWARE CATALOGO
# ==============================================================================
@router.post("/catalogo",
             response_model=SoftwareCatalogo,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_CATALOGOS]))],
             summary="Crear entrada en Catálogo de Software",
            #  tags=["licencias", "catalogo"]
             )
def create_software_catalogo_entry(
    *,
    db: Session = Depends(deps.get_db),
    catalogo_in: SoftwareCatalogoCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Crea un nuevo registro en el catálogo de software."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' creando entrada de catálogo SW: {catalogo_in.nombre} v{catalogo_in.version}")
    try:
        catalogo = software_catalogo_service.create(db=db, obj_in=catalogo_in)
        db.commit()
        db.refresh(catalogo)
        logger.info(f"Entrada de catálogo SW '{catalogo.nombre} v{catalogo.version}' (ID: {catalogo.id}) creada exitosamente.")
        return catalogo
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al crear entrada de catálogo SW '{catalogo_in.nombre}': {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al crear entrada de catálogo SW '{catalogo_in.nombre}': {error_detail}", exc_info=True)
        if "software_catalogo_nombre_version_key" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: Ya existe una entrada en el catálogo con el mismo nombre y versión.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear la entrada de catálogo.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando entrada de catálogo SW '{catalogo_in.nombre}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear la entrada de catálogo.")

@router.get("/catalogo",
            response_model=List[SoftwareCatalogo],
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_LICENCIAS]))],
            summary="Listar Catálogo de Software",
            # tags=["licencias", "catalogo"]
            )
def read_software_catalogo(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Obtiene la lista de software definido en el catálogo."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando catálogo de software.")
    return software_catalogo_service.get_multi(db, skip=skip, limit=limit)

@router.get("/catalogo/{catalogo_id}",
            response_model=SoftwareCatalogo,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_LICENCIAS]))],
            summary="Obtener entrada de Catálogo por ID",
            # tags=["licencias", "catalogo"]
            )
def read_software_catalogo_by_id(
    catalogo_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Obtiene una entrada específica del catálogo de software."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando entrada de catálogo SW ID: {catalogo_id}.")
    return software_catalogo_service.get_or_404(db, id=catalogo_id)

@router.put("/catalogo/{catalogo_id}",
            response_model=SoftwareCatalogo,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_CATALOGOS]))],
            summary="Actualizar entrada de Catálogo",
            # tags=["licencias", "catalogo"]
            )
def update_software_catalogo_entry(
    *,
    db: Session = Depends(deps.get_db),
    catalogo_id: PyUUID,
    catalogo_in: SoftwareCatalogoUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Actualiza una entrada existente en el catálogo de software."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' actualizando entrada de catálogo SW ID: {catalogo_id} con datos: {catalogo_in.model_dump(exclude_unset=True)}")
    db_catalogo = software_catalogo_service.get_or_404(db, id=catalogo_id)
    try:
        updated_catalogo = software_catalogo_service.update(db=db, db_obj=db_catalogo, obj_in=catalogo_in)
        db.commit()
        db.refresh(updated_catalogo)
        logger.info(f"Entrada de catálogo SW '{updated_catalogo.nombre} v{updated_catalogo.version}' (ID: {catalogo_id}) actualizada exitosamente.")
        return updated_catalogo
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al actualizar entrada de catálogo SW ID {catalogo_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al actualizar entrada de catálogo SW ID {catalogo_id}: {error_detail}", exc_info=True)
        if "software_catalogo_nombre_version_key" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: Ya existe otra entrada con el mismo nombre y versión.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar la entrada de catálogo.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando entrada de catálogo SW ID {catalogo_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar la entrada de catálogo.")

@router.delete("/catalogo/{catalogo_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_CATALOGOS]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar entrada de Catálogo",
            #    tags=["licencias", "catalogo"]
               )
def delete_software_catalogo_entry(
    *,
    db: Session = Depends(deps.get_db),
    catalogo_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Elimina una entrada del catálogo de software (si no tiene licencias asociadas)."""
    logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando eliminar entrada de catálogo SW ID: {catalogo_id}")
    catalogo_a_eliminar = software_catalogo_service.get_or_404(db, id=catalogo_id)
    nombre_catalogo_log = f"{catalogo_a_eliminar.nombre} v{catalogo_a_eliminar.version}"
    try:
        software_catalogo_service.remove(db=db, id=catalogo_id)
        db.commit()
        logger.info(f"Entrada de catálogo SW '{nombre_catalogo_log}' (ID: {catalogo_id}) eliminada exitosamente.")
        return {"msg": f"Entrada de catálogo '{nombre_catalogo_log}' eliminada."}
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al eliminar entrada de catálogo SW ID {catalogo_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al eliminar catálogo SW '{nombre_catalogo_log}' (ID: {catalogo_id}): {error_detail}", exc_info=True)
        if "violates foreign key constraint" in error_detail.lower() and "fk_licencias_software_catalogo" in error_detail.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede eliminar la entrada de catálogo '{nombre_catalogo_log}': tiene licencias de software asociadas.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al eliminar la entrada de catálogo.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando entrada de catálogo SW '{nombre_catalogo_log}' (ID: {catalogo_id}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar la entrada de catálogo.")

# ==============================================================================
# Endpoints para LICENCIAS DE SOFTWARE (Instancias/Compras)
# ==============================================================================
@router.post("/",
             response_model=LicenciaSoftware,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_LICENCIAS]))],
             summary="Registrar una nueva Licencia Adquirida",
            #  tags=["licencias"]
             )
def create_licencia(
    *,
    db: Session = Depends(deps.get_db),
    licencia_in: LicenciaSoftwareCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Registra una nueva licencia o grupo de licencias adquiridas."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' registrando nueva licencia para SoftwareCatalogo ID: {licencia_in.software_catalogo_id}")
    try:
        licencia = licencia_software_service.create(db=db, obj_in=licencia_in)
        db.commit()
        db.refresh(licencia)
        sw_nombre = licencia.software_info.nombre if licencia.software_info else "N/A"
        logger.info(f"Licencia para '{sw_nombre}' (Clave: {licencia.clave_producto}, ID: {licencia.id}) creada exitosamente.")
        return licencia
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al registrar licencia: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al registrar licencia: {error_detail}", exc_info=True)
        if "licencias_software_clave_producto_key" in error_detail:
             raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: La clave de producto ya existe.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al registrar la licencia.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado registrando licencia: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al registrar la licencia.")

@router.get("/",
            response_model=List[LicenciaSoftware],
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_LICENCIAS]))],
            summary="Listar Licencias Adquiridas",
            # tags=["licencias"]
            )
def read_licencias(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    software_catalogo_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de software del catálogo"),
    expiring_days: Optional[int] = Query(None, ge=0, description="Mostrar licencias que expiran en los próximos N días"),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Obtiene una lista de licencias adquiridas, con filtros opcionales."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando licencias.")
    if expiring_days is not None:
        licencias = licencia_software_service.get_expiring_soon(db, days_ahead=expiring_days, skip=skip, limit=limit)
    elif software_catalogo_id:
        licencias = licencia_software_service.get_multi_by_software(db, software_catalogo_id=software_catalogo_id, skip=skip, limit=limit)
    else:
        licencias = licencia_software_service.get_multi(db, skip=skip, limit=limit)
    return licencias

# ==============================================================================
# Endpoints para ASIGNACIONES DE LICENCIAS
# ==============================================================================

@router.post("/asignaciones",
             response_model=AsignacionLicencia,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([perms.PERM_ASIGNAR_LICENCIAS]))],
             summary="Asignar una Licencia",
            #  tags=["licencias", "asignaciones"]
             )
@router.post("/asignaciones/", include_in_schema=False,
             dependencies=[Depends(deps.PermissionChecker([perms.PERM_ASIGNAR_LICENCIAS]))])
def create_asignacion(
    *,
    db: Session = Depends(deps.get_db),
    asignacion_in: AsignacionLicenciaCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Asigna una licencia disponible a un equipo o a un usuario."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' asignando licencia ID: {asignacion_in.licencia_id} a Equipo/Usuario.")
    try:
        asignacion = asignacion_licencia_service.create(db=db, obj_in=asignacion_in)
        db.commit()
        db.refresh(asignacion)
        target_info = f"equipo ID {asignacion.equipo_id}" if asignacion.equipo_id else f"usuario ID {asignacion.usuario_id}"
        lic_info = asignacion.licencia.software_info.nombre if asignacion.licencia and asignacion.licencia.software_info else "N/A"
        logger.info(f"Licencia '{lic_info}' (ID: {asignacion.licencia_id}) asignada a {target_info}. Asignación ID: {asignacion.id}.")
        return asignacion
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al crear asignación de licencia: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al crear asignación de licencia: {error_detail}", exc_info=True)
        if "uq_asignacion_licencia_equipo" in error_detail or "uq_asignacion_licencia_usuario" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: Esta licencia ya está asignada a este destino (equipo/usuario).")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear la asignación.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando asignación de licencia: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear la asignación.")

@router.get("/asignaciones",
            response_model=List[AsignacionLicencia],
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_LICENCIAS]))],
            summary="Listar Asignaciones de Licencias",
            )
@router.get("/asignaciones/", include_in_schema=False,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_LICENCIAS]))])
def read_asignaciones(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    licencia_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de licencia"),
    equipo_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de equipo"),
    usuario_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de usuario"),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Obtiene una lista de asignaciones de licencias, con filtros opcionales."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando asignaciones de licencias.")
    if licencia_id:
        asignaciones = asignacion_licencia_service.get_multi_by_licencia(db, licencia_id=licencia_id, skip=skip, limit=limit)
    elif equipo_id:
        asignaciones = asignacion_licencia_service.get_multi_by_equipo(db, equipo_id=equipo_id, skip=skip, limit=limit)
    elif usuario_id:
        asignaciones = asignacion_licencia_service.get_multi_by_usuario(db, usuario_id=usuario_id, skip=skip, limit=limit)
    else:
        asignaciones = asignacion_licencia_service.get_multi(db, skip=skip, limit=limit)
    return asignaciones

@router.get("/asignaciones/{asignacion_id}",
            response_model=AsignacionLicencia,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_LICENCIAS]))],
            summary="Obtener Asignación por ID",
            )
def read_asignacion_by_id(
    asignacion_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Obtiene la información detallada de una asignación específica."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando asignación de licencia ID: {asignacion_id}.")
    return asignacion_licencia_service.get_or_404(db, id=asignacion_id)

@router.put("/asignaciones/{asignacion_id}",
            response_model=AsignacionLicencia,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_ASIGNAR_LICENCIAS]))],
            summary="Actualizar una Asignación",
            )
def update_asignacion(
    *,
    db: Session = Depends(deps.get_db),
    asignacion_id: PyUUID,
    asignacion_in: AsignacionLicenciaUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Actualiza campos menores de una asignación (ej. fecha_instalacion, notas)."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' actualizando asignación de licencia ID: {asignacion_id} con datos {asignacion_in.model_dump(exclude_unset=True)}")
    db_asignacion = asignacion_licencia_service.get_or_404(db, id=asignacion_id)
    try:
        updated_asignacion = asignacion_licencia_service.update(db=db, db_obj=db_asignacion, obj_in=asignacion_in)
        db.commit()
        db.refresh(updated_asignacion)
        logger.info(f"Asignación de licencia ID {asignacion_id} actualizada exitosamente.")
        return updated_asignacion
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al actualizar asignación ID {asignacion_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando asignación ID {asignacion_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar la asignación.")

@router.delete("/asignaciones/{asignacion_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([perms.PERM_ASIGNAR_LICENCIAS]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar una Asignación (Desasignar Licencia)",
            #    tags=["licencias", "asignaciones"]
               )
def delete_asignacion(
    *,
    db: Session = Depends(deps.get_db),
    asignacion_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Elimina una asignación de licencia (desasigna la licencia).
    El trigger de base de datos (`actualizar_cantidad_disponible_licencia_fn` en `asignaciones_licencia`)
    debería incrementar la cantidad disponible de la licencia.
    """
    logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando eliminar asignación de licencia ID: {asignacion_id}")
    asignacion_a_eliminar = asignacion_licencia_service.get_or_404(db, id=asignacion_id)
    lic_id_log = asignacion_a_eliminar.licencia_id
    try:
        asignacion_licencia_service.remove(db=db, id=asignacion_id)
        db.commit()
        logger.info(f"Asignación de licencia ID {asignacion_id} (para Licencia ID: {lic_id_log}) eliminada exitosamente.")
        return {"msg": f"Asignación de licencia (ID: {asignacion_id}) eliminada correctamente."}
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al eliminar asignación ID {asignacion_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando asignación ID {asignacion_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al eliminar la asignación.")

# ==============================================================================
# Endpoints dinámicos /{licencia_id}
# ==============================================================================
@router.get("/{licencia_id}",
            response_model=LicenciaSoftware,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_LICENCIAS]))],
            summary="Obtener Licencia por ID",
            )
def read_licencia_by_id(
    licencia_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Obtiene la información detallada de una licencia específica."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando licencia ID: {licencia_id}.")
    return licencia_software_service.get_or_404(db, id=licencia_id)

@router.put("/{licencia_id}",
            response_model=LicenciaSoftware,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_LICENCIAS]))],
            summary="Actualizar Licencia Adquirida",
            )
def update_licencia(
    *,
    db: Session = Depends(deps.get_db),
    licencia_id: PyUUID,
    licencia_in: LicenciaSoftwareUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Actualiza la información de una licencia adquirida."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' actualizando licencia ID: {licencia_id} con datos {licencia_in.model_dump(exclude_unset=True)}")
    db_licencia = licencia_software_service.get_or_404(db, id=licencia_id)
    try:
        updated_licencia = licencia_software_service.update(db=db, db_obj=db_licencia, obj_in=licencia_in)
        db.commit()
        db.refresh(updated_licencia)
        logger.info(f"Licencia ID {licencia_id} (SW: '{updated_licencia.software_info.nombre if updated_licencia.software_info else 'N/A'}') actualizada exitosamente.")
        return updated_licencia
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al actualizar licencia ID {licencia_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al actualizar licencia ID {licencia_id}: {error_detail}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar la licencia.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando licencia ID {licencia_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar la licencia.")

@router.delete("/{licencia_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_LICENCIAS]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar Licencia Adquirida",
               )
def delete_licencia(
    *,
    db: Session = Depends(deps.get_db),
    licencia_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Elimina un registro de licencia adquirida.
    Las asignaciones activas deben ser manejadas (ej. prevenidas por trigger o borradas en cascada).
    El trigger `prevenir_eliminacion_licencia_asignada_fn` previene esto.
    """
    logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando eliminar licencia ID: {licencia_id}")
    licencia_a_eliminar = licencia_software_service.get_or_404(db, id=licencia_id)
    nombre_sw_log = licencia_a_eliminar.software_info.nombre if licencia_a_eliminar.software_info else "N/A"
    try:
        licencia_software_service.remove(db=db, id=licencia_id)
        db.commit()
        logger.info(f"Licencia ID {licencia_id} para '{nombre_sw_log}' eliminada exitosamente.")
        return {"msg": f"Licencia para '{nombre_sw_log}' (ID: {licencia_id}) eliminada."}
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al eliminar licencia ID {licencia_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al eliminar licencia ID {licencia_id}: {error_detail}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede eliminar la licencia '{nombre_sw_log}' (ID: {licencia_id}) debido a restricciones de integridad.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando licencia ID {licencia_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar la licencia.")
