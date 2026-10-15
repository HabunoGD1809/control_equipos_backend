"""Regression checks for complete assemblies and ledger-preserving batch correction."""
from uuid import uuid4
import pytest
from app.core.config import settings

pytestmark = pytest.mark.asyncio


async def test_assembly_transfer_and_cancellation(client, auth_token_admin, test_estado_disponible):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    base = settings.API_V1_STR

    async def request(method, path, data=None, expected=200):
        response = await client.request(method, base + path, headers=headers, json=data)
        assert response.status_code == expected, response.text
        return response.json() if response.content else None

    origin = await request("POST", "/ubicaciones/", {"nombre": "Origen " + uuid4().hex}, 201)
    destination = await request("POST", "/ubicaciones/", {"nombre": "Destino " + uuid4().hex}, 201)
    async def equipment():
        return await request("POST", "/equipos/", {"nombre": "Equipo de conjunto", "numero_serie": "GROUP-" + uuid4().hex, "estado_id": str(test_estado_disponible.id), "ubicacion_id": origin["id"]}, 201)
    parent, child, other_parent = await equipment(), await equipment(), await equipment()
    relation = {"equipo_componente_id": child["id"], "cantidad": 1, "tipo_relacion": "componente"}
    await request("POST", f'/equipos/{parent["id"]}/componentes', {**relation, "cantidad": 2}, 422)
    await request("POST", f'/equipos/{parent["id"]}/componentes', relation, 201)
    components = await request("GET", f'/equipos/{parent["id"]}/componentes')
    assert len(components) == 1 and components[0]['id']
    assert components[0]['componente']['id'] == child['id']
    parents = await request("GET", f'/equipos/{child["id"]}/parte_de')
    assert len(parents) == 1 and parents[0]['padre']['id'] == parent['id']
    assert parents[0]['id'] == components[0]['id'] and parents[0]['cantidad'] == 1
    await request("POST", f'/equipos/{other_parent["id"]}/componentes', relation, 409)
    await request("POST", f'/equipos/{child["id"]}/componentes', {**relation, "equipo_componente_id": parent["id"]}, 409)
    await request("POST", "/movimientos/", {"equipo_id": child["id"], "tipo_movimiento": "Transferencia Bodega", "ubicacion_destino_id": destination["id"]}, 409)
    movement = await request("POST", "/movimientos/", {"equipo_id": parent["id"], "tipo_movimiento": "Transferencia Bodega", "ubicacion_destino_id": destination["id"]}, 201)
    assert movement["equipos_incluidos"] == 2
    moved_child = await request("GET", f'/equipos/{child["id"]}')
    assert moved_child["ubicacion_id"] == destination["id"]
    await request("POST", f'/movimientos/{movement["id"]}/cancelar', {})
    restored = await request("GET", f'/equipos/{child["id"]}')
    assert restored["ubicacion_id"] == origin["id"]
    assert restored["estado_id"] == str(test_estado_disponible.id)
    history = await request("GET", f'/movimientos/?equipo_id={child["id"]}')
    assert any(entry["id"] == movement["id"] for entry in history)


async def test_batch_correction_preserves_stock_and_ledger(client, auth_token_admin):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    base = settings.API_V1_STR
    location = await client.post(base + "/ubicaciones/", headers=headers, json={"nombre": "Lotes " + uuid4().hex})
    assert location.status_code == 201
    item = await client.post(base + "/inventario/tipos/", headers=headers, json={"nombre": "Lotes " + uuid4().hex, "categoria": "Consumible", "unidad_medida": "Unidad"})
    assert item.status_code == 201
    key = {"tipo_item_id": item.json()["id"]}
    entry = await client.post(base + "/inventario/movimientos/", headers=headers, json={**key, "tipo_movimiento": "Entrada Compra", "cantidad": 10, "ubicacion_destino_id": location.json()["id"], "lote_destino": "INCORRECTO", "costo_unitario": "12.5000"})
    assert entry.status_code == 201, entry.text
    stocks = await client.get(base + "/inventario/stock/", headers=headers, params=key)
    old_stock = stocks.json()[0]
    rename = await client.put(base + f'/inventario/stock/{old_stock["id"]}/details', headers=headers, json={"lote": "CORRECTO"})
    assert rename.status_code == 409, rename.text
    transfer = await client.post(base + "/inventario/movimientos/", headers=headers, json={**key, "tipo_movimiento": "Transferencia Salida", "cantidad": 10, "ubicacion_origen_id": location.json()["id"], "ubicacion_destino_id": location.json()["id"], "lote_origen": "INCORRECTO", "lote_destino": "CORRECTO"})
    assert transfer.status_code == 201, transfer.text
    stocks = await client.get(base + "/inventario/stock/", headers=headers, params=key)
    balances = {row["lote"]: row["cantidad_actual"] for row in stocks.json()}
    assert balances == {"INCORRECTO": 0, "CORRECTO": 10}
    ledger = await client.get(base + "/inventario/movimientos/", headers=headers, params=key)
    assert sorted(row["tipo_movimiento"] for row in ledger.json()) == ["Entrada Compra", "Transferencia Entrada", "Transferencia Salida"]
