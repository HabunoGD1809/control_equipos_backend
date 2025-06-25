import uuid
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, DateTime, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .equipo import Equipo  # noqa: F401


class EstadoEquipo(Base):
    """
    Modelo ORM para la tabla 'estados_equipo'. 
    """
    __tablename__ = "estados_equipo"
    # __table_args__ = {"schema": "control_equipos"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    permite_movimientos: Mapped[bool] = mapped_column(Boolean, default=True)
    requiere_autorizacion: Mapped[bool] = mapped_column(Boolean, default=False)
    es_estado_final: Mapped[bool] = mapped_column(Boolean, default=False)
    color_hex: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    icono: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- Relaciones mapeadas ---
    equipos: Mapped[List["Equipo"]] = relationship(
        "Equipo",
        back_populates="estado",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<EstadoEquipo(id={self.id}, nombre='{self.nombre}')>"
