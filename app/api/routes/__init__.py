from fastapi import APIRouter

# Importar los routers individuales de cada módulo
from . import auth, usuarios, roles_permisos, proveedores, catalogos, equipos
from . import movimientos, mantenimiento, documentacion, inventario, licencias
from . import reservas, notificaciones, dashboard, auditoria, backup_log

# Crear el router principal de la API
api_router = APIRouter()

# Incluir cada router individual con su prefijo y etiquetas
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(usuarios.router, prefix="/usuarios", tags=["Usuarios"])
api_router.include_router(roles_permisos.router, prefix="/gestion", tags=["Roles y Permisos"]) # Mantenido /gestion como prefijo
api_router.include_router(proveedores.router, prefix="/proveedores", tags=["Proveedores"])
api_router.include_router(catalogos.router, prefix="/catalogos", tags=["Catálogos"]) # Agrupa estados, tipo_doc, tipo_mant
api_router.include_router(equipos.router, prefix="/equipos", tags=["Equipos y Componentes"])
api_router.include_router(movimientos.router, prefix="/movimientos", tags=["Movimientos Equipos"])
api_router.include_router(mantenimiento.router, prefix="/mantenimientos", tags=["Mantenimiento"])
api_router.include_router(documentacion.router, prefix="/documentacion", tags=["Documentación"])
api_router.include_router(inventario.router, prefix="/inventario", tags=["Inventario"])
api_router.include_router(licencias.router, prefix="/licencias", tags=["Licencias"])
api_router.include_router(reservas.router, prefix="/reservas", tags=["Reservas"])
api_router.include_router(notificaciones.router, prefix="/notificaciones", tags=["Notificaciones"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(auditoria.router, prefix="/auditoria", tags=["Auditoría"])
api_router.include_router(backup_log.router, prefix="/backups/logs", tags=["Backups y Logs"]) # Etiqueta más descriptiva

# Nota: Los prefijos y etiquetas ayudan a organizar la documentación de la API.
