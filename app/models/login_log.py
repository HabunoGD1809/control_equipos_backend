import uuid
from typing import TYPE_CHECKING, Optional
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, func, ForeignKey, Boolean
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .usuario import Usuario


class LoginLog(Base):
    """
    Modelo ORM para la tabla 'login_logs'. 
    """
    __tablename__ = "login_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    nombre_usuario_intento: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    intento: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    exito: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, index=True)
    ip_origen: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    motivo_fallo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    usuario: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        back_populates="logs_acceso",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        status = "Exitoso" if self.exito else ("Fallido" if self.exito is False else "N/A")
        user = self.nombre_usuario_intento or str(self.usuario_id)
        return f"<LoginLog(id={self.id}, usuario='{user}', exito='{status}', ip='{self.ip_origen}')>"
