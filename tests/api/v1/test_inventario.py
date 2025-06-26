import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from fastapi import status
from fastapi.encoders import jsonable_encoder
from decimal import Decimal
from pydantic import ValidationError 

from app.core.config import settings
from app.models.tipo_item_inventario import TipoItemInventario
from app.models.inventario_stock import InventarioStock
from app.schemas.tipo_item_inventario import TipoItemInventarioCreate, TipoItemInventarioUpdate
from app.schemas.inventario_stock import InventarioStockUpdate
from app.schemas.inventario_movimiento import InventarioMovimientoCreate
from app.schemas.enums import TipoMovimientoInvEnum, UnidadMedidaEnum 

from sqlalchemy.orm import Session

pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="function")
async def tipo_item_toner(db: Session) -> TipoItemInventario:
    nombre_test = "Toner Test Fixture"
    sku_test = f"TONER-FX-{uuid4().hex[:6]}"
    categoria_valida = 'Consumible'
    item = db.query(TipoItemInventario).filter(TipoItemInventario.nombre == nombre_test).first()
    if not item:
        item = TipoItemInventario(
            nombre=nombre_test, categoria=categoria_valida, 
            unidad_medida=UnidadMedidaEnum.UNIDAD.value, sku=sku_test, stock_minimo=2
        )
        db.add(item); db.flush(); db.refresh(item)
    else:
        if item.categoria != categoria_valida: item.categoria = categoria_valida
        if not item.sku: item.sku = sku_test
        db.add(item); db.flush(); db.refresh(item)
    return item

@pytest.fixture(scope="function")
def stock_inicial_toner(db: Session, tipo_item_toner: TipoItemInventario) -> InventarioStock:
    """
    Asegura que haya una cantidad de stock predecible para un item y lote específicos.
    Usa un lote fijo para hacer la prueba determinista.
    """
    ubicacion_test = "Almacén Principal Test"
    # CORREGIDO: Usar un lote fijo en lugar de uno aleatorio
    lote_fijo = "LOTE-SALIDA-TEST-001"
    cantidad_necesaria = 10 
    costo_inicial = Decimal("25.50")
    
    stock = db.query(InventarioStock).filter_by(
        tipo_item_id=tipo_item_toner.id, ubicacion=ubicacion_test, lote=lote_fijo
    ).first()

    if not stock:
        stock = InventarioStock(
            tipo_item_id=tipo_item_toner.id,
            ubicacion=ubicacion_test,
            lote=lote_fijo,
            cantidad_actual=cantidad_necesaria,
            costo_promedio_ponderado=costo_inicial
        )
        db.add(stock)
    # Asegura que el stock siempre sea el esperado para la prueba
    elif stock.cantidad_actual < cantidad_necesaria:
        stock.cantidad_actual = cantidad_necesaria
    
    db.commit()
    db.refresh(stock)
    return stock

