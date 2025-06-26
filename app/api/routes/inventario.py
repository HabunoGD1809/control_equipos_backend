import logging
from typing import Any, Dict, List, Optional
from uuid import UUID as PyUUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, ProgrammingError

try:
    from psycopg import errors as psycopg_errors
    PG_RaiseException = psycopg_errors.RaiseException
except ImportError:
    psycopg_errors = None
    PG_RaiseException = None # type: ignore


from app.api import deps
from app.schemas.tipo_item_inventario import (
    TipoItemInventario, TipoItemInventarioCreate, TipoItemInventarioUpdate,
)
from app.schemas.inventario_stock import InventarioStock, InventarioStockUpdate, InventarioStockTotal
from app.schemas.inventario_movimiento import InventarioMovimiento, InventarioMovimientoCreate
from app.schemas.common import Msg
from app.services.tipo_item_inventario import tipo_item_inventario_service
from app.services.inventario_stock import inventario_stock_service
from app.services.inventario_movimiento import inventario_movimiento_service
from app.models.usuario import Usuario as UsuarioModel
from app.schemas.enums import TipoMovimientoInvEnum

PERM_ADMIN_TIPOS_INV = "administrar_inventario_tipos"
PERM_ADMIN_STOCK_INV = "administrar_inventario_stock"
PERM_VER_INV = "ver_inventario"

logger = logging.getLogger(__name__)
router = APIRouter()

# ==============================================================================
# Endpoints para TIPOS DE ITEM DE INVENTARIO (Catálogo)
# ==============================================================================
@router.post("/tipos/",
             response_model=TipoItemInventario,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_TIPOS_INV]))],
             summary="Crear Tipo de Item de Inventario",
             )
def create_tipo_item_inventario(
    *,
    db: Session = Depends(deps.get_db),
    tipo_in: TipoItemInventarioCreate,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Crea un nuevo tipo de item para el inventario."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' creando tipo de item de inventario: {tipo_in.nombre}")
    try:
        tipo_item = tipo_item_inventario_service.create(db=db, obj_in=tipo_in)
        db.commit()
        db.refresh(tipo_item)
        logger.info(f"Tipo de item de inventario '{tipo_item.nombre}' (ID: {tipo_item.id}) creado exitosamente.")
        return tipo_item
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al crear tipo de item '{tipo_in.nombre}': {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al crear tipo de item '{tipo_in.nombre}': {error_detail}", exc_info=True)
        if "uq_tipo_item_inventario_nombre" in error_detail or "tipo_item_inventario_nombre_key" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto: Ya existe un tipo de item con el nombre '{tipo_in.nombre}'.")
        if "uq_tipo_item_inventario_sku" in error_detail or "tipo_item_inventario_sku_key" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto: Ya existe un tipo de item con el SKU '{tipo_in.sku}'.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear el tipo de item.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando tipo de item '{tipo_in.nombre}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el tipo de item.")

@router.get("/tipos/",
            response_model=List[TipoItemInventario],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_INV]))],
            summary="Listar Tipos de Item de Inventario",
            )
def read_tipos_item_inventario(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando tipos de item de inventario.")
    return tipo_item_inventario_service.get_multi(db, skip=skip, limit=limit)

@router.get("/tipos/bajo-stock/",
            response_model=List[Dict[str, Any]],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_INV, PERM_ADMIN_STOCK_INV]))],
            summary="Listar Items con Bajo Stock",
            )
def read_low_stock_items(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando items con bajo stock.")
    return tipo_item_inventario_service.get_low_stock_items(db, skip=skip, limit=limit)

@router.get("/tipos/{tipo_id}",
            response_model=TipoItemInventario,
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_INV]))],
            summary="Obtener Tipo de Item por ID",
            )
def read_tipo_item_inventario_by_id(
    tipo_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando tipo de item ID: {tipo_id}.")
    return tipo_item_inventario_service.get_or_404(db, id=tipo_id)

@router.put("/tipos/{tipo_id}",
            response_model=TipoItemInventario,
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_TIPOS_INV]))],
            summary="Actualizar Tipo de Item",
            )
def update_tipo_item_inventario(
    *,
    db: Session = Depends(deps.get_db),
    tipo_id: PyUUID,
    tipo_in: TipoItemInventarioUpdate = Body(...),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' actualizando tipo de item ID: {tipo_id} con datos {tipo_in.model_dump(exclude_unset=True)}")
    db_tipo = tipo_item_inventario_service.get_or_404(db, id=tipo_id)
    try:
        updated_tipo = tipo_item_inventario_service.update(db=db, db_obj=db_tipo, obj_in=tipo_in)
        db.commit()
        db.refresh(updated_tipo)
        logger.info(f"Tipo de item '{updated_tipo.nombre}' (ID: {tipo_id}) actualizado exitosamente.")
        return updated_tipo
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al actualizar tipo de item ID {tipo_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al actualizar tipo de item ID {tipo_id}: {error_detail}", exc_info=True)
        if "uq_tipo_item_inventario_nombre" in error_detail or "tipo_item_inventario_nombre_key" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto: Ya existe un tipo de item con el nombre '{tipo_in.nombre}'.")
        if "uq_tipo_item_inventario_sku" in error_detail or "tipo_item_inventario_sku_key" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto: Ya existe un tipo de item con el SKU '{tipo_in.sku}'.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar el tipo de item.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando tipo de item ID {tipo_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar el tipo de item.")

@router.delete("/tipos/{tipo_id}",
               response_model=Msg,
               dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_TIPOS_INV]))],
               status_code=status.HTTP_200_OK,
               summary="Eliminar Tipo de Item",
               )
