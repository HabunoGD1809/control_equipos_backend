import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING, List

from sqlalchemy import String, Text, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .equipo import Equipo
    from .inventario_stock import InventarioStock

class Ubicacion(Base):
    """Modelo ORM para el catálogo de Ubicaciones Físicas."""
    __tablename__ = "ubicaciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    edificio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    departamento: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    equipos: Mapped[List["Equipo"]] = relationship(
        "Equipo", back_populates="ubicacion", lazy="selectin"
    )
    
    stock: Mapped[List["InventarioStock"]] = relationship(
        "InventarioStock", back_populates="ubicacion_fisica", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Ubicacion(id={self.id}, nombre='{self.nombre}')>"
