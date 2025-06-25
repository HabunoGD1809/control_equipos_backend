import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from datetime import datetime, timedelta, timezone
from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session


from app.core.config import settings
# Importar modelos/schemas si se necesita crear datos para filtrar
from app.models.backup_log import BackupLog as BackupLogModel # Renombrar para evitar conflicto

# Marcar todos los tests en este módulo para usar asyncio
pytestmark = pytest.mark.asyncio

# Asumimos fixtures: auth_token_admin (tiene 'administrar_sistema'), auth_token_user (no tiene)

# --- Fixture para crear logs de backup de prueba ---
@pytest.fixture(scope="function")
def create_backup_logs(db: Session):
    """Crea algunos logs de backup para probar la lectura y filtros."""
    log1 = BackupLogModel(
        backup_status="completado", backup_type="full",
        duration=timedelta(minutes=15, seconds=30),
        file_path="/backups/full_20250430.bak",
        backup_timestamp=datetime.now(timezone.utc) - timedelta(days=1)
    )
    log2 = BackupLogModel(
        backup_status="fallido", backup_type="incremental",
        error_message="Conexión perdida",
        backup_timestamp=datetime.now(timezone.utc) - timedelta(hours=12)
    )
    log3 = BackupLogModel(
        backup_status="completado", backup_type="incremental",
        duration=timedelta(minutes=2, seconds=10),
        file_path="/backups/inc_20250430_1200.bak",
        backup_timestamp=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    db.add_all([log1, log2, log3])
    db.flush()
    return [log1, log2, log3]


async def test_read_backup_logs_success(
    client: AsyncClient, auth_token_admin: str, create_backup_logs: list
):
    """Prueba listar logs de backup (Admin tiene 'administrar_sistema')."""
    if not auth_token_admin: pytest.fail("No se pudo obtener token admin.")
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/backups/logs/", headers=headers)

    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"
    logs = response.json()
    assert isinstance(logs, list)
    assert len(logs) >= 3 # Deben existir al menos los creados por la fixture
    log_ids_fixture = {str(log.id) for log in create_backup_logs}
    log_ids_response = {log["id"] for log in logs}
    assert log_ids_fixture.issubset(log_ids_response) # Verificar que los creados están en la respuesta

async def test_read_backup_logs_no_permission(client: AsyncClient, auth_token_user: str):
    """Prueba listar logs de backup sin permiso."""
    if not auth_token_user: pytest.fail("No se pudo obtener token usuario.")
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    response = await client.get(f"{settings.API_V1_STR}/backups/logs/", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_read_backup_logs_unauthenticated(client: AsyncClient):
    """Prueba listar logs de backup sin autenticación."""
    response = await client.get(f"{settings.API_V1_STR}/backups/logs/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

async def test_read_backup_logs_with_filters(
    client: AsyncClient, auth_token_admin: str, create_backup_logs: list
):
    """Prueba listar logs de backup con filtros (status 'completado')."""
    if not auth_token_admin: pytest.fail("No se pudo obtener token admin.")
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    params = {
        "backup_status": "completado",
        "limit": 5
    }
    response = await client.get(f"{settings.API_V1_STR}/backups/logs/", headers=headers, params=params)

    assert response.status_code == status.HTTP_200_OK
    logs = response.json()
    assert isinstance(logs, list)
    # Verificar que todos los logs listados tienen el estado correcto
    assert all(log.get("backup_status") == "completado" for log in logs)
    # Verificar que el log fallido NO está en la lista
    failed_log_id = str(create_backup_logs[1].id) # El segundo log en la fixture era fallido
    assert not any(log["id"] == failed_log_id for log in logs)
    # Verificar que al menos uno de los completados está
    completed_log_id = str(create_backup_logs[0].id)
    assert any(log["id"] == completed_log_id for log in logs)


async def test_read_backup_log_by_id_success(
    client: AsyncClient, auth_token_admin: str, create_backup_logs: list
):
    """Prueba obtener un log de backup por ID."""
    if not auth_token_admin: pytest.fail("No se pudo obtener token admin.")
    target_log = create_backup_logs[0] # Tomar el primer log creado
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/backups/logs/{target_log.id}", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    log_data = response.json()
    assert log_data["id"] == str(target_log.id)
    assert log_data["backup_status"] == target_log.backup_status
    assert log_data["file_path"] == target_log.file_path

async def test_read_backup_log_by_id_not_found(
    client: AsyncClient, auth_token_admin: str
):
    """Prueba obtener un log de backup con ID inexistente."""
    if not auth_token_admin: pytest.fail("No se pudo obtener token admin.")
    non_existent_id = uuid4()
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/backups/logs/{non_existent_id}", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
