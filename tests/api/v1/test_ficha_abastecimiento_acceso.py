import pytest
from uuid import uuid4
from sqlalchemy import select
from app.models import InventarioStock
from app.services.reporte import reporte_service
from tests.helpers import location_id
from tests.helpers import employee_id

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("field,value", [
    ("bloqueado", True), ("rol_id", "same"), ("password", "OtherPassword123!"),
    ("requiere_cambio_contrasena", True), ("intentos_fallidos", 0), ("nombre_usuario", "renamed-self"),
    ("departamento_id", None), ("empleado_id", None),
])
async def test_admin_cannot_manage_own_access(client, auth_token_admin, test_admin_fixture, field, value):
    headers = {"Authorization": "Bearer " + auth_token_admin}
    if value == "same": value = str(test_admin_fixture.rol_id)
    response = await client.put(f"/api/v1/usuarios/{test_admin_fixture.id}", headers=headers, json={field: value})
    assert response.status_code == 403, response.text
    assert (await client.get("/api/v1/usuarios/me", headers=headers)).status_code == 200


@pytest.mark.parametrize("field,value", [("password", "OtherPassword123!"), ("requiere_cambio_contrasena", False), ("intentos_fallidos", 0), ("avatar_url", "https://external.example/image.jpg")])
async def test_profile_cannot_bypass_access_or_avatar_endpoints(client, auth_token_admin, field, value):
    response = await client.put("/api/v1/usuarios/me", headers={"Authorization": "Bearer " + auth_token_admin}, json={field: value})
    assert response.status_code == 400, response.text


async def test_own_reset_and_role_permission_changes_are_denied(client, auth_token_admin, test_admin_fixture):
    headers = {"Authorization": "Bearer " + auth_token_admin}
    response = await client.post("/api/v1/auth/password-recovery/request-reset", headers=headers, json={"username_or_email": test_admin_fixture.nombre_usuario})
    assert response.status_code == 403, response.text
    response = await client.put(f"/api/v1/gestion/roles/{test_admin_fixture.rol_id}", headers=headers, json={"permiso_ids": []})
    assert response.status_code == 403, response.text
    response = await client.put(f"/api/v1/gestion/roles/{test_admin_fixture.rol_id}", headers=headers, json={"descripcion": "Descripción administrativa"})
    assert response.status_code == 200, response.text


