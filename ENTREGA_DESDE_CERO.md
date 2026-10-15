# Entrega e instalación desde cero

La instalación inicial utiliza una sola revisión, `f01d20261014_initial_release.py`. Incluye tablas, restricciones, funciones de movimientos y stock, auditoría, particiones, vistas y catálogos esenciales. No contiene personas, equipos, documentos, licencias, contraseñas ni datos DEMO. La cadena anterior se conserva en `backups/migration-history-20261014.zip`; no mezclar una base con la revisión antigua con esta nueva instalación.

## Datos iniciales

Se crean 38 permisos, el rol `admin` con esos permisos, 11 estados de equipo, 11 tipos de documento, 8 tipos de mantenimiento, una ubicación inicial y la configuración de empresa. `scripts/bootstrap.py --from-env` crea únicamente el administrador indicado en `SUPERUSER_*`, verifica su contraseña y exige cambiarla al ingresar. Repetirlo conserva su contraseña y las personalizaciones de los catálogos. `--reset-password` es una operación explícita que revoca sus sesiones.

Los cinco estados operativos tienen códigos estables: `disponible`, `en_uso`, `prestado`, `en_mantenimiento` y `dado_de_baja`. Sus nombres, colores y descripciones pueden personalizarse; las transiciones usan sus códigos y las reglas críticas están protegidas. Los otros estados y los tipos de documento y mantenimiento son catálogos configurables.

## Inicio nativo

Configure `.env` a partir de `.env.example` y cree una base PostgreSQL vacía. Use dos claves de tokens distintas y aleatorias. Después:

```powershell
uv sync --frozen --no-dev
uv run --frozen --no-sync alembic upgrade head
uv run --frozen --no-sync python scripts/bootstrap.py --from-env
.\scripts\start.ps1
```

El frontend usa `API_BASE_URL=http://127.0.0.1:8086/api/v1` en `.env.local`. Instale sus dependencias desde el archivo de bloqueo, compile con `npm run build` y arranque con `npm run start`. En desarrollo se puede usar `npm run dev`. Los reportes funcionan en modo `background` sin Redis.

## Docker Compose

La configuración incluye frontend, backend, PostgreSQL 17, Redis con contraseña, Celery worker y Beat. El código queda dentro de imágenes y los datos en volúmenes persistentes; los procesos de aplicación usan usuarios sin privilegios. Redis no expone un puerto al host. Los puertos del frontend, API y PostgreSQL se vinculan a `127.0.0.1`.

Configure `REDIS_PASSWORD` además de los datos de PostgreSQL y `SUPERUSER_*`. `FRONTEND_BUILD_CONTEXT` permite indicar la ruta del frontend si la estructura de carpetas difiere. Compose establece las conexiones internas de PostgreSQL y Redis y usa `REPORT_EXECUTION_MODE=celery`.

```powershell
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
```

El backend aplica la migración y prepara el administrador automáticamente. No se necesita crear cuentas adicionales. Acceso local: `http://localhost:3000`; salud del frontend: `/api/health`; salud del backend: `http://localhost:8086/health`.

Para un servidor institucional, configure HTTPS y un proxy inverso hacia el frontend. Las cookies de producción requieren un contexto seguro. Preserve la conexión SSE sin buffering. No publique directamente PostgreSQL ni Redis. Configure el dominio, certificados y copia externa de los respaldos antes de abrir el acceso a usuarios.

## Configuración funcional inicial

1. Ingresar con el administrador configurado y cambiar su contraseña.
2. Configurar Empresa: nombre, logo y datos de contacto.
3. Crear los departamentos, ubicaciones, empleados, técnicos, proveedores y marcas reales que se utilizarán.
4. Registrar activos con serie única y sus características; registrar consumibles con color, rendimiento y compatibilidad cuando corresponda.
5. Asignar equipos mediante Movimientos para conservar el custodio, el usuario que registra la acción y la persona que recibe físicamente. Un empleado puede recibir sin tener cuenta de acceso; las recepciones externas se identifican separadamente.
6. Registrar abastecimientos con procedencia y acta, remisión, orden o factura. Adjuntar documentos a equipos, mantenimientos o licencias para mantener su expediente.
7. Crear los roles y cuentas de trabajo con los permisos necesarios. Conservar el administrador para configuración y recuperación.

## Pruebas reproducibles

