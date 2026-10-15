"""Private backups containing the PostgreSQL dump and local attachment files."""
import json
import os
import shutil
import subprocess
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from app.core.config import settings

ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backups"


def postgres_tool(name):
    executable = shutil.which(name)
    if not executable and os.name == "nt":
        candidates = sorted(Path("C:/Program Files/PostgreSQL").glob(f"*/bin/{name}.exe"), reverse=True)
        executable = str(candidates[0]) if candidates else None
    if not executable:
        raise RuntimeError(f"Instale las herramientas de PostgreSQL: no se encontró {name}.")
    return executable


def create_system_backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    identifier = uuid.uuid4().hex
    temporary = BACKUP_DIR / f".temporary_backup_{identifier}"
    temporary.mkdir()
    destination = BACKUP_DIR / f"{settings.POSTGRES_DB}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{identifier[:8]}.zip"
    try:
        dump = temporary / "database.dump"
        environment = {**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD, "PGCONNECT_TIMEOUT": "10"}
        subprocess.run([postgres_tool("pg_dump"), "--host", settings.POSTGRES_SERVER, "--port", str(settings.POSTGRES_PORT),
            "--username", settings.POSTGRES_USER, "--dbname", settings.POSTGRES_DB, "--no-password", "--format=custom", "--file", str(dump)],
            env=environment, check=True, capture_output=True, timeout=300)
        # Confirm that pg_restore can inspect the dump before publishing a successful backup.
        subprocess.run([postgres_tool("pg_restore"), "--list", str(dump)], check=True, capture_output=True, timeout=30)
        uploads = Path(settings.UPLOADS_DIRECTORY).resolve()
        if uploads == ROOT or uploads in ROOT.parents or BACKUP_DIR.resolve().is_relative_to(uploads):
            raise RuntimeError("La carpeta de archivos debe estar separada del código y los respaldos.")
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
            archive.write(dump, "database.dump")
            if uploads.is_dir():
                for file in uploads.rglob("*"):
                    if file.is_file():
                        if not file.resolve().is_relative_to(uploads):
                            raise RuntimeError("Un archivo enlazado está fuera de la carpeta de almacenamiento.")
                        archive.write(file, "uploads/" + file.relative_to(uploads).as_posix())
            archive.writestr("manifest.json", json.dumps({"database": settings.POSTGRES_DB, "generated_utc": datetime.now(timezone.utc).isoformat(), "includes_local_uploads": True, "cloud_storage_requires_separate_backup": bool(settings.AWS_BUCKET_NAME)}, ensure_ascii=False))
            archive.writestr("RESTAURAR.txt", "Extraiga el ZIP. Restaure database.dump en una base vacía con pg_restore. Copie el contenido de uploads a UPLOADS_DIRECTORY. El almacenamiento S3, si está configurado, se conserva por separado. Nunca restaure sobre datos activos sin un respaldo previo.")
        return destination
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        if temporary.resolve().parent == BACKUP_DIR.resolve() and temporary.name == f".temporary_backup_{identifier}":
            shutil.rmtree(temporary)