async def test_technical_sheet_roundtrip_and_partial_update(client, auth_token_admin, test_estado_disponible, db):
    headers = {"Authorization": "Bearer " + auth_token_admin}
    payload = {"nombre": "Servidor institucional", "numero_serie": "SRV/" + uuid4().hex[:12], "estado_id": str(test_estado_disponible.id), "tipo_activo": "Servidor", "especificaciones_tecnicas": {"direccion_ip": "2001:db8::1", "direccion_mac": "AA:BB:CC:DD:EE:01", "ram": "64 GB", "rack": "R1", "posicion_rack": "U12-U14", "Circuito eléctrico": "UPS-A", "cpu": "  Xeon  "}}
    response = await client.post("/api/v1/equipos/", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    equipment = response.json()
    assert equipment["tipo_activo"] == "Servidor"
    assert equipment["especificaciones_tecnicas"]["cpu"] == "Xeon"
    response = await client.put(f"/api/v1/equipos/{equipment['id']}", headers=headers, json={"nombre": "Servidor actualizado"})
    assert response.status_code == 200, response.text
    assert response.json()["especificaciones_tecnicas"] == equipment["especificaciones_tecnicas"]
    rows = reporte_service.obtener_datos(db, "equipos", None, None)
    row = next(row for row in rows if row["Serie"] == payload["numero_serie"])
    assert row["Tipo"] == "Servidor" and "64 GB" in row["Ficha técnica"] and "UPS-A" in row["Ficha técnica"]
    response = await client.get("/api/v1/equipos/", headers=headers, params={"q": "2001:db8::1"})
    assert response.status_code == 200 and any(row["id"] == equipment["id"] for row in response.json())


async def test_custody_requires_delivery_and_preserves_real_responsible(client, auth_token_admin, test_admin_fixture, auth_token_supervisor, test_supervisor_fixture, test_estado_disponible, db):
    headers = {"Authorization": "Bearer " + auth_token_admin}
    employee = str(employee_id(db))
    destination = str(location_id(db, "Departamento receptor"))
    payload = {"nombre": "Equipo para entrega", "numero_serie": "ASIG-" + uuid4().hex[:12], "estado_id": str(test_estado_disponible.id), "ubicacion_id": destination}
    invalid = await client.post("/api/v1/equipos/", headers=headers, json={**payload, "empleado_asignado_id": employee})
    assert invalid.status_code == 422
    response = await client.post("/api/v1/equipos/", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    equipment = response.json()
    invalid = await client.put(f"/api/v1/equipos/{equipment['id']}", headers=headers, json={"empleado_asignado_id": employee})
    assert invalid.status_code == 409
    supervisor = {"Authorization": "Bearer " + auth_token_supervisor}
    response = await client.post("/api/v1/movimientos/", headers=supervisor, json={"equipo_id": equipment["id"], "tipo_movimiento": "Asignacion Interna", "ubicacion_destino_id": destination, "empleado_destino_id": employee})
    assert response.status_code == 201, response.text
    movement = response.json()
    if movement["estado"] == "Pendiente":
        response = await client.patch(f"/api/v1/movimientos/{movement['id']}/estado", headers=headers, json={"estado": "Autorizado"})
        assert response.status_code == 200, response.text
    response = await client.patch(f"/api/v1/movimientos/{movement['id']}/estado", headers=headers, json={"estado": "Completado"})
    assert response.status_code == 200, response.text
    assert response.json()["empleado_destino_id"] == employee
    assert response.json()["usuario_registrador"]["id"] == str(test_supervisor_fixture.id)
    response = await client.get(f"/api/v1/equipos/{equipment['id']}", headers=headers)
    assert response.json()["empleado_asignado_id"] == employee
    from app.services.timeline import timeline_service
    from uuid import UUID
    events = timeline_service.get_equipo_timeline(db, UUID(equipment["id"]))
    assert any(event["usuario"] == test_supervisor_fixture.nombre_usuario for event in events)
    exported = next(row for row in reporte_service.obtener_datos(db, "movimientos", None, None) if row["Serie"] == payload["numero_serie"])
    assert exported["Registrado por"] == test_supervisor_fixture.nombre_usuario
    assert exported["Autorizado por"] and exported["Custodio"]
    response = await client.delete(f"/api/v1/usuarios/{test_supervisor_fixture.id}", headers=headers)
    assert response.status_code == 409, response.text


@pytest.mark.parametrize("specs", [{"direccion_ip": "999.2.3.4"}, {"direccion_mac": "xyz"}, {"contraseña": "hidden"}, {"key": {"nested": "invalid"}}, {str(i): "x" for i in range(21)}])
async def test_invalid_technical_sheet_is_rejected(client, auth_token_admin, test_estado_disponible, specs):
    payload = {"nombre": "Servidor", "numero_serie": uuid4().hex, "estado_id": str(test_estado_disponible.id), "especificaciones_tecnicas": specs}
    response = await client.post("/api/v1/equipos/", headers={"Authorization": "Bearer " + auth_token_admin}, json=payload)
    assert response.status_code == 422, response.text


async def test_supply_receipt_conserves_stock_actor_cost_and_report(client, auth_token_admin, test_admin_fixture, tipo_item_toner, db):
    headers = {"Authorization": "Bearer " + auth_token_admin}
    destination = location_id(db, "Almacén de tecnología")
    payload = {"tipo_item_id": str(tipo_item_toner.id), "tipo_movimiento": "Entrada Abastecimiento", "cantidad": 10, "ubicacion_destino_id": str(destination), "lote_destino": "SUM-01", "costo_unitario": "2.0000", "procedencia": "Departamento de Suministro", "entregado_por": "Responsable de Suministro", "referencia_externa": "ACTA-2026-001"}
    response = await client.post("/api/v1/inventario/movimientos/", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert receipt["usuario_id"] == str(test_admin_fixture.id)
    assert receipt["usuario_registrador"]["nombre_usuario"] == test_admin_fixture.nombre_usuario
    assert receipt["procedencia"] == payload["procedencia"] and receipt["entregado_por"] == payload["entregado_por"]
    response = await client.post("/api/v1/inventario/movimientos/", headers=headers, json={"tipo_item_id": str(tipo_item_toner.id), "tipo_movimiento": "Salida Uso", "cantidad": 3, "ubicacion_origen_id": str(destination), "lote_origen": "SUM-01", "referencia_externa": "USO-001"})
    assert response.status_code == 201, response.text
    stock = db.scalar(select(InventarioStock).where(InventarioStock.tipo_item_id == tipo_item_toner.id, InventarioStock.ubicacion_id == destination))
    assert stock.cantidad_actual == 7 and float(stock.costo_promedio_ponderado) == 2
    kardex = reporte_service.obtener_datos(db, "kardex", None, None)
    row = next(row for row in kardex if row["Referencia"] == "ACTA-2026-001")
    assert row["Entrada"] == 10 and row["Salida"] == 0 and row["Saldo"] == 10
    assert row["Procedencia"] == payload["procedencia"] and row["Entregado por"] == payload["entregado_por"]
    balance = next(row for row in reporte_service.obtener_datos(db, "inventario", None, None) if row["Lote"] == "SUM-01")
    assert balance["Existencias"] == 7
    too_many = await client.post("/api/v1/inventario/movimientos/", headers=headers, json={"tipo_item_id": str(tipo_item_toner.id), "tipo_movimiento": "Salida Uso", "cantidad": 8, "ubicacion_origen_id": str(destination), "lote_origen": "SUM-01"})
    assert too_many.status_code == 409


@pytest.mark.parametrize("missing", ["procedencia", "referencia_externa", "ubicacion_destino_id"])
async def test_supply_requires_source_document_and_destination(client, auth_token_admin, tipo_item_toner, db, missing):
    payload = {"tipo_item_id": str(tipo_item_toner.id), "tipo_movimiento": "Entrada Abastecimiento", "cantidad": 2, "ubicacion_destino_id": str(location_id(db, "Destino suministro")), "procedencia": "Suministro", "referencia_externa": "ACTA-001"}
    payload.pop(missing)
    response = await client.post("/api/v1/inventario/movimientos/", headers={"Authorization": "Bearer " + auth_token_admin}, json=payload)
    assert response.status_code == 422, response.text
