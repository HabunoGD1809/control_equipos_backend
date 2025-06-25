import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from fastapi import status
from fastapi.encoders import jsonable_encoder
from typing import Dict, List

from app.core.config import settings
from app.models.rol import Rol
from app.models.permiso import Permiso
from app.models.usuario import Usuario
from app.schemas.rol import RolCreate, RolUpdate

from sqlalchemy.orm import Session

pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="function")
def test_permisos_basicos(db: Session) -> Dict[str, Permiso]:
    nombres_permisos = ["ver_equipos", "crear_equipos", "administrar_catalogos"]
    permisos = {}
    for nombre in nombres_permisos:
        perm = db.query(Permiso).filter(Permiso.nombre == nombre).first()
        if not perm:
            perm = Permiso(nombre=nombre, descripcion=f"Permiso base {nombre}")
            db.add(perm)
    db.commit() # Commit para que los permisos estén disponibles
    for nombre in nombres_permisos:
        permisos[nombre] = db.query(Permiso).filter(Permiso.nombre == nombre).first()
    return permisos

@pytest.fixture(scope="function")
async def create_test_rol(db: Session, test_permisos_basicos: Dict[str, Permiso]) -> Rol:
    permiso_ver_equipos = test_permisos_basicos.get("ver_equipos")
    assert permiso_ver_equipos is not None, "Fixture 'test_permisos_basicos' no proporcionó 'ver_equipos'."

    rol_name = f"rol_simple_{uuid4().hex[:6]}"
    rol = db.query(Rol).filter(Rol.nombre == rol_name).first()
    if not rol:
        rol = Rol(nombre=rol_name, descripcion="Rol para GET/DELETE test")
        rol.permisos.append(permiso_ver_equipos)
        db.add(rol)
        db.commit()
        db.refresh(rol, attribute_names=['permisos'])
    return rol

