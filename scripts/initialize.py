"""Migrate and bootstrap a usable administrator; reset test data only when explicit."""
import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.db.session import SessionLocal
from scripts.bootstrap import bootstrap


def backup_database(url):
    executable = shutil.which("pg_dump")
    if not executable and sys.platform == "win32":
        candidates = sorted(Path("C:/Program Files/PostgreSQL").glob("*/bin/pg_dump.exe"), reverse=True)
        executable = str(candidates[0]) if candidates else None
    if not executable:
        raise RuntimeError("No se encontró pg_dump. Instale las herramientas de PostgreSQL antes de limpiar los datos.")
    folder = ROOT / "backups"
    folder.mkdir(exist_ok=True)
    filename = folder / f"{url.database}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.dump"
    environment = {**os.environ, "PGPASSWORD": url.password or ""}
    subprocess.run([executable, "--host", url.host or "localhost", "--port", str(url.port or 5432),
        "--username", url.username or "postgres", "--dbname", url.database, "--format=custom", "--file", str(filename)],
        env=environment, check=True)
    print(f"Respaldo previo guardado en {filename}")


def backup_uploads():
    uploads = Path(settings.UPLOADS_DIRECTORY).resolve()
    folder = (ROOT / "backups").resolve()
    if not uploads.is_dir():
        return
    if uploads == ROOT or uploads in ROOT.parents or folder.is_relative_to(uploads):
        raise RuntimeError("Configure UPLOADS_DIRECTORY como una carpeta de archivos separada del código y los respaldos.")
    folder.mkdir(exist_ok=True)
    name = folder / f"uploads_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    filename = shutil.make_archive(str(name), "zip", root_dir=uploads)
    print(f"Respaldo de los archivos locales guardado en {filename}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset-test-data", action="store_true", help="Borra el esquema control_equipos y recrea sus tablas")
    parser.add_argument("--database", help="Nombre exacto de la base que se autoriza a limpiar")
    parser.add_argument("--reset-password", action="store_true", help="Restablecer la contraseña del administrador existente")
    args = parser.parse_args()
    url = make_url(str(settings.DATABASE_URI))
    if args.reset_test_data:
        if not args.database or args.database != url.database:
            parser.error("Para limpiar los datos indique --database con el nombre exacto de la base configurada.")
        backup_database(url)
        backup_uploads()
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS control_equipos CASCADE"))
            connection.execute(text("DROP TABLE IF EXISTS public.alembic_version"))
        engine.dispose()
        print(f"Datos de prueba eliminados de {url.database}.")
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    with SessionLocal() as db:
        bootstrap(db, settings.SUPERUSER_USERNAME, str(settings.SUPERUSER_EMAIL), settings.SUPERUSER_PASSWORD,
            reset_password=args.reset_password)
    print("Inicialización completada. Las credenciales proceden de SUPERUSER_* en .env.")


if __name__ == "__main__":
    main()
