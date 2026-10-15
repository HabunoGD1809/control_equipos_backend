#!/bin/sh
set -eu
echo "Esperando PostgreSQL..."
attempt=0
until pg_isready -h "${POSTGRES_SERVER:-db}" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q; do
  attempt=$((attempt+1))
  if [ "$attempt" -ge 60 ]; then echo "PostgreSQL no está disponible." >&2; exit 1; fi
  sleep 2
done
if [ "${APP_COMPONENT:-backend}" = "backend" ]; then
  uv run --frozen --no-sync alembic upgrade head
  uv run --frozen --no-sync python scripts/bootstrap.py --from-env
fi
exec "$@"
