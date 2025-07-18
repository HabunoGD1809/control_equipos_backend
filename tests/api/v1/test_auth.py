import pytest
import asyncio
from httpx import AsyncClient
from unittest import mock
from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.usuario import Usuario

pytestmark = pytest.mark.asyncio


@mock.patch("app.api.routes.auth.log_login_attempt_task")
async def test_login_success(mock_log_attempt, client: AsyncClient, test_usuario_regular_fixture: Usuario):
    """
    Verifica la presencia de token y refresh_token.
    """
    login_data = {"username": test_usuario_regular_fixture.nombre_usuario, "password": "UsuarioPass123!"}
    response = await client.post(f"{settings.API_V1_STR}/auth/login/access-token", data=login_data)
    
    assert response.status_code == status.HTTP_200_OK
    token = response.json()
    assert "access_token" in token
    assert "refresh_token" in token
    assert token["token_type"] == "bearer"

@mock.patch("app.api.routes.auth.log_login_attempt_task")
async def test_login_wrong_password(mock_log_attempt, client: AsyncClient, test_usuario_regular_fixture: Usuario):
    login_data = {"username": test_usuario_regular_fixture.nombre_usuario, "password": "wrongpassword"}
    response = await client.post(f"{settings.API_V1_STR}/auth/login/access-token", data=login_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "detail" in response.json()
    assert response.json()["detail"] == "Nombre de usuario o contraseña incorrectos, o usuario bloqueado."

@mock.patch("app.api.routes.auth.log_login_attempt_task")
async def test_login_user_not_found(mock_log_attempt, client: AsyncClient):
    login_data = {"username": "nonexistentuser", "password": "somepassword"}
    response = await client.post(f"{settings.API_V1_STR}/auth/login/access-token", data=login_data)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "detail" in response.json()
    assert response.json()["detail"] == "Nombre de usuario o contraseña incorrectos, o usuario bloqueado."

class TestRefreshTokenFlow:
    """
    Grupo de tests para la nueva funcionalidad de refresh token.
    """
    @mock.patch("app.api.routes.auth.log_login_attempt_task")
    async def test_refresh_token_success_flow(
        self, mock_log_attempt, client: AsyncClient, test_usuario_regular_fixture: Usuario, db: Session
    ):
        """
        Test del flujo completo: login, refresh y uso del nuevo access token.
        """
        # 1. Login para obtener tokens iniciales
        login_data = {"username": test_usuario_regular_fixture.nombre_usuario, "password": "UsuarioPass123!"}
        login_response = await client.post(f"{settings.API_V1_STR}/auth/login/access-token", data=login_data)
        assert login_response.status_code == status.HTTP_200_OK
        initial_tokens = login_response.json()
        initial_access_token = initial_tokens["access_token"]
        initial_refresh_token = initial_tokens["refresh_token"]

        await asyncio.sleep(1)

        # 2. Usar el refresh token para obtener un nuevo par de tokens
        refresh_data = {"refresh_token": initial_refresh_token}
        refresh_response = await client.post(f"{settings.API_V1_STR}/auth/refresh-token", json=refresh_data)
        
        assert refresh_response.status_code == status.HTTP_200_OK
        new_tokens = refresh_response.json()
        new_access_token = new_tokens["access_token"]
        new_refresh_token = new_tokens["refresh_token"]

        # 3. Verificar que los nuevos tokens son diferentes a los antiguos
        assert new_access_token != initial_access_token
        assert new_refresh_token != initial_refresh_token
        assert new_tokens["token_type"] == "bearer"

        # 4. Verificar que el nuevo access token funciona
        headers = {"Authorization": f"Bearer {new_access_token}"}
        test_response = await client.post(f"{settings.API_V1_STR}/auth/login/test-token", headers=headers)
        assert test_response.status_code == status.HTTP_200_OK
        assert test_response.json()["nombre_usuario"] == test_usuario_regular_fixture.nombre_usuario

        # 5. (Importante) Verificar que el refresh token antiguo ya no es válido (rotación)
        old_refresh_data = {"refresh_token": initial_refresh_token}
        old_refresh_response = await client.post(f"{settings.API_V1_STR}/auth/refresh-token", json=old_refresh_data)
        assert old_refresh_response.status_code == status.HTTP_403_FORBIDDEN
        assert "no es válido o ha sido revocado" in old_refresh_response.json()["detail"]

    async def test_refresh_token_failure_invalid_token(self, client: AsyncClient) -> None:
        """
        Test de fallo al usar un refresh token malformado o inválido.
        """
        refresh_data = {"refresh_token": "this.is.an.invalid.token"}
        response = await client.post(f"{settings.API_V1_STR}/auth/refresh-token", json=refresh_data)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "inválido o expirado" in response.json()["detail"]
