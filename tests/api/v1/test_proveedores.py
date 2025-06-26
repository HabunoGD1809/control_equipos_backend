import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from fastapi import status
from fastapi.encoders import jsonable_encoder
from pydantic import HttpUrl

from app.core.config import settings
from app.models.proveedor import Proveedor
from app.schemas.proveedor import ProveedorCreate, ProveedorUpdate

from sqlalchemy.orm import Session

pytestmark = pytest.mark.asyncio

async def test_create_proveedor_success(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    prov_name = f"Proveedor Test Creación {uuid4().hex[:6]}"
    prov_rnc = f"RNC{uuid4().hex[:8]}"
    
    # CORRECCIÓN: Se envuelve la URL en HttpUrl
    prov_schema = ProveedorCreate(
        nombre=prov_name,
        descripcion="Proveedor de prueba",
        contacto="contacto@proveedor-test.com",
        direccion="Calle Falsa 123",
        sitio_web=HttpUrl("https://proveedor.test"),
        rnc=prov_rnc
    )
    data = jsonable_encoder(prov_schema)
    response = await client.post(f"{settings.API_V1_STR}/proveedores/", headers=headers, json=data)
    
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_prov = response.json()
    assert created_prov["nombre"] == prov_name
    assert created_prov["rnc"] == prov_rnc
    assert "id" in created_prov

async def test_create_proveedor_no_permission(client: AsyncClient, auth_token_usuario_regular: str):
    """
    Verifica que un usuario sin el permiso 'administrar_catalogos' no puede crear un proveedor.
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    
    # CORRECCIÓN: Se envuelve la URL en HttpUrl
    prov_schema = ProveedorCreate(
        nombre=f"Prov Forbidden {uuid4().hex[:6]}",
        descripcion="Test",
        contacto="test",
        direccion="test",
        sitio_web=HttpUrl("https://test.com"),
        rnc=f"RNCF{uuid4().hex[:7]}"
    )
    data = jsonable_encoder(prov_schema)
    response = await client.post(f"{settings.API_V1_STR}/proveedores/", headers=headers, json=data)

    # Un usuario regular no tiene permiso para 'administrar_catalogos'
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_create_proveedor_duplicate_name(client: AsyncClient, auth_token_admin: str, test_proveedor: Proveedor):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    
    # CORRECCIÓN: Se envuelve la URL en HttpUrl
    prov_schema = ProveedorCreate(
        nombre=test_proveedor.nombre,
        rnc=f"RNC{uuid4().hex[:8]}",
        descripcion="Test",
        contacto="test",
        direccion="test",
        sitio_web=HttpUrl("https://test.com")
    )
    data = jsonable_encoder(prov_schema)
    response = await client.post(f"{settings.API_V1_STR}/proveedores/", headers=headers, json=data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "nombre" in response.text.lower()

async def test_create_proveedor_duplicate_rnc(client: AsyncClient, auth_token_admin: str, test_proveedor: Proveedor):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    if not test_proveedor.rnc: pytest.skip("Fixture proveedor no tiene RNC para probar duplicado.")
    
    # CORRECCIÓN: Se envuelve la URL en HttpUrl
    prov_schema = ProveedorCreate(
        nombre=f"Prov Dup RNC {uuid4().hex[:6]}",
        rnc=test_proveedor.rnc,
        descripcion="Test",
        contacto="test",
        direccion="test",
        sitio_web=HttpUrl("https://test.com")
    )
    data = jsonable_encoder(prov_schema)
    response = await client.post(f"{settings.API_V1_STR}/proveedores/", headers=headers, json=data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "rnc" in response.text.lower()

async def test_update_proveedor_success(client: AsyncClient, auth_token_admin: str, test_proveedor: Proveedor):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    
    # CORRECCIÓN: Se envuelve la URL en HttpUrl
    update_schema = ProveedorUpdate(
        nombre=f"Prov-Updated-{uuid4().hex[:4]}",
        contacto="Contacto Actualizado",
        sitio_web=HttpUrl("https://updated.proveedor-test.com"),
        rnc=f"RNC-UPD-{uuid4().hex[:6]}"
    )
    update_data = jsonable_encoder(update_schema.model_dump(exclude_unset=True))
    response = await client.put(f"{settings.API_V1_STR}/proveedores/{test_proveedor.id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"

async def test_delete_proveedor_success(client: AsyncClient, auth_token_admin: str, db: Session):
    prov_name = f"Proveedor Borrar {uuid4().hex[:6]}"
    prov_rnc = f"RNCBORRAR{uuid4().hex[:6]}"
    
    # CORRECCIÓN: Se añade el campo 'rnc' que faltaba
    prov_to_delete = Proveedor(
        nombre=prov_name,
        rnc=prov_rnc,
        descripcion="Test",
        contacto="test",
        direccion="test",
        sitio_web="https://test.com"
    )
    db.add(prov_to_delete); db.flush(); db.refresh(prov_to_delete)
    prov_id = prov_to_delete.id

    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    delete_response = await client.delete(f"{settings.API_V1_STR}/proveedores/{prov_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_200_OK, f"Detalle error: {delete_response.text}"
    assert "eliminado correctamente" in delete_response.json()["msg"]

    get_response = await client.get(f"{settings.API_V1_STR}/proveedores/{prov_id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND
