"""
Módulo de Servicios

Este paquete contiene la lógica de negocio y las interacciones
con la base de datos para las diferentes entidades de la aplicación.

Cada módulo define un servicio (usualmente una instancia de una clase)
que encapsula las operaciones CRUD y específicas para un modelo ORM.
"""

# Importar instancias de servicio para facilitar el acceso
from .permiso import permiso_service
from .rol import rol_service
from .usuario import usuario_service
from .proveedor import proveedor_service
from .estado_equipo import estado_equipo_service
from .tipo_documento import tipo_documento_service
from .tipo_mantenimiento import tipo_mantenimiento_service
from .equipo import equipo_service
from .equipo_componente import equipo_componente_service
from .movimiento import movimiento_service
from .mantenimiento import mantenimiento_service
from .documentacion import documentacion_service
from .tipo_item_inventario import tipo_item_inventario_service
from .inventario_stock import inventario_stock_service
from .inventario_movimiento import inventario_movimiento_service
from .software_catalogo import software_catalogo_service
from .licencia_software import licencia_software_service
from .asignacion_licencia import asignacion_licencia_service
from .reserva_equipo import reserva_equipo_service
from .notificacion import notificacion_service
from .login_log import login_log_service
from .audit_log import audit_log_service # Servicio opcional para leer auditoría
from .backup_log import backup_log_service # Servicio opcional para leer logs de backup

# Definir __all__ es una buena práctica para indicar qué se exporta públicamente
# aunque no es estrictamente necesario si siempre importas desde app.services.nombre_servicio
__all__ = [
    "permiso_service",
    "rol_service",
    "usuario_service",
    "proveedor_service",
    "estado_equipo_service",
    "tipo_documento_service",
    "tipo_mantenimiento_service",
    "equipo_service",
    "equipo_componente_service",
    "movimiento_service",
    "mantenimiento_service",
    "documentacion_service",
    "tipo_item_inventario_service",
    "inventario_stock_service",
    "inventario_movimiento_service",
    "software_catalogo_service",
    "licencia_software_service",
    "asignacion_licencia_service",
    "reserva_equipo_service",
    "notificacion_service",
    "login_log_service",
    "audit_log_service",
    "backup_log_service",
]
