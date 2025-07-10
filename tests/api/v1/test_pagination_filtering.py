# tests/test_pagination_filtering.py
import pytest
from httpx import AsyncClient
from app.models import Usuario, TipoItemInventario, InventarioStock

pytestmark = pytest.mark.asyncio

async def test_pagination_on_equipos(client: AsyncClient, auth_token_admin: str):
    """Verifica que la paginación básica (skip/limit) funciona en el endpoint de equipos."""
    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}

    # Se asume que hay al menos 4 equipos creados por las fixtures a lo largo de las pruebas.
    # Pedimos la primera página con 2 items.
    response_p1 = await client.get("/api/v1/equipos/?skip=0&limit=2", headers=admin_headers)
    assert response_p1.status_code == 200
    page1_items = response_p1.json()
    assert len(page1_items) == 2, "La página 1 debe contener exactamente 2 items."

    # Pedimos la segunda página con 2 items.
    response_p2 = await client.get("/api/v1/equipos/?skip=2&limit=2", headers=admin_headers)
    assert response_p2.status_code == 200
    page2_items = response_p2.json()
    assert len(page2_items) > 0, "La página 2 debe contener al menos 1 item."

    # Verificación clave: los IDs de ambas páginas no deben solaparse.
    page1_ids = {item['id'] for item in page1_items}
    page2_ids = {item['id'] for item in page2_items}
    assert not page1_ids.intersection(page2_ids), "Los items de la página 1 y 2 no deben ser los mismos."

async def test_filter_mantenimientos_by_date_range_and_status(client: AsyncClient, auth_token_admin: str):
    """Verifica el filtrado combinado de mantenimientos por rango de fechas y estado."""
    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}

    # Buscamos mantenimientos 'Completado' en una fecha específica de los datos de prueba.
    start_date = "2025-04-01"
    end_date = "2025-04-01"
    estado = "Completado"
    
    url = f"/api/v1/mantenimientos/?start_date={start_date}&end_date={end_date}&estado={estado}"
    response = await client.get(url, headers=admin_headers)
    
    assert response.status_code == 200
    mantenimientos = response.json()
    assert len(mantenimientos) > 0, "Debería encontrarse al menos un mantenimiento completado en esa fecha."
    
    for mant in mantenimientos:
        assert mant['fecha_programada'].split('T')[0] == start_date
        assert mant['estado'] == estado

async def test_filter_inventario_by_location_and_type(
    client: AsyncClient,
    auth_token_admin: str,
    tipo_item_toner: TipoItemInventario,
    stock_inicial_toner: InventarioStock
):
    """Verifica el filtrado combinado en el inventario por ID de tipo de item y ubicación."""
    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}

    tipo_item_id = str(tipo_item_toner.id)
    ubicacion = stock_inicial_toner.ubicacion

    url = f"/api/v1/inventario/stock/?tipo_item_id={tipo_item_id}&ubicacion={ubicacion}"
    response = await client.get(url, headers=admin_headers)

    assert response.status_code == 200
    stock_items = response.json()
    assert len(stock_items) == 1, "Debe haber exactamente un registro de stock para ese item en esa ubicación."
    assert stock_items[0]['tipo_item']['id'] == tipo_item_id
    assert stock_items[0]['ubicacion'] == ubicacion
