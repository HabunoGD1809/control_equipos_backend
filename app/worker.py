import logging.config # Importar logging config
from celery import Celery

# Importar configuración de la aplicación principal
from app.core.config import settings
# Importar configuración de logging para que el worker también loggee
from app.core.logging_config import setup_logging

# Configurar logging para el worker ANTES de definir tareas
setup_logging()
logger = logging.getLogger(__name__)
logger.info("Configurando Celery worker...")

# Crear instancia de Celery
# El primer argumento es el nombre del módulo actual (importante para auto-descubrimiento)
# 'broker' y 'backend' se leen de la configuración
celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    # Incluir los módulos donde están definidas las tareas
    include=["app.tasks.maintenance_tasks", "app.tasks.notification_tasks", "app.tasks.report_tasks"]
)

# Opcional: Configuración adicional de Celery
celery_app.conf.update(
    task_serializer="json", # Usar json para serializar argumentos de tareas
    accept_content=["json"],  # Aceptar solo contenido json
    result_serializer="json", # Usar json para resultados
    timezone="UTC", # Usar UTC para horarios consistentes
    enable_utc=True,
    # Configuración de reintentos, colas, etc., podría ir aquí
    # task_track_started=True, # Útil para monitoreo
)

logger.info(f"Celery worker configurado. Broker: {settings.CELERY_BROKER_URL}")

# Para ejecutar el worker desde la línea de comandos (estando en el directorio raíz del proyecto):
# celery -A app.worker worker --loglevel=info
