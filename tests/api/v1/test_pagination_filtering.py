# C:\Users\fjvaldez\Desktop\control_equipos_backend\tests\api\v1\test_pagination_filtering.py

import pytest
from httpx import AsyncClient
from app.models import (
    Usuario,
    TipoItemInventario,
    InventarioStock,
    EstadoEquipo,
    Equipo,
    TipoMantenimiento,
)

pytestmark = pytest.mark.asyncio


async def test_pagination_on_equipos(
    client: AsyncClient, auth_token_admin: str, test_estado_disponible: EstadoEquipo
):
    """
    Verifica que la paginación básica (skip/limit) funciona en el endpoint de equipos.
    Este test ahora crea sus propios equipos para ser independiente.
    """
    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}

    for i in range(4):
        response_create = await client.post(
            "/api/v1/equipos/",
            headers=admin_headers,
            json={
                "nombre": f"Equipo de Paginación {i+1}",
                "numero_serie": f"PAG-TST-{i+1:03d}",
                "estado_id": str(test_estado_disponible.id),
            },
        )
        assert response_create.status_code == 201, f"Falló la creación del equipo de paginación {i+1}"

    response_p1 = await client.get("/api/v1/equipos/?skip=0&limit=2", headers=admin_headers)
    assert response_p1.status_code == 200
    page1_items = response_p1.json()
    assert len(page1_items) == 2, "La página 1 debe contener exactamente 2 items."

    response_p2 = await client.get("/api/v1/equipos/?skip=2&limit=2", headers=admin_headers)
    assert response_p2.status_code == 200
    page2_items = response_p2.json()
    assert len(page2_items) >= 1, "La página 2 debe contener al menos 1 item."

    page1_ids = {item["id"] for item in page1_items}
    page2_ids = {item["id"] for item in page2_items}
    assert not page1_ids.intersection(page2_ids), "Los items de la página 1 y 2 no deben ser los mismos."


async def test_filter_mantenimientos_by_date_range_and_status(
    client: AsyncClient,
    auth_token_admin: str,
    test_equipo_reservable: Equipo,
    # === CORRECCIÓN: Usar un nombre de fixture que sí existe. ===
    tipo_mantenimiento_correctivo: TipoMantenimiento,
):
    """
    Verifica el filtrado de mantenimientos por fecha y estado.
    Este test ahora crea su propio registro de mantenimiento.
    """
    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}

    fecha_programada_iso = "2025-04-01T10:00:00"
    estado_buscado = "Completado"
    mantenimiento_data = {
        "equipo_id": str(test_equipo_reservable.id),
        "tipo_mantenimiento_id": str(tipo_mantenimiento_correctivo.id),
        "fecha_programada": fecha_programada_iso,
        "estado": estado_buscado,
        "tecnico_responsable": "Técnico de Prueba de Filtro",
    }
    response_create = await client.post(
        "/api/v1/mantenimientos/", headers=admin_headers, json=mantenimiento_data
    )
    assert response_create.status_code == 201, "Falló la creación del mantenimiento para el test."

    start_date = "2025-04-01"
    end_date = "2025-04-01"

    url = f"/api/v1/mantenimientos/?start_date={start_date}&end_date={end_date}&estado={estado_buscado}"
    response = await client.get(url, headers=admin_headers)

    assert response.status_code == 200
    mantenimientos = response.json()
    assert (
        len(mantenimientos) > 0
    ), "Debería encontrarse al menos un mantenimiento completado en esa fecha."

    for mant in mantenimientos:
        assert mant["fecha_programada"].split("T")[0] == start_date
        assert mant["estado"] == estado_buscado


async def test_filter_inventario_by_location_and_type(
    client: AsyncClient,
    auth_token_admin: str,
    tipo_item_toner: TipoItemInventario,
    stock_inicial_toner: InventarioStock,
):
    """Verifica el filtrado en inventario."""
    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}
    tipo_item_id = str(tipo_item_toner.id)
    ubicacion = stock_inicial_toner.ubicacion
    url = f"/api/v1/inventario/stock/?tipo_item_id={tipo_item_id}&ubicacion={ubicacion}"
    response = await client.get(url, headers=admin_headers)
    assert response.status_code == 200
    stock_items = response.json()
    assert len(stock_items) == 1, "Debe haber exactamente un registro de stock para ese item en esa ubicación."
    assert stock_items[0]["tipo_item"]["id"] == tipo_item_id
    assert stock_items[0]["ubicacion"] == ubicacion
