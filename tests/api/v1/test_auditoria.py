import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from datetime import datetime, timedelta, timezone
from fastapi import status
from fastapi.encoders import jsonable_encoder

from app.core.config import settings

pytestmark = pytest.mark.asyncio

async def test_read_audit_logs_success(client: AsyncClient, auth_token_admin: str):
    """Prueba listar logs de auditoría (Admin tiene 'ver_auditoria')."""
    if not auth_token_admin:
        pytest.fail("No se pudo obtener el token de admin en la fixture 'client'. Verifica el login.")

    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/auditoria/", headers=headers)

    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"
    logs = response.json()
    assert isinstance(logs, list)
    if logs:
        log_sample = logs[0]
        assert "id" in log_sample
        assert "audit_timestamp" in log_sample
        assert "table_name" in log_sample
        assert "operation" in log_sample
        assert log_sample.get("old_data") is None or isinstance(log_sample.get("old_data"), dict)
        assert log_sample.get("new_data") is None or isinstance(log_sample.get("new_data"), dict)

async def test_read_audit_logs_no_permission(client: AsyncClient, auth_token_usuario_regular: str):
    """Prueba listar logs de auditoría sin permiso."""
    if not auth_token_usuario_regular:
        pytest.fail("No se pudo obtener el token de usuario normal.")

    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    response = await client.get(f"{settings.API_V1_STR}/auditoria/", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_read_audit_logs_unauthenticated(client: AsyncClient):
    """Prueba listar logs de auditoría sin autenticación."""
    response = await client.get(f"{settings.API_V1_STR}/auditoria/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

async def test_read_audit_logs_with_filters(client: AsyncClient, auth_token_admin: str):
    """Prueba listar logs de auditoría con filtros (ej: tabla 'usuarios')."""
    if not auth_token_admin:
        pytest.fail("No se pudo obtener el token de admin.")
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    params = {
        "table_name": "usuarios",
        "limit": 10
    }
    response = await client.get(f"{settings.API_V1_STR}/auditoria/", headers=headers, params=params)

    assert response.status_code == status.HTTP_200_OK
    logs = response.json()
    assert isinstance(logs, list)
    assert all(log.get("table_name") == "usuarios" for log in logs)

    params_insert = {"operation": "INSERT", "limit": 5}
    response_insert = await client.get(f"{settings.API_V1_STR}/auditoria/", headers=headers, params=params_insert)
    assert response_insert.status_code == status.HTTP_200_OK
    logs_insert = response_insert.json()
    assert all(log.get("operation") == "INSERT" for log in logs_insert)
