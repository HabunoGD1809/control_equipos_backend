import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select

# Importar modelos
from app.models.backup_log import BackupLog as BackupLogModel
# El schema BackupLogSchema no se usa directamente en el servicio,
# pero las rutas lo usarán para la validación de la respuesta.

logger = logging.getLogger(__name__) # Configurar logger

class BackupLogService:
    """
    Servicio para CONSULTAR los logs de backups.
    La creación y actualización de estos logs se asume que es manejada por
    funciones de base de datos (ej. registrar_inicio_backup, registrar_fin_backup)
    llamadas por un proceso/script de backup externo.
    """
    model = BackupLogModel

    def get(self, db: Session, id: UUID) -> Optional[BackupLogModel]:
        """Obtiene un log de backup por su ID."""
        logger.debug(f"Obteniendo log de backup por ID: {id}")
        statement = select(self.model).where(self.model.id == id) # type: ignore[attr-defined]
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        backup_status: Optional[str] = None, # Renombrado de 'status' para evitar colisión con built-in
        backup_type: Optional[str] = None,   # Renombrado de 'type'
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[BackupLogModel]:
        """
        Obtiene logs de backup con filtros opcionales, ordenados por fecha descendente.
        """
        logger.debug(
            f"Listando logs de backup con filtros: Status='{backup_status}', Type='{backup_type}', "
            f"RangoTiempo='{start_time}-{end_time}' (Skip: {skip}, Limit: {limit})"
        )
        statement = select(self.model) # type: ignore[var-annotated]
        
        if backup_status:
            statement = statement.where(self.model.backup_status == backup_status) # type: ignore[attr-defined]
        if backup_type:
            statement = statement.where(self.model.backup_type == backup_type) # type: ignore[attr-defined]
        if start_time:
            statement = statement.where(self.model.backup_timestamp >= start_time) # type: ignore[attr-defined]
        if end_time:
            # Ajustar end_time para incluir todo el día si solo se pasa la fecha
            end_date_inclusive = end_time
            if isinstance(end_time, datetime) and end_time.hour == 0 and end_time.minute == 0 and end_time.second == 0:
                end_date_inclusive = end_time + timedelta(days=1, microseconds=-1)
            statement = statement.where(self.model.backup_timestamp <= end_date_inclusive) # type: ignore[attr-defined]

        statement = statement.order_by(self.model.backup_timestamp.desc()).offset(skip).limit(limit) # type: ignore[attr-defined]
        result = db.execute(statement)
        return list(result.scalars().all())

    # No hay métodos create/update/delete expuestos aquí, ya que se manejan
    # por funciones de BD llamadas por el script de backup.
    # Si se necesitara crear un log desde la API (ej. para un backup manual disparado por API),
    # se añadiría un método create aquí que NO haría commit.

backup_log_service = BackupLogService()
