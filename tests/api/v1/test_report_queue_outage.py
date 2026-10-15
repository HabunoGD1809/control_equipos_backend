from datetime import date
from uuid import UUID, uuid4

from celery import Celery
from kombu.exceptions import OperationalError
from sqlalchemy import select

from app.api.routes import reportes
from app.core.config import settings
from app.models.reporte import Reporte


def isolated_queue(monkeypatch):
    queue = 'report-test-' + uuid4().hex
    app = Celery(queue, broker='memory://', backend='redis://127.0.0.1:1/0', set_as_current=False)
    app.conf.task_default_queue = queue
    monkeypatch.setattr(reportes, 'celery_app', app)
    monkeypatch.setattr(settings, 'REPORT_EXECUTION_MODE', 'celery')

    def unexpected_subscription(*args, **kwargs):
        raise AssertionError('HTTP report publishing must not subscribe to result events.')

    monkeypatch.setattr(app.backend, 'on_task_call', unexpected_subscription)
    return app, queue


def payload():
    today = date.today().isoformat()
    return {'tipo_reporte': 'equipos', 'formato': 'pdf', 'fecha_inicio': today, 'fecha_fin': today}


async def test_report_can_publish_without_connecting_to_result_backend(client, db, auth_token_admin, monkeypatch):
    app, queue_name = isolated_queue(monkeypatch)
    try:
        response = await client.post(settings.API_V1_STR + '/reportes/', json=payload(), headers={'Authorization': 'Bearer ' + auth_token_admin})
        assert response.status_code == 200
        identifier = response.json()['reporte_id']
        assert db.get(Reporte, UUID(identifier)).estado == 'pendiente'
        with app.connection_for_read() as connection:
            queue = connection.SimpleQueue(queue_name)
            try:
                message = queue.get(block=False)
                assert message.headers['task'] == 'tasks.generate_report'
                assert message.payload[0][0] == identifier
                message.ack()
            finally:
                queue.close()
    finally:
        app.close()


async def test_broker_outage_returns_503_and_persists_report_error(client, db, auth_token_admin, monkeypatch):
    app, _ = isolated_queue(monkeypatch)

    def unavailable(*args, **kwargs):
        raise OperationalError('Isolated test broker is unavailable.')

    monkeypatch.setattr(app.amqp, 'send_task_message', unavailable)
    before = set(db.scalars(select(Reporte.id)))
    try:
        response = await client.post(settings.API_V1_STR + '/reportes/', json=payload(), headers={'Authorization': 'Bearer ' + auth_token_admin})
        assert response.status_code == 503
        report = db.scalar(select(Reporte).where(Reporte.id.not_in(before)))
        assert report.estado == 'error'
        assert response.json()['detail'] == report.error_msg
        assert 'no está disponible' in report.error_msg
    finally:
        app.close()
