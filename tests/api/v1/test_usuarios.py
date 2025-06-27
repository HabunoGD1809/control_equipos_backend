import pytest
from httpx import AsyncClient
from fastapi import status
from uuid import uuid4

from app.core.config import settings
from app.models import Usuario, Rol
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate

# ==============================================================================
# Tests para el endpoint /api/v1/usuarios/me
# ==============================================================================

@pytest.mark.asyncio
async def test_read_usuario_me_success(
    client: AsyncClient, 
    test_usuario_regular_fixture: Usuario,
    auth_token_usuario_regular: str
):
    """
    Prueba que un usuario autenticado pueda obtener sus propios datos.
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    response = await client.get(f"{settings.API_V1_STR}/usuarios/me", headers=headers)
    
    assert response.status_code == status.HTTP_200_OK
    user_data = response.json()
    
    assert user_data["id"] == str(test_usuario_regular_fixture.id)
    assert user_data["nombre_usuario"] == test_usuario_regular_fixture.nombre_usuario
    assert user_data["email"] == test_usuario_regular_fixture.email
    assert user_data["rol_id"] == str(test_usuario_regular_fixture.rol_id)
    assert "hashed_password" not in user_data

@pytest.mark.asyncio
async def test_read_usuario_me_unauthenticated(client: AsyncClient):
    """
    Prueba que un usuario no autenticado reciba un error 401.
    """
    response = await client.get(f"{settings.API_V1_STR}/usuarios/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_update_usuario_me_success(
    client: AsyncClient, 
    test_usuario_regular_fixture: Usuario,
    auth_token_usuario_regular: str
):
    """
    Prueba que un usuario autenticado pueda actualizar sus propios datos.
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    new_email = f"updated_{uuid4().hex[:6]}@example.com"
    update_data = {"email": new_email}
    
    response = await client.put(f"{settings.API_V1_STR}/usuarios/me", headers=headers, json=update_data)
    
    assert response.status_code == status.HTTP_200_OK
    updated_user_data = response.json()
    
    assert updated_user_data["id"] == str(test_usuario_regular_fixture.id)
    assert updated_user_data["email"] == new_email
    assert updated_user_data["rol_id"] == str(test_usuario_regular_fixture.rol_id)

# ==============================================================================
# Tests para el endpoint /api/v1/usuarios/ (CRUD administrado)
# ==============================================================================

