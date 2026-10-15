"""Explicit clean delivery: verified backup, initial migration and one administrator.

Stop the API/worker before using --reset-existing. Never use it to upgrade production.
The old database and attachments remain recoverable in backups; no backup is deleted.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, help='Exact configured database; no default.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5433)
    parser.add_argument('--reset-existing', action='store_true', help='Erase existing application data after verified backup.')
    parser.add_argument('--isolated-test', action='store_true', help='Exercise this installer on a separate test database and upload directory.')
    args = parser.parse_args()
    from dotenv import dotenv_values
    configured = dotenv_values(ROOT / '.env').get('POSTGRES_DB')
    target_valid = (args.database != configured and '_test' in args.database and args.database.replace('_', '').isalnum()) if args.isolated_test else args.database == configured
    if not target_valid or args.host not in {'127.0.0.1', 'localhost'}:
        parser.error('El destino debe ser exactamente la base local configurada en .env.')
    os.environ.update(POSTGRES_SERVER=args.host, POSTGRES_PORT=str(args.port), POSTGRES_DB=args.database)
    expected_uploads = (ROOT / 'verification' / args.database / 'uploads') if args.isolated_test else ROOT / 'uploads'
    if args.isolated_test:
        os.environ['UPLOADS_DIRECTORY'] = str(expected_uploads)
    from app.core.config import settings
    from sqlalchemy import text, select
    from sqlalchemy.engine import make_url
    from app.db.session import engine, SessionLocal
    from app.models import Usuario
    from app.schemas.usuario import UsuarioCreate
    from app.core.password import verify_password
    from app.core.backup import create_system_backup
    from scripts.seed_demo import verify_backup_restore
    from scripts.bootstrap import bootstrap
    from alembic.config import Config
    from alembic import command
    address = make_url(str(settings.DATABASE_URI))
    assert address.database == args.database and address.host == args.host and address.port == args.port
    if settings.AWS_BUCKET_NAME:
        raise RuntimeError('Respaldar primero el almacenamiento S3 por separado. Este reinicio solo cubre archivos locales.')
    from pydantic import ValidationError
    try:
        UsuarioCreate(nombre_usuario=settings.SUPERUSER_USERNAME, email=settings.SUPERUSER_EMAIL, password=settings.SUPERUSER_PASSWORD, rol_id=uuid4())
    except ValidationError:
        raise RuntimeError('Las credenciales SUPERUSER_* no cumplen las reglas. Corrige .env antes de reiniciar la base.') from None
    assert settings.SUPERUSER_USERNAME == 'admin', 'La entrega solicitada requiere un único usuario admin.'
    versions = list((ROOT / 'alembic/versions').glob('*.py'))
    assert len(versions) == 1 and versions[0].name == 'f01d20261014_initial_release.py'
    upload_source = Path(settings.UPLOADS_DIRECTORY)
    uploads = upload_source.resolve()
    expected_uploads = expected_uploads.absolute()
    if uploads != expected_uploads or not uploads.is_relative_to(ROOT) or upload_source.is_symlink() or getattr(upload_source, 'is_junction', lambda: False)():
        raise RuntimeError('Se exige el directorio uploads exacto de este proyecto, sin enlaces.')
    directory = (ROOT / 'backups' / ('clean-delivery-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid4().hex[:8])).resolve()
    assert directory.parent == (ROOT / 'backups').absolute(), 'La carpeta de respaldos no puede redirigir fuera del proyecto.'
    directory.mkdir(parents=True, exist_ok=False)
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT current_database()')) == args.database
        exists = connection.scalar(text("SELECT to_regclass('control_equipos.usuarios') IS NOT NULL"))
    result = {'database': args.database, 'revision': 'f01d20261014', 'reset_existing': args.reset_existing}
    if exists:
        if not args.reset_existing:
            raise RuntimeError('La base contiene una instalación. El reinicio exige --reset-existing explícito.')
        archive = create_system_backup()
        assert verify_backup_restore(archive, address, directory)
        result.update(backup=str(archive), backup_restored_and_compared=True)
        (directory / 'pre-reset.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        # Restrict the destructive operation to the named application schema in the verified database.
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='10s'"))
            connection.execute(text('DROP SCHEMA control_equipos CASCADE'))
        engine.dispose()
        if uploads.exists():
            destination = (directory / 'uploads_previous').resolve()
            assert destination.parent == directory and uploads == expected_uploads
            shutil.move(str(uploads), str(destination))
            result['previous_attachments'] = str(destination)
    uploads.mkdir(parents=True, exist_ok=True)
    command.upgrade(Config(str(ROOT / 'alembic.ini')), 'head')
    with SessionLocal() as db:
        user = bootstrap(db, settings.SUPERUSER_USERNAME, str(settings.SUPERUSER_EMAIL), settings.SUPERUSER_PASSWORD)
        assert verify_password(settings.SUPERUSER_PASSWORD, user.hashed_password)
        assert user.requiere_cambio_contrasena and not user.bloqueado
        counts = {table: db.scalar(text('SELECT count(*) FROM control_equipos.' + table)) for table in [
            'usuarios', 'roles', 'permisos', 'estados_equipo', 'tipos_documento', 'tipos_mantenimiento', 'ubicaciones', 'configuracion_empresa',
            'equipos', 'equipo_componentes', 'movimientos', 'inventario_movimientos', 'inventario_stock', 'tipos_item_inventario',
            'documentacion', 'licencias_software', 'asignaciones_licencia', 'software_catalogo', 'reservas_equipo', 'mantenimiento',
            'empleados', 'departamentos', 'marcas', 'proveedores', 'tecnicos_mantenimiento', 'notificaciones', 'reportes', 'refresh_tokens',
        ]}
        expected = {'usuarios': 1, 'roles': 1, 'permisos': 38, 'estados_equipo': 11, 'tipos_documento': 11, 'tipos_mantenimiento': 8, 'ubicaciones': 1, 'configuracion_empresa': 1}
        assert all(counts[name] == expected.get(name, 0) for name in counts), 'La instalación no quedó limpia.'
        assert list(db.scalars(select(Usuario.nombre_usuario))) == ['admin']
        result.update(counts=counts, password_hash_verified=True, first_login_password_change_required=True)
    result['attachment_files'] = len([file for file in uploads.rglob('*') if file.is_file()])
    assert result['attachment_files'] == 0
    result['completed'] = True
    (directory / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Instalación limpia completada. Evidencia:', directory / 'results.json')


if __name__ == '__main__':
    main()
