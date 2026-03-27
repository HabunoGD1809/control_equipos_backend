import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, Text, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .ubicacion import Ubicacion
    from .usuario import Usuario


class Departamento(Base):
    """Modelo ORM para el catálogo de Departamentos o Unidades de la institución."""
    __tablename__ = "departamentos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    ubicaciones_fisicas: Mapped[List["Ubicacion"]] = relationship("Ubicacion", back_populates="departamento_rel", lazy="selectin")
    usuarios: Mapped[List["Usuario"]] = relationship("Usuario", back_populates="departamento_rel", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Departamento(id={self.id}, nombre='{self.nombre}')>"
