import logging
from typing import Any, List, Optional
from uuid import UUID as PyUUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.core import permissions as perms
from app.models.inventario_stock import InventarioStock
from app.models.inventario_movimiento import InventarioMovimiento
from app.models.usuario import Usuario as UsuarioModel

try:
    from psycopg import errors as psycopg_errors
    PG_RaiseException = psycopg_errors.RaiseException
except ImportError:
    psycopg_errors = None
    PG_RaiseException = None # type: ignore


from app.api import deps
from app.schemas.tipo_item_inventario import (
    TipoItemInventario, TipoItemInventarioCreate, TipoItemInventarioUpdate, TipoItemInventarioConStock
)
from app.schemas.inventario_stock import InventarioStock as InventarioStockSchema, InventarioStockUpdate, InventarioStockTotal
from app.schemas.inventario_movimiento import InventarioMovimiento as InventarioMovimientoSchema, InventarioMovimientoCreate
from app.schemas.common import Msg
from app.services.tipo_item_inventario import tipo_item_inventario_service
from app.services.inventario_stock import inventario_stock_service
from app.services.inventario_movimiento import inventario_movimiento_service
from app.schemas.enums import TipoMovimientoInvEnum

logger = logging.getLogger(__name__)
router = APIRouter()

# ==============================================================================
# Endpoints para TIPOS DE ITEM DE INVENTARIO (Catálogo)
# ==============================================================================
@router.post("/tipos/",
             response_model=TipoItemInventario,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_INVENTARIO_TIPOS]))],
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
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_INVENTARIO]))],
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
            response_model=List[TipoItemInventarioConStock],
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_INVENTARIO, perms.PERM_ADMINISTRAR_INVENTARIO_STOCK]))],
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
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_INVENTARIO]))],
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
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_INVENTARIO_TIPOS]))],
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
               dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_INVENTARIO_TIPOS]))],
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
    
    stock_existente = db.query(InventarioStock).filter(InventarioStock.tipo_item_id == tipo_id).first()
    if stock_existente:
        logger.warning(f"Intento de eliminar tipo de item '{nombre_tipo_log}' que tiene stock asociado.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede eliminar el tipo '{nombre_tipo_log}' porque tiene stock o movimientos asociados.")
    
    movimientos_existentes = db.query(InventarioMovimiento).filter(InventarioMovimiento.tipo_item_id == tipo_id).first()
    if movimientos_existentes:
        logger.warning(f"Intento de eliminar tipo de item '{nombre_tipo_log}' que tiene movimientos asociados.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"No se puede eliminar el tipo '{nombre_tipo_log}' porque tiene stock o movimientos asociados.")

    try:
        tipo_item_inventario_service.remove(db=db, id=tipo_id)
        db.commit()
        logger.info(f"Tipo de item '{nombre_tipo_log}' (ID: {tipo_id}) eliminado exitosamente.")
        return {"msg": f"Tipo de item '{nombre_tipo_log}' eliminado."}
    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado eliminando tipo item '{nombre_tipo_log}' (ID: {tipo_id}): {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor.")

# ==============================================================================
# Endpoints para STOCK DE INVENTARIO
# ==============================================================================
@router.get("/stock/",
            response_model=List[InventarioStockSchema],
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_INVENTARIO]))],
            summary="Consultar Stock de Inventario",
            )
def read_inventario_stock(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    ubicacion: Optional[str] = Query(None, description="Filtrar por ubicación específica"),
    lote: Optional[str] = Query(None, description="Filtrar por lote específico"),
    tipo_item_id: Optional[PyUUID] = Query(None, description="Filtrar por ID de tipo de item"),
    current_user: UsuarioModel = Depends(deps.get_current_active_user),
) -> Any:
    logger.info(f"Usuario '{current_user.nombre_usuario}' consultando stock con filtros: ubicacion='{ubicacion}', lote='{lote}', tipo_item_id='{tipo_item_id}'.")
    
    stock_records = inventario_stock_service.get_multi_by_filters(
        db,
        tipo_item_id=tipo_item_id,
        ubicacion=ubicacion,
        lote=lote,
        skip=skip,
        limit=limit
    )
    return stock_records

