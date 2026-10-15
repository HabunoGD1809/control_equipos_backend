"""Exercise real Compose services. Only the generated isolated database is accepted."""
import argparse
from datetime import date
import io
import json
import os
from pathlib import Path
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.config import settings
from app.db.session import SessionLocal
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

assert settings.POSTGRES_DB == 'control_equipos_docker_test'
assert make_url(str(settings.DATABASE_URI)).database == settings.POSTGRES_DB
with SessionLocal() as db:
    assert db.scalar(text('SELECT current_database()')) == settings.POSTGRES_DB
assert settings.AWS_ENDPOINT_URL == 'http://minio:9000'
assert settings.SMTP_HOST == 'mailpit'
BASE = 'http://127.0.0.1:8000/api/v1'
RESULT = ROOT / 'backups/docker-verification.json'
STATE = ROOT / 'backups/docker-test-private.json'
report = json.loads(RESULT.read_text()) if RESULT.exists() else {'database': settings.POSTGRES_DB, 'checks': []}
state = json.loads(STATE.read_text()) if STATE.exists() else {}


def record(name):
    if name not in report['checks']: report['checks'].append(name)
    RESULT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('OK:', name, flush=True)


def call(method, path, payload=None, expected=200, headers=None, base=BASE):
    body = json.dumps(payload).encode() if payload is not None else None
    request_headers = {'Content-Type': 'application/json', **(headers or {})}
    if state.get('access'): request_headers.setdefault('Authorization', 'Bearer ' + state['access'])
    request = urllib.request.Request(base + path, data=body, method=method, headers=request_headers)
    try:
        response = urllib.request.urlopen(request, timeout=40)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        content = response.read()
        assert response.status == expected, f'{method} {path}: status {response.status}, expected {expected}'
        return json.loads(content) if content and 'json' in response.headers.get('Content-Type', '') else content


def login():
    body = urllib.parse.urlencode({'username': 'admin', 'password': state.get('password', settings.SUPERUSER_PASSWORD)}).encode()
    with urllib.request.urlopen(urllib.request.Request(BASE + '/auth/login/access-token', data=body), timeout=20) as response:
        state['access'] = json.load(response)['access_token']
    me = call('GET', '/usuarios/me')
    if me['requiere_cambio_contrasena']:
        password = 'Qa!2' + secrets.token_hex(24)
        call('POST', '/auth/change-password', {'current_password': settings.SUPERUSER_PASSWORD, 'new_password': password}, 204)
        state['password'] = password
        save_state(); login()
    state['user_id'] = me['id']; save_state()


def save_state():
    STATE.write_text(json.dumps(state), encoding='utf-8'); STATE.chmod(0o600)


def request_report(module='equipos', format_='pdf', expected=200):
    today = date.today().isoformat()
    return call('POST', '/reportes/', {'tipo_reporte': module, 'formato': format_, 'fecha_inicio': today, 'fecha_fin': today}, expected)


def wait_report(report_id):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        rows = call('GET', '/reportes/historial?limit=100')
        row = next((item for item in rows if item['id'] == report_id), None)
        assert not row or row['estado'] != 'error', 'Worker marcó el reporte como error.'
        if row and row['estado'] == 'completado':
            return call('GET', f'/reportes/{report_id}/download')
        time.sleep(1)
    raise AssertionError('El trabajador no completó el reporte en 120 segundos.')


