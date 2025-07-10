# =================================================================
# Roles del Sistema
# =================================================================
# Nombres de los roles definidos en la base de datos.
# Total: 6 roles.
# =================================================================

ADMIN_ROLE_NAME = "admin"
SUPERVISOR_ROLE_NAME = "supervisor"
AUDITOR_ROLE_NAME = "auditor"
TECNICO_ROLE_NAME = "tecnico"
USUARIO_REGULAR_ROLE_NAME = "usuario_regular"
TESTER_ROLE_NAME = "tester"


# =================================================================
# Permisos del Sistema
# =================================================================
# Nombres de todos los permisos definidos en la base de datos.
# Total: 38 permisos.
# =================================================================

# --- Permisos de Administración y Configuración ---
PERM_ADMINISTRAR_CATALOGOS = "administrar_catalogos"
PERM_ADMINISTRAR_ROLES = "administrar_roles"
PERM_ADMINISTRAR_SISTEMA = "administrar_sistema"
PERM_ADMINISTRAR_SOFTWARE_CATALOGO = "administrar_software_catalogo"
PERM_ADMINISTRAR_USUARIOS = "administrar_usuarios"
PERM_CONFIGURAR_SISTEMA = "configurar_sistema"
PERM_VER_AUDITORIA = "ver_auditoria"
PERM_VER_DASHBOARD = "ver_dashboard"
PERM_VER_PROVEEDORES = "ver_proveedores"
PERM_GENERAR_REPORTES = "generar_reportes"

# --- Permisos de Equipos ---
PERM_CREAR_EQUIPOS = "crear_equipos"
PERM_EDITAR_EQUIPOS = "editar_equipos"
PERM_ELIMINAR_EQUIPOS = "eliminar_equipos"
PERM_GESTIONAR_COMPONENTES = "gestionar_componentes"
PERM_VER_EQUIPOS = "ver_equipos"

# --- Permisos de Movimientos ---
PERM_AUTORIZAR_MOVIMIENTOS = "autorizar_movimientos"
PERM_CANCELAR_MOVIMIENTOS = "cancelar_movimientos"
PERM_EDITAR_MOVIMIENTOS = "editar_movimientos"
PERM_REGISTRAR_MOVIMIENTOS = "registrar_movimientos"
PERM_VER_MOVIMIENTOS = "ver_movimientos"

# --- Permisos de Mantenimiento ---
PERM_EDITAR_MANTENIMIENTOS = "editar_mantenimientos"
PERM_ELIMINAR_MANTENIMIENTOS = "eliminar_mantenimientos"
PERM_PROGRAMAR_MANTENIMIENTOS = "programar_mantenimientos"
PERM_VER_MANTENIMIENTOS = "ver_mantenimientos"

# --- Permisos de Documentación ---
PERM_EDITAR_DOCUMENTOS = "editar_documentos"
PERM_ELIMINAR_DOCUMENTOS = "eliminar_documentos"
PERM_SUBIR_DOCUMENTOS = "subir_documentos"
PERM_VER_DOCUMENTOS = "ver_documentos"
PERM_VERIFICAR_DOCUMENTOS = "verificar_documentos"

# --- Permisos de Inventario ---
PERM_ADMINISTRAR_INVENTARIO_STOCK = "administrar_inventario_stock"
PERM_ADMINISTRAR_INVENTARIO_TIPOS = "administrar_inventario_tipos"
PERM_VER_INVENTARIO = "ver_inventario"

# --- Permisos de Licencias ---
PERM_ADMINISTRAR_LICENCIAS = "administrar_licencias"
PERM_ASIGNAR_LICENCIAS = "asignar_licencias"
PERM_VER_LICENCIAS = "ver_licencias"

# --- Permisos de Reservas ---
PERM_APROBAR_RESERVAS = "aprobar_reservas"
PERM_RESERVAR_EQUIPOS = "reservar_equipos"
PERM_VER_RESERVAS = "ver_reservas"
