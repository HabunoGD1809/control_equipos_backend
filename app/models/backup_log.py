import uuid
from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy import Column, String, Text, DateTime, Interval, func # Añadir func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

class BackupLog(Base):
    """
    Modelo ORM (solo lectura) para la tabla 'backup_logs'.
    """
    __tablename__ = "backup_logs"
    # __table_args__ = {"schema": "control_equipos"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    backup_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    backup_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # 'iniciado', 'completado', 'fallido'
    backup_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # 'full', 'incremental'
    duration: Mapped[Optional[timedelta]] = mapped_column(Interval, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # No relaciones definidas aquí.

    def __repr__(self) -> str:
        return f"<BackupLog(id={self.id}, status='{self.backup_status}', ts='{self.backup_timestamp}')>"
