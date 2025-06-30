import logging 
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select

# Importar modelos
from app.models.audit_log import AuditLog as AuditLogModel

logger = logging.getLogger(__name__) # Configurar logger

class AuditLogService:
    """
    Servicio para CONSULTAR los logs de auditoría.
    Los logs son generados por triggers en la base de datos.
    """
    model = AuditLogModel

    def get(self, db: Session, *, id: UUID, timestamp: datetime) -> Optional[AuditLogModel]:
        """Obtiene un log de auditoría por su Clave Primaria compuesta (id de la entidad auditada, timestamp de auditoría)."""
        logger.debug(f"Obteniendo log de auditoría por ID entidad: {id}, Timestamp: {timestamp}")
        statement = select(self.model).where(
            self.model.id == id, # type: ignore[attr-defined]
            self.model.audit_timestamp == timestamp # type: ignore[attr-defined]
        )
        result = db.execute(statement)
        return result.scalar_one_or_none()


    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        table_name: Optional[str] = None,
        operation: Optional[str] = None,
        username: Optional[str] = None, # Usuario de la base de datos que realizó la operación
        app_user_id: Optional[UUID] = None, # ID del usuario de la aplicación (si se capturó)
        record_pk_value: Optional[str] = None, # Valor de la PK del registro afectado (como string)
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[AuditLogModel]:
        """
        Obtiene múltiples logs de auditoría con filtros opcionales, ordenados por fecha descendente.
        """
        logger.debug(
            f"Listando logs de auditoría con filtros: Table='{table_name}', Op='{operation}', "
            f"DBUser='{username}', AppUserID='{app_user_id}', RecordPKValue='{record_pk_value}', "
            f"RangoTiempo='{start_time}-{end_time}' (Skip: {skip}, Limit: {limit})"
        )
        statement = select(self.model) # type: ignore[var-annotated]
        
        if table_name:
            statement = statement.where(self.model.table_name.ilike(f"%{table_name}%")) # type: ignore[attr-defined]
        if operation:
            statement = statement.where(self.model.operation == operation) # type: ignore[attr-defined]
        if username: 
            statement = statement.where(self.model.username.ilike(f"%{username}%")) # type: ignore[attr-defined]
        if app_user_id:
            statement = statement.where(self.model.app_user_id == app_user_id) # type: ignore[attr-defined]
        
        if record_pk_value:
            # Asumiendo que record_pk es JSONB y queremos buscar un valor dentro de él.
            # Esto requiere que el valor de la PK se guarde consistentemente, ej: {"id": "valor_uuid"}
            # o si es una PK simple, que la columna 'record_pk' la contenga directamente como texto.
            # Por ahora, haremos una búsqueda simple si 'record_pk' fuera un campo de texto que contiene el ID.
            # Si es JSONB: from sqlalchemy.dialects.postgresql import JSONB
            # statement = statement.where(self.model.record_pk.cast(JSONB).op('->>')('id') == record_pk_value)
            # O si 'record_pk' es una columna TEXT y la PK es simple:
            # statement = statement.where(self.model.record_pk == record_pk_value)
            # Dado que 'record_pk' es JSONB y puede tener múltiples claves, una búsqueda genérica es compleja.
            # Se puede buscar si el JSONB contiene un valor específico:
            # statement = statement.where(self.model.record_pk.op('->>')('id') == record_pk_value) # Ejemplo si la PK se llama 'id' dentro del JSON
            logger.info(f"Filtrando logs de auditoría por record_pk_value: '{record_pk_value}'. La consulta exacta dependerá de la estructura de 'record_pk'.")
            # Ejemplo de búsqueda si record_pk es JSON y contiene una clave 'id' con el valor:
            # from sqlalchemy.dialects.postgresql import JSONB
            # statement = statement.where(self.model.record_pk.cast(JSONB).op('?&')([record_pk_value])) # No, esto es para existencia de claves
            # Para buscar un valor específico dentro del JSONB (si es un texto):
            # statement = statement.where(self.model.record_pk.cast(TEXT).ilike(f'%"{record_pk_value}"%')) # Búsqueda textual simple en el JSON
            # Es mejor si el trigger guarda una columna de texto separada con la PK principal si es simple.
            # Por ahora, no se aplica un filtro complejo de JSONB aquí sin más detalles de la estructura de record_pk.

        if start_time:
            statement = statement.where(self.model.audit_timestamp >= start_time) # type: ignore[attr-defined]
        if end_time:
            end_date_inclusive = end_time
            if isinstance(end_time, datetime) and end_time.hour == 0 and end_time.minute == 0 and end_time.second == 0:
                 # Si solo se pasa la fecha, incluir todo el día
                end_date_inclusive = end_time + timedelta(days=1, microseconds=-1)
            statement = statement.where(self.model.audit_timestamp <= end_date_inclusive) # type: ignore[attr-defined]

        statement = statement.order_by(self.model.audit_timestamp.desc()).offset(skip).limit(limit) # type: ignore[attr-defined]
        result = db.execute(statement)
        return list(result.scalars().all())

audit_log_service = AuditLogService()
