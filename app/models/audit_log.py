import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import Base

class AuditLog(Base):
    """
    Modelo ORM (solo lectura) para la tabla particionada 'audit_log'. 
    """
    __tablename__ = "audit_log"
    # __table_args__ = {"schema": "control_equipos"}

    # PK compuesta: SQLAlchemy puede manejarla declarando ambas columnas como primary_key=True
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    audit_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    table_name: Mapped[str] = mapped_column(Text)
    operation: Mapped[str] = mapped_column(Text) # 'INSERT', 'UPDATE', 'DELETE'
    old_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    new_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Usuario DB
    app_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True) # Usuario App

    # No definir relaciones inversas complejas aquí, es solo para lectura de logs.

    def __repr__(self) -> str:
        return f"<AuditLog(tabla='{self.table_name}', op='{self.operation}', ts='{self.audit_timestamp}')>"
