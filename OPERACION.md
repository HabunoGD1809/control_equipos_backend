# Operación y recuperación

## Arranque local en Windows

Requisitos: PostgreSQL disponible en `127.0.0.1:5433`, Python 3.11 o posterior y uv. El proyecto actual ya tiene `.env` configurado. En instalaciones nuevas copie `.env.example`, configure las credenciales y genere dos claves aleatorias diferentes para los tokens.

```powershell
cd C:\Users\fjvaldez\Desktop\control_equipos_backend
.\scripts\start.ps1
```

El script instala desde `uv.lock`, migra la base y prepara el administrador sin borrar datos ni cambiar una contraseña existente. API: `http://127.0.0.1:8086`; documentación: `/api/v1/docs`. Los reportes y sus tareas de mantenimiento funcionan localmente sin Redis.

## Administrador

El usuario inicial es `admin`. Su contraseña procede de `SUPERUSER_PASSWORD` en `.env`; deberá cambiarla al ingresar. No se escriben contraseñas en la salida de los scripts.

Para preparar el administrador en otra instalación:

```powershell
uv run --frozen python scripts/initialize.py
```

Para recuperar explícitamente el acceso:

```powershell
uv run --frozen python scripts/bootstrap.py --from-env --reset-password
```

Ese restablecimiento revoca las sesiones existentes. También se puede ejecutar `bootstrap.py` sin `--from-env` para ingresar las credenciales de forma interactiva.

La limpieza de datos de prueba ya se ejecutó en `control_equipos_dbv1`; no vuelva a ejecutarla para arrancar. Para una limpieza deliberada en el futuro, `initialize.py --reset-test-data --database NOMBRE_EXACTO` exige que el nombre coincida con la configuración y guarda un respaldo previo de la base y los archivos locales.

## Empresa, inventario y custodia

En el frontend, Administración → Empresa permite cambiar el nombre, contactos y logo PNG/JPEG/WebP de hasta 2 MB. Aparecen en el login y los reportes.

Los tóneres permiten color, tecnología, rendimiento, fabricante, condición original y modelos compatibles. Registre compras, consumos, devoluciones y transferencias para conservar el kardex. Un lote se corrige mediante transferencia entre lotes, incluso dentro de la misma ubicación. No cambie directamente la identidad de un saldo que tiene movimientos.

La recepción, devolución, reserva y mantenimiento de un equipo incluyen sus componentes físicos. Verifique el conjunto completo al recibir. Las operaciones pendientes requieren su aprobación; los préstamos sin devolver y los mantenimientos activos bloquean movimientos incompatibles. Los historiales y las bajas finales se protegen de modificaciones destructivas.

## Reportes y respaldos

Siete módulos exportan PDF, Excel `.xlsx` y CSV: equipos, movimientos, mantenimiento, inventario, kardex, licencias y auditoría. Las fechas de los reportes usan UTC y se indica en los archivos. Los reportes caducan a las 24 horas; la descarga exige autorización. El límite de exportación es de 50.000 registros y se informa cuando se excede, sin entregar un archivo truncado.

Administración → Backups genera un ZIP privado con `database.dump`, los archivos de `UPLOADS_DIRECTORY`, un manifiesto e instrucciones. Necesita `pg_dump` y `pg_restore`; en Windows se detectan también bajo `C:\Program Files\PostgreSQL`. El contenedor instala estas herramientas y conserva un volumen independiente para respaldos. Solo los administradores pueden descargarlos.

Para restaurar: detenga las aplicaciones, extraiga el ZIP, cree una base vacía y use `pg_restore --exit-on-error --no-owner --dbname NOMBRE database.dump`, configurando host, puerto y usuario apropiados. Restaure `uploads` en `UPLOADS_DIRECTORY`, ajuste `.env` y arranque. Conserve una copia previa antes de reemplazar datos activos. Si usa S3/MinIO, respalde ese almacenamiento por separado: el ZIP contiene archivos locales. Mantenga copias de los respaldos fuera del mismo disco y pruebe periódicamente la restauración.

El respaldo inmediatamente anterior a la entrega limpia del 14 de octubre está en `backups/control_equipos_dbv1_20261014_201525_90fc2135.zip`. Se restauró y comparó antes del reinicio. Los archivos anteriores están en `backups/clean-delivery-20261014-201525-3e2a4253/uploads_previous`; `results.json` contiene los recuentos posteriores. Estas carpetas y `.env` están excluidas de Git. Un respaldo con la cadena antigua requiere su historial archivado; no marcarlo como la migración inicial nueva sin verificar el esquema.

## Pruebas y despliegue

```powershell
.\scripts\test.ps1
```

El script usa una base separada cuyo nombre contiene `test`, aplica migraciones y ejecuta la regresión y los flujos completos con 21 reportes. No ejecute pytest sobre la base operativa; las pruebas lo rechazan. `scripts/verify_integration.py` acepta `--database`, `--host`, `--port` y `--output` para repetir la integración en una base de pruebas migrada.

Docker Compose incluye frontend, PostgreSQL 17, Redis autenticado, API, worker y Beat. El ensayo real de `scripts/verify-docker.ps1` comprobó reportes, notificaciones SSE, correo capturado, fotos S3 privadas, restauración de respaldo y reinicios/caída de Redis en un proyecto aislado. Configure HTTPS y el dominio de la institución antes de publicar el acceso. Consulte [ENTREGA_DESDE_CERO.md](ENTREGA_DESDE_CERO.md) para la instalación completa y la migración consolidada. SMTP es opcional para la tarea de correo; la recuperación de contraseña se administra con un token privado. Las fotos pueden utilizar S3; los documentos y reportes usan archivos locales persistentes.
