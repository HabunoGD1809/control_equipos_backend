import uuid
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, DateTime, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.db.base import Base

if TYPE_CHECKING:
    from .documentacion import Documentacion  # noqa: F401


class TipoDocumento(Base):
    """
    Modelo ORM para la tabla 'tipos_documento'. 
    """
    __tablename__ = "tipos_documento"
    # __table_args__ = {"schema": "control_equipos"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requiere_verificacion: Mapped[bool] = mapped_column(Boolean, default=False)
    formato_permitido: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- Relaciones mapeadas ---
    documentos: Mapped[List["Documentacion"]] = relationship(
        "Documentacion",
        back_populates="tipo_documento",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<TipoDocumento(id={self.id}, nombre='{self.nombre}')>"
