import pytest
from httpx import AsyncClient
from fastapi import status
from app.core.config import settings
from app.models import Equipo, TipoDocumento

pytestmark = pytest.mark.asyncio

async def test_subir_archivo_muy_grande_falla(
    client: AsyncClient, auth_token_supervisor: str,
    test_equipo_reservable: Equipo, test_tipo_doc_manual: TipoDocumento
):
    """
    Prueba que la API rechaza activamente un archivo que excede el tamaño máximo.
    """
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    metadata = {
        "tipo_documento_id": str(test_tipo_doc_manual.id),
        "equipo_id": str(test_equipo_reservable.id),
        "titulo": "Archivo Grande"
    }
    
    dummy_content = b'a' * (settings.MAX_FILE_SIZE_BYTES + 1)
    files = {'file': ('large_file.txt', dummy_content, 'text/plain')}

    response = await client.post(
        f"{settings.API_V1_STR}/documentacion/",
        headers=headers, data=metadata, files=files
    )

    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert "demasiado grande" in response.json()["detail"].lower()

async def test_subir_archivo_tipo_no_permitido_falla(
    client: AsyncClient, auth_token_supervisor: str,
    test_equipo_reservable: Equipo, test_tipo_doc_manual: TipoDocumento
):
    """Prueba la validación de tipo MIME."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    metadata = {
        "tipo_documento_id": str(test_tipo_doc_manual.id),
        "equipo_id": str(test_equipo_reservable.id),
        "titulo": "Archivo ZIP"
    }
    files = {'file': ('archive.zip', b'zipcontent', 'application/zip')}

    response = await client.post(
        f"{settings.API_V1_STR}/documentacion/",
        headers=headers, data=metadata, files=files
    )

    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert "tipo de archivo 'application/zip' no permitido" in response.json()["detail"].lower()
