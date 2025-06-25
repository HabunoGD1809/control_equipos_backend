import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from fastapi import status

from app.core.config import settings
from app.schemas.dashboard import DashboardData, EquipoPorEstado
from app.models.equipo import Equipo
from app.models.estado_equipo import EstadoEquipo

pytestmark = pytest.mark.asyncio

async def test_read_dashboard_summary_success(
    client: AsyncClient, auth_token_admin: str,
    test_equipo_reservable: Equipo
):
    """Prueba obtener los datos resumen del dashboard."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/dashboard/", headers=headers)

    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"
    dashboard_data = response.json()

    try:
        DashboardData.model_validate(dashboard_data)
    except Exception as e:
        pytest.fail(f"Respuesta del dashboard no cumple el schema: {e}\nRespuesta: {dashboard_data}")

    assert dashboard_data["total_equipos"] >= 1
    assert isinstance(dashboard_data["equipos_por_estado"], list)
    if dashboard_data["equipos_por_estado"]:
        first_estado = dashboard_data["equipos_por_estado"][0]
        EquipoPorEstado.model_validate(first_estado)

    assert dashboard_data["mantenimientos_proximos_count"] >= 0
    assert dashboard_data["licencias_por_expirar_count"] >= 0
    assert dashboard_data["items_bajo_stock_count"] >= 0

async def test_read_dashboard_summary_no_permission(client: AsyncClient, auth_token_usuario_regular: str):
    """Prueba obtener dashboard sin el permiso 'ver_dashboard'."""
    if not auth_token_usuario_regular:
         pytest.skip("Se necesita token de usuario normal (sin ver_dashboard) para este test.")

    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    response = await client.get(f"{settings.API_V1_STR}/dashboard/", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_read_dashboard_summary_unauthenticated(client: AsyncClient):
    """Prueba obtener dashboard sin autenticación."""
    response = await client.get(f"{settings.API_V1_STR}/dashboard/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
