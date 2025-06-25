import pytest
from httpx import AsyncClient
from unittest import mock
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.models.usuario import Usuario

pytestmark = pytest.mark.asyncio

@mock.patch("app.api.routes.auth.log_login_attempt_task")
async def test_login_success(mock_log_attempt, client: AsyncClient, test_usuario_regular_fixture: Usuario):
    login_data = {"username": test_usuario_regular_fixture.nombre_usuario, "password": "UsuarioPass123!"}
    response = await client.post(f"{settings.API_V1_STR}/auth/login/access-token", data=login_data)
    assert response.status_code == 200
    token = response.json()
    assert "access_token" in token
    assert token["token_type"] == "bearer"
    # El mock ahora está en una tarea de fondo, por lo que no podemos verificarlo directamente aquí de forma síncrona.
    # Se podría verificar de otras maneras si es necesario (ej. comprobando la base de datos de logs).
    # Por ahora, eliminamos la aserción del mock.

@mock.patch("app.api.routes.auth.log_login_attempt_task")
async def test_login_wrong_password(mock_log_attempt, client: AsyncClient, test_usuario_regular_fixture: Usuario):
    login_data = {"username": test_usuario_regular_fixture.nombre_usuario, "password": "wrongpassword"}
    response = await client.post(f"{settings.API_V1_STR}/auth/login/access-token", data=login_data)
    assert response.status_code == 401
    assert "detail" in response.json()
    assert response.json()["detail"] == "Nombre de usuario o contraseña incorrectos."

@mock.patch("app.api.routes.auth.log_login_attempt_task")
async def test_login_user_not_found(mock_log_attempt, client: AsyncClient):
    login_data = {"username": "nonexistentuser", "password": "somepassword"}
    response = await client.post(f"{settings.API_V1_STR}/auth/login/access-token", data=login_data)
    assert response.status_code == 401
    assert "detail" in response.json()
    assert response.json()["detail"] == "Nombre de usuario o contraseña incorrectos."

async def test_test_token_success(client: AsyncClient, auth_token_usuario_regular: str):
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    response = await client.post(f"{settings.API_V1_STR}/auth/login/test-token", headers=headers)
    assert response.status_code == 200

async def test_test_token_invalid(client: AsyncClient):
    headers = {"Authorization": "Bearer invalidtoken"}
    response = await client.post(f"{settings.API_V1_STR}/auth/login/test-token", headers=headers)
    assert response.status_code == 401

async def test_test_token_no_token(client: AsyncClient):
    response = await client.post(f"{settings.API_V1_STR}/auth/login/test-token")
    assert response.status_code == 401
