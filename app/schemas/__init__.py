from .common import Msg

# Token & Auth
from .token import Token, TokenPayload
# from .auth import LoginRequest # LoginRequest es opcional si se usa OAuth2PasswordRequestForm

# Roles y Permisos
from .permiso import Permiso, PermisoCreate, PermisoUpdate
from .rol import Rol, RolCreate, RolUpdate

# Usuario
from .usuario import Usuario, UsuarioCreate, UsuarioUpdate, UsuarioSimple

# Proveedor
from .proveedor import Proveedor, ProveedorCreate, ProveedorUpdate, ProveedorSimple

# Estados Equipo (Catálogo)
from .estado_equipo import EstadoEquipo, EstadoEquipoCreate, EstadoEquipoUpdate, EstadoEquipoSimple # anadido ahora

# Tipos Documento (Catálogo)
from .tipo_documento import TipoDocumento, TipoDocumentoCreate, TipoDocumentoUpdate

# Tipos Mantenimiento (Catálogo)
from .tipo_mantenimiento import TipoMantenimiento, TipoMantenimientoCreate, TipoMantenimientoUpdate

# Equipo y Componentes
from .equipo import (
    EquipoBase,
    EquipoCreate,
    EquipoUpdate,
    EquipoSimple,
    EquipoRead, 
    EquipoSearchResult,
    GlobalSearchResult
)

from .equipo_componente import (
    EquipoComponente,
    EquipoComponenteCreate,
    EquipoComponenteUpdate,
    ComponenteInfo,
    PadreInfo,
)

# Movimientos de Equipos
from .movimiento import Movimiento, MovimientoCreate, MovimientoUpdate

# Mantenimiento
from .mantenimiento import (
    Mantenimiento, MantenimientoCreate, MantenimientoUpdate, MantenimientoSimple
)

# Documentacion
from .documentacion import (
    Documentacion,
    DocumentacionCreateInternal,
    DocumentacionUpdate,
    DocumentacionVerify,
    DocumentacionSimple,
)

# Inventario
from .tipo_item_inventario import (
    TipoItemInventario,
    TipoItemInventarioCreate,
    TipoItemInventarioUpdate,
    TipoItemInventarioSimple,
)
from .inventario_stock import InventarioStock, InventarioStockUpdate
from .inventario_movimiento import (
    InventarioMovimiento, InventarioMovimientoCreate, InventarioMovimientoUpdate 
)

# Licencias de Software
from .software_catalogo import (
    SoftwareCatalogo,
    SoftwareCatalogoCreate,
    SoftwareCatalogoUpdate,
    SoftwareCatalogoSimple,
)
from .licencia_software import (
    LicenciaSoftware,
    LicenciaSoftwareCreate,
    LicenciaSoftwareUpdate,
    LicenciaSoftwareSimple,
)
from .asignacion_licencia import (
    AsignacionLicencia,
    AsignacionLicenciaCreate,
    AsignacionLicenciaUpdate,
)

# Reservas
from .reserva_equipo import (
    ReservaEquipo,
    ReservaEquipoCreate,
    ReservaEquipoUpdate,
    ReservaEquipoUpdateEstado,
    ReservaEquipoCheckInOut,
)

# Notificaciones y Logs
from .notificacion import Notificacion, NotificacionUpdate # Create es interno
from .login_log import LoginLog
from .audit_log import AuditLog
from .backup_log import BackupLog

# Dashboard
from .dashboard import DashboardData, EquipoPorEstado

EquipoRead.model_rebuild()
ComponenteInfo.model_rebuild()
PadreInfo.model_rebuild()
EquipoComponente.model_rebuild()

__all__ = [
    "Msg", "Token", "TokenPayload", #"LoginRequest",
    "Permiso", "PermisoCreate", "PermisoUpdate",
    "Rol", "RolCreate", "RolUpdate",
    "Usuario", "UsuarioCreate", "UsuarioUpdate", "UsuarioSimple",
    "Proveedor", "ProveedorCreate", "ProveedorUpdate", "ProveedorSimple",
    "EstadoEquipo", "EstadoEquipoCreate", "EstadoEquipoUpdate", "EstadoEquipoSimple",
    "TipoDocumento", "TipoDocumentoCreate", "TipoDocumentoUpdate",
    "TipoMantenimiento", "TipoMantenimientoCreate", "TipoMantenimientoUpdate",
    "EquipoCreate", "EquipoUpdate", "EquipoSimple", "EquipoSearchResult", "GlobalSearchResult", "EquipoRead", #"Equipo",
    "EquipoComponente", "EquipoComponenteCreate", "EquipoComponenteUpdate", "ComponenteInfo", "PadreInfo",
    "Movimiento", "MovimientoCreate", "MovimientoUpdate",
    "Mantenimiento", "MantenimientoCreate", "MantenimientoUpdate", "MantenimientoSimple",
    "Documentacion", "DocumentacionCreateInternal", "DocumentacionUpdate", "DocumentacionVerify", "DocumentacionSimple",
    "TipoItemInventario", "TipoItemInventarioCreate", "TipoItemInventarioUpdate", "TipoItemInventarioSimple",
    "InventarioStock", "InventarioStockUpdate",
    "InventarioMovimiento", "InventarioMovimientoCreate", "InventarioMovimientoUpdate",
    "SoftwareCatalogo", "SoftwareCatalogoCreate", "SoftwareCatalogoUpdate", "SoftwareCatalogoSimple",
    "LicenciaSoftware", "LicenciaSoftwareCreate", "LicenciaSoftwareUpdate", "LicenciaSoftwareSimple",
    "AsignacionLicencia", "AsignacionLicenciaCreate", "AsignacionLicenciaUpdate",
    "ReservaEquipo", "ReservaEquipoCreate", "ReservaEquipoUpdate", "ReservaEquipoUpdateEstado", "ReservaEquipoCheckInOut",
    "Notificacion", "NotificacionUpdate",
    "LoginLog", "AuditLog", "BackupLog",
    "DashboardData", "EquipoPorEstado",
]
