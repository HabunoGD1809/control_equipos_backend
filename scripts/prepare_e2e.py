"""Prepare isolated browser-test fixtures; refuse the configured operational database."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5433)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--backend-url', default='http://127.0.0.1:8091')
    parser.add_argument('--first-login-only', action='store_true', help='Reset only the two isolated first-login fixtures for a repeated browser run.')
    args = parser.parse_args()
    from dotenv import dotenv_values
    configured = dotenv_values(ROOT / '.env').get('POSTGRES_DB')
    if '_test' not in args.database.lower() or args.database == configured or args.host not in {'localhost', '127.0.0.1'}:
        parser.error('E2E requiere una base local separada con _test en su nombre.')
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'verification'):
        parser.error('Guarde las credenciales únicamente bajo verification del backend.')
    from urllib.parse import urlsplit
    address = urlsplit(args.backend_url)
    if address.scheme != 'http' or address.hostname not in {'localhost', '127.0.0.1'} or address.username or address.password:
        parser.error('La API de E2E debe ejecutarse en una dirección local.')
    os.environ.update(POSTGRES_SERVER=args.host, POSTGRES_PORT=str(args.port), POSTGRES_DB=args.database, REPORT_EXECUTION_MODE='background', UPLOADS_DIRECTORY=str(output.parent / 'uploads'))
    from app.core.config import settings
    from sqlalchemy.engine import make_url
    assert make_url(str(settings.DATABASE_URI)).database == args.database
    if args.first_login_only:
        from scripts.bootstrap import bootstrap
        from app.db.session import SessionLocal
        from sqlalchemy import text
        fixture = json.loads(output.read_text(encoding='utf-8'))
        assert fixture['database'] == args.database and set(fixture['first_login']) == {'desktop', 'mobile'}
        with SessionLocal() as db:
            assert db.scalar(text('SELECT current_database()')) == args.database
            for account in fixture['first_login'].values():
                assert account['username'].startswith('e2e_first_')
                bootstrap(db, account['username'], account['username'] + '@example.com', account['password'], reset_password=True)
        print('Solo se restablecieron las cuentas de primer acceso de la base aislada.')
        return
    from scripts.create_test_database import main as create_database
    create_database()
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config(str(ROOT / 'alembic.ini')), 'head')
    from scripts.bootstrap import bootstrap
    from scripts.seed_demo import private_json
    from app.db.session import SessionLocal
    from app.models import Usuario
    from sqlalchemy import select
    run_id = 'DEMO-E2E-' + secrets.token_hex(4).upper()
    password = 'Qa!1' + secrets.token_urlsafe(24)
    first = {}
    with SessionLocal() as db:
        user = bootstrap(db, 'admin', 'e2e.admin@example.com', password, reset_password=True)
        assert user.requiere_cambio_contrasena
        user.requiere_cambio_contrasena = False  # Main fixture account; first-use is tested separately below.
        db.commit()
        for viewport in ['desktop', 'mobile']:
            initial_password, final_password = 'Qa!1' + secrets.token_urlsafe(24), 'Qa!2' + secrets.token_urlsafe(24)
            username = f'e2e_first_{viewport}_{secrets.token_hex(3)}'
            account = bootstrap(db, username, username + '@example.com', initial_password)
            assert account.requiere_cambio_contrasena
            first[viewport] = {'username': username, 'password': initial_password, 'final_password': final_password}
    # Reuse the guarded dataset script with the same initialized environment.
    from scripts.seed_demo import main as seed_demo
    original_arguments = sys.argv
    try:
        sys.argv = ['seed_demo', '--database', args.database, '--actor', 'admin', '--run-id', run_id]
        seed_demo()
    finally:
        sys.argv = original_arguments
    directory = ROOT / 'backups/demo_runs' / run_id
    credentials = json.loads((directory / 'credentials.json').read_text(encoding='utf-8'))
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    with SessionLocal() as db:
        roles = {}
        for label, account in credentials.items():
            user = db.scalar(select(Usuario).where(Usuario.nombre_usuario == account['username']))
            roles[label] = {'username': account['username'], 'password': account['password'], 'permissions': [permission.nombre for permission in user.rol.permisos]}
    from fpdf import FPDF
    sample = output.parent / 'sample.pdf'
    sample.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF(); pdf.add_page(); pdf.set_font('Helvetica', size=12)
    pdf.multi_cell(0, 8, 'Documento de prueba E2E. Validacion de subida y descarga.')
    pdf.output(str(sample))
    from PIL import Image
    photo = output.parent / 'profile.png'
    Image.new('RGB', (96, 96), (24, 96, 128)).save(photo)
    from app.core.security import create_access_token
    data = {'database': args.database, 'backend_url': args.backend_url, 'run_id': run_id, 'prefix': run_id, 'orphan_access_token': create_access_token(subject=uuid4()), 'admin': {'username': 'admin', 'password': password}, 'first_login': first, 'roles': roles, 'steps': manifest['steps'], 'sample_pdf': str(sample), 'profile_photo': str(photo)}
    private_json(output, data)
    print('Datos E2E preparados en la base aislada; credenciales privadas guardadas sin imprimirlas.')


if __name__ == '__main__':
    main()
