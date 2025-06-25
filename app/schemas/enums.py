from enum import Enum

class EstadoMantenimientoEnum(str, Enum):
    PROGRAMADO = 'Programado'
    EN_PROCESO = 'En Proceso'
    COMPLETADO = 'Completado'
    CANCELADO = 'Cancelado'
    PENDIENTE_APROBACION = 'Pendiente Aprobacion' # Usado en la BD
    REQUIERE_PIEZAS = 'Requiere Piezas'
    PAUSADO = 'Pausado'

class UnidadMedidaEnum(str, Enum):
    UNIDAD = 'Unidad'
    METRO = 'Metro'
    KILOGRAMO = 'Kg' # CORREGIDO: De 'Kilogramo' a 'Kg' para coincidir con SQL
    LITRO = 'Litro'
    CAJA = 'Caja'
    PAQUETE = 'Paquete'
    # Añadir otras unidades si es necesario

class TipoMovimientoInvEnum(str, Enum):
    # --- Valores según la constraint CHECK de la BD ---
    # Estos deben coincidir exactamente con los valores permitidos en
    # la restricción CHECK de la tabla 'inventario_movimientos'
    ENTRADA_COMPRA = 'Entrada Compra'
    SALIDA_USO = 'Salida Uso'
    SALIDA_DESCARTE = 'Salida Descarte'
    AJUSTE_POSITIVO = 'Ajuste Positivo'
    AJUSTE_NEGATIVO = 'Ajuste Negativo'
    TRANSFERENCIA_SALIDA = 'Transferencia Salida'
    TRANSFERENCIA_ENTRADA = 'Transferencia Entrada'
    DEVOLUCION_PROVEEDOR = 'Devolucion Proveedor'
    DEVOLUCION_INTERNA = 'Devolucion Interna' # Asumiendo que es una devolución de un departamento a almacén
    # --- FIN Valores de BD ---

class TipoRelacionComponenteEnum(str, Enum):
    """
    Define los tipos de relación que un equipo componente puede tener con un equipo padre.
    Estos valores deben coincidir con la restricción CHECK en la tabla equipo_componentes.
    """
    INSTALADO_EN = 'Instalado en'         # Ej: RAM instalada en una Laptop
    CONECTADO_A = 'Conectado a'          # Ej: Monitor conectado a una PC
    SOFTWARE_ASOCIADO = 'Software asociado' # Ej: Licencia de Office asociada a una PC
    PARTE_DE = 'Parte de'              # Ej: Batería como parte de una Laptop (más genérico)
    ACCESORIO_DE = 'Accesorio de'        # Ej: Mouse como accesorio de una Laptop
    CONSUMIBLE_PARA = 'Consumible para'    # Ej: Toner para una Impresora (aunque esto podría ir más en inventario)
    OTRO = 'Otro'                      # Para relaciones no especificadas

class EstadoReservaEnum(str, Enum):
    """
    Define los estados posibles para una reserva de equipo.
    Estos valores deben coincidir con la restricción CHECK en la tabla reservas_equipo.
    """
    PENDIENTE_APROBACION = "Pendiente Aprobacion"
    CONFIRMADA = "Confirmada"
    RECHAZADA = "Rechazada"
    CANCELADA_USUARIO = "Cancelada por Usuario"
    EN_CURSO = "En Curso"
    COMPLETADA = "Completada"
    NO_ASISTIO = "No Asistio" # El usuario no recogió el equipo

class EstadoDocumentoEnum(str, Enum):
    """
    Define los estados posibles para un documento.
    Estos valores deben coincidir con la restricción CHECK en la tabla documentacion.
    """
    PENDIENTE = "Pendiente" # Pendiente de verificación/aprobación
    APROBADO = "Aprobado"   # Verificado y aprobado
    RECHAZADO = "Rechazado" # No aprobado
    OBSOLETO = "Obsoleto"   # Ya no es la versión actual o relevante

class TipoNotificacionEnum(str, Enum):
    """
    Define los tipos de notificaciones que se pueden generar.
    """
    INFO = "info"
    ADVERTENCIA = "advertencia"
    ERROR = "error"
    MANTENIMIENTO = "mantenimiento"
    RESERVA = "reserva"
    LICENCIA = "licencia"
    DOCUMENTO = "documento"
    SISTEMA = "sistema"

# Puedes añadir más Enums según las necesidades de tu aplicación,
# por ejemplo, para tipos de licencia, métricas de licenciamiento, etc.
# Asegúrate de que los valores coincidan con las restricciones CHECK de la base de datos
# si los usas para columnas con dichas restricciones.

class MetricaLicenciamientoEnum(str, Enum):
    POR_DISPOSITIVO = "Por Dispositivo"
    POR_USUARIO = "Por Usuario"
    POR_NUCLEO = "Por Núcleo (Core)"
    POR_CONCURRENCIA = "Por Concurrencia"
    VOLUMEN = "Volumen (MAK/VLK)"
    SUSCRIPCION_ANUAL = "Suscripción Anual"
    SUSCRIPCION_MENSUAL = "Suscripción Mensual"
    OTRA = "Otra"

class TipoLicenciaSoftwareEnum(str, Enum):
    PERPETUA = "Perpetua"
    SUSCRIPCION = "Suscripción"
    OEM = "OEM (Original Equipment Manufacturer)"
    RETAIL = "Retail (FPP - Full Packaged Product)"
    VOLUMEN = "Volumen (Open, Select, EA)"
    CLOUD_BASED = "Cloud-based (SaaS)"
    FREEWARE = "Freeware"
    SHAREWARE = "Shareware"
    OPEN_SOURCE = "Open Source"
    OTRA = "Otra"

class EstadoAsignacionLicenciaEnum(str, Enum):
    ASIGNADA = "Asignada"
    DEVUELTA = "Devuelta" # Cuando una licencia se desasigna y vuelve al pool disponible
    RETIRADA = "Retirada" # Cuando la licencia se da de baja permanentemente