def delete_tipo_item_inventario(
    *,
    db: Session = Depends(deps.get_db),
    tipo_id: PyUUID,
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.warning(f"Usuario '{current_user.nombre_usuario}' intentando eliminar tipo de item ID: {tipo_id}")
    tipo_a_eliminar = tipo_item_inventario_service.get_or_404(db, id=tipo_id)
    nombre_tipo_log = tipo_a_eliminar.nombre
    try:
        tipo_item_inventario_service.remove(db=db, id=tipo_id)
        db.commit()
        logger.info(f"Tipo de item '{nombre_tipo_log}' (ID: {tipo_id}) eliminado exitosamente.")
        return {"msg": f"Tipo de item '{nombre_tipo_log}' eliminado."}
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al eliminar tipo item '{nombre_tipo_log}' (ID: {tipo_id}): {error_detail}", exc_info=True)
        if "violates foreign key constraint" in error_detail.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede eliminar el tipo '{nombre_tipo_log}' porque tiene stock o movimientos asociados.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No se puede eliminar el tipo de item debido a referencias existentes.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando tipo item '{nombre_tipo_log}' (ID: {tipo_id}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")

# ==============================================================================
# Endpoints para STOCK DE INVENTARIO
# ==============================================================================
@router.get("/stock/",
            response_model=List[InventarioStock],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_INV]))],
            summary="Consultar Stock de Inventario",
            )
def read_inventario_stock(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    ubicacion: Optional[str] = Query(None, description="Filtrar por ubicación específica"),
    # ===== INICIO CORRECCIÓN =====
    lote: Optional[str] = Query(None, description="Filtrar por lote específico"),
    # ===== FIN CORRECCIÓN =====
    tipo_item_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de tipo de item"),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' consultando stock con filtros: ubicacion='{ubicacion}', lote='{lote}', tipo_item_id='{tipo_item_id}'.")
    
    # ===== INICIO CORRECCIÓN =====
    # Modificar la lógica para manejar el filtro por lote correctamente
    stock_records = inventario_stock_service.get_multi_by_filters(
        db,
        tipo_item_id=tipo_item_id,
        ubicacion=ubicacion,
        lote=lote,
        skip=skip,
        limit=limit
    )
    return stock_records
    # ===== FIN CORRECCIÓN =====

@router.get("/stock/item/{tipo_item_id}/total",
            response_model=InventarioStockTotal,
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_INV]))],
            summary="Obtener Stock Total de un Item",
            )
def read_total_stock_for_item(
    tipo_item_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando stock total para TipoItem ID: {tipo_item_id}.")
    tipo_item_inventario_service.get_or_404(db, id=tipo_item_id)
    total = inventario_stock_service.get_total_stock_for_item(db, tipo_item_id=tipo_item_id)
    return {"tipo_item_id": tipo_item_id, "cantidad_total": total}


@router.put("/stock/{stock_id}/details",
            response_model=InventarioStock,
            dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_STOCK_INV]))],
            summary="Actualizar Detalles Menores de un Registro de Stock",
            )
def update_inventario_stock_details(
    *,
    db: Session = Depends(deps.get_db),
    stock_id: PyUUID,
    stock_in: InventarioStockUpdate = Body(...),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Actualiza campos como lote, fecha_caducidad, notas de un registro de stock existente."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' actualizando detalles de stock ID: {stock_id} con datos {stock_in.model_dump(exclude_unset=True)}")
    db_stock = inventario_stock_service.get_or_404(db, id=stock_id)
    try:
        updated_stock = inventario_stock_service.update_stock_details(db=db, stock_record=db_stock, obj_in=stock_in)
        db.commit()
        db.refresh(updated_stock)
        logger.info(f"Detalles de stock ID {stock_id} actualizados exitosamente.")
        return updated_stock
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al actualizar detalles de stock ID {stock_id}: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al actualizar detalles de stock ID {stock_id}: {error_detail}", exc_info=True)
        if "uq_item_ubicacion_lote" in error_detail.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto: Ya existe un registro de stock con ese tipo de item, ubicación y lote.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al actualizar los detalles del stock.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado actualizando detalles de stock ID {stock_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al actualizar los detalles del stock.")

# ==============================================================================
# Endpoints para MOVIMIENTOS DE INVENTARIO
# ==============================================================================
@router.post("/movimientos/",
             response_model=InventarioMovimiento,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([PERM_ADMIN_STOCK_INV]))],
             summary="Registrar un Movimiento de Inventario",
             )
