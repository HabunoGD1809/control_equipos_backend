import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# 1. Definir BASE_DIR de forma absoluta y dinámica.
# Desde core/logging_config.py -> parent(core) -> parent(app) -> parent(root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"

LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)-8s] [%(name)s] [%(process)d:%(threadName)s] [%(filename)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logging():
    """Configura los manejadores y el nivel para el logger raíz y loggers específicos."""
    
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    LOG_FILENAME = LOGS_DIR / "control_equipos.log"

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(LOG_LEVEL)

    file_handler = TimedRotatingFileHandler(
        filename=LOG_FILENAME,
        when="midnight",
        interval=1,
        backupCount=14, 
        encoding='utf-8',
        delay=True
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(LOG_LEVEL)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    root_logger.handlers.clear()
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Bajar el ruido de loggers externos
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    root_logger.info("="*50)
    root_logger.info("Configuración de Logging Inicializada")
    root_logger.info(f"Ruta Base Absoluta: {BASE_DIR}")
    root_logger.info("="*50)
