import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

# Importar selectores de error de manera más robusta
PG_UNIQUE_VIOLATION_SQLSTATE = '23505'
PG_CHECK_VIOLATION_SQLSTATE = '23514'
PG_FK_VIOLATION_SQLSTATE = '23503' # Para Foreign Key violations

try:
    from psycopg import errors as psycopg_errors
    PsycopgUniqueViolation = psycopg_errors.UniqueViolation
    PsycopgCheckViolation = psycopg_errors.CheckViolation
    PsycopgForeignKeyViolation = psycopg_errors.ForeignKeyViolation # Añadido
    logging.info("Psycopg (v3) exceptions found. Using specific exception types for IntegrityError.")
except ImportError:
    psycopg_errors = None # type: ignore
    PsycopgUniqueViolation = None # type: ignore
    PsycopgCheckViolation = None # type: ignore
    PsycopgForeignKeyViolation = None # type: ignore
    logging.info("Psycopg (v3) not found. Falling back to SQLSTATE codes for IntegrityError details.")


from app.api import deps
from app.schemas.equipo import (
    EquipoRead, EquipoCreate, EquipoUpdate,
    EquipoSearchResult, GlobalSearchResult
)
from app.schemas.equipo_componente import (
    EquipoComponente,
    EquipoComponenteBodyCreate,
    EquipoComponenteCreate,
    EquipoComponenteUpdate,
    ComponenteInfo, PadreInfo
)

from app.schemas.common import Msg
from app.services.equipo import equipo_service
from app.services.equipo_componente import equipo_componente_service
from app.models.usuario import Usuario as UsuarioModel

logger = logging.getLogger(__name__)
router = APIRouter()

PERM_CREAR_EQUIPOS = "crear_equipos"
PERM_VER_EQUIPOS = "ver_equipos"
PERM_EDITAR_EQUIPOS = "editar_equipos"
PERM_ELIMINAR_EQUIPOS = "eliminar_equipos"
PERM_GESTIONAR_COMPONENTES = "gestionar_componentes"

# ==============================================================================
# Endpoints para EQUIPOS (CRUD y Búsqueda)
# ==============================================================================

@router.post("/",
             response_model=EquipoRead,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_CREAR_EQUIPOS]))],
             summary="Crear Nuevo Equipo",
             response_description="El equipo creado.")
