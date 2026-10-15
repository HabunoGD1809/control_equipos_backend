from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.security import create_access_token


@pytest.mark.parametrize('endpoint', ['/usuarios/me', '/equipos/'])
async def test_signed_token_without_existing_user_is_unauthorized(client, endpoint):
    token = create_access_token(subject=uuid4())
    response = await client.get(settings.API_V1_STR + endpoint, headers={'Authorization': 'Bearer ' + token})
    assert response.status_code == 401
    assert response.headers['WWW-Authenticate'] == 'Bearer'
    assert response.json()['detail'] == 'No se pudieron validar las credenciales'
