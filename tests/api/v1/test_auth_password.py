import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session
from uuid import uuid4
from typing import AsyncGenerator
import asyncio # <--- 1. Importar asyncio

from app.core.config import settings
from app.models.usuario import Usuario
from app.models.rol import Rol
from app.schemas.usuario import UsuarioCreate

# Marca todos los tests en este archivo para que se ejecuten de forma asíncrona
pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="function")
async def temp_user_for_password_reset(db: Session, test_rol_usuario_regular: Rol) -> AsyncGenerator[Usuario, None]:
    """
    Crea un usuario temporal, lo guarda en la BD, y lo limpia después.
    """
    from app.services.usuario import usuario_service

    # Usamos valores únicos para evitar colisiones entre ejecuciones de tests
    unique_id = uuid4().hex[:6]
    email = f"test.reset.{unique_id}@example.com"
    username = f"test_reset_user_{unique_id}"
    password = "SecurePassword123!"

    # Creamos el usuario usando el servicio para asegurar consistencia
    user_in = UsuarioCreate(
        nombre_usuario=username,
        email=email,
        password=password,
        rol_id=test_rol_usuario_regular.id # Usamos el ID del rol de la fixture
    )
    db_user = usuario_service.create(db, obj_in=user_in)
    
    db.commit()
    db.refresh(db_user)

    yield db_user # El test se ejecuta con este usuario ya persistido y completo.
    
    # 2. Pequeña pausa para dar tiempo a las tareas de fondo a ejecutarse
    #    antes de que borremos los datos de los que dependen.
    await asyncio.sleep(0.1)

    # 3. Limpieza robusta
    try:
        # Re-adjuntamos el objeto a la sesión actual antes de borrarlo
        local_user = db.merge(db_user)
        db.delete(local_user)
        db.commit()
    except Exception:
        # Si hay un error (ej. el objeto ya no existe), hacemos rollback
        # para asegurar que la sesión quede limpia y no falle el test.
        db.rollback()

@pytest.mark.asyncio
async def test_password_recovery_flow(
    client: AsyncClient,
    temp_user_for_password_reset: Usuario,
    auth_token_admin: str, # Fixture para obtener un token de admin
):
    """
    Prueba el flujo completo de recuperación de contraseña:
    1. Admin solicita el reseteo para un usuario.
    2. Se usa el token generado para establecer una nueva contraseña.
    3. Se verifica que la nueva contraseña funciona para iniciar sesión.
    4. Se verifica que la contraseña antigua ya NO funciona.
    5. Se verifica que el token de reseteo no se puede usar dos veces.
    """
    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}
    user_to_reset = temp_user_for_password_reset

    # 1. Admin solicita un token de reseteo para el usuario
    request_data = {"username": user_to_reset.nombre_usuario}
    response_request = await client.post(
        f"{settings.API_V1_STR}/auth/password-recovery/request-reset",
        headers=admin_headers,
        json=request_data
    )
    # Verificamos que la solicitud fue exitosa y obtenemos el token
    assert response_request.status_code == 200, response_request.text
    response_data = response_request.json()
    assert "reset_token" in response_data
    reset_token = response_data["reset_token"]

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


@pytest.mark.asyncio
async def test_request_password_recovery_for_nonexistent_user(client: AsyncClient, auth_token_admin: str):
    """
    Prueba que solicitar un reseteo para un usuario que no existe falla.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    non_existent_username = "usuario_que_no_existe_jamás"
    request_data = {"username": non_existent_username}
    response = await client.post(
        f"{settings.API_V1_STR}/auth/password-recovery/request-reset",
        headers=headers, 
        json=request_data
    )
    # El endpoint, tal como está implementado, devuelve 404 si el usuario no existe.
    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_reset_password_with_invalid_token(
    client: AsyncClient, 
    temp_user_for_password_reset: Usuario # <-- Añade esta fixture
):
    """
    Prueba que no se puede restablecer la contraseña con un token inválido.
    """
    # Generamos un token UUID aleatorio que sabemos que no es válido
    invalid_token = str(uuid4())
    
    # Usamos el username del usuario temporal que SÍ existe
    reset_data = {
        "token": invalid_token, 
        "new_password": "somepassword", 
        "username": temp_user_for_password_reset.nombre_usuario
    }
    
    response = await client.post(
        f"{settings.API_V1_STR}/auth/password-recovery/confirm-reset",
        json=reset_data
    )
    
    # Ahora la API encontrará al usuario, validará el token (que es inválido)
    # y devolverá correctamente el error 400.
    assert response.status_code == 400, response.text
    assert "inválido" in response.json()["detail"].lower()
