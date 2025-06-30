import pytest
from httpx import AsyncClient
from fastapi import status

from app.core.config import settings

# Marca todas las pruebas en este módulo para que se ejecuten con anyio
pytestmark = pytest.mark.anyio


async def test_read_dashboard_summary_success(client: AsyncClient, auth_token_admin: str):
    """
    Prueba el acceso exitoso al dashboard con un usuario que tiene permisos (admin).
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/dashboard/", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total_equipos" in data
    assert "equipos_por_estado" in data


async def test_read_dashboard_summary_tecnico_access(client: AsyncClient, auth_token_tecnico: str):
    """
    Prueba que un usuario con el rol 'tecnico' con permiso para ver el dashboard.
    """
    headers = {"Authorization": f"Bearer {auth_token_tecnico}"}
    response = await client.get(f"{settings.API_V1_STR}/dashboard/", headers=headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total_equipos" in data
    assert "equipos_por_estado" in data


async def test_read_dashboard_summary_unauthenticated(client: AsyncClient):
    """Prueba obtener dashboard sin autenticación."""
    response = await client.get(f"{settings.API_V1_STR}/dashboard/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
