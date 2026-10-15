import csv
import io
import json
from uuid import uuid4

import pytest
from sqlalchemy import select
from app.models import Equipo

pytestmark = pytest.mark.asyncio


async def upload(client, token, content):
    return await client.post('/api/v1/equipos/bulk-upload', headers={'Authorization': 'Bearer ' + token}, files={'file': ('INVENTARIO.CSV', content.encode('utf-8-sig'), 'text/csv')})


async def test_csv_bom_semicolon_imports_technical_data_and_preserves_valid_rows(client, auth_token_admin, test_estado_disponible, db):
    suffix = uuid4().hex[:10]
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(['nombre', 'numero_serie', 'tipo_activo', 'estado', 'tecnico.direccion_ip', 'tecnico.ram'])
    writer.writerow(['Servidor ' + suffix, 'Srv/CSV-' + suffix, 'Servidor', 'Disponible', '2001:db8::10', '64 GB'])
    writer.writerow(['Duplicado', 'Srv/CSV-' + suffix, 'Servidor', 'Disponible', '', ''])
    writer.writerow(['Red ' + suffix, 'Red/CSV-' + suffix, 'Red', 'Disponible', '192.0.2.10', ''])
    writer.writerow(['IP inválida', 'BAD-IP-' + suffix, 'Red', 'Disponible', '999.1.2.3', ''])
    writer.writerow(['Estado inválido', 'BAD-STATE-' + suffix, 'Red', 'Estado inexistente', '', ''])
    response = await upload(client, auth_token_admin, buffer.getvalue())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['total_procesados'] == 5 and result['insertados'] == 2
    assert len(result['errores']) == 3
    assert all(any(f'Fila {row}:' in error for error in result['errores']) for row in (3, 5, 6))
    records = list(db.scalars(select(Equipo).where(Equipo.numero_serie.in_(['Srv/CSV-' + suffix, 'Red/CSV-' + suffix]))))
    server = next(record for record in records if record.tipo_activo == 'Servidor')
    assert server.numero_serie == 'Srv/CSV-' + suffix
    assert server.especificaciones_tecnicas == {'direccion_ip': '2001:db8::10', 'ram': '64 GB'}
    assert len(records) == 2


@pytest.mark.parametrize('content', [
    'nombre,serie\nEquipo,ABC\n',
    'nombre,numero_serie,nombre\nEquipo,ABC,Otro\n',
    'nombre,numero_serie,empleado_asignado_id\nEquipo,ABC,123\n',
    'nombre,numero_serie\n',
    'nombre,numero_serie\n"Comillas sin cierre,ABC\n',
    'nombre,numero_serie\n' + 'Equipo,ABC\n' * 5001,
], ids=['missing-column', 'duplicate-column', 'custody-bypass', 'no-rows', 'broken-quotes', 'too-many-rows'])
async def test_csv_rejects_invalid_structure_without_importing(client, auth_token_admin, content, db):
    before = set(db.scalars(select(Equipo.id)))
    response = await upload(client, auth_token_admin, content)
    assert response.status_code == 400, response.text
    assert set(db.scalars(select(Equipo.id))) == before


async def test_csv_json_uses_normal_validation_and_reports_bad_cells(client, auth_token_admin, test_estado_disponible, db):
    suffix = uuid4().hex[:10]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['NOMBRE', 'NUMERO_SERIE', 'especificaciones_tecnicas', 'fecha_adquisicion', 'valor_adquisicion'])
    writer.writerow(['Ficha JSON', 'CSV-JSON-' + suffix, json.dumps({'Circuito eléctrico': 'UPS-A', 'rack': 'R2'}), '2026-10-01', '1500.50'])
    writer.writerow(['Credencial', 'CSV-PW-' + suffix, json.dumps({'contraseña': 'secret-test'}), '', ''])
    writer.writerow(['Valor inválido', 'CSV-COST-' + suffix, '{}', '', '-1'])
    writer.writerow(['Falta celda', 'CSV-SHORT-' + suffix])
    writer.writerow(['Sobran celdas', 'CSV-LONG-' + suffix, '{}', '', '', 'sobrante'])
    response = await upload(client, auth_token_admin, buffer.getvalue())
    assert response.status_code == 200, response.text
    assert response.json()['insertados'] == 1 and len(response.json()['errores']) == 4
    assert 'secret-test' not in response.text
    record = db.scalar(select(Equipo).where(Equipo.numero_serie == 'CSV-JSON-' + suffix))
    assert record.especificaciones_tecnicas['Circuito eléctrico'] == 'UPS-A'
    assert str(record.valor_adquisicion) == '1500.50'


async def test_csv_size_is_bounded_before_processing(client, auth_token_admin, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'MAX_FILE_SIZE_BYTES', 30)
    response = await upload(client, auth_token_admin, 'nombre,numero_serie\n' + 'Equipo,ABC\n' * 5)
    assert response.status_code == 413


async def test_negative_asset_cost_is_rejected_on_creation_and_update(client, auth_token_admin, test_estado_disponible):
    headers = {'Authorization': 'Bearer ' + auth_token_admin}
    payload = {'nombre': 'Costo validado', 'numero_serie': 'COST-' + uuid4().hex[:12], 'estado_id': str(test_estado_disponible.id), 'valor_adquisicion': -1}
    assert (await client.post('/api/v1/equipos/', headers=headers, json=payload)).status_code == 422
    response = await client.post('/api/v1/equipos/', headers=headers, json={**payload, 'valor_adquisicion': 100})
    assert response.status_code == 201
    assert (await client.put('/api/v1/equipos/' + response.json()['id'], headers=headers, json={'valor_adquisicion': -1})).status_code == 422
