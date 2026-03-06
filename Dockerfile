# 1. Imagen base anclada a Debian 12 (Bookworm)
FROM python:3.11-slim-bookworm

# 2. Variables de entorno esenciales
ENV PYTHONDONTWRITEBYTECODE=1 \
   PYTHONUNBUFFERED=1 \
   UV_COMPILE_BYTECODE=1 \
   UV_LINK_MODE=copy

# 3. Instalar dependencias del sistema + aplicar todos los parches de seguridad disponibles.
RUN apt-get update && \
   apt-get upgrade -y --no-install-recommends && \
   apt-get install -y --no-install-recommends \
   postgresql-client && \
   rm -rf /var/lib/apt/lists/*

# 4. Crear usuario no-root por seguridad
RUN addgroup --system app && adduser --system --group app

# 5. Directorio de trabajo
WORKDIR /home/app

# --- INTEGRACIÓN CON UV ---
# 6. Copiar el binario ultrarrápido de uv desde la imagen oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 7. Copiar SOLO archivos de dependencias primero.
COPY --chown=app:app pyproject.toml uv.lock ./

# 8. Sincronizar dependencias usando uv
#    --frozen:              Usa uv.lock sin actualizarlo
#    --no-dev:              Excluye dependencias de testing (pytest) en producción
#    --no-install-project:  Instala SOLO dependencias, no el proyecto en sí.
RUN uv sync --frozen --no-dev --no-install-project

# 9. Copiar el código fuente y aplicar el propietario en una sola capa
COPY --chown=app:app ./app ./app
COPY --chown=app:app ./alembic ./alembic
COPY --chown=app:app alembic.ini .
COPY --chown=app:app ./scripts ./scripts

# 10. Instalar el proyecto en sí
RUN uv sync --frozen --no-dev

# 11. Garantizar que los scripts tengan permisos de ejecución
RUN chmod +x ./scripts/*.sh

# 12. Cambiar al usuario seguro
USER app

# Exponer el puerto
EXPOSE 8000

# CMD por defecto — usa uv run para ejecutar en el virtualenv gestionado por uv
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
