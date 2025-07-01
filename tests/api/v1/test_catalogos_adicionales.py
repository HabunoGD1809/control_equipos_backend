import pytest
from httpx import AsyncClient
from uuid import uuid4
from fastapi import status
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.schemas.tipo_documento import TipoDocumentoCreate
from app.schemas.tipo_mantenimiento import TipoMantenimientoCreate

pytestmark = pytest.mark.asyncio

# --- Tests para Tipos de Documento ---
@pytest.mark.asyncio
async def test_crud_tipos_documento(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    tipo_nombre = f"Documento Test CRUD {uuid4().hex[:6]}"
    
    # 1. CREATE
    create_schema = TipoDocumentoCreate(
        nombre=tipo_nombre,
        descripcion="Tipo para test CRUD",
        requiere_verificacion=True,
        formato_permitido=["pdf", "jpg", "png"]
    )
    create_response = await client.post(f"{settings.API_V1_STR}/catalogos/tipos-documento/", headers=headers, json=jsonable_encoder(create_schema))
    assert create_response.status_code == status.HTTP_201_CREATED
    created_tipo = create_response.json()
    assert created_tipo["nombre"] == tipo_nombre
    tipo_id = created_tipo["id"]

    # 2. READ (List)
    read_response = await client.get(f"{settings.API_V1_STR}/catalogos/tipos-documento/", headers=headers)
    assert read_response.status_code == status.HTTP_200_OK
    assert any(t["id"] == tipo_id for t in read_response.json())

    # 3. UPDATE
    update_data = {"descripcion": "Descripción actualizada", "formato_permitido": ["pdf"]}
    update_response = await client.put(f"{settings.API_V1_STR}/catalogos/tipos-documento/{tipo_id}", headers=headers, json=update_data)
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["descripcion"] == "Descripción actualizada"
    assert update_response.json()["formato_permitido"] == ["pdf"]

    # 4. DELETE
    delete_response = await client.delete(f"{settings.API_V1_STR}/catalogos/tipos-documento/{tipo_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert "eliminado" in delete_response.json()["msg"]

    # Verify DELETE
    get_response = await client.get(f"{settings.API_V1_STR}/catalogos/tipos-documento/{tipo_id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND

# --- Tests para Tipos de Mantenimiento ---
@pytest.mark.asyncio
async def test_crud_tipos_mantenimiento(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    tipo_nombre = f"Mantenimiento Test CRUD {uuid4().hex[:6]}"
    
    # 1. CREATE
    create_schema = TipoMantenimientoCreate(
        nombre=tipo_nombre,
        descripcion="Mantenimiento para test CRUD",
        es_preventivo=True,
        periodicidad_dias=30,
        requiere_documentacion=False
    )
    create_response = await client.post(f"{settings.API_V1_STR}/catalogos/tipos-mantenimiento/", headers=headers, json=jsonable_encoder(create_schema))
    assert create_response.status_code == status.HTTP_201_CREATED
    created_tipo = create_response.json()
    assert created_tipo["nombre"] == tipo_nombre
    tipo_id = created_tipo["id"]

    # 2. READ (List)
    read_response = await client.get(f"{settings.API_V1_STR}/catalogos/tipos-mantenimiento/", headers=headers)
    assert read_response.status_code == status.HTTP_200_OK
    assert any(t["id"] == tipo_id for t in read_response.json())

    # 3. UPDATE
    update_data = {"periodicidad_dias": 45, "requiere_documentacion": True}
    update_response = await client.put(f"{settings.API_V1_STR}/catalogos/tipos-mantenimiento/{tipo_id}", headers=headers, json=update_data)
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["periodicidad_dias"] == 45
    assert update_response.json()["requiere_documentacion"] is True

    # 4. DELETE
    delete_response = await client.delete(f"{settings.API_V1_STR}/catalogos/tipos-mantenimiento/{tipo_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert "eliminado" in delete_response.json()["msg"]

    # Verify DELETE
    get_response = await client.get(f"{settings.API_V1_STR}/catalogos/tipos-mantenimiento/{tipo_id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND
