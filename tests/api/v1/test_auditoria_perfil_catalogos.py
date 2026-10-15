import io
from uuid import uuid4
import pytest
from PIL import Image
from sqlalchemy import select
from app.models import AuditLog, Equipo, LicenciaSoftware, SoftwareCatalogo, Usuario, Rol, Permiso

pytestmark = pytest.mark.asyncio

async def test_audit_actor_filter_pk_and_pagination(client, db, auth_token_admin, test_admin_fixture, test_estado_disponible):
    headers = {'Authorization': 'Bearer ' + auth_token_admin}
    asset = await client.post('/api/v1/equipos/', headers=headers, json={'nombre': 'Auditoría de equipo', 'numero_serie': 'AUD-' + uuid4().hex[:10], 'estado_id': str(test_estado_disponible.id)})
    assert asset.status_code == 201
    response = await client.get('/api/v1/auditoria/', headers=headers, params={'table_name': 'equipos', 'username': test_admin_fixture.nombre_usuario, 'record_pk_value': asset.json()['id']})
    assert response.status_code == 200
    assert response.json() and all(log['app_username'] == test_admin_fixture.nombre_usuario for log in response.json())
    assert any(log['new_data']['id'] == asset.json()['id'] for log in response.json())
    assert (await client.get('/api/v1/auditoria/', headers=headers, params={'username': 'missing_' + uuid4().hex})).json() == []
    from app.services.reporte import reporte_service
    exported = reporte_service.obtener_datos(db, 'auditoria', None, None)
    assert any(row['Tabla'] == 'equipos' and row['Usuario'] == test_admin_fixture.nombre_usuario for row in exported)

async def test_avatar_requires_active_session_and_has_no_public_static_route(client, auth_token_admin):
    buffer = io.BytesIO()
    Image.new('RGB', (32, 32), (25, 65, 95)).save(buffer, 'PNG')
    response = await client.post('/api/v1/usuarios/me/avatar', headers={'Authorization': 'Bearer ' + auth_token_admin}, files={'file': ('foto.png', buffer.getvalue(), 'image/png')})
    assert response.status_code == 200, response.text
    filename = response.json()['avatar_url'].split('?')[0].rsplit('/', 1)[1]
    assert (await client.get('/api/v1/usuarios/avatar/' + filename)).status_code == 401
    assert (await client.get('/static/uploads/avatars/' + filename)).status_code == 404
    private = await client.get('/api/v1/usuarios/avatar/' + filename, headers={'Authorization': 'Bearer ' + auth_token_admin})
    assert private.status_code == 200 and private.headers['cache-control'] == 'private, no-store'
    assert private.headers['content-type'].startswith('image/')

@pytest.mark.parametrize('change', [{'permite_movimientos': False}, {'es_estado_final': True}])
async def test_system_states_cannot_break_business_flows(client, auth_token_admin, test_estado_disponible, change):
    response = await client.put(f'/api/v1/catalogos/estados-equipo/{test_estado_disponible.id}', headers={'Authorization': 'Bearer ' + auth_token_admin}, json=change)
    assert response.status_code == 409

async def test_system_state_cannot_be_deleted_but_description_can_change(client, auth_token_admin, test_estado_disponible):
    headers = {'Authorization': 'Bearer ' + auth_token_admin}
    assert (await client.delete(f'/api/v1/catalogos/estados-equipo/{test_estado_disponible.id}', headers=headers)).status_code == 409
    assert (await client.put(f'/api/v1/catalogos/estados-equipo/{test_estado_disponible.id}', headers=headers, json={'descripcion': 'Descripción válida'})).status_code == 200

async def test_document_type_normalizes_formats_and_refuses_executables(client, auth_token_admin):
    headers = {'Authorization': 'Bearer ' + auth_token_admin}
    payload = {'nombre': 'Expediente ' + uuid4().hex[:8], 'requiere_verificacion': True, 'formato_permitido': [' PDF ', '.png', 'pdf']}
    response = await client.post('/api/v1/catalogos/tipos-documento/', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    assert response.json()['formato_permitido'] == ['pdf', 'png']
    assert (await client.put('/api/v1/catalogos/tipos-documento/' + response.json()['id'], headers=headers, json={'formato_permitido': ['exe']})).status_code == 422

async def test_inventory_invalid_category_is_validation_error(client, auth_token_admin):
    response = await client.post('/api/v1/inventario/tipos/', headers={'Authorization': 'Bearer ' + auth_token_admin}, json={'nombre': 'Inválido ' + uuid4().hex[:6], 'categoria': 'Parte', 'unidad_medida': 'Unidad'})
    assert response.status_code == 422

async def test_nested_license_schemas_exclude_activation_keys():
    from app.schemas.licencia_software import LicenciaSoftwareSimple
    assert 'clave_producto' not in LicenciaSoftwareSimple(id=uuid4(), clave_producto='PRIVATE-ACTIVATION-KEY').model_dump()