async def test_create_inventario_movimiento_salida_success(
    client: AsyncClient, auth_token_admin: str, 
    stock_inicial_toner: InventarioStock, 
    tipo_item_toner: TipoItemInventario
):
    """Prueba registrar una salida de inventario y verificar que el stock se reduce."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    cantidad_salida = 2 
    stock_antes = stock_inicial_toner.cantidad_actual
    
    mov_data = {
        "tipo_item_id": str(tipo_item_toner.id),
        "tipo_movimiento": TipoMovimientoInvEnum.SALIDA_USO.value,
        "cantidad": cantidad_salida,
        "ubicacion_origen": stock_inicial_toner.ubicacion,
        "lote_origen": stock_inicial_toner.lote,
    }

    response = await client.post(f"{settings.API_V1_STR}/inventario/movimientos/", headers=headers, json=mov_data)
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error API (Salida): {response.text}"
    
    # Verificar el stock después del movimiento
    stock_despues_resp = await client.get(
        f"{settings.API_V1_STR}/inventario/stock/", 
        headers=headers, 
        params={
            "tipo_item_id": mov_data["tipo_item_id"], 
            "ubicacion": stock_inicial_toner.ubicacion,
            "lote": stock_inicial_toner.lote 
        }
    )
    assert stock_despues_resp.status_code == status.HTTP_200_OK, f"No se pudo obtener el stock después del movimiento: {stock_despues_resp.text}"
    stock_despues_data = stock_despues_resp.json()
    
    assert len(stock_despues_data) > 0, "La API no devolvió ningún registro de stock para los filtros dados."
    stock_actual = int(stock_despues_data[0]["cantidad_actual"])
    
    assert stock_actual == stock_antes - cantidad_salida, "El stock no se redujo correctamente."

async def test_create_inventario_movimiento_entrada_success(
    client: AsyncClient, auth_token_admin: str,
    tipo_item_toner: TipoItemInventario
):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    cantidad_entrada = 5 
    ubicacion_destino = f"Almacén Test Entrada OK {uuid4().hex[:4]}"
    costo_entrada = Decimal("28.50")

    stock_antes_resp = await client.get(f"{settings.API_V1_STR}/inventario/stock/", headers=headers, params={"tipo_item_id": str(tipo_item_toner.id), "ubicacion": ubicacion_destino})
    stock_antes_data = stock_antes_resp.json()
    stock_item = next((s for s in stock_antes_data if s["ubicacion"] == ubicacion_destino), None)
    stock_antes = int(stock_item["cantidad_actual"]) if stock_item else 0
        
    mov_data = {
        "tipo_item_id": str(tipo_item_toner.id),
        "tipo_movimiento": TipoMovimientoInvEnum.ENTRADA_COMPRA.value, 
        "cantidad": cantidad_entrada,
        "ubicacion_destino": ubicacion_destino,
        "costo_unitario": float(costo_entrada),
        "referencia_externa": f"Factura-ENT-OK-v3-{uuid4().hex[:6]}"
    }
    try:
        InventarioMovimientoCreate(**mov_data)
    except ValidationError as e:
        pytest.fail(f"Payload inválido (Entrada): {e}")

    response = await client.post(f"{settings.API_V1_STR}/inventario/movimientos/", headers=headers, json=mov_data)

    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error API (Entrada): {response.text}"
    created_mov = response.json()
    assert created_mov["tipo_movimiento"] == TipoMovimientoInvEnum.ENTRADA_COMPRA.value
    assert int(created_mov["cantidad"]) == cantidad_entrada

    stock_despues_resp = await client.get(f"{settings.API_V1_STR}/inventario/stock/", headers=headers, params={"tipo_item_id": mov_data["tipo_item_id"], "ubicacion": ubicacion_destino})
    assert stock_despues_resp.status_code == status.HTTP_200_OK
    stock_despues_data = stock_despues_resp.json()
    stock_item_despues = next((s for s in stock_despues_data if s["ubicacion"] == ubicacion_destino), None)
    assert stock_item_despues is not None
    stock_actual = int(stock_item_despues["cantidad_actual"])
    assert stock_actual == stock_antes + cantidad_entrada, "Stock no aumentó correctamente"

async def test_create_inventario_movimiento_stock_insuficiente(
    client: AsyncClient, auth_token_admin: str,
    stock_inicial_toner: InventarioStock, 
    tipo_item_toner: TipoItemInventario
):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    cantidad_salida = stock_inicial_toner.cantidad_actual + 1 
    ubicacion_stock = stock_inicial_toner.ubicacion

    mov_data = {
        "tipo_item_id": str(tipo_item_toner.id),
        "tipo_movimiento": TipoMovimientoInvEnum.SALIDA_USO.value, 
        "cantidad": cantidad_salida,
        "ubicacion_origen": ubicacion_stock,
    }
    try:
        InventarioMovimientoCreate(**mov_data)
    except ValidationError as e:
        pytest.fail(f"Payload inválido (Stock Insuf): {e}")

    response = await client.post(f"{settings.API_V1_STR}/inventario/movimientos/", headers=headers, json=mov_data)

    assert response.status_code == status.HTTP_409_CONFLICT, f"Detalle error API (Stock Insuf): {response.text}"
    assert "stock insuficiente" in response.json()["detail"].lower()

async def test_read_inventario_movimientos_success(
    client: AsyncClient, auth_token_usuario_regular: str,
    tipo_item_toner: TipoItemInventario, 
    auth_token_admin: str 
):
    headers_user = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    headers_admin = {"Authorization": f"Bearer {auth_token_admin}"}
    if not headers_admin["Authorization"]:
        pytest.skip("Se necesita token admin")

    ubicacion_ajuste = f"Almacén Listar Ajuste OK {uuid4().hex[:4]}"
    cantidad_ajuste = 1
    mov_data = {
        "tipo_item_id": str(tipo_item_toner.id), 
        "tipo_movimiento": TipoMovimientoInvEnum.AJUSTE_POSITIVO.value, 
        "cantidad": cantidad_ajuste,
        "ubicacion_destino": ubicacion_ajuste,
        "motivo_ajuste": "Ajuste OK v3 para Test Listar Movimientos"
    }
    try:
        InventarioMovimientoCreate(**mov_data)
    except ValidationError as e:
        pytest.fail(f"Payload inválido (Listar): {e}")

    create_resp = await client.post(f"{settings.API_V1_STR}/inventario/movimientos/", headers=headers_admin, json=mov_data)
    assert create_resp.status_code == status.HTTP_201_CREATED, f"Fallo al crear movimiento previo para listar: {create_resp.text}"
    created_mov_id = create_resp.json().get("id")

    response = await client.get(f"{settings.API_V1_STR}/inventario/movimientos/", headers=headers_user)
    assert response.status_code == status.HTTP_200_OK, f"Detalle error API (Listar): {response.text}"
    
    try:
        movimientos = response.json() 
    except Exception as e:
        pytest.fail(f"Error al decodificar JSON (Listar): {e} - Text: {response.text}")

    assert isinstance(movimientos, list)
    assert any(mov["id"] == created_mov_id for mov in movimientos), "Movimiento creado no encontrado"
    
    mov_encontrado = next((mov for mov in movimientos if mov["id"] == created_mov_id), None)
    assert mov_encontrado is not None
    assert mov_encontrado["tipo_movimiento"] == TipoMovimientoInvEnum.AJUSTE_POSITIVO.value
    assert "usuario_registrador" in mov_encontrado
    assert mov_encontrado["usuario_registrador"] is not None
    assert "id" in mov_encontrado["usuario_registrador"]
