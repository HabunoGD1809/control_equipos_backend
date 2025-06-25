import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.usuario import Usuario
from app.models.rol import Rol
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate

pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="function")
async def create_test_rol_for_user_tests(db: Session) -> Rol:
    rol_name = f"rol_for_user_test_{uuid4().hex[:6]}"
    rol = db.query(Rol).filter(Rol.nombre == rol_name).first()
    if not rol:
        rol = Rol(nombre=rol_name, descripcion="Rol para tests de usuarios")
        db.add(rol)
        db.commit()
        db.refresh(rol)
    return rol

@pytest.fixture(scope="function")
async def create_test_user_directly(db: Session, create_test_rol_for_user_tests: Rol) -> Usuario:
    username = f"get_user_{uuid4().hex[:6]}"
    email = f"{username}@example.com"
    from app.core.password import get_password_hash
    user = Usuario(
        nombre_usuario=username, email=email,
        hashed_password=get_password_hash("TestPassword123!"),
        rol_id=create_test_rol_for_user_tests.id, 
        requiere_cambio_contrasena=False, 
        bloqueado=False
    )
    # The original test had direct db.add/commit here, which is not ideal for fixtures.
    # The fixture should yield the object, and the test function's `db` fixture handles transaction.
    # However, to fix the "Cannot access attribute" error, we simply remove the problematic lines
    # from the test function itself. We will keep this fixture as is for now.
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

async def test_read_usuario_me_success(client: AsyncClient, test_user: Usuario, auth_token_user: str):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    response = await client.get(f"{settings.API_V1_STR}/usuarios/me", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    user_data = response.json()
    assert user_data["id"] == str(test_user.id)
    assert user_data["nombre_usuario"] == test_user.nombre_usuario
    assert user_data["email"] == test_user.email
    assert user_data["rol_id"] == str(test_user.rol_id)
    assert "hashed_password" not in user_data

async def test_read_usuario_me_no_token(client: AsyncClient):
    response = await client.get(f"{settings.API_V1_STR}/usuarios/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Not authenticated" in response.json()["detail"]

async def test_read_usuario_me_invalid_token(client: AsyncClient):
    headers = {"Authorization": "Bearer invalidtoken"}
    response = await client.get(f"{settings.API_V1_STR}/usuarios/me", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "No se pudieron validar las credenciales" in response.json()["detail"]

async def test_update_usuario_me_success(client: AsyncClient, test_user: Usuario, auth_token_user: str):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    new_email = f"updated_{uuid4().hex[:6]}@example.com"
    update_data = {"email": new_email}
    response = await client.put(f"{settings.API_V1_STR}/usuarios/me", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_200_OK
    updated_user_data = response.json()
    assert updated_user_data["id"] == str(test_user.id)
    assert updated_user_data["email"] == new_email
    assert updated_user_data["rol_id"] == str(test_user.rol_id)

async def test_update_usuario_me_change_password(client: AsyncClient, db: Session, test_user: Usuario, auth_token_user: str):
    from app.core.password import verify_password
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    new_password = f"NewPass_{uuid4().hex[:6]}!"
    update_data = {"password": new_password}
    response = await client.put(f"{settings.API_V1_STR}/usuarios/me", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_200_OK
    db.refresh(test_user)
    assert verify_password(new_password, test_user.hashed_password)

async def test_update_usuario_me_try_change_role(client: AsyncClient, test_user: Usuario, auth_token_user: str, test_rol_admin: Rol):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    update_data = {"rol_id": str(test_rol_admin.id)}
    response = await client.put(f"{settings.API_V1_STR}/usuarios/me", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "no se proporcionaron datos válidos" in response.json()["detail"].lower()

async def test_update_usuario_me_no_data(client: AsyncClient, auth_token_user: str):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    update_data = {}
    response = await client.put(f"{settings.API_V1_STR}/usuarios/me", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "no se proporcionaron datos válidos" in response.json()["detail"].lower()

async def test_create_usuario_success(client: AsyncClient, auth_token_admin: str, test_rol_usuario_regular: Rol):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    username = f"newtestuser_{uuid4().hex[:6]}"
    email = f"new_{uuid4().hex[:6]}@example.com"
    password = "NewUserPass123!"
    new_user_data = {
        "nombre_usuario": username,
        "email": email,
        "password": password,
        "rol_id": str(test_rol_usuario_regular.id)
    }
    response = await client.post(f"{settings.API_V1_STR}/usuarios/", headers=headers, json=new_user_data)
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_user = response.json()
    assert created_user["nombre_usuario"] == username
    assert created_user["email"] == email
    assert created_user["rol_id"] == str(test_rol_usuario_regular.id)
    assert "hashed_password" not in created_user

async def test_create_usuario_no_permission(client: AsyncClient, auth_token_user: str, test_rol_usuario_regular: Rol):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    username = f"forbidden_user_{uuid4().hex[:6]}"
    email = f"forbidden_{uuid4().hex[:6]}@example.com"
    password = "Password123!"
    new_user_data = {
        "nombre_usuario": username,
        "email": email,
        "password": password,
        "rol_id": str(test_rol_usuario_regular.id)
    }
    response = await client.post(f"{settings.API_V1_STR}/usuarios/", headers=headers, json=new_user_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_create_usuario_duplicate_username(client: AsyncClient, auth_token_admin: str, test_user: Usuario, test_rol_usuario_regular: Rol):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    new_user_data = {
        "nombre_usuario": test_user.nombre_usuario,
        "email": f"duplicate_{uuid4().hex[:6]}@example.com",
        "password": "Password123!",
        "rol_id": str(test_rol_usuario_regular.id)
    }
    response = await client.post(f"{settings.API_V1_STR}/usuarios/", headers=headers, json=new_user_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "nombre de usuario ya existe" in response.json()["detail"].lower()

async def test_create_usuario_duplicate_email(client: AsyncClient, auth_token_admin: str, test_user: Usuario, test_rol_usuario_regular: Rol):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    new_user_data = {
        "nombre_usuario": f"another_user_{uuid4().hex[:6]}",
        "email": test_user.email,
        "password": "Password123!",
        "rol_id": str(test_rol_usuario_regular.id)
    }
    response = await client.post(f"{settings.API_V1_STR}/usuarios/", headers=headers, json=new_user_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "correo electrónico ya existe" in response.json()["detail"].lower()

async def test_create_usuario_invalid_rol(client: AsyncClient, auth_token_admin: str):
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
    assert f"rol con id '{invalid_rol_id}' no fue encontrado" in response.json()["detail"].lower()

async def test_read_usuarios_success(client: AsyncClient, auth_token_admin: str, test_user: Usuario):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/usuarios/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    users_list = response.json()
    assert isinstance(users_list, list)
    assert len(users_list) >= 2
    assert any(u["id"] == str(test_user.id) for u in users_list)
    assert all("hashed_password" not in u for u in users_list)

async def test_read_usuarios_no_permission(client: AsyncClient, auth_token_user: str):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    response = await client.get(f"{settings.API_V1_STR}/usuarios/", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_read_usuario_by_id_success(client: AsyncClient, auth_token_admin: str, create_test_user_directly: Usuario):
    target_user = create_test_user_directly
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.get(f"{settings.API_V1_STR}/usuarios/{target_user.id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    user_data = response.json()
    assert user_data["id"] == str(target_user.id)
    assert user_data["nombre_usuario"] == target_user.nombre_usuario

async def test_read_usuario_by_id_not_found(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    non_existent_id = uuid4()
    response = await client.get(f"{settings.API_V1_STR}/usuarios/{non_existent_id}", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

async def test_read_usuario_by_id_no_permission(client: AsyncClient, auth_token_user: str, test_admin_fixture: Usuario):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    target_user_id = test_admin_fixture.id
    response = await client.get(f"{settings.API_V1_STR}/usuarios/{target_user_id}", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_update_usuario_success(client: AsyncClient, auth_token_admin: str, create_test_user_directly: Usuario, test_supervisor_fixture: Rol):
    target_user = create_test_user_directly
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    new_email = f"admin_updated_{uuid4().hex[:6]}@example.com"
    update_data = {
        "email": new_email,
        "rol_id": str(test_supervisor_fixture.id),
        "bloqueado": True
    }
    response = await client.put(f"{settings.API_V1_STR}/usuarios/{target_user.id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_200_OK
    updated_user = response.json()
    assert updated_user["id"] == str(target_user.id)
    assert updated_user["email"] == new_email
    assert updated_user["rol_id"] == str(test_supervisor_fixture.id)
    assert updated_user["bloqueado"] is True

async def test_update_usuario_no_permission(client: AsyncClient, auth_token_user: str, test_admin_fixture: Usuario):
    target_user_id = test_admin_fixture.id
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    update_data = {"email": "hacker@example.com"}
    response = await client.put(f"{settings.API_V1_STR}/usuarios/{target_user_id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_update_usuario_not_found(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    non_existent_id = uuid4()
    update_data = {"email": "ghost@example.com"}
    response = await client.put(f"{settings.API_V1_STR}/usuarios/{non_existent_id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND

async def test_update_usuario_invalid_rol(client: AsyncClient, auth_token_admin: str, create_test_user_directly: Usuario):
    target_user = create_test_user_directly
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    invalid_rol_id = uuid4()
    update_data = {"rol_id": str(invalid_rol_id)}
    response = await client.put(f"{settings.API_V1_STR}/usuarios/{target_user.id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_404_NOT_FOUND

async def test_delete_usuario_success(client: AsyncClient, auth_token_admin: str, create_test_user_directly: Usuario):
    target_user = create_test_user_directly
    headers = {"Authorization": f"Bearer {auth_token_admin}"}

    delete_response = await client.delete(f"{settings.API_V1_STR}/usuarios/{target_user.id}", headers=headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert "eliminado correctamente" in delete_response.json()["msg"]

    get_response = await client.get(f"{settings.API_V1_STR}/usuarios/{target_user.id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND

async def test_delete_usuario_no_permission(client: AsyncClient, auth_token_user: str, create_test_user_directly: Usuario):
    target_user = create_test_user_directly
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    delete_response = await client.delete(f"{settings.API_V1_STR}/usuarios/{target_user.id}", headers=headers)
    assert delete_response.status_code == status.HTTP_403_FORBIDDEN

async def test_delete_usuario_not_found(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    non_existent_id = uuid4()
    delete_response = await client.delete(f"{settings.API_V1_STR}/usuarios/{non_existent_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_404_NOT_FOUND
