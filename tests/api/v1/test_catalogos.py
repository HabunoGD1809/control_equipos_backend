import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.models.estado_equipo import EstadoEquipo
from app.schemas.estado_equipo import EstadoEquipoCreate, EstadoEquipoUpdate 

pytestmark = pytest.mark.asyncio

# --- Tests para Estados de Equipo ---

async def test_create_estado_equipo(client: AsyncClient, auth_token_admin: str):
    """Prueba crear un nuevo estado de equipo (admin debe tener 'administrar_catalogos')."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    estado_name = f"EstadoTest_{uuid4().hex[:6]}"
    # Crear schema
    estado_schema = EstadoEquipoCreate(
        nombre=estado_name,
        descripcion="Estado de prueba creado por test",
        permite_movimientos=True,
        requiere_autorizacion=False,
        es_estado_final=False,
        color_hex="#FF00FF",
        icono="fa-plus"
    )
    # Usar jsonable_encoder
    data = jsonable_encoder(estado_schema)

    response = await client.post(f"{settings.API_V1_STR}/catalogos/estados-equipo/", headers=headers, json=data)
    # Verificar permiso admin
    assert response.status_code == 201, f"Detalle del error: {response.text}"
    created_estado = response.json()
    assert created_estado["nombre"] == estado_name
    assert created_estado["color_hex"] == "#FF00FF"
    assert "id" in created_estado

async def test_create_estado_equipo_duplicate_name(client: AsyncClient, auth_token_admin: str):
    """Prueba crear un estado con nombre duplicado (admin debe tener 'administrar_catalogos')."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    estado_name = f"EstadoDup_{uuid4().hex[:6]}"
    estado_schema = EstadoEquipoCreate(
        nombre=estado_name,
        descripcion="Estado duplicado",
        permite_movimientos=True,
        requiere_autorizacion=False,
        es_estado_final=False,
        color_hex="#FFFFFF",
        icono="fa-clone"
    )
    data = jsonable_encoder(estado_schema)
    # Crear primero
    response1 = await client.post(f"{settings.API_V1_STR}/catalogos/estados-equipo/", headers=headers, json=data)
    assert response1.status_code == 201, f"Error al crear primer estado: {response1.text}"
    # Intentar crear de nuevo
    response2 = await client.post(f"{settings.API_V1_STR}/catalogos/estados-equipo/", headers=headers, json=data)
    # El servicio debería validar y devolver 400 o 409
    assert response2.status_code in [400, 409], f"Se esperaba 400/409 pero se obtuvo {response2.status_code}"
    # Verificar mensaje de error si aplica

async def test_read_estados_equipo(client: AsyncClient, auth_token_usuario_regular: str):
    """Prueba listar estados (cualquier usuario autenticado debería poder)."""
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    response = await client.get(f"{settings.API_V1_STR}/catalogos/estados-equipo/", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    nombres_estados = {estado['nombre'] for estado in response.json()}
    assert "Disponible" in nombres_estados
    assert "En Uso" in nombres_estados

async def test_update_estado_equipo(client: AsyncClient, auth_token_admin: str):
    """Prueba actualizar un estado de equipo (admin debe tener 'administrar_catalogos')."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    # Crear estado
    estado_name = f"EstadoUpdate_{uuid4().hex[:6]}"
    create_schema = EstadoEquipoCreate(
        nombre=estado_name, 
        permite_movimientos=True,
        descripcion="Original",
        requiere_autorizacion=False,
        es_estado_final=False,
        color_hex="#000000",
        icono="fa-edit"
        )
    create_data = jsonable_encoder(create_schema)
    create_response = await client.post(f"{settings.API_V1_STR}/catalogos/estados-equipo/", headers=headers, json=create_data)
    assert create_response.status_code == 201, f"Error al crear estado: {create_response.text}"
    estado_id = create_response.json()["id"]

    # Actualizar
    update_schema = EstadoEquipoUpdate(
        nombre=f"EstadoActualizado_{uuid4().hex[:6]}",
        descripcion="Descripción Actualizada", 
        permite_movimientos=False, 
        color_hex="#112233",
        icono="fa-lock",
    )
    # Usar model_dump() y jsonable_encoder
    update_data = jsonable_encoder(update_schema.model_dump(exclude_unset=True))
    update_response = await client.put(f"{settings.API_V1_STR}/catalogos/estados-equipo/{estado_id}", headers=headers, json=update_data)
    # Verificar permiso admin
    assert update_response.status_code == 200, f"Detalle del error: {update_response.text}"
    updated_estado = update_response.json()
    assert updated_estado["id"] == estado_id
    assert updated_estado["nombre"] == update_schema.nombre
    assert updated_estado["descripcion"] == "Descripción Actualizada"
    assert updated_estado["permite_movimientos"] is False
    assert updated_estado["icono"] == "fa-lock"

async def test_delete_estado_equipo(client: AsyncClient, auth_token_admin: str):
    """Prueba eliminar un estado de equipo (admin debe tener 'administrar_catalogos')."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    # Crear estado
    estado_name = f"EstadoDelete_{uuid4().hex[:6]}"
    create_schema = EstadoEquipoCreate(
        nombre=estado_name,
        descripcion="Para borrar",
        permite_movimientos=True,
        requiere_autorizacion=False,
        es_estado_final=True,
        color_hex="#FF0000",
        icono="fa-trash"
    )
    create_data = jsonable_encoder(create_schema)
    create_response = await client.post(f"{settings.API_V1_STR}/catalogos/estados-equipo/", headers=headers, json=create_data)
    assert create_response.status_code == 201, f"Error al crear estado: {create_response.text}"
    estado_id = create_response.json()["id"]

    # Eliminar
    delete_response = await client.delete(f"{settings.API_V1_STR}/catalogos/estados-equipo/{estado_id}", headers=headers)
    # Verificar permiso admin
    assert delete_response.status_code == 200, f"Detalle del error: {delete_response.text}"
    assert "eliminado" in delete_response.json().get("msg", "")

    # Verificar que ya no existe
    get_response = await client.get(f"{settings.API_V1_STR}/catalogos/estados-equipo/{estado_id}", headers=headers)
    assert get_response.status_code == 404
