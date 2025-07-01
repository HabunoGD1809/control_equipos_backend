import pytest
from httpx import AsyncClient
from fastapi import status

from app.core.config import settings
from app.models import (
    Usuario, Rol, Equipo, EstadoEquipo, Proveedor,
    TipoItemInventario, InventarioStock
)
from sqlalchemy.orm import Session

pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_delete_rol_en_uso_falla(
    client: AsyncClient,
    auth_token_admin: str,
    test_rol_usuario_regular: Rol,
    test_usuario_regular_fixture: Usuario
):
    """Prueba que no se puede eliminar un Rol si está asignado a un usuario."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    rol_id = test_rol_usuario_regular.id
    
    response = await client.delete(
        f"{settings.API_V1_STR}/gestion/roles/{rol_id}",
        headers=headers
    )
    
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "no se puede eliminar el rol" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_delete_estado_equipo_en_uso_falla(
    client: AsyncClient,
    auth_token_admin: str,
    test_estado_disponible: EstadoEquipo,
    test_equipo_principal: Equipo
):
    """Prueba que no se puede eliminar un EstadoEquipo si está en uso."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    estado_id = test_estado_disponible.id
    
    response = await client.delete(
        f"{settings.API_V1_STR}/catalogos/estados-equipo/{estado_id}",
        headers=headers
    )
    
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "está en uso" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_delete_proveedor_en_uso_falla(
    client: AsyncClient,
    auth_token_admin: str,
    db: Session,
    test_proveedor: Proveedor,
    test_equipo_principal: Equipo
):
    """Prueba que no se puede eliminar un Proveedor si está asociado a un equipo."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    
    test_equipo_principal.proveedor_id = test_proveedor.id
    db.flush()
    
    proveedor_id = test_proveedor.id
    
    response = await client.delete(
        f"{settings.API_V1_STR}/proveedores/{proveedor_id}",
        headers=headers
    )
    
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "está asociado" in response.json()["detail"].lower()
    
@pytest.mark.asyncio
async def test_delete_tipo_item_con_stock_falla(
    client: AsyncClient,
    auth_token_admin: str,
    stock_inicial_toner: InventarioStock
):
    """
    Prueba que no se puede eliminar un Tipo de Item si tiene stock asociado.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    tipo_item_id = stock_inicial_toner.tipo_item_id

    response = await client.delete(
        f"{settings.API_V1_STR}/inventario/tipos/{tipo_item_id}",
        headers=headers
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "tiene stock o movimientos asociados" in response.json()["detail"].lower()
