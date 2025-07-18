import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.orm import Session
from uuid import uuid4

from app.core.config import settings
from app.models import Usuario, Rol

pytestmark = pytest.mark.asyncio

async def test_login_usuario_bloqueado_falla(
    client: AsyncClient, db: Session, test_usuario_regular_fixture: Usuario
):
    """Verifica que un usuario bloqueado no puede iniciar sesión."""
    test_usuario_regular_fixture.bloqueado = True
    db.add(test_usuario_regular_fixture)
    db.commit()

    login_data = {
        "username": test_usuario_regular_fixture.nombre_usuario,
        "password": "UsuarioPass123!"
    }
    response = await client.post(f"{settings.API_V1_STR}/auth/login/access-token", data=login_data)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "incorrectos, o usuario bloqueado" in response.json()["detail"]

async def test_admin_no_puede_cambiar_su_propio_rol(
    client: AsyncClient, auth_token_admin: str, test_admin_fixture: Usuario, test_rol_usuario_regular: Rol
):
    """Un admin no debería poder cambiar su propio rol a uno inferior."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    update_data = {"rol_id": str(test_rol_usuario_regular.id)}

    response = await client.put(
        f"{settings.API_V1_STR}/usuarios/{test_admin_fixture.id}",
        headers=headers,
        json=update_data
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "no puede cambiar su propio rol" in response.json()["detail"].lower()

async def test_admin_no_puede_eliminarse_a_si_mismo(client: AsyncClient, auth_token_admin: str, test_admin_fixture: Usuario):
    """Verifica que un admin no puede auto-eliminarse."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.delete(f"{settings.API_V1_STR}/usuarios/{test_admin_fixture.id}", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "no puedes eliminar tu propia cuenta" in response.json()["detail"].lower()

