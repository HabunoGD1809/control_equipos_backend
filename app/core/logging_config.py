import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime

from app.core.config import settings

# Crear directorio de logs si no existe
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Nombre del archivo de log (se puede configurar)
# Usar fecha en nombre previene problemas con múltiples instancias si no rota bien
LOG_FILENAME = LOGS_DIR / f"control_equipos_{datetime.now().strftime('%Y%m%d')}.log"

# Nivel de logging (Leer de config o default)
# LOG_LEVEL_STR = getattr(settings, "LOG_LEVEL", "INFO").upper()
# LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)
LOG_LEVEL = logging.INFO # Mantener simple por ahora

# Formato de los logs
LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)-8s] [%(name)s] [%(process)d:%(threadName)s] [%(filename)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Crear formateador
formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

# Crear manejadores (handlers)
# Handler para consola (siempre útil en desarrollo/contenedores)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(LOG_LEVEL)

# Handler para archivo rotativo por tiempo (diario)
# 'midnight' rota cada medianoche, backupCount guarda 7 archivos viejos
file_handler = TimedRotatingFileHandler(
    filename=LOG_FILENAME,
    when="midnight",
    interval=1,
    backupCount=14, # Guardar logs de las últimas 2 semanas
    encoding='utf-8',
    delay=False # Crear archivo inmediatamente
)
file_handler.setFormatter(formatter)
file_handler.setLevel(LOG_LEVEL)

# Función para configurar el logging al iniciar la app
def setup_logging():
    """Configura los manejadores y el nivel para el logger raíz y loggers específicos."""
    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    # Limpiar handlers existentes para evitar duplicados con --reload
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Configurar nivel de loggers específicos (ej: uvicorn, sqlalchemy)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING) # WARNING para ver errores SQL, INFO para ver todas las queries

    root_logger.info("="*50)
    root_logger.info("Configuración de Logging Iniciada")
    root_logger.info(f"Nivel de Log: {logging.getLevelName(LOG_LEVEL)}")
    root_logger.info(f"Archivo de Log: {LOG_FILENAME}")
    root_logger.info("="*50)

# Para usar en otros módulos:
# import logging
# logger = logging.getLogger(__name__)
# logger.info("Mensaje de prueba")
