import pytest
from httpx import AsyncClient
from uuid import uuid4
from fastapi import status
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.schemas.tipo_item_inventario import TipoItemInventarioCreate
from app.schemas.enums import CategoriaItemInventarioEnum, UnidadMedidaEnum, TipoMovimientoInvEnum
from app.models.tipo_item_inventario import TipoItemInventario

# Marca todos los tests en este archivo para que se ejecuten con el runner de asyncio
pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_crud_tipo_item_inventario(client: AsyncClient, auth_token_admin: str):
    """
    Prueba el ciclo completo de Crear, Leer, Actualizar y Borrar (CRUD)
    para un tipo de item de inventario.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    item_name = f"Item CRUD {uuid4().hex[:6]}"
    item_sku = f"SKU-CRUD-{uuid4().hex[:8].upper()}"

    # 1. CREATE
    create_schema = TipoItemInventarioCreate(
        nombre=item_name,
        descripcion="Item para probar el CRUD completo",
        categoria=CategoriaItemInventarioEnum.PARTE_REPUESTO,
        unidad_medida=UnidadMedidaEnum.UNIDAD,
        sku=item_sku,
        stock_minimo=5,
        marca="MarcaTest",
        modelo="Modelo-XYZ",
        codigo_barras=None,
        proveedor_preferido_id=None
    )
    create_response = await client.post(
        f"{settings.API_V1_STR}/inventario/tipos/",
        headers=headers,
        json=jsonable_encoder(create_schema)
    )
    assert create_response.status_code == status.HTTP_201_CREATED, create_response.text
    created_item = create_response.json()
    assert created_item["nombre"] == item_name
    item_id = created_item["id"]

    # 2. READ (by ID)
    get_response = await client.get(f"{settings.API_V1_STR}/inventario/tipos/{item_id}", headers=headers)
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["id"] == item_id

    # 3. UPDATE
    update_data = {"descripcion": "Descripción CRUD actualizada", "stock_minimo": 15}
    update_response = await client.put(f"{settings.API_V1_STR}/inventario/tipos/{item_id}", headers=headers, json=update_data)
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["stock_minimo"] == 15

    # 4. DELETE
    delete_response = await client.delete(f"{settings.API_V1_STR}/inventario/tipos/{item_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_200_OK

    # Verify DELETE
    get_after_delete_response = await client.get(f"{settings.API_V1_STR}/inventario/tipos/{item_id}", headers=headers)
    assert get_after_delete_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_get_low_stock_items(client: AsyncClient, auth_token_admin: str, tipo_item_toner: TipoItemInventario):
    """
    Prueba el endpoint de bajo stock. Primero se asegura de que haya stock,
    luego realiza una salida para que quede por debajo del mínimo, y finalmente verifica.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    
    # Paso 1: Realizar una ENTRADA de stock para asegurar que tenemos inventario.
    # La fixture 'tipo_item_toner' establece un stock mínimo de 2. Vamos a añadir 10 unidades.
    entrada_data = {
        "tipo_item_id": str(tipo_item_toner.id),
        "tipo_movimiento": TipoMovimientoInvEnum.ENTRADA_COMPRA.value,
        "cantidad": 10,
        "ubicacion_destino": "Almacén Principal Toner Fixture",
        "costo_unitario": 75.50
    }
    entrada_response = await client.post(
        f"{settings.API_V1_STR}/inventario/movimientos/",
        headers=headers,
        json=jsonable_encoder(entrada_data)
    )
    assert entrada_response.status_code == status.HTTP_201_CREATED, \
        f"FALLO PRE-CONDICIÓN: La entrada de stock no se pudo crear. Error: {entrada_response.text}"

    # Paso 2: Realizar una SALIDA que deje el stock por debajo del mínimo (stock_minimo=2).
    # Stock actual: 10. Salida: 9. Stock final: 1.
    salida_data = {
        "tipo_item_id": str(tipo_item_toner.id),
        "tipo_movimiento": TipoMovimientoInvEnum.SALIDA_USO.value,
        "cantidad": 9,
        "ubicacion_origen": "Almacén Principal Toner Fixture",
    }
    salida_response = await client.post(
        f"{settings.API_V1_STR}/inventario/movimientos/",
        headers=headers,
        json=jsonable_encoder(salida_data)
    )
    assert salida_response.status_code == status.HTTP_201_CREATED, \
        f"FALLO: La salida de stock falló cuando debería haber tenido éxito. Error: {salida_response.text}"

    # Paso 3: Verificar que el endpoint de bajo stock ahora incluye nuestro item.
    response = await client.get(f"{settings.API_V1_STR}/inventario/tipos/bajo-stock/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    low_stock_items = response.json()
    assert isinstance(low_stock_items, list)
    
    found = any(item["id"] == str(tipo_item_toner.id) for item in low_stock_items)
    assert found, "El item de prueba, que ahora tiene bajo stock, no fue encontrado en la lista del endpoint."
