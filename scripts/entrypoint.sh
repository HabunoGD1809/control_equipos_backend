#!/bin/bash
set -e

echo "Waiting for database..."
while ! pg_isready -h db -p 5432 -q -U ${POSTGRES_USER:-postgres}; do
  sleep 2
done
echo "Database is ready!"

# Aplicar las migraciones de la base de datos
echo "Applying database migrations..."
alembic upgrade head

# Iniciar la aplicación principal (el comando que se pasa desde docker-compose)
echo "Starting application..."
exec "$@"
