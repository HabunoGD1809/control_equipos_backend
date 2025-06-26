import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
import io
from fastapi import status
from fastapi.encoders import jsonable_encoder
from unittest import mock

from app.core.config import settings
from app.models.documentacion import Documentacion
from app.models.equipo import Equipo
from app.models.tipo_documento import TipoDocumento
from app.models.usuario import Usuario
# Importar sólo los schemas necesarios
from app.schemas.documentacion import DocumentacionUpdate, DocumentacionVerify

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_save_file():
    file_info = {
        "file_path": f"test_uploads/{uuid4()}.pdf",
        "filename": "simulated_upload.pdf",
        "mime_type": "application/pdf",
        "size": 12345,
    }
    # Apuntamos el mock a la función correcta en el módulo donde se usa (routes)
    with mock.patch("app.api.routes.documentacion.save_upload_file", new_callable=mock.AsyncMock, return_value=file_info) as _mock:
        yield _mock

# --- Tests para Documentación ---

async def test_create_documentacion_success(
    client: AsyncClient, auth_token_supervisor: str,
    test_equipo_reservable: Equipo,
    test_tipo_doc_manual: TipoDocumento,
    mock_save_file: mock.AsyncMock
):
    """Prueba subir un documento y crear el registro."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}

    metadata_dict = {
        "titulo": "Manual de Usuario Test",
        "descripcion": "Manual subido desde test",
        "tipo_documento_id": str(test_tipo_doc_manual.id),
        "equipo_id": str(test_equipo_reservable.id)
    }

    file_content = b"dummy pdf content"
    files = {'file': ('test_manual.pdf', io.BytesIO(file_content), 'application/pdf')}

    response = await client.post(
        f"{settings.API_V1_STR}/documentacion/",
        headers=headers,
        data=metadata_dict,
        files=files
    )

    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_doc = response.json()
    assert created_doc["titulo"] == metadata_dict["titulo"]
    mock_save_file.assert_called_once()

# ===== INICIO DE LAS CORRECCIONES =====

async def test_read_documentacion_success(
    client: AsyncClient, auth_token_usuario_regular: str, 
    test_documento_pendiente: Documentacion
):
    """Prueba listar documentación."""
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    response = await client.get(f"{settings.API_V1_STR}/documentacion/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    documentos = response.json()
    assert isinstance(documentos, list)
    assert any(d["id"] == str(test_documento_pendiente.id) for d in documentos)

async def test_read_documentacion_by_equipo(
    client: AsyncClient, auth_token_usuario_regular: str, 
    test_documento_pendiente: Documentacion,
    test_equipo_reservable: Equipo
):
    """Prueba listar documentación filtrando por equipo."""
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    equipo_id = test_equipo_reservable.id
    response = await client.get(f"{settings.API_V1_STR}/documentacion/equipo/{equipo_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    documentos = response.json()
    assert isinstance(documentos, list)
    assert len(documentos) > 0
    assert all(d["equipo_id"] == str(equipo_id) for d in documentos)

async def test_read_documentacion_by_id_success(
    client: AsyncClient, auth_token_usuario_regular: str, 
    test_documento_pendiente: Documentacion
):
    """Prueba obtener un documento por ID."""
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    doc_id = test_documento_pendiente.id
    response = await client.get(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    doc_data = response.json()
    assert doc_data["id"] == str(doc_id)

async def test_update_documentacion_metadata_success(
    client: AsyncClient, auth_token_supervisor: str,
    test_documento_pendiente: Documentacion,
    test_tipo_doc_manual: TipoDocumento
):
    """Prueba actualizar metadatos de un documento."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    doc_id = test_documento_pendiente.id
    update_schema = DocumentacionUpdate(
        titulo="Título Metadato Actualizado",
        descripcion="Desc Actualizada",
        tipo_documento_id=test_tipo_doc_manual.id
    )
    update_data = jsonable_encoder(update_schema.model_dump(exclude_unset=True))
    response = await client.put(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers, json=update_data)

    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"
    updated_doc = response.json()
    assert updated_doc["id"] == str(doc_id)
    assert updated_doc["titulo"] == "Título Metadato Actualizado"

async def test_verify_documentacion_success(
    client: AsyncClient, auth_token_supervisor: str,
    test_documento_pendiente: Documentacion
):
    """Prueba verificar un documento pendiente."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    doc_id = test_documento_pendiente.id
    assert test_documento_pendiente.estado == "Pendiente"

    verify_schema = DocumentacionVerify(estado="Verificado", notas_verificacion="Factura correcta.")
    verify_data = jsonable_encoder(verify_schema)
    response = await client.post(f"{settings.API_V1_STR}/documentacion/{doc_id}/verificar", headers=headers, json=verify_data)

    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"
    verified_doc = response.json()
    assert verified_doc["estado"] == "Verificado"

async def test_reject_documentacion_success(
    client: AsyncClient, auth_token_supervisor: str,
    test_documento_pendiente: Documentacion
):
    """Prueba rechazar un documento pendiente."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    doc_id = test_documento_pendiente.id

    verify_schema = DocumentacionVerify(estado="Rechazado", notas_verificacion="Documento ilegible.")
    verify_data = jsonable_encoder(verify_schema)
    response = await client.post(f"{settings.API_V1_STR}/documentacion/{doc_id}/verificar", headers=headers, json=verify_data)

    assert response.status_code == status.HTTP_200_OK
    rejected_doc = response.json()
    assert rejected_doc["estado"] == "Rechazado"

# Se corrige la ruta del mock para apuntar a la función correcta en storage.py
@mock.patch("app.core.storage.aiofiles.os.remove", new_callable=mock.AsyncMock)
@mock.patch("app.core.storage.aiofiles.os.path.isfile", new_callable=mock.AsyncMock)
async def test_delete_documentacion_success(
    mock_is_file: mock.AsyncMock, mock_os_remove: mock.AsyncMock,
    client: AsyncClient, auth_token_admin: str,
    test_documento_pendiente: Documentacion
):
    """Prueba eliminar un documento y su archivo simulado."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    doc_id = test_documento_pendiente.id
    mock_is_file.return_value = True

    delete_response = await client.delete(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers)

    assert delete_response.status_code == status.HTTP_200_OK, f"Detalle error: {delete_response.text}"
    assert "Archivo asociado también eliminado" in delete_response.json()["msg"]
    mock_is_file.assert_called_once()
    mock_os_remove.assert_called_once()

    # Verificar que el registro DB ya no existe
    get_response = await client.get(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND

# Se corrige la ruta del mock y el texto esperado en el assert
@mock.patch("app.core.storage.aiofiles.os.remove", new_callable=mock.AsyncMock)
@mock.patch("app.core.storage.aiofiles.os.path.isfile", new_callable=mock.AsyncMock)
async def test_delete_documentacion_file_not_found(
    mock_is_file: mock.AsyncMock, mock_os_remove: mock.AsyncMock,
    client: AsyncClient, auth_token_admin: str,
    test_documento_pendiente: Documentacion
):
    """Prueba eliminar un documento cuando el archivo físico no se encuentra."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    doc_id = test_documento_pendiente.id
    mock_is_file.return_value = False

    delete_response = await client.delete(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers)

    assert delete_response.status_code == status.HTTP_200_OK
    assert "Archivo asociado no encontrado" in delete_response.json()["msg"]
    mock_is_file.assert_called_once() # Se debe llamar para saber que no existe
    mock_os_remove.assert_not_called()

    # Verificar que el registro DB sí se eliminó
    get_response = await client.get(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND
