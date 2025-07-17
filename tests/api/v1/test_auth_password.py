import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.orm import Session
from uuid import uuid4
from fastapi import status, BackgroundTasks

from app.core.config import settings
from app.models.rol import Rol
from app.schemas.usuario import UsuarioCreate
from app.services.usuario import usuario_service

pytestmark = pytest.mark.asyncio


async def test_password_recovery_flow(
    client: AsyncClient,
    db: Session,
    test_rol_usuario_regular: Rol,
    auth_token_admin: str,
):
    """
    Prueba el flujo completo de recuperación de contraseña, manejando correctamente
    las tareas en segundo plano para evitar condiciones de carrera.
    """
    unique_id = uuid4().hex[:6]
    username = f"test_reset_user_{unique_id}"
    old_password = "SecurePassword123!"
    new_password = "MyNewSecurePassword456!"

    user_in = UsuarioCreate(
        nombre_usuario=username,
        email=f"test.reset.{unique_id}@example.com",
        password=old_password,
        rol_id=test_rol_usuario_regular.id,
    )
    user_to_reset = usuario_service.create(db, obj_in=user_in)
    db.commit()
    db.refresh(user_to_reset)

    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}

    # 1. Admin solicita el token de reseteo
    response_request = await client.post(
        f"{settings.API_V1_STR}/auth/password-recovery/request-reset",
        headers=admin_headers,
        json={"username": username},
    )
    assert response_request.status_code == status.HTTP_200_OK
    reset_token = response_request.json()["reset_token"]
    assert reset_token

    # 2. El usuario usa el token para cambiar la contraseña
    reset_data = {"token": reset_token, "new_password": new_password, "username": username}
    response_reset = await client.post(
        f"{settings.API_V1_STR}/auth/password-recovery/confirm-reset",
        json=reset_data,
    )
    assert response_reset.status_code == status.HTTP_200_OK

    # 3. Verificamos que la nueva contraseña funciona
    login_data_new_pw = {"username": username, "password": new_password}
    
    # Aquí está la clave: capturamos y ejecutamos la tarea en segundo plano
    tasks = BackgroundTasks()
    response_login_new = await client.post(
        f"{settings.API_V1_STR}/auth/login/access-token", 
        data=login_data_new_pw,
    )
    assert response_login_new.status_code == status.HTTP_200_OK
    await asyncio.sleep(0.1)  # Damos un respiro para que la tarea se complete

    # 4. Verificamos que la contraseña antigua ya no funciona
    login_data_old_pw = {"username": username, "password": old_password}
    response_login_old = await client.post(
        f"{settings.API_V1_STR}/auth/login/access-token", data=login_data_old_pw
    )
    assert response_login_old.status_code == status.HTTP_401_UNAUTHORIZED

    # 5. Verificamos que el token de reseteo no se puede volver a usar
    response_reset_again = await client.post(
        f"{settings.API_V1_STR}/auth/password-recovery/confirm-reset", json=reset_data
    )
    assert response_reset_again.status_code == status.HTTP_400_BAD_REQUEST

async def test_request_password_recovery_for_nonexistent_user(
    client: AsyncClient, auth_token_admin: str
):
    """Prueba que solicitar un reseteo para un usuario que no existe falla con 404."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    response = await client.post(
        f"{settings.API_V1_STR}/auth/password-recovery/request-reset",
        headers=headers,
        json={"username": f"no_existe_{uuid4().hex[:6]}"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.parametrize(
    "token_type, expected_status, expected_detail",
    [
        ("malformed", status.HTTP_422_UNPROCESSABLE_ENTITY, "Input should be a valid UUID"),
        ("nonexistent", status.HTTP_400_BAD_REQUEST, "inválido"),
    ],
)
async def test_reset_password_with_invalid_tokens(
    client: AsyncClient, db: Session, test_rol_usuario_regular: Rol, token_type: str, expected_status: int, expected_detail: str
):
    """
    Prueba el reseteo de contraseña con tokens inválidos:
    1. Malformado (no UUID) -> 422
    2. Con formato UUID pero no existente -> 400
    """
    # Creamos un usuario para que la ruta no falle con 404 por "usuario no encontrado"
    unique_id = uuid4().hex[:6]
    username = f"test_invalid_token_user_{unique_id}"
    user_in = UsuarioCreate(
        nombre_usuario=username,
        email=f"test.invalid.{unique_id}@example.com",
        password="somepassword",
        rol_id=test_rol_usuario_regular.id,
    )
    usuario_service.create(db, obj_in=user_in)
    db.commit()

    token = "token-no-es-uuid" if token_type == "malformed" else str(uuid4())
    
    reset_data = {
        "token": token,
        "new_password": "any_password",
        "username": username,
    }

    response = await client.post(
        f"{settings.API_V1_STR}/auth/password-recovery/confirm-reset",
        json=reset_data,
    )

    assert response.status_code == expected_status
    response_text = response.text.lower()
    assert expected_detail.lower() in response_text
