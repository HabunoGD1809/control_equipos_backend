import uuid
from typing import TYPE_CHECKING, Optional
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, func, ForeignKey, Integer, UniqueConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .equipo import Equipo


class EquipoComponente(Base):
    """
    Modelo ORM para la tabla 'equipo_componentes'. 
    """
    __tablename__ = "equipo_componentes"
    __table_args__ = (
        UniqueConstraint('equipo_padre_id', 'equipo_componente_id', 'tipo_relacion', name='uq_componente'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipo_padre_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("equipos.id", ondelete="CASCADE"), index=True)
    equipo_componente_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("equipos.id", ondelete="CASCADE"), index=True)
    tipo_relacion: Mapped[str] = mapped_column(String(50), default='componente')
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    equipo_padre: Mapped["Equipo"] = relationship(
        "Equipo",
        foreign_keys=[equipo_padre_id],
        back_populates="componentes",
        lazy="selectin"
    )
    equipo_componente: Mapped["Equipo"] = relationship(
        "Equipo",
        foreign_keys=[equipo_componente_id],
        back_populates="parte_de",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<EquipoComponente(padre={self.equipo_padre_id}, componente={self.equipo_componente_id})>"
