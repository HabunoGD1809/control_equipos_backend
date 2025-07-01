import pytest
from httpx import AsyncClient
from uuid import uuid4
from fastapi import status
from fastapi.encoders import jsonable_encoder
from decimal import Decimal

from app.core.config import settings
from app.models.tipo_item_inventario import TipoItemInventario
from app.models.inventario_stock import InventarioStock
from app.schemas.inventario_stock import InventarioStockUpdate
from app.schemas.inventario_movimiento import InventarioMovimientoCreate
from app.schemas.enums import TipoMovimientoInvEnum

from sqlalchemy.orm import Session

# Marcar todos los tests en este archivo para que se ejecuten con el runner de asyncio
pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_get_total_stock_for_item(
    client: AsyncClient,
    auth_token_supervisor: str,
    stock_inicial_toner: InventarioStock
):
    """
    Prueba el endpoint GET /inventario/stock/item/{tipo_item_id}/total.
    Verifica que el total de stock para un ítem se calcule correctamente.
    """
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    tipo_item_id = stock_inicial_toner.tipo_item_id
    cantidad_esperada = stock_inicial_toner.cantidad_actual

    # 1. Llamar al endpoint para obtener el stock total
    response = await client.get(
        f"{settings.API_V1_STR}/inventario/stock/item/{tipo_item_id}/total",
        headers=headers
    )

    # 2. Verificar la respuesta
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert data["tipo_item_id"] == str(tipo_item_id)
    assert data["cantidad_total"] == cantidad_esperada, "La cantidad total de stock no coincide con la esperada."

@pytest.mark.asyncio
async def test_update_stock_details(
    client: AsyncClient,
    auth_token_admin: str,
    stock_inicial_toner: InventarioStock
):
    """
    Prueba el endpoint PUT /inventario/stock/{stock_id}/details.
    Verifica la actualización de detalles menores como el lote o fecha de caducidad.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    stock_id = stock_inicial_toner.id
    nuevo_lote = f"LOTE-ACTUALIZADO-{uuid4().hex[:6]}"
    nueva_fecha = "2099-12-31"

    update_data = {
        "lote": nuevo_lote,
        "fecha_caducidad": nueva_fecha
    }

    # 1. Llamar al endpoint de actualización
    response = await client.put(
        f"{settings.API_V1_STR}/inventario/stock/{stock_id}/details",
        headers=headers,
        json=update_data
    )

    # 2. Verificar la respuesta de la actualización
    assert response.status_code == status.HTTP_200_OK, response.text
    updated_stock = response.json()
    assert updated_stock["lote"] == nuevo_lote
    assert updated_stock["fecha_caducidad"] == nueva_fecha

@pytest.mark.asyncio
async def test_delete_tipo_item_con_stock_falla(
    client: AsyncClient,
    auth_token_admin: str,
    stock_inicial_toner: InventarioStock
):
    """
    Prueba de lógica de negocio cruzada:
    Verifica que no se puede eliminar un Tipo de Item si tiene stock asociado.
    Esto prueba la restricción de Foreign Key (ON DELETE RESTRICT).
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    tipo_item_id = stock_inicial_toner.tipo_item_id

    # 1. Intentar eliminar el tipo de ítem que tiene stock
    response = await client.delete(
        f"{settings.API_V1_STR}/inventario/tipos/{tipo_item_id}",
        headers=headers
    )

    # 2. Verificar que la API responde con un error de conflicto (409)
    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    error_detail = response.json().get("detail", "").lower()
    assert "no se puede eliminar" in error_detail
    assert "tiene stock o movimientos asociados" in error_detail

@pytest.mark.asyncio
async def test_salida_inventario_sin_stock_suficiente_falla(
    client: AsyncClient,
    auth_token_admin: str,
    stock_inicial_toner: InventarioStock
):
    """
    Prueba de lógica de negocio cruzada:
    Verifica que un movimiento de salida falla si la cantidad solicitada
    es mayor que el stock disponible, probando el trigger de la base de datos.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    cantidad_a_sacar = stock_inicial_toner.cantidad_actual + 1  # Una unidad más de la que hay

    movimiento_data = {
        "tipo_item_id": str(stock_inicial_toner.tipo_item_id),
        "tipo_movimiento": TipoMovimientoInvEnum.SALIDA_USO.value,
        "cantidad": cantidad_a_sacar,
        "ubicacion_origen": stock_inicial_toner.ubicacion,
        "lote_origen": stock_inicial_toner.lote,
        "motivo_ajuste": "Prueba de stock insuficiente"
    }

    # 1. Intentar crear el movimiento de salida
    response = await client.post(
        f"{settings.API_V1_STR}/inventario/movimientos/",
        headers=headers,
        json=movimiento_data
    )

    # 2. Verificar que la API devuelve un error de conflicto (409) por stock insuficiente
    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    error_detail = response.json().get("detail", "").lower()
    assert "stock insuficiente" in error_detail