@pytest.mark.asyncio
async def test_create_usuario_success(client: AsyncClient, auth_token_admin: str, test_rol_usuario_regular: Rol):
    """
    Prueba la creación exitosa de un nuevo usuario por un administrador.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    username = f"new_user_{uuid4().hex[:6]}"
    email = f"{username}@example.com"
    password = "SecurePassword123!"
    
    new_user_data = {
        "nombre_usuario": username,
        "email": email,
        "password": password,
        "rol_id": str(test_rol_usuario_regular.id)
    }
    
    response = await client.post(f"{settings.API_V1_STR}/usuarios/", headers=headers, json=new_user_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    created_user = response.json()
    assert created_user["nombre_usuario"] == username
    assert created_user["email"] == email
    assert created_user["rol_id"] == str(test_rol_usuario_regular.id)
    assert not created_user["bloqueado"]
    assert "hashed_password" not in created_user

@pytest.mark.asyncio
async def test_create_usuario_no_permission(client: AsyncClient, auth_token_usuario_regular: str, test_rol_usuario_regular: Rol):
    """
    Prueba que un usuario sin permisos no pueda crear otros usuarios.
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    new_user_data = {
        "nombre_usuario": "test_permission",
        "email": "permission@example.com",
        "password": "Password123!",
        "rol_id": str(test_rol_usuario_regular.id)
    }
    response = await client.post(f"{settings.API_V1_STR}/usuarios/", headers=headers, json=new_user_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_create_usuario_duplicate_username(
    client: AsyncClient, 
    auth_token_admin: str, 
    test_usuario_regular_fixture: Usuario, 
    test_rol_usuario_regular: Rol
):
    """
    Prueba que no se pueda crear un usuario con un nombre de usuario duplicado.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    new_user_data = {
        "nombre_usuario": test_usuario_regular_fixture.nombre_usuario, 
        "email": f"duplicate_{uuid4().hex[:6]}@example.com",
        "password": "Password123!",
        "rol_id": str(test_rol_usuario_regular.id)
    }
    response = await client.post(f"{settings.API_V1_STR}/usuarios/", headers=headers, json=new_user_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "ya existe un usuario con ese nombre de usuario" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_create_usuario_duplicate_email(
    client: AsyncClient, 
    auth_token_admin: str, 
    test_usuario_regular_fixture: Usuario, 
    test_rol_usuario_regular: Rol
):
    """
    Prueba que no se pueda crear un usuario con un email duplicado.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    new_user_data = {
        "nombre_usuario": f"another_user_{uuid4().hex[:6]}",
        "email": test_usuario_regular_fixture.email, 
        "password": "Password123!",
        "rol_id": str(test_rol_usuario_regular.id)
    }
    response = await client.post(f"{settings.API_V1_STR}/usuarios/", headers=headers, json=new_user_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "ya existe un usuario con ese correo electrónico" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_create_usuario_invalid_rol(client: AsyncClient, auth_token_admin: str):
    """
    Prueba que no se pueda crear un usuario con un rol_id inválido.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    invalid_rol_id = uuid4()
    new_user_data = {
        "nombre_usuario": f"invalid_role_user_{uuid4().hex[:6]}",
        "email": f"invalid_role_{uuid4().hex[:6]}@example.com",
        "password": "Password123!",
        "rol_id": str(invalid_rol_id)
    }
    response = await client.post(f"{settings.API_V1_STR}/usuarios/", headers=headers, json=new_user_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    detail = response.json()["detail"].lower()
    expected_fragment = f"el rol con id {str(invalid_rol_id).lower()} no fue encontrado"
    assert expected_fragment in detail


@pytest.mark.asyncio
async def test_read_usuarios_success(
    client: AsyncClient, 
    auth_token_admin: str, 
    test_usuario_regular_fixture: Usuario 
):
    """
    Prueba que un administrador pueda obtener la lista de usuarios.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/usuarios/", headers=headers)
    
    assert response.status_code == status.HTTP_200_OK
    users_list = response.json()
    assert isinstance(users_list, list)
    assert len(users_list) >= 2  
    
    assert any(u["id"] == str(test_usuario_regular_fixture.id) for u in users_list)
    assert all("hashed_password" not in u for u in users_list)

@pytest.mark.asyncio
async def test_read_usuarios_no_permission(client: AsyncClient, auth_token_usuario_regular: str):
    """
    Prueba que un usuario sin permisos no pueda obtener la lista de usuarios.
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    response = await client.get(f"{settings.API_V1_STR}/usuarios/", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_read_usuario_by_id_success(client: AsyncClient, auth_token_admin: str, create_test_user_directly: Usuario):
    """
    Prueba que un admin pueda obtener un usuario por su ID.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    target_user = create_test_user_directly
    response = await client.get(f"{settings.API_V1_STR}/usuarios/{target_user.id}", headers=headers)
    
    assert response.status_code == status.HTTP_200_OK
    user_data = response.json()
    assert user_data["id"] == str(target_user.id)
    assert user_data["nombre_usuario"] == target_user.nombre_usuario

@pytest.mark.asyncio
async def test_read_usuario_by_id_not_found(client: AsyncClient, auth_token_admin: str):
    """
    Prueba que se devuelva un 404 si el usuario no existe.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    non_existent_id = uuid4()
    response = await client.get(f"{settings.API_V1_STR}/usuarios/{non_existent_id}", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_read_usuario_by_id_no_permission(client: AsyncClient, auth_token_usuario_regular: str, test_admin_fixture: Usuario):
    """
    Prueba que un usuario regular no pueda ver los datos de otro usuario.
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    response = await client.get(f"{settings.API_V1_STR}/usuarios/{test_admin_fixture.id}", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_update_usuario_success(
    client: AsyncClient, 
    auth_token_admin: str, 
    create_test_user_directly: Usuario, 
    test_rol_supervisor: Rol
):
    """
    Prueba la actualización exitosa de un usuario por un administrador.
    """
    target_user = create_test_user_directly
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    new_email = f"admin_updated_{uuid4().hex[:6]}@example.com"
    
    update_data = {
        "email": new_email,
        "rol_id": str(test_rol_supervisor.id),
        "bloqueado": True
    }
    
    response = await client.put(f"{settings.API_V1_STR}/usuarios/{target_user.id}", headers=headers, json=update_data)
    
    assert response.status_code == status.HTTP_200_OK
    updated_user = response.json()
    assert updated_user["id"] == str(target_user.id)
    assert updated_user["email"] == new_email
    assert updated_user["rol_id"] == str(test_rol_supervisor.id)
    assert updated_user["bloqueado"] is True


@pytest.mark.asyncio
async def test_update_usuario_no_permission(client: AsyncClient, auth_token_usuario_regular: str, test_admin_fixture: Usuario):
    """
    Prueba que un usuario sin permisos no pueda actualizar a otro usuario.
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    update_data = {"email": "no_permission@example.com"}
    response = await client.put(f"{settings.API_V1_STR}/usuarios/{test_admin_fixture.id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_update_usuario_not_found(client: AsyncClient, auth_token_admin: str):
    """
    Prueba que la actualización falle si el usuario no existe.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    non_existent_id = uuid4()
    update_data = {"email": "ghost@example.com"}
    response = await client.put(f"{settings.API_V1_STR}/usuarios/{non_existent_id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_update_usuario_invalid_rol(client: AsyncClient, auth_token_admin: str, create_test_user_directly: Usuario):
    """
    Prueba que la actualización falle si se proporciona un rol_id inválido.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    invalid_rol_id = uuid4()
    update_data = {"rol_id": str(invalid_rol_id)}
    response = await client.put(f"{settings.API_V1_STR}/usuarios/{create_test_user_directly.id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_delete_usuario_success(client: AsyncClient, auth_token_admin: str, create_test_user_directly: Usuario):
    """
    Prueba la eliminación exitosa de un usuario por un administrador.
    """
    target_user = create_test_user_directly
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    
    # Eliminar
    delete_response = await client.delete(f"{settings.API_V1_STR}/usuarios/{target_user.id}", headers=headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert "eliminado correctamente" in delete_response.json()["msg"]
    
    # Verificar que ya no se puede obtener
    get_response = await client.get(f"{settings.API_V1_STR}/usuarios/{target_user.id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.asyncio
async def test_delete_usuario_no_permission(client: AsyncClient, auth_token_usuario_regular: str, create_test_user_directly: Usuario):
    """
    Prueba que un usuario sin permisos no pueda eliminar a otro.
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    response = await client.delete(f"{settings.API_V1_STR}/usuarios/{create_test_user_directly.id}", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.asyncio
async def test_delete_usuario_not_found(client: AsyncClient, auth_token_admin: str):
    """
    Prueba que la eliminación falle si el usuario no existe.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    non_existent_id = uuid4()
    response = await client.delete(f"{settings.API_V1_STR}/usuarios/{non_existent_id}", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
