from uuid import uuid4
import pytest
from sqlalchemy import select
from app.models import Permiso
from app.core.config import settings


def role_permissions(db, user, names):
    user.rol.permisos = list(db.scalars(select(Permiso).where(Permiso.nombre.in_(names))))
    db.flush()


@pytest.mark.parametrize('permission,expected', [('administrar_software_catalogo', 201), ('administrar_catalogos', 403)])
async def test_software_catalog_requires_its_own_permission(client, db, test_usuario_regular_fixture, auth_token_usuario_regular, permission, expected):
    role_permissions(db, test_usuario_regular_fixture, [permission, 'ver_licencias'])
    response = await client.post(settings.API_V1_STR + '/licencias/catalogo', headers={'Authorization': 'Bearer ' + auth_token_usuario_regular}, json={'nombre': 'Permisos software QA ' + uuid4().hex, 'tipo_licencia': 'Perpetua', 'metrica_licenciamiento': 'Por Dispositivo'})
    assert response.status_code == expected
    if expected == 201:
        identifier = response.json()['id']
        updated = await client.put(settings.API_V1_STR + '/licencias/catalogo/' + identifier, headers={'Authorization': 'Bearer ' + auth_token_usuario_regular}, json={'descripcion': 'Actualizado con permiso específico'})
        assert updated.status_code == 200
        deleted = await client.delete(settings.API_V1_STR + '/licencias/catalogo/' + identifier, headers={'Authorization': 'Bearer ' + auth_token_usuario_regular})
        assert deleted.status_code == 200


async def test_assigner_can_select_identities_without_user_admin(client, db, test_usuario_regular_fixture, auth_token_usuario_regular):
    role_permissions(db, test_usuario_regular_fixture, ['asignar_licencias', 'ver_licencias'])
    headers = {'Authorization': 'Bearer ' + auth_token_usuario_regular}
    response = await client.get(settings.API_V1_STR + '/licencias/destinatarios', headers=headers)
    assert response.status_code == 200
    assert any(row['id'] == str(test_usuario_regular_fixture.id) for row in response.json())
    assert all(set(row) == {'id', 'nombre_usuario'} for row in response.json())
    assert (await client.get(settings.API_V1_STR + '/usuarios/', headers=headers)).status_code == 403


async def test_license_reader_cannot_list_assignment_identities(client, db, test_usuario_regular_fixture, auth_token_usuario_regular):
    role_permissions(db, test_usuario_regular_fixture, ['ver_licencias'])
    response = await client.get(settings.API_V1_STR + '/licencias/destinatarios', headers={'Authorization': 'Bearer ' + auth_token_usuario_regular})
    assert response.status_code == 403