async def test_read_permisos_success(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/gestion/permisos/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    permisos = response.json()
    assert isinstance(permisos, list)
    assert len(permisos) > 0
    nombres_permisos = {p["nombre"] for p in permisos}
    assert "ver_equipos" in nombres_permisos
    assert "administrar_usuarios" in nombres_permisos

async def test_read_permisos_no_permission(client: AsyncClient, auth_token_user: str):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    response = await client.get(f"{settings.API_V1_STR}/gestion/permisos/", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_create_rol_success(
    client: AsyncClient,
    auth_token_admin: str,
    test_permisos_basicos: Dict[str, Permiso]
):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    rol_name = f"RolTest_{uuid4().hex[:6]}"
    
    perm_ver_equipos = test_permisos_basicos.get("ver_equipos")
    perm_crear_equipos = test_permisos_basicos.get("crear_equipos")
    assert perm_ver_equipos and perm_crear_equipos, "Faltan permisos básicos"
    
    perm_ids_to_assign: List[UUID] = [perm_ver_equipos.id, perm_crear_equipos.id]
    
    rol_schema = RolCreate(
        nombre=rol_name,
        descripcion="Rol de prueba con permisos",
        permiso_ids=perm_ids_to_assign
    )
    data = jsonable_encoder(rol_schema)

    response = await client.post(f"{settings.API_V1_STR}/gestion/roles/", headers=headers, json=data)
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_rol = response.json()
    assert created_rol["nombre"] == rol_name
    assert "id" in created_rol
    returned_perm_ids = {p["id"] for p in created_rol.get("permisos", [])}
    assert set(map(str, perm_ids_to_assign)) == returned_perm_ids

async def test_create_rol_no_permission(client: AsyncClient, auth_token_user: str):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    rol_schema = RolCreate(nombre=f"RolForbidden_{uuid4().hex[:6]}", descripcion="Test", permiso_ids=[])
    data = jsonable_encoder(rol_schema)
    response = await client.post(f"{settings.API_V1_STR}/gestion/roles/", headers=headers, json=data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_create_rol_duplicate_name(client: AsyncClient, auth_token_admin: str, test_rol_usuario: Rol):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    rol_schema = RolCreate(nombre=test_rol_usuario.nombre, descripcion="Duplicado", permiso_ids=[])
    data = jsonable_encoder(rol_schema)
    response = await client.post(f"{settings.API_V1_STR}/gestion/roles/", headers=headers, json=data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "nombre" in response.json()["detail"].lower()

async def test_create_rol_invalid_permission_id(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    invalid_perm_id = uuid4()
    rol_schema = RolCreate(
        nombre=f"RolInvalidPerm_{uuid4().hex[:6]}",
        descripcion="Test",
        permiso_ids=[invalid_perm_id]
    )
    data = jsonable_encoder(rol_schema)
    response = await client.post(f"{settings.API_V1_STR}/gestion/roles/", headers=headers, json=data)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert f"permiso con id {invalid_perm_id} no encontrado" in response.json()["detail"].lower()

async def test_read_roles_success(client: AsyncClient, auth_token_admin: str, test_rol_usuario: Rol):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/gestion/roles/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    roles = response.json()
    assert isinstance(roles, list)
    assert any(r["id"] == str(test_rol_usuario.id) for r in roles)
    assert any(r["nombre"] == "admin" for r in roles)

async def test_read_roles_permission_ok_for_user_admin(client: AsyncClient, auth_token_supervisor: str):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    response = await client.get(f"{settings.API_V1_STR}/gestion/roles/", headers=headers)
    assert response.status_code == status.HTTP_200_OK, f"Supervisor debería poder ver roles"
    assert isinstance(response.json(), list)

async def test_read_roles_no_permission(client: AsyncClient, auth_token_user: str):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    response = await client.get(f"{settings.API_V1_STR}/gestion/roles/", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_read_rol_by_id_success(client: AsyncClient, auth_token_admin: str, create_test_rol: Rol):
    target_rol = create_test_rol
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/gestion/roles/{target_rol.id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    rol_data = response.json()
    assert rol_data["id"] == str(target_rol.id)
    assert rol_data["nombre"] == target_rol.nombre
    assert "permisos" in rol_data
    assert isinstance(rol_data["permisos"], list)
    if target_rol.permisos:
         assert len(rol_data["permisos"]) >= 1
         perm_ids_retornados = {p['id'] for p in rol_data["permisos"]}
         assert str(target_rol.permisos[0].id) in perm_ids_retornados

async def test_read_rol_by_id_not_found(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    non_existent_id = uuid4()
    response = await client.get(f"{settings.API_V1_STR}/gestion/roles/{non_existent_id}", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

async def test_update_rol_success(
    client: AsyncClient,
    auth_token_admin: str,
    create_test_rol: Rol,
    test_permisos_basicos: Dict[str, Permiso]
):
    target_rol = create_test_rol
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    new_name = f"RolActualizado_{uuid4().hex[:6]}"
    new_desc = "Descripción actualizada."
    
    perm_crear_equipos = test_permisos_basicos.get("crear_equipos")
    perm_admin_catalogos = test_permisos_basicos.get("administrar_catalogos")
    assert perm_crear_equipos and perm_admin_catalogos, "Faltan permisos básicos"
    
    new_perm_ids = [perm_crear_equipos.id, perm_admin_catalogos.id]
    
    update_schema = RolUpdate(
        nombre=new_name,
        descripcion=new_desc,
        permiso_ids=new_perm_ids
    )
    update_data = jsonable_encoder(update_schema.model_dump(exclude_unset=True))

    response = await client.put(f"{settings.API_V1_STR}/gestion/roles/{target_rol.id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"
    updated_rol = response.json()
    assert updated_rol["id"] == str(target_rol.id)
    assert updated_rol["nombre"] == new_name
    assert updated_rol["descripcion"] == new_desc
    returned_perm_ids = {p["id"] for p in updated_rol.get("permisos", [])}
    assert set(map(str, new_perm_ids)) == returned_perm_ids

async def test_update_rol_remove_all_permissions(client: AsyncClient, auth_token_admin: str, create_test_rol: Rol):
    target_rol = create_test_rol
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    
    # CORRECCIÓN: Se añaden todos los campos obligatorios
    update_schema = RolUpdate(
        nombre=target_rol.nombre,
        descripcion=target_rol.descripcion,
        permiso_ids=[]
    )
    update_data = jsonable_encoder(update_schema.model_dump(exclude_unset=True))

    response = await client.put(f"{settings.API_V1_STR}/gestion/roles/{target_rol.id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_200_OK
    updated_rol = response.json()
    assert updated_rol["id"] == str(target_rol.id)
    assert len(updated_rol.get("permisos", [])) == 0

async def test_update_rol_no_permission(client: AsyncClient, auth_token_user: str, create_test_rol: Rol):
    target_rol = create_test_rol
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    
    # CORRECCIÓN: Se añaden todos los campos obligatorios
    update_schema = RolUpdate(
        nombre=target_rol.nombre,
        descripcion="Intento no autorizado",
        permiso_ids=[]
    )
    update_data = jsonable_encoder(update_schema.model_dump(exclude_unset=True))
    response = await client.put(f"{settings.API_V1_STR}/gestion/roles/{target_rol.id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_update_rol_not_found(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    non_existent_id = uuid4()
    
    # CORRECCIÓN: Se añaden todos los campos obligatorios
    update_schema = RolUpdate(
        nombre="Fantasma",
        descripcion="Fantasma",
        permiso_ids=[]
    )
    update_data = jsonable_encoder(update_schema.model_dump(exclude_unset=True))
    response = await client.put(f"{settings.API_V1_STR}/gestion/roles/{non_existent_id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND

async def test_delete_rol_success(client: AsyncClient, auth_token_admin: str, create_test_rol: Rol):
    target_rol = create_test_rol
    headers = {"Authorization": f"Bearer {auth_token_admin}"}

    delete_response = await client.delete(f"{settings.API_V1_STR}/gestion/roles/{target_rol.id}", headers=headers)
    assert delete_response.status_code == status.HTTP_200_OK, f"Detalle error: {delete_response.text}"
    assert "eliminado correctamente" in delete_response.json()["msg"]

    get_response = await client.get(f"{settings.API_V1_STR}/gestion/roles/{target_rol.id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND

async def test_delete_rol_no_permission(client: AsyncClient, auth_token_user: str, create_test_rol: Rol):
    target_rol = create_test_rol
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    delete_response = await client.delete(f"{settings.API_V1_STR}/gestion/roles/{target_rol.id}", headers=headers)
    assert delete_response.status_code == status.HTTP_403_FORBIDDEN

async def test_delete_rol_not_found(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    non_existent_id = uuid4()
    delete_response = await client.delete(f"{settings.API_V1_STR}/gestion/roles/{non_existent_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_404_NOT_FOUND

async def test_delete_rol_with_assigned_user(client: AsyncClient, db: Session, auth_token_admin: str, test_usuario_regular_fixture: Usuario):
    rol_usuario_regular_id = test_usuario_regular_fixture.rol_id
    headers = {"Authorization": f"Bearer {auth_token_admin}"}

    delete_response = await client.delete(f"{settings.API_V1_STR}/gestion/roles/{rol_usuario_regular_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_409_CONFLICT, f"Detalle error: {delete_response.text}"
    assert "no se puede eliminar el rol" in delete_response.json()["detail"].lower()
