from app.db.base import Base

from .audit_log import AuditLog
from .asignacion_licencia import AsignacionLicencia
from .backup_log import BackupLog
from .documentacion import Documentacion
from .equipo import Equipo
from .equipo_componente import EquipoComponente
from .estado_equipo import EstadoEquipo
from .inventario_movimiento import InventarioMovimiento
from .inventario_stock import InventarioStock
from .licencia_software import LicenciaSoftware
from .login_log import LoginLog
from .mantenimiento import Mantenimiento
from .movimiento import Movimiento
from .notificacion import Notificacion
from .permiso import Permiso
from .proveedor import Proveedor
from .reserva_equipo import ReservaEquipo
from .rol import Rol
from .rol_permiso import RolPermiso
from .software_catalogo import SoftwareCatalogo
from .tipo_documento import TipoDocumento
from .tipo_item_inventario import TipoItemInventario
from .tipo_mantenimiento import TipoMantenimiento
from .usuario import Usuario

# Opcionalmente, puedes definir __all__ si quieres controlar lo que se exporta
# cuando alguien hace 'from app.models import *', aunque no es estrictamente necesario
# para el funcionamiento de SQLAlchemy/Alembic si los modelos están importados arriba.
__all__ = [
    "Base", 
    "AuditLog",
    "AsignacionLicencia",
    "BackupLog",
    "Documentacion",
    "Equipo",
    "EquipoComponente",
    "EstadoEquipo",
    "InventarioMovimiento",
    "InventarioStock",
    "LicenciaSoftware",
    "LoginLog",
    "Mantenimiento",
    "Movimiento",
    "Notificacion",
    "Permiso",
    "Proveedor",
    "ReservaEquipo",
    "Rol",
    "RolPermiso",
    "SoftwareCatalogo",
    "TipoDocumento",
    "TipoItemInventario",
    "TipoMantenimiento",
    "Usuario",
]
