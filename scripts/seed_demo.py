"""Create a complete, identifiable DEMO dataset after a verified backup.

Refuses remote databases and needs an explicit opt-in for an existing local database.
Never changes the original administrator, company, passwords or existing records.
Run with the development extra installed (uv sync --extra dev).
"""
import argparse
import asyncio
import io
import json
import logging
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]


def private_json(path, value):
    new_file = not path.exists()
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    path.chmod(0o600)
    if os.name == 'nt' and new_file:
        identity = subprocess.run(['whoami', '/user'], capture_output=True, text=True, check=True)
        sid = re.search(r'S-1-5-[\d-]+', identity.stdout).group()
        subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r', f'*{sid}:(F)', '*S-1-5-18:(F)'], check=True, capture_output=True)


def verify_backup_restore(backup, address, directory):
    from uuid import uuid4
    import psycopg
    from psycopg import sql
    from app.core.backup import postgres_tool
    tables = ['equipos', 'inventario_stock', 'inventario_movimientos', 'movimientos', 'mantenimiento', 'reservas_equipo', 'documentacion', 'licencias_software', 'usuarios', 'configuracion_empresa']
    connection_args = {'host': address.host, 'port': address.port, 'user': address.username, 'password': address.password, 'connect_timeout': 10}
    def counts(database):
        with psycopg.connect(**connection_args, dbname=database) as connection:
            return {table: connection.execute(sql.SQL('SELECT count(*) FROM control_equipos.{}').format(sql.Identifier(table))).fetchone()[0] for table in tables}
    expected = counts(address.database)
    name = 'demo_backup_test_' + uuid4().hex[:16]
    assert name.startswith('demo_backup_test_') and name != address.database
    dump = directory / 'backup-verification.dump'
    created = False
    try:
        with zipfile.ZipFile(backup) as archive:
            if archive.testzip(): raise RuntimeError('El ZIP de respaldo está dañado.')
            dump.write_bytes(archive.read('database.dump'))
        with psycopg.connect(**connection_args, dbname='postgres', autocommit=True) as connection:
            connection.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(name)))
            created = True
        environment = {**os.environ, 'PGPASSWORD': address.password, 'PGCONNECT_TIMEOUT': '10'}
        subprocess.run([postgres_tool('pg_restore'), '--host', address.host, '--port', str(address.port), '--username', address.username, '--dbname', name, '--no-owner', '--exit-on-error', str(dump)], env=environment, check=True, capture_output=True, timeout=300)
        assert counts(name) == expected, 'El respaldo restaurado no coincide con los registros existentes; revisar actividad concurrente.'
        print('Respaldo restaurado y comparado en una base temporal, sin modificar el destino.', flush=True)
        return True
    finally:
        if created:
            with psycopg.connect(**connection_args, dbname='postgres', autocommit=True) as connection:
                connection.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        if dump.resolve().parent == directory.resolve(): dump.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--actor', default='admin')
    parser.add_argument('--run-id', default='DEMO-' + date.today().strftime('%Y%m%d'))
    parser.add_argument('--allow-current-local-development', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Continue the same recorded run after an interruption')
    args = parser.parse_args()
    if not re.fullmatch(r'DEMO-[A-Za-z0-9-]{6,40}', args.run_id):
        parser.error('El identificador debe empezar con DEMO- y contener solo letras, cifras y guiones.')
    if 'test' not in args.database.lower() and not args.allow_current_local_development:
        parser.error('Base no aislada: se necesita --allow-current-local-development. No ejecutar en producción.')
    if any(os.environ.get(key, '').lower() in ('prod', 'production') for key in ('ENVIRONMENT', 'APP_ENV', 'NODE_ENV')):
        parser.error('La carga DEMO está prohibida en un entorno de producción.')
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ['POSTGRES_DB'] = args.database
    os.environ['REPORT_EXECUTION_MODE'] = 'background'
    from app.core.config import settings
    from sqlalchemy.engine import make_url
    address = make_url(str(settings.DATABASE_URI))
    if address.database != args.database or address.host not in ('localhost', '127.0.0.1', '::1'):
        parser.error('El destino debe coincidir exactamente con --database y estar en este equipo.')
    if settings.AWS_BUCKET_NAME:
        parser.error('La carga exige respaldo completo; respalda S3/MinIO por separado antes de usar una base aislada.')
    from app.core.backup import create_system_backup
    from app.db.session import SessionLocal
    from app.models import Usuario, Rol, Notificacion
    from app.core.security import create_access_token
    from sqlalchemy import select, text
    from app.main import app
    from httpx import AsyncClient, ASGITransport
    logging.getLogger().setLevel(logging.ERROR)
    directory = ROOT / 'backups' / 'demo_runs' / args.run_id
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / 'manifest.json'
    credentials_path = directory / 'credentials.json'
    if manifest_path.exists() and not args.resume:
        parser.error('Esta carga ya tiene un registro. No se duplicará: revise manifest.json o use --resume si quedó incompleta.')
    with SessionLocal() as db:
        actor = db.scalar(select(Usuario).where(Usuario.nombre_usuario == args.actor))
        if not actor or actor.bloqueado or actor.requiere_cambio_contrasena or actor.rol.nombre.lower() != 'admin':
            parser.error('Se requiere un administrador existente, activo y con su cambio inicial completado.')
        actor_id = actor.id
        actor_version = actor.session_version
        original_user = (actor.nombre_usuario, actor.email, actor.hashed_password, actor.rol_id, actor.bloqueado, actor.avatar_url, actor.departamento_id, actor.empleado_id, actor.session_version)
        original_company = repr(db.execute(text('SELECT * FROM control_equipos.configuracion_empresa ORDER BY id')).fetchall())
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['database'] != args.database or manifest['status'] == 'completed':
            parser.error('El registro pertenece a otra base o la carga ya terminó.')
        credentials = json.loads(credentials_path.read_text(encoding='utf-8')) if credentials_path.exists() else {}
    else:
        backup = create_system_backup()
        restored = verify_backup_restore(backup, address, directory)
        manifest = {'run_id': args.run_id, 'database': args.database, 'actor': args.actor, 'backup': str(backup), 'backup_verified': True, 'backup_restore_verified': restored, 'status': 'started', 'steps': {}, 'checks': {}}
        credentials = {}
        private_json(manifest_path, manifest)
        print('Respaldo previo verificado:', backup, flush=True)
    prefix = args.run_id
    user_prefix = prefix.lower().replace('-', '_')

    def persist():
        private_json(manifest_path, manifest)
        private_json(credentials_path, credentials)

    async def seed():
        token = create_access_token(actor_id, expires_delta=timedelta(minutes=60), session_version=actor_version)
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url='http://demo.local', headers={'Authorization': 'Bearer ' + token}, timeout=120, follow_redirects=True) as client:
                async def call(method, path, data=None, expected=200, step=None, **kwargs):
                    if step and step in manifest['steps']:
                        return manifest['steps'][step]
                    response = await client.request(method, '/api/v1' + path, json=data, **kwargs)
                    if response.status_code != expected:
                        raise RuntimeError(f'{method} {path}: HTTP {response.status_code}: {response.text[:600]}')
                    result = response.json() if response.content and 'json' in response.headers.get('content-type', '') else response
                    if step:
                        manifest['steps'][step] = result
                        persist()
                    return result
                async def create(path, data, label):
                    return await call('POST', path, data, 201, label)

                states = await call('GET', '/catalogos/estados-equipo/')
                available = next(row['id'] for row in states if row.get('codigo') == 'disponible')
                departments = [await create('/catalogos/departamentos/', {'nombre': f'{prefix} {name}'}, 'department-' + str(i)) for i, name in enumerate(['Tecnología', 'Suministro', 'Administración'])]
                brands = [await create('/catalogos/marcas/', {'nombre': f'{prefix} Fabricante {i+1}'}, f'brand-{i}') for i in range(3)]
                places = [await create('/ubicaciones/', {'nombre': f'{prefix} {name}'}, f'place-{i}') for i, name in enumerate(['Almacén central', 'Centro de datos', 'Soporte', 'Oficina administrativa', 'Suministro', 'Sala de reuniones'])]
                suppliers = [await create('/proveedores/', {'nombre': f'{prefix} Proveedor ficticio {i+1}', 'contacto': f'contacto{i+1}@example.com', 'descripcion': 'Entidad ficticia para pruebas; sin transacciones reales.'}, f'supplier-{i}') for i in range(3)]
                employees = [await create('/empleados/', {'nombre_completo': f'{prefix} Custodio ficticio {i+1}', 'cargo': ['Soporte', 'Redes', 'Servidor', 'Oficina'][i % 4], 'departamento_id': departments[i % 3]['id'], 'email_corporativo': f'custodio{i+1}.{user_prefix}@example.com'}, f'employee-{i}') for i in range(6)]
                technicians = [await create('/tecnicos/', {'nombre_completo': f'{prefix} Técnico ficticio {i+1}'}, f'technician-{i}') for i in range(2)]
                maintenance_types = [await create('/catalogos/tipos-mantenimiento/', {'nombre': f'{prefix} Preventivo {i+1}', 'es_preventivo': True, 'periodicidad_dias': 90 if i == 0 else 180}, f'maintenance-type-{i}') for i in range(2)]
                document_type = await create('/catalogos/tipos-documento/', {'nombre': f'{prefix} Expediente de pruebas', 'descripcion': 'Actas, garantías, manuales y evidencias ficticias.', 'requiere_verificacion': True, 'formato_permitido': ['pdf', 'png', 'txt', 'xlsx', 'docx']}, 'document-type')
                permissions = await call('GET', '/gestion/permisos/')
                from scripts.demo_catalog import DEMO_ROLE_PERMISSIONS
                roles = {}
                for label, names in DEMO_ROLE_PERMISSIONS.items():
                    role = await create('/gestion/roles/', {'nombre': f'{prefix} {label.capitalize()}', 'descripcion': 'Rol exclusivo de la carga de pruebas.', 'permiso_ids': [row['id'] for row in permissions if row['nombre'] in names]}, 'role-' + label)
                    roles[label] = role['id']
                reader_role = await create('/gestion/roles/', {'nombre': f'{prefix} Consulta de inventario', 'descripcion': 'Solo puede consultar inventario.', 'permiso_ids': [row['id'] for row in permissions if row['nombre'] == 'ver_inventario']}, 'reader-role')
                no_access_role = await create('/gestion/roles/', {'nombre': f'{prefix} Sin acceso operativo', 'descripcion': 'Prueba de denegación: solo perfil.', 'permiso_ids': []}, 'no-access-role')
                user_roles = [('supervisor', roles['supervisor']), ('tecnico', roles['tecnico']), ('auditor', roles['auditor']), ('inventario', reader_role['id']), ('sin_acceso', no_access_role['id'])]
                users = {}
                for i, (label, role_id) in enumerate(user_roles):
                    if label not in credentials:
                        credentials[label] = {'username': f'{user_prefix}_{label}', 'temporary_password': 'Demo!1' + secrets.token_urlsafe(24), 'password': 'Demo!2' + secrets.token_urlsafe(24)}
                        persist()
                    account = credentials[label]
                    user = await create('/usuarios/', {'nombre_usuario': account['username'], 'email': account['username'] + '@example.com', 'password': account['temporary_password'], 'rol_id': role_id, 'departamento_id': departments[0]['id'], 'empleado_id': employees[i]['id']}, 'user-' + label)
                    users[label] = user
                    if 'activated-' + label not in manifest['steps']:
                        login = await client.post('/api/v1/auth/login/access-token', data={'username': account['username'], 'password': account['temporary_password']})
                        if login.status_code != 200: raise RuntimeError('No se pudo iniciar sesión con la cuenta DEMO temporal.')
                        headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
                        protected = await client.get('/api/v1/inventario/stock/', headers=headers)
                        assert protected.status_code == 403, 'El cambio inicial debe ser obligatorio.'
                        response = await client.post('/api/v1/auth/change-password', headers=headers, json={'current_password': account['temporary_password'], 'new_password': account['password']})
                        assert response.status_code == 204
                        manifest['steps']['activated-' + label] = True
                        persist()
                types = ['Equipo', 'Servidor', 'Red', 'Impresora', 'UPS', 'Almacenamiento', 'Periférico', 'Otro']
                equipment = []
                for i in range(32):
                    kind = types[i % len(types)]
                    technical = {'hostname': f'demo-{i+1:02d}', 'direccion_ip': f'192.0.2.{i+1}', 'rack': 'DEMO-R1', 'posicion_rack': f'U{i+1}'} if kind in ['Servidor', 'Red', 'Impresora'] else {'Descripción técnica': 'Equipo ficticio para validar el sistema.'}
                    equipment.append(await create('/equipos/', {'nombre': f'{prefix} {kind} {i+1:02d}', 'numero_serie': f'{prefix}/ACT-{i+1:03d}', 'codigo_interno': f'{prefix}-AF-{i+1:03d}', 'tipo_activo': kind, 'especificaciones_tecnicas': technical, 'estado_id': available, 'ubicacion_id': places[0]['id'], 'marca_id': brands[i % 3]['id'], 'modelo': f'Modelo DEMO {i%4+1}', 'proveedor_id': suppliers[i % 3]['id'], 'valor_adquisicion': str(200 + i * 80), 'fecha_adquisicion': (date.today() - timedelta(days=60+i)).isoformat(), 'fecha_garantia_expiracion': (date.today() + timedelta(days=30+i*15)).isoformat(), 'notas': 'Registro ficticio, identificado DEMO. No corresponde a un activo real.'}, f'equipment-{i}'))
                await call('POST', f"/equipos/{equipment[0]['id']}/componentes", {'equipo_componente_id': equipment[6]['id'], 'cantidad': 1, 'tipo_relacion': 'componente', 'notas': 'Conjunto ficticio para verificar custodia.'}, 201, 'assembly')
                for i in range(4):
                    movement = await create('/movimientos/', {'equipo_id': equipment[i]['id'], 'tipo_movimiento': 'Asignacion Interna', 'ubicacion_origen_id': places[0]['id'], 'ubicacion_destino_id': places[i+1]['id'], 'empleado_destino_id': employees[i]['id'], 'notas': 'Acta de entrega ficticia ' + prefix}, f'assignment-{i}')
                    if i < 3:
                        await call('PATCH', f"/movimientos/{movement['id']}/estado", {'estado': 'Completado'}, step=f'assignment-received-{i}')
                transfer = await create('/movimientos/', {'equipo_id': equipment[4]['id'], 'tipo_movimiento': 'Transferencia Bodega', 'ubicacion_origen_id': places[0]['id'], 'ubicacion_destino_id': places[1]['id']}, 'transfer-cancelled')
                await call('POST', f"/movimientos/{transfer['id']}/cancelar", {}, step='cancel-transfer')
                colors = ['Negro', 'Cian', 'Magenta', 'Amarillo', 'Tricolor', 'Otro', None]
                items = []
                for i in range(14):
                    color = colors[i % len(colors)]
                    items.append(await create('/inventario/tipos/', {'nombre': f'{prefix} ' + (f'Tóner {color or "sin color"}' if i < 7 else f'Insumo {i+1}'), 'categoria': 'Consumible' if i < 7 else ['Parte Repuesto', 'Accesorio', 'Otro'][i % 3], 'unidad_medida': 'Unidad', 'sku': f'{prefix}-SKU-{i+1:02d}', 'marca_id': brands[i % 3]['id'], 'proveedor_preferido_id': suppliers[i % 3]['id'], 'stock_minimo': 8, 'color': color if i < 7 else None, 'tecnologia': 'Tóner' if i < 7 else None, 'rendimiento_paginas': 3000 if i < 7 else None, 'modelos_equipo_compatibles': ['Impresora DEMO', 'Modelo DEMO 4'] if i < 7 else None, 'es_original': True}, f'item-{i}'))
                    for j in range(2):
                        await create('/inventario/movimientos/', {'tipo_item_id': items[-1]['id'], 'tipo_movimiento': 'Entrada Abastecimiento', 'cantidad': 1 if i < 3 and j == 1 else 12, 'ubicacion_destino_id': places[j]['id'], 'lote_destino': f'{prefix}-L{i+1:02d}-{j+1}', 'costo_unitario': str(20+i*2), 'procedencia': departments[1]['nombre'], 'entregado_por': employees[1]['nombre_completo'], 'referencia_externa': f'{prefix}-ACTA-{i+1:02d}-{j+1}'}, f'supply-{i}-{j}')
                    await create('/inventario/movimientos/', {'tipo_item_id': items[-1]['id'], 'tipo_movimiento': 'Salida Uso', 'cantidad': 10 if i < 3 else 3, 'ubicacion_origen_id': places[0]['id'], 'lote_origen': f'{prefix}-L{i+1:02d}-1', 'equipo_asociado_id': equipment[11]['id'], 'notas': 'Consumo ficticio de prueba.'}, f'consumption-{i}')
                maintenances = []
                for i in range(6):
                    maintenance = await create('/mantenimientos/', {'equipo_id': equipment[16+i]['id'], 'tecnico_id': technicians[i % 2]['id'], 'tipo_mantenimiento_id': maintenance_types[i % 2]['id'], 'fecha_programada': (datetime.now(timezone.utc)+timedelta(days=3+i)).isoformat(), 'estado': 'Programado', 'observaciones': prefix + ' Revisión preventiva ficticia'}, f'maintenance-{i}')
                    if i % 3 != 0:
                        maintenance = await call('PUT', f"/mantenimientos/{maintenance['id']}", {'estado': 'En Proceso'}, step=f'maintenance-start-{i}')
                    if i % 3 == 2:
                        maintenance = await call('PUT', f"/mantenimientos/{maintenance['id']}", {'estado': 'Completado', 'observaciones': prefix + ' Limpieza y pruebas satisfactorias.'}, step=f'maintenance-finish-{i}')
                    maintenances.append(maintenance)
                for i in range(4):
                    start = datetime.now(timezone.utc) + timedelta(days=i+1)
                    reservation = await create('/reservas/', {'equipo_id': equipment[24+i]['id'], 'fecha_hora_inicio': start.isoformat(), 'fecha_hora_fin': (start+timedelta(hours=2)).isoformat(), 'proposito': prefix + ' Reunión ficticia'}, f'reservation-{i}')
                    if i == 1:
                        await call('PATCH', f"/reservas/{reservation['id']}/check-in-out", {'check_out_time': datetime.now(timezone.utc).isoformat()}, step='reservation-out')
                    if i == 2:
                        await call('PATCH', f"/reservas/{reservation['id']}/check-in-out", {'check_out_time': datetime.now(timezone.utc).isoformat()}, step='reservation-complete-out')
                        await call('PATCH', f"/reservas/{reservation['id']}/check-in-out", {'check_in_time': datetime.now(timezone.utc).isoformat(), 'notas_devolucion': 'Sin daños, prueba ficticia.'}, step='reservation-complete-in')
                licenses = []
                for i in range(4):
                    software = await create('/licencias/catalogo', {'nombre': f'{prefix} Software ficticio {i+1}', 'categoria': 'Ofimática' if i < 2 else 'Infraestructura', 'tipo_licencia': 'Perpetua', 'metrica_licenciamiento': 'Por Dispositivo'}, f'software-{i}')
                    license = await create('/licencias/', {'software_catalogo_id': software['id'], 'fecha_adquisicion': date.today().isoformat(), 'cantidad_total': 5, 'clave_producto': f'{prefix}-CLAVE-FICTICIA-{i+1}', 'costo_adquisicion': '150.00', 'proveedor_id': suppliers[i % 3]['id']}, f'license-{i}')
                    licenses.append(license)
                    await create('/licencias/asignaciones', {'licencia_id': license['id'], 'equipo_id': equipment[8+i]['id'], 'instalado': i % 2 == 0, 'notas': prefix + ' Instalación ficticia'}, f'license-assignment-{i}')
                from app.services.report_export import generar_pdf, generar_excel
                pdf_path = directory / 'documento-demo.pdf'
                xlsx_path = directory / 'documento-demo.xlsx'
                rows = [{'Acta': prefix, 'Observación': 'Datos ficticios para validación del sistema.'}]
                generar_pdf(pdf_path, rows, 'Acta de prueba DEMO')
                generar_excel(xlsx_path, rows, 'Evidencia ficticia DEMO')
                from PIL import Image
                image = io.BytesIO()
                Image.new('RGB', (320, 160), (25, 66, 88)).save(image, 'PNG')
                docx = io.BytesIO()
                with zipfile.ZipFile(docx, 'w') as archive:
                    archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
                    archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
                    archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Documento DEMO ficticio</w:t></w:r></w:p></w:body></w:document>')
                files = [('pdf', pdf_path.read_bytes(), 'application/pdf'), ('png', image.getvalue(), 'image/png'), ('txt', ('Evidencia ficticia ' + prefix).encode(), 'text/plain'), ('xlsx', xlsx_path.read_bytes(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'), ('docx', docx.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')]
                for i in range(15):
                    extension, content, mime = files[i % len(files)]
                    target = {'equipo_id': equipment[i]['id']} if i < 5 else {'mantenimiento_id': maintenances[i % 6]['id']} if i < 10 else {'licencia_id': licenses[i % 4]['id']}
                    if f'document-{i}' in manifest['steps']:
                        document = manifest['steps'][f'document-{i}']
                    else:
                        response = await client.post('/api/v1/documentacion/', data={'titulo': f'{prefix} Evidencia {i+1:02d}', 'descripcion': 'Expediente ficticio de equipo, mantenimiento o licencia.', 'tipo_documento_id': document_type['id'], **target}, files={'file': (f'evidencia-{i+1:02d}.{extension}', content, mime)})
                        if response.status_code != 201: raise RuntimeError(f'Subida {extension}: HTTP {response.status_code}: {response.text[:500]}')
                        document = response.json()
                        manifest['steps'][f'document-{i}'] = document
                        persist()
                    if i % 3 != 0:
                        await call('POST', f"/documentacion/{document['id']}/verificar", {'estado': 'Verificado' if i % 3 == 1 else 'Rechazado', 'notas_verificacion': 'Resultado ficticio para comprobar el flujo de revisión.'}, step=f'document-verification-{i}')
                if 'notifications' not in manifest['steps']:
                    with SessionLocal() as db:
                        db.execute(text("SELECT set_config('myapp.current_user_id', :actor, true)"), {'actor': str(actor_id)})
                        for i in range(6):
                            db.add(Notificacion(usuario_id=actor_id, mensaje=f'{prefix} Aviso ficticio {i+1}: revisar inventario y expediente.', tipo=['info', 'sistema', 'alerta'][i % 3], urgencia=i % 3, referencia_tabla='equipos', referencia_id=equipment[i]['id']))
                        db.commit()
                    manifest['steps']['notifications'] = True
                    persist()
                for report_type in ['equipos', 'movimientos', 'inventario', 'kardex', 'mantenimientos', 'licencias', 'auditoria']:
                    for format_ in ['pdf', 'excel', 'csv']:
                        report = await call('POST', '/reportes/', {'tipo_reporte': report_type, 'formato': format_, 'fecha_inicio': (date.today()-timedelta(days=90)).isoformat(), 'fecha_fin': date.today().isoformat()}, step=f'report-{report_type}-{format_}')
                        download = await client.get(f"/api/v1/reportes/{report['reporte_id']}/download")
                        assert download.status_code == 200 and len(download.content) > 20
                for label, account in credentials.items():
                    login = await client.post('/api/v1/auth/login/access-token', data={'username': account['username'], 'password': account['password']})
                    assert login.status_code == 200
                    access = {'Authorization': 'Bearer ' + login.json()['access_token']}
                    me = await client.get('/api/v1/usuarios/me', headers=access)
                    names = {permission['nombre'] for permission in me.json()['rol']['permisos']}
                    routes = [('/equipos/', {'ver_equipos'}), ('/inventario/stock/', {'ver_inventario'}), ('/documentacion/', {'ver_documentos'}), ('/gestion/roles/', {'administrar_roles', 'administrar_usuarios'}), ('/usuarios/', {'administrar_usuarios'}), ('/auditoria/', {'ver_auditoria'})]
                    checks = {}
                    for path, allowed_permissions in routes:
                        response = await client.get('/api/v1' + path, headers=access)
                        expected = 200 if names.intersection(allowed_permissions) else 403
                        checks[path] = {'expected': expected, 'actual': response.status_code}
                        assert response.status_code == expected, f'Permisos DEMO {label}: {path} devolvió {response.status_code}; esperado {expected}.'
                    manifest['checks'][label] = checks
                    persist()
                print('Carga completa: equipos, stock, entregas, mantenimiento, reservas, licencias, documentos, roles y 21 reportes.', flush=True)
    try:
        asyncio.run(seed())
        with SessionLocal() as db:
            actor = db.get(Usuario, actor_id)
            current = (actor.nombre_usuario, actor.email, actor.hashed_password, actor.rol_id, actor.bloqueado, actor.avatar_url, actor.departamento_id, actor.empleado_id, actor.session_version)
            assert current == original_user, 'Revisar cambios concurrentes del administrador.'
            assert repr(db.execute(text('SELECT * FROM control_equipos.configuracion_empresa ORDER BY id')).fetchall()) == original_company
        manifest['original_admin_and_company_preserved'] = True
        manifest['status'] = 'completed'
        persist()
        print('Administrador y empresa preservados. Registro de carga:', manifest_path, flush=True)
        print('Las credenciales DEMO se conservan en un archivo local privado; no se imprimen.', flush=True)
    except BaseException:
        manifest['status'] = 'interrupted'
        persist()
        print('Carga interrumpida. Conserve el respaldo y revise el registro antes de continuar con --resume.', flush=True)
        raise


if __name__ == '__main__':
    main()
