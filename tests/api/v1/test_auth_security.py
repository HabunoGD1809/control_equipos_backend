"""Password onboarding and session revocation use the real HTTP contracts."""
import pytest
from app.core.config import settings
pytestmark = pytest.mark.asyncio

async def test_profile_contains_permissions_for_non_admin_navigation(client, auth_token_supervisor):
    response = await client.get('/api/v1/usuarios/me', headers={'Authorization': 'Bearer '+auth_token_supervisor})
    assert response.status_code == 200
    profile = response.json()
    assert profile['rol']['nombre'] == 'supervisor'
    assert 'ver_equipos' in {permission['nombre'] for permission in profile['rol']['permisos']}
    assert 'hashed_password' not in profile
    assert 'token_temporal' not in profile

async def test_forced_change_blocks_operations_and_revokes_tokens(client, db, test_usuario_regular_fixture):
    user = test_usuario_regular_fixture
    user.requiere_cambio_contrasena = True
    db.commit()
    old_password = settings.TEST_USER_REGULAR_PASSWORD
    response = await client.post('/api/v1/auth/login/access-token', data={'username': user.nombre_usuario, 'password': old_password})
    assert response.status_code == 200
    old = response.json()
    headers = {'Authorization': 'Bearer '+old['access_token']}
    assert (await client.get('/api/v1/usuarios/me', headers=headers)).status_code == 200
    assert (await client.get('/api/v1/notificaciones/', headers=headers)).status_code == 403
    changed = await client.post('/api/v1/auth/change-password', json={'current_password': old_password, 'new_password': 'NuevaClave2026!'}, headers=headers)
    assert changed.status_code == 204, changed.text
    assert (await client.get('/api/v1/usuarios/me', headers=headers)).status_code == 401
    assert (await client.post('/api/v1/auth/refresh-token', json={'refresh_token': old['refresh_token']})).status_code == 403
    login = await client.post('/api/v1/auth/login/access-token', data={'username': user.nombre_usuario, 'password': 'NuevaClave2026!'})
    assert login.status_code == 200
    current = {'Authorization': 'Bearer '+login.json()['access_token']}
    assert (await client.get('/api/v1/notificaciones/', headers=current)).status_code == 200
