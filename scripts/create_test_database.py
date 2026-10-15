"""Create an isolated regression database without modifying existing databases."""
import os
import sys
from pathlib import Path
import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from app.core.config import settings


def main():
    name = settings.POSTGRES_DB
    if "test" not in name.lower():
        raise SystemExit("Las pruebas requieren POSTGRES_DB con un nombre que contenga test.")
    with psycopg.connect(host=settings.POSTGRES_SERVER, port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD, dbname="postgres", autocommit=True) as connection:
        if connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            print(f"Se utilizará la base de pruebas existente: {name}")
        else:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            print(f"Base de pruebas creada: {name}")


if __name__ == "__main__":
    main()
