from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.models import EstadoEquipo, Rol, Permiso, TipoDocumento, TipoMantenimiento, Movimiento, Notificacion
from app.db.seed import seed_system_catalogs
from app.tasks.notification_tasks import task_check_overdue_loans
from app.tasks.maintenance_tasks import task_refresh_materialized_views, task_manage_audit_log_partitions
from unittest.mock import Mock
from tests.helpers import location_id, employee_id
from tests.api.v1.test_movimientos import equipo_para_movimiento

pytestmark = pytest.mark.asyncio


async def test_renaming_operational_states_preserves_assignment_and_csv_default(client, db, auth_token_admin, test_estado_disponible, test_estado_en_uso):
    headers = {'Authorization': 'Bearer ' + auth_token_admin}
    origin = location_id(db, 'Origen de prueba códigos')
    destination = location_id(db, 'Destino de prueba códigos')
    for state, label in [(test_estado_disponible, 'Listo para entregar'), (test_estado_en_uso, 'Bajo custodia')]:
        response = await client.put(f'/api/v1/catalogos/estados-equipo/{state.id}', headers=headers, json={'nombre': label})
        assert response.status_code == 200
        assert response.json()['codigo'] == state.codigo
    asset = await client.post('/api/v1/equipos/', headers=headers, json={'nombre': 'Servidor con catálogo personalizado', 'numero_serie': uuid4().hex, 'estado_id': str(test_estado_disponible.id), 'ubicacion_id': str(origin)})
    assert asset.status_code == 201
    move = await client.post('/api/v1/movimientos/', headers=headers, json={'equipo_id': asset.json()['id'], 'tipo_movimiento': 'Asignacion Interna', 'ubicacion_origen_id': str(origin), 'ubicacion_destino_id': str(destination), 'empleado_destino_id': str(employee_id(db)), 'proposito': 'Entrega con nombres personalizados'})
    assert move.status_code == 201, move.text
    current = await client.get('/api/v1/equipos/' + asset.json()['id'], headers=headers)
    assert current.json()['estado']['nombre'] == 'Bajo custodia'
    assert current.json()['estado']['codigo'] == 'en_uso'
    assert current.json()['estado']['permite_movimientos'] is True
    csv = f'nombre,numero_serie\nEquipo importado,{uuid4().hex}\n'.encode()
    response = await client.post('/api/v1/equipos/bulk-upload', headers=headers, files={'file': ('equipos.csv', csv, 'text/csv')})
    assert response.status_code == 200, response.text
    assert response.json()['insertados'] == 1


async def test_seed_preserves_state_names_and_other_catalog_customizations(db, test_estado_disponible):
    counts = lambda: [db.scalar(select(func.count(model.id))) for model in [EstadoEquipo, Rol, Permiso, TipoDocumento, TipoMantenimiento]]
    before = counts()
    test_estado_disponible.nombre = 'Disponible personalizado'
    doc = db.scalar(select(TipoDocumento).limit(1)); doc.nombre = 'Expediente institucional'
    maintenance = db.scalar(select(TipoMantenimiento).limit(1)); maintenance.nombre = 'Revisión institucional'
    db.flush()
    seed_system_catalogs(db); db.flush()
    seed_system_catalogs(db); db.flush()
    assert counts() == before
    assert test_estado_disponible.nombre == 'Disponible personalizado'
    assert doc.nombre == 'Expediente institucional' and maintenance.nombre == 'Revisión institucional'


@pytest.mark.parametrize('body', [{'codigo': 'disponible', 'nombre': 'Estado inventado'}, {'nombre': 'Nuevo', 'campo_ajeno': True}])
async def test_operational_code_cannot_be_injected(client, auth_token_admin, body):
    headers = {'Authorization': 'Bearer ' + auth_token_admin}
    assert (await client.post('/api/v1/catalogos/estados-equipo/', headers=headers, json=body)).status_code == 422


async def test_operational_code_cannot_be_changed(client, auth_token_admin, test_estado_disponible):
    response = await client.put(f'/api/v1/catalogos/estados-equipo/{test_estado_disponible.id}', headers={'Authorization': 'Bearer ' + auth_token_admin}, json={'codigo': 'otro'})
    assert response.status_code == 422


class TaskSession:
    def __init__(self, db): self.db = db
    def __getattr__(self, name): return getattr(self.db, name)
    def close(self): pass


async def test_overdue_loans_alert_active_admin_despite_previous_info_and_do_not_repeat(db, monkeypatch, test_admin_fixture, test_estado_disponible, equipo_para_movimiento):
    identifier = test_admin_fixture.id
    move = Movimiento(equipo_id=equipo_para_movimiento.id, usuario_id=identifier, tipo_movimiento='Salida Temporal', estado='Completado', fecha_prevista_retorno=datetime.now(timezone.utc) - timedelta(days=2), proposito='Préstamo vencido de prueba')
    db.add(move); db.flush()
    db.add(Notificacion(usuario_id=identifier, referencia_id=move.id, referencia_tabla='movimientos', tipo='info', mensaje='Movimiento registrado'))
    db.flush()
    monkeypatch.setattr('app.tasks.notification_tasks.SessionLocal', lambda: TaskSession(db))
    task_check_overdue_loans.run()
    alerts = lambda: list(db.scalars(select(Notificacion).where(Notificacion.usuario_id == identifier, Notificacion.referencia_id == move.id, Notificacion.tipo == 'alerta', Notificacion.urgencia == 2)))
    assert len(alerts()) == 1 and 'retraso' in alerts()[0].mensaje
    task_check_overdue_loans.run()
    assert len(alerts()) == 1


@pytest.mark.parametrize('task', [task_refresh_materialized_views, task_manage_audit_log_partitions])
async def test_worker_failures_are_reported_as_failures_instead_of_success_text(monkeypatch, task):
    session = Mock()
    session.execute.side_effect = RuntimeError('Database unavailable')
    monkeypatch.setattr('app.tasks.maintenance_tasks.SessionLocal', lambda: session)
    with pytest.raises(RuntimeError): task.run()
    session.rollback.assert_called_once()
    session.close.assert_called_once()