@router.get("/stock/item/{tipo_item_id}/total",
            response_model=InventarioStockTotal,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_INVENTARIO]))],
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
            response_model=InventarioStockSchema,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_INVENTARIO_STOCK]))],
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
             response_model=InventarioMovimientoSchema,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(deps.PermissionChecker([perms.PERM_ADMINISTRAR_INVENTARIO_STOCK]))],
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
    El trigger de la base de datos se encargará de actualizar el stock total.
    """
    
    # 1. Obtenemos el valor string del Enum para logging y validaciones
    tipo_mov_valor = movimiento_in.tipo_movimiento.value
    
    logger.info(
        f"Usuario '{current_user.nombre_usuario}' registrando movimiento de inventario "
        f"tipo '{tipo_mov_valor}' para TipoItem ID {movimiento_in.tipo_item_id}."
    )

    # 2. Definimos qué tipos de movimiento son de salida
    tipos_de_salida = [
        TipoMovimientoInvEnum.SALIDA_USO,
        TipoMovimientoInvEnum.SALIDA_DESCARTE,
        TipoMovimientoInvEnum.AJUSTE_NEGATIVO,
        TipoMovimientoInvEnum.TRANSFERENCIA_SALIDA,
        TipoMovimientoInvEnum.DEVOLUCION_PROVEEDOR
    ]

    # 3. Verificamos el stock ANTES de intentar la operación si es una salida
    if movimiento_in.tipo_movimiento in tipos_de_salida and movimiento_in.ubicacion_origen:
        stock_origen = inventario_stock_service.get_stock_record(
            db,
            tipo_item_id=movimiento_in.tipo_item_id,
            ubicacion=movimiento_in.ubicacion_origen,
            lote=movimiento_in.lote_origen
        )
        
        stock_disponible = stock_origen.cantidad_actual if stock_origen else 0
        
        if stock_disponible < movimiento_in.cantidad:
            logger.warning(
                f"Intento de registrar salida con stock insuficiente. "
                f"Item: {movimiento_in.tipo_item_id}, Ubicación: {movimiento_in.ubicacion_origen}, "
                f"Requerido: {movimiento_in.cantidad}, Disponible: {stock_disponible}"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Stock insuficiente en '{movimiento_in.ubicacion_origen}'. "
                    f"Se requieren {movimiento_in.cantidad} unidades, pero solo hay {stock_disponible} disponibles."
                ),
            )

    try:
        movimiento = inventario_movimiento_service.create_movimiento(db=db, obj_in=movimiento_in, current_user=current_user)
        db.commit()
        db.refresh(movimiento)
        
        # Refrescar relaciones para que se muestren en la respuesta
        if hasattr(movimiento, 'tipo_item'): db.refresh(movimiento, attribute_names=['tipo_item'])
        if hasattr(movimiento, 'usuario_registrador'): db.refresh(movimiento, attribute_names=['usuario_registrador'])
        if movimiento.equipo_asociado_id: db.refresh(movimiento, attribute_names=['equipo_asociado'])
        if movimiento.mantenimiento_id: db.refresh(movimiento, attribute_names=['mantenimiento_asociado'])
        
        logger.info(f"Movimiento de inventario ID {movimiento.id} ({tipo_mov_valor}) creado exitosamente por '{current_user.nombre_usuario}'.")
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
            if PG_RaiseException and isinstance(e.orig, PG_RaiseException) and hasattr(e.orig.diag, 'message_primary'):
                error_message_from_db = e.orig.diag.message_primary
            else:
                error_message_from_db = pg_error_detail

        logger.error(f"Error de base de datos (ProgrammingError) creando movimiento: {pg_error_detail or str(e)}", exc_info=True)

        if error_message_from_db and "stock insuficiente" in error_message_from_db.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_message_from_db)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No se pudo procesar el movimiento: {error_message_from_db}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error inesperado creando movimiento de inventario: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servidor al crear el movimiento de inventario.")


@router.get("/movimientos/",
            response_model=List[InventarioMovimientoSchema],
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_INVENTARIO]))],
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
            response_model=InventarioMovimientoSchema,
            dependencies=[Depends(deps.PermissionChecker([perms.PERM_VER_INVENTARIO]))],
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