def full():
    from app.worker import celery_app
    from app.core.storage import get_s3_client
    from PIL import Image
    import redis
    client = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=3, socket_timeout=3)
    assert client.ping()
    assert celery_app.control.ping(timeout=10), 'No hay trabajador Celery disponible.'
    record('Redis autenticado y trabajador Celery real')
    login(); record('Primer acceso, cambio obligatorio y autenticación')
    for path in ['/equipos/', '/inventario/stock/', '/movimientos/', '/mantenimientos/', '/reservas/', '/documentacion/', '/licencias/', '/auditoria/', '/catalogos/tipos-documento/']:
        call('GET', path)
    available = next(row for row in call('GET', '/catalogos/estados-equipo/') if row['codigo'] == 'disponible')
    equipment = call('POST', '/equipos/', {'nombre': 'Servidor Docker QA', 'numero_serie': 'DOCKER-' + secrets.token_hex(6), 'estado_id': available['id'], 'tipo_activo': 'Servidor', 'especificaciones_tecnicas': {}}, 201)
    assert call('GET', '/equipos/' + equipment['id'] + '/ficha').startswith(b'%PDF-')
    record('Listados, alta de equipo y ficha PDF en contenedores')
    origin = call('POST', '/ubicaciones/', {'nombre': 'Almacén Docker QA'}, 201)
    destination = call('POST', '/ubicaciones/', {'nombre': 'Oficina Docker QA'}, 201)
    item = call('POST', '/inventario/tipos/', {'nombre': 'Tóner Docker QA', 'categoria': 'Consumible', 'unidad_medida': 'Unidad', 'color': 'Cian', 'tecnologia': 'Tóner'}, 201)
    call('POST', '/inventario/movimientos/', {'tipo_item_id': item['id'], 'tipo_movimiento': 'Entrada Compra', 'cantidad': 10, 'ubicacion_destino_id': origin['id']}, 201)
    call('POST', '/inventario/movimientos/', {'tipo_item_id': item['id'], 'tipo_movimiento': 'Salida Uso', 'cantidad': 3, 'ubicacion_origen_id': origin['id']}, 201)
    call('POST', '/inventario/movimientos/', {'tipo_item_id': item['id'], 'tipo_movimiento': 'Transferencia Salida', 'cantidad': 2, 'ubicacion_origen_id': origin['id'], 'ubicacion_destino_id': destination['id']}, 201)
    call('POST', '/inventario/movimientos/', {'tipo_item_id': item['id'], 'tipo_movimiento': 'Salida Uso', 'cantidad': 6, 'ubicacion_origen_id': origin['id']}, 409)
    stock = call('GET', '/inventario/stock/?tipo_item_id=' + item['id'])
    assert sum(row['cantidad_actual'] for row in stock) == 7
    record('Stock real: entrada, consumo, traslado y rechazo de sobregiro')
    for module in ['equipos', 'movimientos', 'inventario', 'kardex', 'licencias', 'mantenimientos', 'auditoria']:
        for format_ in ['pdf', 'excel', 'csv']:
            last_report = request_report(module, format_)['reporte_id']
            output = wait_report(last_report)
            assert len(output) > 10
            if format_ == 'pdf': assert output.startswith(b'%PDF-')
            if format_ == 'excel': assert output.startswith(b'PK')
    record('21 reportes por Redis y Celery: PDF, Excel y CSV')
    from app.models import Notificacion
    baseline = call('GET', '/notificaciones/count/unread')['unread_count']
    request = urllib.request.Request(BASE + '/notificaciones/stream', headers={'Authorization': 'Bearer ' + state['access']})
    with urllib.request.urlopen(request, timeout=10) as stream:
        while not stream.readline().startswith(b'data:'): pass
        started = time.monotonic()
        with SessionLocal() as db:
            db.add(Notificacion(usuario_id=state['user_id'], mensaje='Notificación entre procesos Docker QA', tipo='info', urgencia=0)); db.commit()
        while True:
            line = stream.readline()
            if line.startswith(b'data:') and int(line.split(b':', 1)[1]) >= baseline + 1: break
        assert time.monotonic() - started < 5
    record('SSE recibe un cambio de otra conexión sin recargar en menos de cinco segundos')
    with SessionLocal() as db:
        db.execute(text("UPDATE control_equipos.reportes SET fecha_completado=now()-interval '25 hours' WHERE id=:id"), {'id': last_report}); db.commit()
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        with SessionLocal() as db:
            status = db.scalar(text('SELECT estado FROM control_equipos.reportes WHERE id=:id'), {'id': last_report})
        if status == 'expirado': break
        time.sleep(2)
    assert status == 'expirado', 'Beat no ejecutó la limpieza periódica.'
    record('Celery Beat ejecuta y persiste la expiración periódica de reportes')
    task = celery_app.send_task('tasks.send_email_notification', args=['qa@example.com', 'Verificación aislada', 'No es un correo real.'])
    assert task.get(timeout=40) == 'Correo enviado.'
    assert call('GET', '/api/v1/messages', base='http://mailpit:8025')['total'] >= 1
    record('SMTP real capturado en Mailpit, sin destinatarios externos')
    s3 = get_s3_client()
    try:
        s3.create_bucket(Bucket=settings.AWS_BUCKET_NAME)
    finally: s3.close()
    buffer = io.BytesIO(); Image.new('RGB', (96, 96), (23, 50, 77)).save(buffer, 'PNG')
    boundary = 'qa' + secrets.token_hex(10)
    image = buffer.getvalue()
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="photo.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + image + f'\r\n--{boundary}--\r\n'.encode())
    request = urllib.request.Request(BASE + '/usuarios/me/avatar', data=body, headers={'Authorization': 'Bearer ' + state['access'], 'Content-Type': 'multipart/form-data; boundary=' + boundary})
    with urllib.request.urlopen(request, timeout=30) as response: avatar = json.load(response)['avatar_url']
    assert avatar.startswith('/api/v1/usuarios/avatar/')
    assert call('GET', avatar.removeprefix('/api/v1')).startswith(b'\xff\xd8')
    url = 'http://minio:9000/' + settings.AWS_BUCKET_NAME + '/avatars/user_' + state['user_id'] + '.jpg'
    try:
        urllib.request.urlopen(url, timeout=10)
        raise AssertionError('La foto S3 se puede consultar públicamente.')
    except urllib.error.HTTPError as exc: assert exc.code == 403
    record('Foto S3 privada, lectura autenticada y rechazo anónimo')
    health = call('GET', '/api/health', base='http://frontend:3000')
    assert health['test_database'] == settings.POSTGRES_DB
    assert b'html' in call('GET', '/login', base='http://frontend:3000').lower()
    record('Frontend standalone y conexión interna con el backend')
    from app.core.backup import create_system_backup
    from scripts.seed_demo import verify_backup_restore
    archive = create_system_backup()
    assert verify_backup_restore(archive, make_url(str(settings.DATABASE_URI)), ROOT / 'backups')
    record('Respaldo PostgreSQL 17 restaurado y comparado en otra base')
    # Beat must remain a live separate process; runner checks the container via Compose.
    record('Flujo completo concluido')


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--phase', choices=['full', 'queue', 'resume', 'outage'], required=True)
phase = parser.parse_args().phase
if phase == 'full': full()
else:
    login()
    if phase == 'queue':
        state['queued_report'] = request_report()['reporte_id']; save_state()
        record('Reporte encolado con trabajador detenido')
    elif phase == 'resume':
        if state.get('queued_report'): assert wait_report(state['queued_report']).startswith(b'%PDF-')
        record('Reporte recuperado tras reinicio de Redis y trabajador')
    elif phase == 'outage':
        start = time.monotonic(); request_report(expected=503)
        assert time.monotonic() - start < 15, 'La caída de Redis bloquea demasiado tiempo.'
        record('Caída de Redis devuelve 503 controlado en menos de 15 segundos')
