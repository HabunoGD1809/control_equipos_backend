# --- Etapa 1: Build ---
# Usa una imagen base de Python
FROM python:3.11-slim-buster AS builder

# Establecer directorio de trabajo
WORKDIR /app

# Establecer variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
   PYTHONUNBUFFERED=1

# --- CAMBIO CLAVE #1 ---
# Instalar las dependencias del sistema necesarias para CONSTRUIR psycopg.
# - libpq-dev: Librerías de desarrollo de PostgreSQL.
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev build-essential

# Instalar dependencias de Python (aprovecha el cache de Docker)
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# --- Etapa 2: Final ---
# Usa la misma imagen base
FROM python:3.11-slim-buster

# --- CAMBIO CLAVE #2 ---
# Instalar solo las librerías de sistema necesarias para EJECUTAR la aplicación.
# - libpq5: Es la librería de cliente de PostgreSQL, más ligera que libpq-dev.
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root para correr la aplicación (buena práctica de seguridad)
RUN addgroup --system app && adduser --system --group app

# Establecer directorio de trabajo
WORKDIR /home/app

# Copiar dependencias pre-compiladas de la etapa builder
COPY --from=builder /wheels /wheels
# Instalar dependencias desde las wheels
RUN pip install --no-cache /wheels/*

# Copiar el código de la aplicación y archivos de migración
COPY ./app ./app
COPY ./alembic ./alembic
COPY alembic.ini .

# Cambiar propietario de los archivos al usuario no-root
RUN chown -R app:app /home/app

# Cambiar al usuario no-root
USER app

# Exponer el puerto que usa la aplicación
EXPOSE 8000

# El CMD del docker-compose anulará este, pero es bueno tener un default.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
