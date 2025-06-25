import uuid
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime # Añadir datetime

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .mantenimiento import Mantenimiento  # noqa: F401


class TipoMantenimiento(Base):
    """
    Modelo ORM para la tabla 'tipos_mantenimiento'. 
    """
    __tablename__ = "tipos_mantenimiento"
    # __table_args__ = {"schema": "control_equipos"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    periodicidad_dias: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requiere_documentacion: Mapped[bool] = mapped_column(Boolean, default=False)
    es_preventivo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- Relaciones mapeadas ---
    mantenimientos: Mapped[List["Mantenimiento"]] = relationship(
        "Mantenimiento",
        back_populates="tipo_mantenimiento",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<TipoMantenimiento(id={self.id}, nombre='{self.nombre}')>"