def create_inventario_movimiento(
    *,
    db: Session = Depends(deps.get_db),
    movimiento_in: InventarioMovimientoCreate = Body(...),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """
    Registra una nueva transacción de inventario.
    Requiere el permiso: `administrar_inventario_stock`.
    """
    tipo_mov_valor = movimiento_in.tipo_movimiento.value if isinstance(movimiento_in.tipo_movimiento, TipoMovimientoInvEnum) else movimiento_in.tipo_movimiento
    logger.info(f"Usuario '{current_user.nombre_usuario}' registrando movimiento de inventario tipo '{tipo_mov_valor}' para TipoItem ID {movimiento_in.tipo_item_id}.")
    try:
        movimiento = inventario_movimiento_service.create_movimiento(db=db, obj_in=movimiento_in, current_user=current_user)
        db.commit()
        db.refresh(movimiento)
        db.refresh(movimiento, attribute_names=['tipo_item', 'usuario_registrador'])
        if movimiento.equipo_asociado_id: db.refresh(movimiento, attribute_names=['equipo_asociado'])
        if movimiento.mantenimiento_id: db.refresh(movimiento, attribute_names=['mantenimiento_asociado'])

        logger.info(f"Movimiento de inventario ID {movimiento.id} ({movimiento.tipo_movimiento}) creado exitosamente por '{current_user.nombre_usuario}'.")
        return movimiento
    except HTTPException as http_exc:
        logger.warning(f"Error HTTP al crear movimiento de inventario: {http_exc.detail}")
        raise http_exc
    except IntegrityError as e:
        db.rollback()
        error_detail = str(getattr(e, 'orig', e))
        logger.error(f"Error de integridad al crear movimiento de inventario: {error_detail}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de base de datos al crear el movimiento de inventario.")
    except ProgrammingError as e:
        db.rollback()
        error_message_from_db = "Error de base de datos al procesar el movimiento."
        pg_error_detail = None

        if hasattr(e, 'orig') and e.orig:
            pg_error_detail = str(e.orig)
            if PG_RaiseException and isinstance(e.orig, PG_RaiseException) and hasattr(e.orig, 'diag') and hasattr(e.orig.diag, 'message_primary'):
                error_message_from_db = e.orig.diag.message_primary
            else:
                error_message_from_db = pg_error_detail

        logger.error(f"Error de base de datos (ProgrammingError) creando movimiento: {pg_error_detail or str(e)}", exc_info=True)

        # ===== INICIO DE LA CORRECCIÓN =====
        if error_message_from_db and "stock insuficiente" in error_message_from_db.lower():
        # ===== FIN DE LA CORRECCIÓN =====
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_message_from_db)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No se pudo procesar el movimiento: {error_message_from_db}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando movimiento de inventario: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el movimiento de inventario.")


@router.get("/movimientos/",
            response_model=List[InventarioMovimiento],
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_INV]))],
            summary="Listar Movimientos de Inventario",
            )
def read_inventario_movimientos(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    tipo_item_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de tipo de item"),
    equipo_asociado_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de equipo asociado"),
    mantenimiento_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de mantenimiento asociado"),
    usuario_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de usuario que registró"),
    tipo_movimiento: Optional[str] = Query(None, description="Filtrar por tipo de movimiento (valor string del Enum)"),
    ubicacion: Optional[str] = Query(None, description="Filtrar por ubicación (origen o destino)"),
    start_date: Optional[datetime] = Query(None, description="Fecha de inicio para filtrar movimientos (YYYY-MM-DDTHH:MM:SS)"),
    end_date: Optional[datetime] = Query(None, description="Fecha de fin para filtrar movimientos (YYYY-MM-DDTHH:MM:SS)"),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    """Obtiene una lista de movimientos de inventario, con filtros opcionales."""
    logger.info(f"Usuario '{current_user.nombre_usuario}' listando movimientos de inventario con filtros.")
    movimientos = inventario_movimiento_service.get_multi_with_filters(
        db,
        skip=skip,
        limit=limit,
        tipo_item_id=tipo_item_id,
        ubicacion=ubicacion,
        tipo_movimiento=tipo_movimiento,
        start_date=start_date,
        end_date=end_date,
        usuario_id=usuario_id,
        equipo_asociado_id=equipo_asociado_id,
        mantenimiento_id=mantenimiento_id
    )
    return movimientos


@router.get("/movimientos/{movimiento_id}",
            response_model=InventarioMovimiento,
            dependencies=[Depends(deps.PermissionChecker([PERM_VER_INV]))],
            summary="Obtener Movimiento de Inventario por ID",
            )
def read_inventario_movimiento_by_id(
    movimiento_id: PyUUID,
    db: Session = Depends(deps.get_db),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' solicitando movimiento de inventario ID: {movimiento_id}.")
    return inventario_movimiento_service.get_or_404(db, id=movimiento_id)

# PUT y DELETE para movimientos de inventario están deshabilitados intencionalmente en el servicio
# ya que los errores se corrigen con movimientos de ajuste.
# Si se necesitara un PUT para actualizar 'notas' o 'referencia_externa', se añadiría aquí
# llamando a inventario_movimiento_service.update() y manejando commit/refresh.
