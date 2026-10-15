"""Receipt identities, permissions, rollback and authenticated print documents."""
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.core.config import settings
from app.models import Empleado, Usuario, Rol, Permiso
from app.core.security import create_access_token
from tests.helpers import employee_id, location_id
from tests.api.v1.test_movimientos import equipo_para_movimiento

pytestmark = pytest.mark.asyncio


async def assignment(client, token, equipo, db):
    response = await client.post(settings.API_V1_STR + '/movimientos/', headers={'Authorization': f'Bearer {token}'}, json={
        'equipo_id': str(equipo.id), 'tipo_movimiento': 'Asignacion Interna',
        'ubicacion_destino_id': str(location_id(db, 'Destino recepción')),
        'empleado_destino_id': str(employee_id(db)), 'recibido_por': 'Nombre no confirmado',
    })
    assert response.status_code == 201, response.text
    assert response.json()['recibido_por'] is None
    return response.json()


async def test_receipt_closes_assignment_and_identifies_three_people(client, auth_token_admin, test_admin_fixture, equipo_para_movimiento, db):
    move = await assignment(client, auth_token_admin, equipo_para_movimiento, db)
    headers = {'Authorization': f'Bearer {auth_token_admin}'}
    endpoint = settings.API_V1_STR + '/movimientos/' + move['id']
    ignored_state = await client.put(endpoint, headers=headers, json={'estado': 'Completado'})
    assert ignored_state.status_code == 422
    assert (await client.get(endpoint, headers=headers)).json()['estado'] == 'En Proceso'
    receipt = await client.patch(endpoint + '/estado', headers=headers, json={'estado': 'Completado'})
    assert receipt.status_code == 200, receipt.text
    row = receipt.json()
    assert row['estado'] == 'Completado'
    assert row['recibido_por'] == 'Custodio de prueba'
    assert row['empleado_receptor_id'] == move['empleado_destino_id']
    assert row['confirmado_por_id'] == str(test_admin_fixture.id)
    assert row['fecha_recepcion'] and row['fecha_retorno'] is None
    from app.services.reporte import reporte_service
    exported = next(record for record in reporte_service.obtener_datos(db, 'movimientos', None, None) if record['Serie'] == equipo_para_movimiento.numero_serie)
    assert exported['Recibió'] == 'Custodio de prueba'
    assert exported['Registró acuse'] == test_admin_fixture.nombre_usuario and exported['Fecha de acuse']
    current = await client.get(settings.API_V1_STR + '/equipos/' + str(equipo_para_movimiento.id), headers=headers)
    assert current.json()['empleado_asignado_id'] == move['empleado_destino_id']
    overwrite = await client.put(endpoint, headers=headers, json={'recibido_por': 'Otro nombre'})
    assert overwrite.status_code == 409
    repeat = await client.patch(endpoint + '/estado', headers=headers, json={'estado': 'Completado'})
    assert repeat.status_code == 409


async def test_delegate_does_not_change_custodian(client, auth_token_admin, equipo_para_movimiento, db):
    move = await assignment(client, auth_token_admin, equipo_para_movimiento, db)
    delegate = Empleado(nombre_completo='Receptor delegado', is_active=True)
    db.add(delegate); db.flush()
    headers = {'Authorization': f'Bearer {auth_token_admin}'}
    receipt = await client.patch(settings.API_V1_STR + '/movimientos/' + move['id'] + '/estado', headers=headers, json={'estado': 'Completado', 'empleado_receptor_id': str(delegate.id)})
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()['recibido_por'] == delegate.nombre_completo
    current = await client.get(settings.API_V1_STR + '/equipos/' + str(equipo_para_movimiento.id), headers=headers)
    assert current.json()['empleado_asignado_id'] == move['empleado_destino_id']


async def test_receipt_rejection_restores_previous_location(client, auth_token_admin, equipo_para_movimiento, db):
    previous_location = equipo_para_movimiento.ubicacion_id
    previous_state = equipo_para_movimiento.estado_id
    move = await assignment(client, auth_token_admin, equipo_para_movimiento, db)
    headers = {'Authorization': f'Bearer {auth_token_admin}'}
    endpoint = settings.API_V1_STR + '/movimientos/' + move['id'] + '/estado'
    invalid = await client.patch(endpoint, headers=headers, json={'estado': 'Rechazado', 'observaciones': '    '})
    assert invalid.status_code == 422
    response = await client.patch(endpoint, headers=headers, json={'estado': 'Rechazado', 'observaciones': 'El equipo llegó con daños físicos.'})
    assert response.status_code == 200, response.text
    assert response.json()['fecha_recepcion'] and response.json()['recibido_por'] is None
    current = await client.get(settings.API_V1_STR + '/equipos/' + str(equipo_para_movimiento.id), headers=headers)
    assert current.json()['ubicacion_id'] == str(previous_location)
    assert current.json()['estado_id'] == str(previous_state)
    assert current.json()['empleado_asignado_id'] is None


async def test_internal_receipt_rejects_external_identity_and_inactive_employee(client, auth_token_admin, equipo_para_movimiento, db):
    move = await assignment(client, auth_token_admin, equipo_para_movimiento, db)
    headers = {'Authorization': f'Bearer {auth_token_admin}'}
    endpoint = settings.API_V1_STR + '/movimientos/' + move['id'] + '/estado'
    external = await client.patch(endpoint, headers=headers, json={'estado': 'Completado', 'recibido_por': 'Persona externa', 'entidad_receptora': 'Empresa'})
    assert external.status_code == 422
    inactive = Empleado(nombre_completo='Inactivo', is_active=False)
    db.add(inactive); db.flush()
    rejected = await client.patch(endpoint, headers=headers, json={'estado': 'Completado', 'empleado_receptor_id': str(inactive.id)})
    assert rejected.status_code == 422
    spoofed = await client.patch(endpoint, headers=headers, json={'estado': 'Completado', 'confirmado_por_id': str(uuid4())})
    assert spoofed.status_code == 422


