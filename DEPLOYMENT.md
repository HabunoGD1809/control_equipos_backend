# 🚀 Guía de Despliegue en Producción - ERP Control de Equipos

Esta guía detalla los pasos exactos para desplegar la arquitectura contenerizada del sistema (FastAPI, PostgreSQL, Redis, Celery) en un entorno de producción (Linux/Ubuntu/Debian).

## Paso 1: Clonar el Repositorio y Preparar Variables

El servidor debe tener instalado **Docker** y **Docker Compose** (versión V2 recomendada).

```bash
# 1. Clonar el repositorio
git clone <https://github.com/HabunoGD1809/control_equipos_backend.git>
cd control_equipos_backend

# 2. Copiar el archivo de entorno de ejemplo
cp .env.example .env

```

**Acción Crítica:** Editar el archivo `.env` usando `nano .env` o `vim .env` y configurar valores fuertes y reales para:

* `POSTGRES_PASSWORD`
* `SECRET_KEY` y `REFRESH_TOKEN_SECRET_KEY` (Generar con `openssl rand -hex 32`)
* `CELERY_BROKER_URL` y `CELERY_RESULT_BACKEND` (Deben apuntar al servicio interno `redis://redis:6379/0`)
* Las credenciales del superusuario inicial (`SUPERUSER_EMAIL`, `SUPERUSER_PASSWORD`).

## Paso 2: Limpiar el `docker-compose.yml` (Modo Producción)

El archivo `docker-compose.yml` actual está optimizado para desarrollo local en Windows. **Antes de levantar los contenedores en el servidor Linux, el SysAdmin DEBE hacer estos dos cambios** en los servicios `backend`, `worker` y `beat`:

1. **Eliminar el usuario root:** Borrar la línea `user: root`. En producción, la imagen de Docker ya está configurada para usar el usuario seguro y sin privilegios `app`.
2. **Eliminar los volúmenes de código fuente:** En producción, el código ya está "congelado" dentro de la imagen gracias a `uv`. Mantener solo los volúmenes de datos (`uploads` y `logs`).

El bloque de volúmenes para esos 3 servicios debe quedar **exactamente así**:

```yaml
    volumes:
      # NO MONTAR ./app ni ./alembic. El código ya vive en la imagen.
      - ./uploads:/home/app/uploads
      - ./logs:/home/app/logs

```

*(Nota: Asegurarse de que las carpetas `./uploads` y `./logs` existan en el servidor host y tengan permisos de escritura).*

## Paso 3: Construcción Inmutable con `uv`

El sistema utiliza `uv` para una resolución de dependencias determinista y ultrarrápida. Se debe construir la imagen sin usar caché para garantizar que tome el `uv.lock` más reciente.

```bash
# Construir las imágenes
docker-compose build --no-cache

# Levantar toda la infraestructura
docker-compose up -d

```

## Paso 4: Migraciones de la Base de Datos

Una vez que los contenedores estén corriendo y PostgreSQL esté listo (sano), es obligatorio aplicar la estructura de la base de datos utilizando Alembic.

```bash
# Ejecutar las migraciones dentro del contenedor del backend usando uv run
docker-compose exec backend uv run alembic upgrade head

```

## Paso 5: Verificación de Salud del Sistema

Para confirmar que todos los engranajes (API, Worker, Beat y Base de datos) se están comunicando correctamente y sin caídas silenciosas:

```bash
# Revisar los logs en tiempo real de toda la infraestructura
docker-compose logs -f

```

Se debe observar que Uvicorn arranca en el puerto 8000, el Worker de Celery se conecta exitosamente a Redis, y el planificador Beat inicializa las tareas periódicas.

## Paso 6: Proxy Inverso y SSL (Recomendación)

El backend expone el puerto `8086` hacia el host (según el `docker-compose.yml`). En producción, **nunca** se debe exponer este puerto directamente a Internet.

* Se debe configurar un **Nginx**, **Traefik** o **Caddy** como proxy inverso que escuche en los puertos `80` y `443` (con certificados SSL/TLS de Let's Encrypt).
* El proxy debe redirigir el tráfico interno hacia `http://localhost:8086`.

---
