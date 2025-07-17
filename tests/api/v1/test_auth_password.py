import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session
from uuid import uuid4

from app.core.config import settings
from app.models.usuario import Usuario
from app.models.rol import Rol
from app.schemas.usuario import UsuarioCreate
from app.services.usuario import usuario_service

pytestmark = pytest.mark.asyncio

# La fixture `temp_user_for_password_reset` se elimina de este archivo,
# ya que gestionaremos el ciclo de vida del usuario manualmente en cada test que lo necesite.

@pytest.mark.asyncio
async def test_password_recovery_flow(
    client: AsyncClient,
    db: Session,
    test_rol_usuario_regular: Rol,
    auth_token_admin: str,
):
    """
    Prueba el flujo completo de recuperación de contraseña, manejando la creación
    y limpieza del usuario de forma explícita para evitar condiciones de carrera.
    """
    unique_id = uuid4().hex[:6]
    user_in = UsuarioCreate(
        nombre_usuario=f"test_reset_user_{unique_id}",
        email=f"test.reset.{unique_id}@example.com",
        password="SecurePassword123!",
        rol_id=test_rol_usuario_regular.id
    )
    user_to_reset = usuario_service.create(db, obj_in=user_in)
    db.commit()
    db.refresh(user_to_reset)
    # Guardamos el ID para poder buscarlo de nuevo en el bloque de limpieza.
    user_id_to_delete = user_to_reset.id

    try:
        admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}

        # 1. Admin solicita un token de reseteo para el usuario
        response_request = await client.post(
            f"{settings.API_V1_STR}/auth/password-recovery/request-reset",
            headers=admin_headers,
            json={"username": user_to_reset.nombre_usuario}
        )
        assert response_request.status_code == 200, response_request.text
        reset_token = response_request.json()["reset_token"]

        # 2. El usuario usa el token para establecer una nueva contraseña
        new_password = "MyNewSecurePassword123!"
        reset_data = {"token": reset_token, "new_password": new_password, "username": user_to_reset.nombre_usuario}
        response_reset = await client.post(
            f"{settings.API_V1_STR}/auth/password-recovery/confirm-reset",
            json=reset_data
        )
        assert response_reset.status_code == 200, response_reset.text
        assert response_reset.json() == {"msg": "La contraseña ha sido actualizada exitosamente."}

        # 3. Verificamos que la nueva contraseña funciona para el login
        login_data = {"username": user_to_reset.nombre_usuario, "password": new_password}
        response_login = await client.post(f"{settings.API_V1_STR}/auth/login/access-token", data=login_data)
        assert response_login.status_code == 200, response_login.text
        
        # 4. Verificamos que la contraseña antigua ya NO funciona
        login_data_old_pw = {"username": user_to_reset.nombre_usuario, "password": "SecurePassword123!"}
        response_login_old = await client.post(f"{settings.API_V1_STR}/auth/login/access-token", data=login_data_old_pw)
        assert response_login_old.status_code == 401, "La contraseña antigua no debería funcionar"

        # 5. Verificamos que el token de reseteo ya no es válido
        response_reset_again = await client.post(
            f"{settings.API_V1_STR}/auth/password-recovery/confirm-reset", 
            json=reset_data
        )
        assert response_reset_again.status_code == 400
        assert "inválido" in response_reset_again.json()["detail"].lower()
    
    finally:
        user_to_delete = db.query(Usuario).filter(Usuario.id == user_id_to_delete).first()
        if user_to_delete:
            db.delete(user_to_delete)
            db.commit()


@pytest.mark.asyncio
async def test_request_password_recovery_for_nonexistent_user(client: AsyncClient, auth_token_admin: str):
    """
    Prueba que solicitar un reseteo para un usuario que no existe falla.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    request_data = {"username": "usuario_que_no_existe_jamás"}
    response = await client.post(
        f"{settings.API_V1_STR}/auth/password-recovery/request-reset",
        headers=headers, 
        json=request_data
    )
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_reset_password_with_invalid_token(
    client: AsyncClient, 
    db: Session,
    test_rol_usuario_regular: Rol
):
    """
    Prueba que no se puede restablecer la contraseña con un token inválido.
    """
    unique_id = uuid4().hex[:6]
    user_in = UsuarioCreate(
        nombre_usuario=f"test_invalid_token_{unique_id}",
        email=f"test.invalid.token.{unique_id}@example.com",
        password="somepassword",
        rol_id=test_rol_usuario_regular.id
    )
    temp_user = usuario_service.create(db, obj_in=user_in)
    db.commit()
    db.refresh(temp_user)
    temp_user_id = temp_user.id

    try:
        invalid_token = str(uuid4())
        reset_data = {
            "token": invalid_token, 
            "new_password": "somepassword", 
            "username": temp_user.nombre_usuario
        }
        
        response = await client.post(
            f"{settings.API_V1_STR}/auth/password-recovery/confirm-reset",
            json=reset_data
        )
        
        assert response.status_code == 400, response.text
        assert "inválido" in response.json()["detail"].lower()
    finally:
        user_to_delete = db.query(Usuario).filter(Usuario.id == temp_user_id).first()
        if user_to_delete:
            db.delete(user_to_delete)
            db.commit()
