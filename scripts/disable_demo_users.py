"""Preview or disable only accounts from a completed local DEMO run.

Does not delete assets, documents or audit actors. Backs up the system before
disabling accounts and revoking all their sessions. The default is read-only.
"""
import argparse
import json
import os
import sys
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--disable', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'DEMO-[A-Z0-9-]{1,60}', args.run_id):
        parser.error('Utiliza el identificador DEMO exacto del registro de carga.')
    os.environ['POSTGRES_DB'] = args.database
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    from app.core.config import settings
    from sqlalchemy.engine import make_url
    address = make_url(str(settings.DATABASE_URI))
    if address.database != args.database or address.host not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('Solo se admite la base local indicada exactamente por --database.')
    run = root/'backups/demo_runs'/args.run_id
    manifest = json.loads((run/'manifest.json').read_text(encoding='utf-8'))
    if manifest['database'] != args.database or manifest['status'] != 'completed':
        parser.error('El registro debe pertenecer a esta base y estar completado.')
    accounts = json.loads((run/'credentials.json').read_text(encoding='utf-8'))
    prefix = args.run_id.lower().replace('-', '_') + '_'
    names = [account['username'] for account in accounts.values()]
    if not names or any(not name.startswith(prefix) or name == 'admin' for name in names):
        parser.error('Hay cuentas fuera del prefijo de prueba. No se realizará ningún cambio.')
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.usuario import Usuario
    from app.services.usuario import usuario_service
    with SessionLocal() as db:
        users = db.scalars(select(Usuario).where(Usuario.nombre_usuario.in_(names))).all()
        if len(users) != len(names):
            parser.error('No se encontraron todas las cuentas. Revisa el registro antes de continuar.')
        print(f'Vista previa: {len(users)} cuentas DEMO; {sum(not user.bloqueado for user in users)} activas. Activos, documentos y administrador se conservarán.')
        if not args.disable:
            print('Sin cambios. Usa --disable para aplicar la operación con respaldo previo.')
            return
        if settings.AWS_BUCKET_NAME:
            parser.error('Se requiere respaldo de S3/MinIO antes de aplicar cambios.')
        from app.core.backup import create_system_backup
        backup = create_system_backup()
        for user in users:
            user.bloqueado = True
            usuario_service.revoke_sessions(db, user)
        db.commit()
        print(f'Cuentas DEMO desactivadas y sesiones revocadas. Respaldo: {backup}')


if __name__ == '__main__':
    main()
