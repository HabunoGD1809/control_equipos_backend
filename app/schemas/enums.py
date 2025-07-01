from enum import Enum

class EstadoMantenimientoEnum(str, Enum):
    """Valores que coinciden con el CHECK constraint de la tabla `mantenimiento`."""
    PROGRAMADO = 'Programado'
    EN_PROCESO = 'En Proceso'
    COMPLETADO = 'Completado'
    CANCELADO = 'Cancelado'
    PENDIENTE_APROBACION = 'Pendiente Aprobacion'
    REQUIERE_PIEZAS = 'Requiere Piezas'
    PAUSADO = 'Pausado'

class UnidadMedidaEnum(str, Enum):
    """Valores que coinciden con la definición en la tabla `tipos_item_inventario`."""
    UNIDAD = 'Unidad'
    METRO = 'Metro'
    KILOGRAMO = 'Kg'
    LITRO = 'Litro'
    CAJA = 'Caja'
    PAQUETE = 'Paquete'

class TipoMovimientoInvEnum(str, Enum):
    """Valores que coinciden con el CHECK constraint de la tabla `inventario_movimientos`."""
    ENTRADA_COMPRA = 'Entrada Compra'
    SALIDA_USO = 'Salida Uso'
    SALIDA_DESCARTE = 'Salida Descarte'
    AJUSTE_POSITIVO = 'Ajuste Positivo'
    AJUSTE_NEGATIVO = 'Ajuste Negativo'
    TRANSFERENCIA_SALIDA = 'Transferencia Salida'
    TRANSFERENCIA_ENTRADA = 'Transferencia Entrada'
    DEVOLUCION_PROVEEDOR = 'Devolucion Proveedor'
    DEVOLUCION_INTERNA = 'Devolucion Interna'

class TipoRelacionComponenteEnum(str, Enum):
    """Valores que coinciden con el CHECK constraint de la tabla `equipo_componentes`."""
    COMPONENTE = 'componente'
    CONECTADO_A = 'conectado_a'
    PARTE_DE = 'parte_de'
    ACCESORIO = 'accesorio'

class EstadoReservaEnum(str, Enum):
    """Valores que coinciden con el CHECK constraint de la tabla `reservas_equipo`."""
    PENDIENTE_APROBACION = "Pendiente Aprobacion"
    CONFIRMADA = "Confirmada"
    RECHAZADA = "Rechazada"
    CANCELADA = "Cancelada"
    CANCELADA_USUARIO = "Cancelada por Usuario"
    CANCELADA_GESTOR = "Cancelada por Gestor"
    EN_CURSO = "En Curso"
    FINALIZADA = "Finalizada"

class EstadoDocumentoEnum(str, Enum):
    """Valores que coinciden con el CHECK constraint de la tabla `documentacion`."""
    PENDIENTE = "Pendiente"
    VERIFICADO = "Verificado"
    RECHAZADO = "Rechazado"

class TipoNotificacionEnum(str, Enum):
    """Valores que coinciden con el CHECK constraint de la tabla `notificaciones`."""
    INFO = "info"
    ALERTA = "alerta"
    ERROR = "error"
    MANTENIMIENTO = "mantenimiento"
    RESERVA = "reserva"
    SISTEMA = "sistema"

class TipoLicenciaSoftwareEnum(str, Enum):
    """Valores que coinciden con el CHECK constraint de la tabla `software_catalogo`."""
    PERPETUA = 'Perpetua'
    SUSCRIPCION_ANUAL = 'Suscripción Anual'
    SUSCRIPCION_MENSUAL = 'Suscripción Mensual'
    OEM = 'OEM'
    FREEWARE = 'Freeware'
    OPEN_SOURCE = 'Open Source'
    OTRA = 'Otra'

class MetricaLicenciamientoEnum(str, Enum):
    """Valores que coinciden con el CHECK constraint de la tabla `software_catalogo`."""
    POR_DISPOSITIVO = 'Por Dispositivo'
    POR_USUARIO_NOMINAL = 'Por Usuario Nominal'
    POR_USUARIO_CONCURRENTE = 'Por Usuario Concurrente'
    POR_CORE = 'Por Core'
    POR_SERVIDOR = 'Por Servidor'
    GRATUITA = 'Gratuita'
    OTRA = 'Otra'

class CategoriaItemInventarioEnum(str, Enum):
    """Valores que coinciden con el CHECK constraint de la tabla `tipos_item_inventario`."""
    CONSUMIBLE = 'Consumible'
    PARTE_REPUESTO = 'Parte Repuesto'
    ACCESORIO = 'Accesorio'
    OTRO = 'Otro'

# --- ENUMS NUEVOS ---
class TipoMovimientoEquipoEnum(str, Enum):
    """Valores que coinciden con el CHECK constraint de la tabla `movimientos`."""
    SALIDA_TEMPORAL = 'Salida Temporal'
    SALIDA_DEFINITIVA = 'Salida Definitiva'
    ENTRADA = 'Entrada'
    ASIGNACION_INTERNA = 'Asignacion Interna'
    TRANSFERENCIA_BODEGA = 'Transferencia Bodega'

class EstadoMovimientoEquipoEnum(str, Enum):
    """Valores que coinciden con el CHECK constraint de la tabla `movimientos`."""
    PENDIENTE = 'Pendiente'
    AUTORIZADO = 'Autorizado'
    EN_PROCESO = 'En Proceso'
    COMPLETADO = 'Completado'
    CANCELADO = 'Cancelado'
    RECHAZADO = 'Rechazado'