def create_equipo(
    *,
    db: Session = Depends(deps.get_db),
    equipo_in: EquipoCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Crea un nuevo equipo físico en el sistema.
    Requiere el permiso: `crear_equipos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando crear equipo '{equipo_in.nombre}'.")
    try:
        # El servicio .create() ya no hace commit y maneja validaciones previas (incluyendo formato N/S).
        equipo = equipo_service.create(db=db, obj_in=equipo_in)
        db.commit()
        db.refresh(equipo)
        db.refresh(equipo, attribute_names=['estado', 'proveedor']) # Cargar relaciones para la respuesta
        logger.info(f"Equipo '{equipo.nombre}' (ID: {equipo.id}) creado exitosamente por '{current_user.nombre_usuario}'.")
        return equipo
    except HTTPException as http_exc:
        db.rollback() # Asegurar rollback si el servicio lanza HTTPException después de alguna interacción con DB (aunque idealmente no lo haría)
        logger.warning(f"Error HTTP al crear equipo '{equipo_in.nombre}': {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_orig = getattr(e, 'orig', None)
        pgcode = getattr(error_orig, 'pgcode', None) if error_orig else None
        error_detail_db = str(error_orig if error_orig else e)
        logger.error(f"Error de integridad al crear equipo '{equipo_in.nombre}'. PGCode: {pgcode}. Detalle DB: {error_detail_db}", exc_info=True)

        if pgcode == PG_UNIQUE_VIOLATION_SQLSTATE or (PsycopgUniqueViolation and isinstance(error_orig, PsycopgUniqueViolation)):
            if "equipos_numero_serie_key" in error_detail_db or "uq_equipos_numero_serie" in error_detail_db:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Número de serie ya registrado.")
            elif "equipos_codigo_interno_key" in error_detail_db or "uq_equipos_codigo_interno" in error_detail_db:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Código interno ya registrado.")
            else: # Otra violación de unicidad no esperada
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto de unicidad: {error_detail_db}")
        elif pgcode == PG_CHECK_VIOLATION_SQLSTATE or (PsycopgCheckViolation and isinstance(error_orig, PsycopgCheckViolation)):
            if "check_numero_serie_format" in error_detail_db: # Captura específica del error de formato de la BD
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El formato del número de serie no es válido según la base de datos. Debe ser similar a 'XXX-YYYY-ZZZZ'.")
            else: # Otra violación de CHECK constraint
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Violación de restricción de datos al crear equipo: {error_detail_db}")
        elif pgcode == PG_FK_VIOLATION_SQLSTATE or (PsycopgForeignKeyViolation and isinstance(error_orig, PsycopgForeignKeyViolation)):
            # Esto no debería ocurrir si el servicio valida las FKs, pero como fallback.
            if ("fk_equipos_estado" in error_detail_db or "equipos_estado_id_fkey" in error_detail_db) and equipo_in.estado_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Estado de equipo con ID '{equipo_in.estado_id}' no encontrado.")
            elif ("fk_equipos_proveedor" in error_detail_db or "equipos_proveedor_id_fkey" in error_detail_db) and equipo_in.proveedor_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor con ID '{equipo_in.proveedor_id}' no encontrado.")
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error de referencia a registro relacionado no válido.")
        else: # Otros IntegrityError no cubiertos
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error de base de datos al crear el equipo: {error_detail_db}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando equipo '{equipo_in.nombre}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el equipo.")

@router.get("/",
            response_model=List[EquipoRead],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_EQUIPOS]))],
            summary="Listar Equipos",
            response_description="Una lista de equipos registrados.")
def read_equipos(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando equipos (skip: {skip}, limit: {limit}).")
    equipos = equipo_service.get_multi(db, skip=skip, limit=limit)
    return equipos

@router.get("/search",
            response_model=List[EquipoSearchResult],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_EQUIPOS]))],
            summary="Buscar Equipos por término",
            response_description="Lista de equipos coincidentes ordenados por relevancia.")
def search_equipos(
    *,
    db: Session = Depends(deps.get_db),
    q: str = Query(..., min_length=3, description="Término de búsqueda (mínimo 3 caracteres)"),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' buscando equipos con término: '{q}'.")
    resultados = equipo_service.search(db=db, termino=q)
    return resultados

@router.get("/search/global",
            response_model=List[GlobalSearchResult],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_EQUIPOS]))],
            summary="Búsqueda Global",
            response_description="Resultados de búsqueda en equipos, documentos y mantenimientos.")
def search_global(
    *,
    db: Session = Depends(deps.get_db),
    q: str = Query(..., min_length=3, description="Término de búsqueda global (mínimo 3 caracteres)"),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' realizando búsqueda global con término: '{q}'.")
    resultados = equipo_service.search_global(db=db, termino=q)
    return resultados

@router.get("/{equipo_id}",
            response_model=EquipoRead,
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_EQUIPOS]))],
            summary="Obtener un Equipo por ID",
            response_description="Información detallada del equipo.")
def read_equipo_by_id(
    equipo_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando equipo ID: {equipo_id}.")
    equipo = equipo_service.get_or_404(db, id=equipo_id) # Lanza 404 si no existe
    return equipo

@router.put("/{equipo_id}",
            response_model=EquipoRead,
            dependencies=[Depends(deps.PermissionChecker([PERM_EDITAR_EQUIPOS]))],
            summary="Actualizar un Equipo",
            response_description="Información actualizada del equipo.")
def update_equipo(
    *,
    db: Session = Depends(deps.get_db),
    equipo_id: PyUUID,
    equipo_in: EquipoUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Actualiza la información de un equipo existente.
    Requiere el permiso: `editar_equipos`.
    """
    logger.info(f"Usuario '{current_user.nombre_usuario}' intentando actualizar equipo ID: {equipo_id} con datos: {equipo_in.model_dump(exclude_unset=True)}")
    db_equipo = equipo_service.get_or_404(db, id=equipo_id)
    try:
        # El servicio .update() ya no hace commit y maneja validaciones previas (incluyendo formato N/S).
        updated_equipo = equipo_service.update(db=db, db_obj=db_equipo, obj_in=equipo_in)
        db.commit()
        db.refresh(updated_equipo)
        db.refresh(updated_equipo, attribute_names=['estado', 'proveedor']) # Cargar relaciones para la respuesta
        logger.info(f"Equipo '{updated_equipo.nombre}' (ID: {equipo_id}) actualizado exitosamente por '{current_user.nombre_usuario}'.")
        return updated_equipo
    except HTTPException as http_exc: # Errores de validación del servicio
        db.rollback()
        logger.warning(f"Error HTTP al actualizar equipo ID {equipo_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e: # Errores de BD no capturados por el servicio
        db.rollback()
        error_orig = getattr(e, 'orig', None)
        pgcode = getattr(error_orig, 'pgcode', None) if error_orig else None
        error_detail_db = str(error_orig if error_orig else e)
        logger.error(f"Error de integridad al actualizar equipo ID {equipo_id}. PGCode: {pgcode}. Detalle DB: {error_detail_db}", exc_info=True)
        
        if pgcode == PG_UNIQUE_VIOLATION_SQLSTATE or (PsycopgUniqueViolation and isinstance(error_orig, PsycopgUniqueViolation)):
            # El servicio ya valida unicidad, pero esto es un fallback.
            if "equipos_numero_serie_key" in error_detail_db or "uq_equipos_numero_serie" in error_detail_db:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Número de serie ya registrado para otro equipo.")
            elif "equipos_codigo_interno_key" in error_detail_db or "uq_equipos_codigo_interno" in error_detail_db:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Código interno ya registrado para otro equipo.")
            else:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto de unicidad al actualizar equipo: {error_detail_db}")
        elif pgcode == PG_CHECK_VIOLATION_SQLSTATE or (PsycopgCheckViolation and isinstance(error_orig, PsycopgCheckViolation)):
            if "check_numero_serie_format" in error_detail_db:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El formato del nuevo número de serie no es válido según la base de datos. Debe ser similar a 'XXX-YYYY-ZZZZ'.")
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Violación de restricción de datos al actualizar equipo: {error_detail_db}")
        elif pgcode == PG_FK_VIOLATION_SQLSTATE or (PsycopgForeignKeyViolation and isinstance(error_orig, PsycopgForeignKeyViolation)):
             # El servicio valida las FKs, esto es un fallback.
            if ("fk_equipos_estado" in error_detail_db or "equipos_estado_id_fkey" in error_detail_db) and hasattr(equipo_in, 'estado_id') and equipo_in.estado_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Estado de equipo con ID '{equipo_in.estado_id}' no encontrado.")
            elif ("fk_equipos_proveedor" in error_detail_db or "equipos_proveedor_id_fkey" in error_detail_db) and hasattr(equipo_in, 'proveedor_id') and equipo_in.proveedor_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Proveedor con ID '{equipo_in.proveedor_id}' no encontrado.")
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Error de referencia a registro relacionado no válido al actualizar equipo.")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error de base de datos al actualizar el equipo: {error_detail_db}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando equipo ID {equipo_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el equipo.")

@router.delete("/{equipo_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_ELIMINAR_EQUIPOS]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar un Equipo",
               response_description="Mensaje de confirmación.")
def delete_equipo(
    *,
    db: Session = Depends(deps.get_db),
    equipo_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando eliminar equipo ID: {equipo_id}.")
    
    equipo_a_eliminar = equipo_service.get_or_404(db, id=equipo_id)
    equipo_nombre_para_log = equipo_a_eliminar.nombre
    
    try:
        equipo_service.remove(db=db, id=equipo_id) # El servicio get_or_404 está dentro de remove
        db.commit()
        logger.info(f"Equipo '{equipo_nombre_para_log}' (ID: {equipo_id}) eliminado exitosamente por '{current_user.nombre_usuario}'.")
        return {"msg": f"Equipo '{equipo_nombre_para_log}' (Serie: {equipo_a_eliminar.numero_serie}) eliminado correctamente."}
    except HTTPException as http_exc: # Captura el 404 del get_or_404 del servicio si ocurre allí.
        db.rollback() # Rollback por si acaso, aunque si es 404 del get, no hubo cambios.
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_orig = getattr(e, 'orig', None)
        error_detail_db = str(error_orig if error_orig else e)
        logger.error(f"Error de integridad al eliminar equipo '{equipo_nombre_para_log}' (ID: {equipo_id}): {error_detail_db}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se puede eliminar el equipo '{equipo_nombre_para_log}': tiene registros asociados (ej. movimientos, mantenimientos, documentos, es componente de otro equipo, o tiene componentes asignados)."
        )
    except Exception as e:
         db.rollback()
         logger.error(f"Error inesperado al eliminar equipo '{equipo_nombre_para_log}' (ID: {equipo_id}): {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al eliminar el equipo.")

# ==============================================================================
# Endpoints para COMPONENTES de Equipos
# ==============================================================================

@router.get("/{equipo_id}/componentes",
            response_model=List[ComponenteInfo],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_EQUIPOS, PERM_GESTIONAR_COMPONENTES]))],
            summary="Listar Componentes de un Equipo",
            )
def read_equipo_componentes(
    equipo_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando componentes del equipo ID: {equipo_id}.")
    equipo_service.get_or_404(db, id=equipo_id)
    component_relations = equipo_componente_service.get_componentes_by_padre(db, equipo_padre_id=equipo_id)
    return [ComponenteInfo.model_validate(rel) for rel in component_relations]

@router.get("/{equipo_id}/parte_de",
            response_model=List[PadreInfo],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_EQUIPOS, PERM_GESTIONAR_COMPONENTES]))],
            summary="Listar Padres de un Equipo (dónde es componente)",
            )
def read_equipo_padres(
    equipo_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando padres del equipo ID: {equipo_id}.")
    equipo_service.get_or_404(db, id=equipo_id)
    parent_relations = equipo_componente_service.get_padres_by_componente(db, equipo_componente_id=equipo_id)
    return [PadreInfo.model_validate(rel) for rel in parent_relations]

@router.post("/{equipo_id}/componentes",
             response_model=EquipoComponente,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_GESTIONAR_COMPONENTES]))],
             summary="Añadir un Componente a un Equipo",
             )
def add_equipo_componente(
    *,
    db: Session = Depends(deps.get_db),
    equipo_id: PyUUID,
    componente_body_in: EquipoComponenteBodyCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user)
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' añadiendo componente '{componente_body_in.equipo_componente_id}' al equipo padre '{equipo_id}'.")
    
    obj_in_for_service = EquipoComponenteCreate(
        equipo_padre_id=equipo_id,
        equipo_componente_id=componente_body_in.equipo_componente_id,
        tipo_relacion=componente_body_in.tipo_relacion,
        cantidad=componente_body_in.cantidad,
        notas=componente_body_in.notas
    )
    try:
        relacion = equipo_componente_service.create(db=db, obj_in=obj_in_for_service)
        db.commit()
        db.refresh(relacion)
        db.refresh(relacion, attribute_names=['equipo_padre', 'equipo_componente'])
        logger.info(f"Componente ID '{relacion.equipo_componente_id}' añadido al equipo padre ID '{relacion.equipo_padre_id}' (Relación ID: {relacion.id}).")
        return relacion
    except HTTPException as http_exc: # Errores de validación del servicio
        db.rollback()
        logger.warning(f"Error HTTP al añadir componente a equipo ID {equipo_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_orig = getattr(e, 'orig', None)
        pgcode = getattr(error_orig, 'pgcode', None) if error_orig else None
        error_detail_db = str(error_orig if error_orig else e)
        logger.error(f"Error de integridad al añadir componente a equipo ID {equipo_id}. PGCode: {pgcode}. Detalle DB: {error_detail_db}", exc_info=True)
        
        if pgcode == PG_UNIQUE_VIOLATION_SQLSTATE or (PsycopgUniqueViolation and isinstance(error_orig, PsycopgUniqueViolation)):
            if "uq_componente" in error_detail_db:
                 raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta relación de componente (mismo padre, mismo componente, mismo tipo) ya existe.")
        elif pgcode == PG_CHECK_VIOLATION_SQLSTATE or (PsycopgCheckViolation and isinstance(error_orig, PsycopgCheckViolation)):
            if "check_no_self_component" in error_detail_db: # Nombre de constraint de la BD
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un equipo no puede ser componente de sí mismo.")
        elif pgcode == PG_FK_VIOLATION_SQLSTATE or (PsycopgForeignKeyViolation and isinstance(error_orig, PsycopgForeignKeyViolation)):
            # El servicio debería haber validado esto, pero como fallback
            if "equipo_componentes_equipo_padre_id_fkey" in error_detail_db:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Equipo padre con ID '{equipo_id}' no encontrado.")
            if "equipo_componentes_equipo_componente_id_fkey" in error_detail_db:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Equipo componente con ID '{componente_body_in.equipo_componente_id}' no encontrado.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al añadir el componente.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado añadiendo componente a equipo ID {equipo_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al añadir componente.")

@router.put("/componentes/{relacion_id}",
            response_model=EquipoComponente,
            dependencies=[Depends(deps.PermissionChecker([PERM_GESTIONAR_COMPONENTES]))],
            summary="Actualizar una Relación de Componente",
            )
def update_equipo_componente(
    *,
    db: Session = Depends(deps.get_db),
    relacion_id: PyUUID,
    relacion_in: EquipoComponenteUpdate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' actualizando relación de componente ID: {relacion_id} con datos {relacion_in.model_dump(exclude_unset=True)}")
    db_relacion = equipo_componente_service.get_or_404(db, id=relacion_id)
    try:
        updated_relacion = equipo_componente_service.update(db=db, db_obj=db_relacion, obj_in=relacion_in)
        db.commit()
        db.refresh(updated_relacion)
        db.refresh(updated_relacion, attribute_names=['equipo_padre', 'equipo_componente'])
        logger.info(f"Relación de componente ID {relacion_id} actualizada exitosamente.")
        return updated_relacion
    except HTTPException as http_exc:
        db.rollback()
        logger.warning(f"Error HTTP al actualizar relación componente ID {relacion_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando relación componente ID {relacion_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar relación de componente.")

@router.delete("/componentes/{relacion_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_GESTIONAR_COMPONENTES]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar una Relación de Componente",
               )
def delete_equipo_componente(
    *,
    db: Session = Depends(deps.get_db),
    relacion_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando eliminar relación de componente ID: {relacion_id}")
    # El servicio remove_relation (o remove) llamará a get_or_404 internamente.
    try:
        equipo_componente_service.remove_relation(db=db, id=relacion_id)
        db.commit()
        logger.info(f"Relación de componente ID {relacion_id} eliminada exitosamente.")
        return {"msg": "Relación de componente eliminada correctamente."}
    except HTTPException as http_exc:
        db.rollback()
        logger.warning(f"Error HTTP al eliminar relación componente ID {relacion_id}: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando relación componente ID {relacion_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al eliminar la relación de componente.")