`scripts/test.ps1` utiliza una base separada con `test` en su nombre. La regresión de API y `scripts/verify_integration.py` cubren estados, custodios, permisos, recepción, reservas, mantenimiento, stock concurrente, documentos, licencias, sesiones y 21 exportaciones. No ejecutar pytest sobre la base principal.

La prueba real de contenedores se ejecuta desde PowerShell normal con Docker Desktop activo:

```powershell
.\scripts\verify-docker.ps1
```

Crea un proyecto único `control-equipos-test-*`, contraseñas aleatorias y volúmenes propios. Prueba PostgreSQL, Redis autenticado, Celery, Beat, reportes, SSE, SMTP capturado en Mailpit, fotos S3 privadas, restauración de respaldo, persistencia tras reinicio y caída controlada de Redis. Al finalizar elimina solo los contenedores y volúmenes de ese proyecto; conserva evidencia y registros en `verification/<proyecto>/`. `-KeepStack` permite conservarlo para investigar un fallo.

MinIO se construye desde una versión oficial fijada y se usa únicamente como proveedor compatible con S3 para esta prueba. No forma parte del despliegue principal ni es una recomendación de almacenamiento de producción; su repositorio está archivado. [Fuente oficial de la versión](https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z).

Las pruebas del frontend están en `tests/*.test.ts` y `tests/e2e`. Playwright verifica pantallas por rol, móvil y escritorio, formularios, archivos, identidad de empresa, foto y notificaciones. Prepare los datos con `scripts/prepare_e2e.py` en una base separada, arranque la API y el frontend de pruebas apuntando a ella y configure `E2E_DATA_FILE` y `E2E_BASE_URL`. Antes de cualquier modificación, la prueba compara `/api/health` con el nombre de esa base. `--first-login-only` restablece únicamente las dos cuentas de primer acceso para repetir ese escenario.

Si prueba una compilación de producción, configure también `E2E_BUILD_ID` con el contenido de `BUILD_ID` de su directorio de compilación. Esto evita validar por error una instancia anterior. La construcción no necesita una API en ejecución; el servidor lee `API_BASE_URL` al atender solicitudes. Las páginas comparten el cliente y la paginación del servidor. El catálogo de software permite lectura sin permiso de edición; su mantenimiento usa `administrar_software_catalogo`. Asignar una licencia permite consultar identidades mínimas mediante `/licencias/destinatarios`, sin habilitar la administración de usuarios.

Movimientos consulta su historial sin acceder al listado administrativo de usuarios y carga los selectores según los permisos del perfil. La publicación de reportes en Celery no se suscribe a resultados de Redis: el historial y los archivos se consultan en PostgreSQL. Ante un fallo de publicación, la solicitud devuelve 503 y conserva el reporte con estado de error; una tarea ya encolada se recupera al volver Redis y el trabajador.

```powershell
# En el frontend, después de preparar y arrancar el entorno aislado:
npx playwright install chromium
npm test
npm run typecheck
npm run lint
npm run test:e2e
```

## Reinicio de datos y recuperación

`scripts/initialize_release.py --database NOMBRE --reset-existing` es destructivo y está destinado únicamente a una entrega vacía explícitamente solicitada. Detenga primero API, worker y Beat. Exige el nombre exacto de la base local configurada y el directorio uploads exacto del proyecto; valida las credenciales, genera un ZIP y lo restaura en otra base antes de borrar el esquema de la aplicación. Conserva los archivos anteriores en `backups/clean-delivery-*/uploads_previous`, aplica la revisión inicial y crea solo `admin`. No usar para actualizar una instalación con datos reales.

Los respaldos contienen `database.dump`, archivos locales y un manifiesto. La carpeta `backups` y las credenciales de pruebas no se publican en Git ni en las imágenes. Conserve respaldos fuera del disco del servidor y ensaye su restauración. Un respaldo anterior a la nueva migración requiere su cadena histórica; no marcarlo como `f01d20261014` sin verificar su esquema.

Si utiliza S3, respalde sus objetos por separado. S3 se utiliza para fotos de perfil; los documentos y reportes utilizan el volumen persistente de archivos locales. SMTP es opcional para la tarea de correo; las notificaciones habituales aparecen dentro de la aplicación. La recuperación de contraseña se administra mediante un token privado y no presupone correo automático.
