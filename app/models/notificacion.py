import uuid
from typing import TYPE_CHECKING, Optional
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, func, ForeignKey, Integer, Boolean
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .usuario import Usuario


class Notificacion(Base):
    """
    Modelo ORM para la tabla 'notificaciones'. 
    """
    __tablename__ = "notificaciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    mensaje: Mapped[str] = mapped_column(Text)
    leido: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    fecha_leido: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    tipo: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    urgencia: Mapped[int] = mapped_column(Integer, default=0, index=True)
    referencia_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    referencia_tabla: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    usuario: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="notificaciones",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        leido_str = "Leído" if self.leido else "No leído"
        return f"<Notificacion(id={self.id}, usuario_id={self.usuario_id}, tipo='{self.tipo}', estado='{leido_str}')>"


    # Opcional: Relaciones polimórficas o individuales si quieres navegar a la referencia
    # Ejemplo (requiere más configuración o hacerlo a nivel de servicio):
    # def get_referencia_objeto(self, db: Session):
    #     if self.referencia_tabla == 'equipos' and self.referencia_id:
    #          return db.query(Equipo).get(self.referencia_id)
    #     # ... etc para otras tablas ...
    #     return None
