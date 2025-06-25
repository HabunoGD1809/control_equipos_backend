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
    with mock.patch("app.api.routes.documentacion.save_upload_file", return_value=file_info) as _mock:
        yield _mock

# --- Tests para Documentación ---

async def test_create_documentacion_success(
    client: AsyncClient, auth_token_supervisor: str,
    test_equipo_reservable: Equipo,
    test_tipo_doc_manual: TipoDocumento,
    mock_save_file: mock.Mock
):
    """Prueba subir un documento y crear el registro."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}

    # --- CORRECCIÓN: Preparar datos como diccionario para 'data' ---
    metadata_dict = {
        "titulo": "Manual de Usuario Test",
        "descripcion": "Manual subido desde test",
        "tipo_documento_id": str(test_tipo_doc_manual.id), # Enviar UUID como string en form data
        "equipo_id": str(test_equipo_reservable.id) # Enviar UUID como string
        # mantenimiento_id y licencia_id son None por defecto
    }
    # ------------------------------------------------------------

    file_content = b"dummy pdf content"
    files = {'file': ('test_manual.pdf', io.BytesIO(file_content), 'application/pdf')}

    # --- CORRECCIÓN: Enviar metadatos en 'data' y archivo en 'files' ---
    response = await client.post(
        f"{settings.API_V1_STR}/documentacion/",
        headers=headers,
        data=metadata_dict, # Pasar diccionario directamente a data
        files=files
    )
    # ----------------------------------------------------------------

    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_doc = response.json()
    assert created_doc["titulo"] == metadata_dict["titulo"]
    assert created_doc["tipo_documento_id"] == metadata_dict["tipo_documento_id"]
    assert created_doc["equipo_id"] == metadata_dict["equipo_id"]
    assert "id" in created_doc
    assert created_doc["estado"] == "Pendiente"
    mock_info = mock_save_file.return_value
    assert created_doc["enlace"] == mock_info["file_path"]
    assert created_doc["nombre_archivo"] == mock_info["filename"]
    assert created_doc["mime_type"] == mock_info["mime_type"]
    assert created_doc["tamano_bytes"] == mock_info["size"]
    mock_save_file.assert_called_once()

async def test_read_documentacion_success(
    client: AsyncClient, auth_token_user: str, # Usuario normal tiene 'ver_documentos'
    test_documento_pendiente: Documentacion
):
    """Prueba listar documentación."""
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    response = await client.get(f"{settings.API_V1_STR}/documentacion/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    documentos = response.json()
    assert isinstance(documentos, list)
    assert len(documentos) > 0
    assert any(d["id"] == str(test_documento_pendiente.id) for d in documentos)

async def test_read_documentacion_by_equipo(
    client: AsyncClient, auth_token_user: str,
    test_documento_pendiente: Documentacion, # Asociado a test_equipo_reservable
    test_equipo_reservable: Equipo
):
    """Prueba listar documentación filtrando por equipo."""
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    equipo_id = test_equipo_reservable.id
    response = await client.get(f"{settings.API_V1_STR}/documentacion/equipo/{equipo_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    documentos = response.json()
    assert isinstance(documentos, list)
    assert len(documentos) > 0
    assert all(d["equipo_id"] == str(equipo_id) for d in documentos)
    assert any(d["id"] == str(test_documento_pendiente.id) for d in documentos)

async def test_read_documentacion_by_id_success(
    client: AsyncClient, auth_token_user: str,
    test_documento_pendiente: Documentacion
):
    """Prueba obtener un documento por ID."""
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    doc_id = test_documento_pendiente.id
    response = await client.get(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    doc_data = response.json()
    assert doc_data["id"] == str(doc_id)
    assert doc_data["titulo"] == test_documento_pendiente.titulo

async def test_update_documentacion_metadata_success(
    client: AsyncClient, auth_token_supervisor: str, # Supervisor tiene 'editar_documentos'
    test_documento_pendiente: Documentacion,
    test_tipo_doc_manual: TipoDocumento
):
    """Prueba actualizar metadatos de un documento."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    doc_id = test_documento_pendiente.id
    update_schema = DocumentacionUpdate(
        titulo="Título Metadato Actualizado",
        descripcion="Desc Actualizada",
        tipo_documento_id=test_tipo_doc_manual.id # Cambiar tipo
    )
    update_data = jsonable_encoder(update_schema.model_dump(exclude_unset=True))
    response = await client.put(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers, json=update_data)

    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"
    updated_doc = response.json()
    assert updated_doc["id"] == str(doc_id)
    assert updated_doc["titulo"] == "Título Metadato Actualizado"
    assert updated_doc["descripcion"] == "Desc Actualizada"
    assert updated_doc["tipo_documento_id"] == str(test_tipo_doc_manual.id)

async def test_verify_documentacion_success(
    client: AsyncClient, auth_token_supervisor: str, # Supervisor tiene 'verificar_documentos'
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
    assert verified_doc["id"] == str(doc_id)
    assert verified_doc["estado"] == "Verificado"
    assert verified_doc["notas_verificacion"] == "Factura correcta."
    assert verified_doc["verificado_por"] is not None # Debe registrar quién verificó
    assert verified_doc["fecha_verificacion"] is not None

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
    assert rejected_doc["id"] == str(doc_id)
    assert rejected_doc["estado"] == "Rechazado"
    assert rejected_doc["notas_verificacion"] == "Documento ilegible."

# Mock para simular os.remove y Path.is_file
@mock.patch("app.api.routes.documentacion.os.remove")
@mock.patch("app.api.routes.documentacion.Path.is_file")
async def test_delete_documentacion_success(
    mock_is_file: mock.Mock, mock_os_remove: mock.Mock,
    client: AsyncClient, auth_token_admin: str, # Admin tiene 'eliminar_documentos'
    test_documento_pendiente: Documentacion
):
    """Prueba eliminar un documento y su archivo simulado."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    doc_id = test_documento_pendiente.id
    # Simular que el archivo existe
    mock_is_file.return_value = True

    delete_response = await client.delete(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers)

    assert delete_response.status_code == status.HTTP_200_OK, f"Detalle error: {delete_response.text}"
    assert "eliminado." in delete_response.json()["msg"]    # Verificar que se intentó borrar el archivo
    mock_is_file.assert_called_once()
    mock_os_remove.assert_called_once()

    # Verificar que el registro DB ya no existe
    get_response = await client.get(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND

@mock.patch("app.api.routes.documentacion.os.remove")
@mock.patch("app.api.routes.documentacion.Path.is_file")
async def test_delete_documentacion_file_not_found(
    mock_is_file: mock.Mock, mock_os_remove: mock.Mock,
    client: AsyncClient, auth_token_admin: str,
    test_documento_pendiente: Documentacion
):
    """Prueba eliminar un documento cuando el archivo físico no se encuentra."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    doc_id = test_documento_pendiente.id
    # Simular que el archivo NO existe
    mock_is_file.return_value = False

    delete_response = await client.delete(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers)

    assert delete_response.status_code == status.HTTP_200_OK
    assert "(archivo no encontrado)" in delete_response.json()["msg"] # Verificar mensaje específico
    # Verificar que NO se intentó borrar el archivo
    mock_os_remove.assert_not_called()

    # Verificar que el registro DB sí se eliminó
    get_response = await client.get(f"{settings.API_V1_STR}/documentacion/{doc_id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND
