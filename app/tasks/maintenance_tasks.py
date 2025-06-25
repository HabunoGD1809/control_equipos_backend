import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

# Importar Celery app (definida en worker.py) y sesión de DB
from app.worker import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.refresh_materialized_views")
def task_refresh_materialized_views() -> str:
    """
    Tarea Celery para refrescar las vistas materializadas en la base de datos.
    """
    logger.info("Iniciando tarea: Refrescar Vistas Materializadas")
    db: Session = SessionLocal()
    try:
        # Llamar a la función SQL directamente
        stmt = text("SELECT control_equipos.refresh_materialized_views();")
        db.execute(stmt)
        db.commit()
        logger.info("Tarea completada: Vistas Materializadas refrescadas.")
        return "Vistas refrescadas exitosamente."
    except Exception as e:
        db.rollback()
        logger.error(f"Error en tarea refresh_materialized_views: {e}", exc_info=True)
        # Podríamos reintentar la tarea usando las opciones de Celery
        # raise self.retry(exc=e, countdown=60) # Reintentar en 60 segundos
        return f"Error al refrescar vistas: {e}"
    finally:
        db.close()
