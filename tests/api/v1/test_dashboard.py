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


# ===== INICIO DE LA CORRECCIÓN =====
async def test_read_dashboard_summary_no_permission(client: AsyncClient, auth_token_tecnico: str):
    """
    Prueba obtener dashboard con un usuario que NO tiene el permiso 'ver_dashboard'.
    El rol 'tecnico' no tiene este permiso según datosControlEquipos.sql.
    """
    headers = {"Authorization": f"Bearer {auth_token_tecnico}"}
    response = await client.get(f"{settings.API_V1_STR}/dashboard/", headers=headers)
    
    # Ahora la prueba es correcta: el técnico no debe tener acceso.
    assert response.status_code == status.HTTP_403_FORBIDDEN
# ===== FIN DE LA CORRECCIÓN =====


async def test_read_dashboard_summary_unauthenticated(client: AsyncClient):
    """Prueba obtener dashboard sin autenticación."""
    response = await client.get(f"{settings.API_V1_STR}/dashboard/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
