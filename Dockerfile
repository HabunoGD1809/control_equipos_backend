# --- Etapa 1: Build ---
FROM python:latest AS builder

# Establecer directorio de trabajo
WORKDIR /app

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
   PYTHONUNBUFFERED=1

# Instalar dependencias del sistema necesarias para COMPILAR psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
   libpq-dev build-essential gcc && \
   rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python en forma de wheels
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# --- Etapa 2: Final ---
FROM python:latest

# Instalar solo librerías mínimas necesarias para EJECUTAR
RUN apt-get update && apt-get install -y --no-install-recommends \
   libpq5 postgresql-client && \
   rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN addgroup --system app && adduser --system --group app

# Directorio de trabajo
WORKDIR /home/app

# Copiar dependencias precompiladas
COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*

# Copiar el código de la aplicación y archivos necesarios
COPY ./app ./app
COPY ./alembic ./alembic
COPY alembic.ini .
COPY ./scripts ./scripts

# Cambiar propietario
RUN chown -R app:app /home/app

# Usar usuario no-root
USER app

# Exponer puerto
EXPOSE 8000

# CMD por defecto (será sobrescrito por docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
