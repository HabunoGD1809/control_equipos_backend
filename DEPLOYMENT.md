# Despliegue de Control Equipos

La guía vigente de instalación, migraciones, pruebas y recuperación está en [ENTREGA_DESDE_CERO.md](ENTREGA_DESDE_CERO.md).

Configure .env desde .env.example, incluyendo PostgreSQL, REDIS_PASSWORD, SUPERUSER_* y las dos claves de tokens distintas. Configure FRONTEND_BUILD_CONTEXT si el frontend está en otra ruta.

```bash
docker compose config --quiet
docker compose up --build -d --wait
docker compose ps
docker compose logs --tail 100 backend worker beat frontend
```

Compose incluye el frontend y aplica automáticamente la migración y el administrador. Las imágenes usan usuarios sin privilegios y volúmenes persistentes. Redis exige contraseña y permanece en la red privada. Los puertos publicados se vinculan a loopback. No hace falta quitar usuarios root ni montajes de código de la configuración actual.

Para acceso institucional, configure HTTPS, dominio y un proxy inverso hacia el frontend, preservando SSE sin buffering. Respalde base de datos, archivos y cualquier almacenamiento S3 externo. La migración consolidada es para instalaciones nuevas; no actualiza directamente una base con la cadena antigua archivada.

En Windows, scripts/verify-docker.ps1 verifica el conjunto en un proyecto separado, conserva evidencia y lo elimina al finalizar. Mailpit y MinIO se usan exclusivamente en ese ensayo y no forman parte del despliegue principal.
