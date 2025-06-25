# --- Etapa 1: Build ---
# Usa una imagen base de Python
FROM python:3.11-slim as builder

# Establecer directorio de trabajo
WORKDIR /app

# Establecer variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Instalar dependencias del sistema si son necesarias (ej: build-essential para algunas libs)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential

# Instalar dependencias de Python primero (aprovecha el cache de Docker)
# Copiar solo requirements.txt
COPY requirements.txt .
# Instalar usando pip
RUN pip install --upgrade pip
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# --- Etapa 2: Final ---
# Usa la misma imagen base o una incluso más ligera si es posible
FROM python:3.11-slim

# Crear usuario no-root para correr la aplicación (mejora seguridad)
RUN addgroup --system app && adduser --system --group app

# Establecer directorio de trabajo
WORKDIR /home/app

# Copiar dependencias pre-compiladas de la etapa builder
COPY --from=builder /wheels /wheels
# Instalar dependencias desde las wheels (más rápido)
RUN pip install --upgrade pip
RUN pip install --no-cache /wheels/*

# Copiar el código de la aplicación
# Asegúrate que el contexto de build (.) sea el raíz de tu proyecto
COPY ./app ./app
# Copiar si necesitas correr migraciones desde el contenedor
COPY ./alembic ./alembic 
COPY alembic.ini .
# ¡Cuidado! Copiar .env puede exponer secretos. Mejor inyectar variables en runtime.
COPY .env . 

# Cambiar propietario de los archivos al usuario no-root
RUN chown -R app:app /home/app

# Cambiar al usuario no-root
USER app

# Exponer el puerto en el que corre la aplicación (el que usa Uvicorn)
EXPOSE 8086

# Comando para ejecutar la aplicación
# Usar la forma exec para que Uvicorn reciba señales correctamente
# No usar --reload en producción
# Usar el host 0.0.0.0 para que sea accesible desde fuera del contenedor
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8086"]