async def test_external_receipt_records_person_and_entity(client, auth_token_admin, equipo_para_movimiento, db):
    headers = {'Authorization': f'Bearer {auth_token_admin}'}
    from datetime import datetime, timedelta, timezone
    response = await client.post(settings.API_V1_STR + '/movimientos/', headers=headers, json={'equipo_id': str(equipo_para_movimiento.id), 'tipo_movimiento': 'Salida Temporal', 'ubicacion_destino_id': str(location_id(db, 'Servicio externo')), 'fecha_prevista_retorno': (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()})
    assert response.status_code == 201, response.text
    endpoint = settings.API_V1_STR + '/movimientos/' + response.json()['id'] + '/estado'
    missing = await client.patch(endpoint, headers=headers, json={'estado': 'Completado', 'recibido_por': 'Técnico externo'})
    assert missing.status_code == 422
    complete = await client.patch(endpoint, headers=headers, json={'estado': 'Completado', 'recibido_por': 'Técnico externo', 'entidad_receptora': 'Servicio autorizado'})
    assert complete.status_code == 200, complete.text
    assert complete.json()['entidad_receptora'] == 'Servicio autorizado'
    assert complete.json()['empleado_receptor_id'] is None


async def test_custodian_can_receive_without_manage_permission_but_not_impersonate(client, auth_token_admin, auth_token_usuario_regular, test_usuario_regular_fixture, equipo_para_movimiento, db):
    move = await assignment(client, auth_token_admin, equipo_para_movimiento, db)
    headers = {'Authorization': f'Bearer {auth_token_usuario_regular}'}
    endpoint = settings.API_V1_STR + '/movimientos/' + move['id'] + '/estado'
    forbidden = await client.patch(endpoint, headers=headers, json={'estado': 'Completado'})
    assert forbidden.status_code == 403
    test_usuario_regular_fixture.empleado_id = employee_id(db)
    other = Empleado(nombre_completo='Otro empleado', is_active=True)
    db.add(other); db.commit()
    impersonation = await client.patch(endpoint, headers=headers, json={'estado': 'Completado', 'empleado_receptor_id': str(other.id)})
    assert impersonation.status_code == 403
    success = await client.patch(endpoint, headers=headers, json={'estado': 'Completado'})
    assert success.status_code == 200, success.text
    assert success.json()['confirmado_por_id'] == str(test_usuario_regular_fixture.id)


async def test_print_documents_require_session_and_module_permission(client, auth_token_admin, equipo_para_movimiento, db):
    move = await assignment(client, auth_token_admin, equipo_para_movimiento, db)
    role = Rol(nombre='Sin permisos ' + uuid4().hex)
    user = Usuario(nombre_usuario='no-print-' + uuid4().hex, email=uuid4().hex+'@example.com', hashed_password='unused-test-hash', rol=role, bloqueado=False, requiere_cambio_contrasena=False)
    db.add(user); db.flush()
    token = create_access_token(subject=user.id, session_version=user.session_version)
    for path in [f'/equipos/{equipo_para_movimiento.id}/ficha', f'/movimientos/{move["id"]}/acuse']:
        anonymous = await client.get(settings.API_V1_STR + path)
        assert anonymous.status_code == 401
        forbidden = await client.get(settings.API_V1_STR + path, headers={'Authorization': f'Bearer {token}'})
        assert forbidden.status_code == 403
        printed = await client.get(settings.API_V1_STR + path, headers={'Authorization': f'Bearer {auth_token_admin}'})
        assert printed.status_code == 200, printed.text
        assert printed.headers['content-type'] == 'application/pdf'
        assert printed.content.startswith(b'%PDF')
        assert 'no-store' in printed.headers['cache-control']


async def test_equipment_history_respects_module_permissions_and_keeps_time_zone(client, auth_token_admin, equipo_para_movimiento, test_documento_pendiente, db):
    await assignment(client, auth_token_admin, equipo_para_movimiento, db)
    test_documento_pendiente.equipo_id = equipo_para_movimiento.id
    role = Rol(nombre='Solo activos ' + uuid4().hex, permisos=[db.scalar(select(Permiso).where(Permiso.nombre == 'ver_equipos'))])
    user = Usuario(nombre_usuario='history-' + uuid4().hex, email=uuid4().hex+'@example.com', hashed_password='unused-test-hash', rol=role, bloqueado=False, requiere_cambio_contrasena=False)
    db.add(user); db.commit()
    token = create_access_token(subject=user.id, session_version=user.session_version)
    path = settings.API_V1_STR + f'/equipos/{equipo_para_movimiento.id}/timeline'
    admin = await client.get(path, headers={'Authorization': f'Bearer {auth_token_admin}'})
    assert admin.status_code == 200, admin.text
    assert any(event['modulo'] == 'Movimientos' for event in admin.json())
    assert any(event['modulo'] == 'Documentacion' for event in admin.json())
    reader = await client.get(path, headers={'Authorization': f'Bearer {token}'})
    assert reader.status_code == 200, reader.text
    assert reader.json() and all(event['modulo'] == 'Equipos' for event in reader.json())
    assert all(event['fecha'].endswith('+00:00') for event in reader.json())
